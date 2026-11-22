from typing import Optional
import asyncpg
import httpx
import json
from datetime import datetime
from core.settings import settings
from schemas import schemas
from redis.asyncio import Redis
from core.utils.enums import ChatbotSessionTime
from core.app_config import logger
from crud import product as product_crud
from crud import cart as cart_crud

MAX_SEARCH_LIMIT = 20
MAX_CART_QUANTITY = 20
BUILD_CANDIDATE_LIMIT = 30
KEYBOARD_CATEGORY_NAMES = ("Bàn phím cơ", "Bàn phím không dây")
SWITCH_KEYCAP_CATEGORY_NAME = "Switch & Keycap"

SYSTEM_PROMPT = (
    "Bạn là chatbot bán hàng của TamStore, chuyên bàn phím cơ và phụ kiện bàn phím. "
    "Khi người dùng hỏi về sản phẩm (tìm theo tên, khoảng giá...), hãy gọi hàm "
    "search_products với tham số phù hợp để lấy dữ liệu thật từ cửa hàng, "
    "KHÔNG được tự bịa thông tin sản phẩm. "
    "Khi hiển thị sản phẩm, luôn theo định dạng:\n"
    "Tên sản phẩm: [Tên sản phẩm]\n"
    "Giá: [Giá] VNĐ\n"
    "Số lượng còn: [Số lượng]\n"
    "Ảnh sản phẩm: ![Ảnh sản phẩm]([URL hình ảnh])\n"
    "---\n"
    "Khi người dùng muốn mua hoặc thêm một sản phẩm cụ thể (đã biết product_id từ kết quả "
    "search_products) vào giỏ hàng, hãy gọi hàm add_to_cart. Việc này CHỈ thêm vào giỏ hàng, "
    "KHÔNG đặt hàng hay thanh toán - luôn nhắc người dùng vào trang giỏ hàng để xác nhận và "
    "thanh toán. Nếu add_to_cart báo lỗi cần đăng nhập, hãy báo người dùng đăng nhập trước.\n"
    "Khi người dùng muốn được tư vấn 'build' một bộ bàn phím cơ (bàn phím/switch/keycap phù hợp "
    "nhu cầu và ngân sách), hãy gọi hàm suggest_build để lấy danh sách sản phẩm thật theo từng "
    "nhóm, sau đó tự chọn ra 1 bàn phím + 1 switch + 1 keycap phù hợp nhất và giải thích ngắn "
    "gọn lý do (âm thanh, cảm giác gõ, mức giá).\n"
    "Nếu không tìm thấy sản phẩm phù hợp hoặc câu hỏi nằm ngoài phạm vi cửa hàng, "
    "hãy trả lời: 'Xin lỗi, tôi không có thông tin cho câu hỏi này.'"
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Tìm kiếm sản phẩm trong cửa hàng theo tên và/hoặc khoảng giá. "
                "Chỉ trả về sản phẩm đang có bán."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Từ khóa trong tên sản phẩm, ví dụ 'bàn phím cơ' hoặc 'switch'",
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Giá tối thiểu tính bằng VNĐ",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Giá tối đa tính bằng VNĐ",
                    },
                    "limit": {
                        "type": "integer",
                        "description": f"Số lượng kết quả tối đa (mặc định 10, tối đa {MAX_SEARCH_LIMIT})",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": (
                "Thêm một sản phẩm vào giỏ hàng của người dùng đang đăng nhập. "
                "Chỉ gọi hàm này với product_id lấy từ kết quả search_products, không tự bịa id. "
                "Hàm này KHÔNG đặt hàng hay thanh toán, chỉ thêm vào giỏ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "ID sản phẩm cần thêm vào giỏ hàng",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": f"Số lượng muốn thêm (mặc định 1, tối đa {MAX_CART_QUANTITY})",
                    },
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_build",
            "description": (
                "Lấy danh sách bàn phím, switch, keycap đang có bán theo ngân sách, "
                "để tư vấn một bộ build phù hợp. Chỉ trả về dữ liệu thật từ cửa hàng."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "budget_max": {
                        "type": "number",
                        "description": "Tổng ngân sách tối đa tính bằng VNĐ cho cả bộ (bàn phím + switch + keycap), nếu người dùng có đề cập",
                    },
                },
                "required": [],
            },
        },
    },
]


def _serialize_products_for_llm(products: list[schemas.Product]) -> list[dict]:
    result = []
    for p in products:
        result.append({
            "id": p.id,
            "name": p.name,
            "price": p.final_price,
            "quantity": p.quantity,
            "image_url": p.image_urls[0] if p.image_urls else None,
        })
    return result


async def _run_search_products_tool(db: asyncpg.Connection, arguments: dict) -> list[dict]:
    name = arguments.get("name")
    min_price = arguments.get("min_price")
    max_price = arguments.get("max_price")
    limit = arguments.get("limit", 10)

    # Clamp/validate everything coming from the LLM before it ever touches the DB -
    # the LLM only ever supplies values to this fixed, parameterized query, never SQL.
    try:
        limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))
    except (TypeError, ValueError):
        limit = 10
    if name is not None:
        name = str(name)[:200]
    try:
        min_price = float(min_price) if min_price is not None else None
    except (TypeError, ValueError):
        min_price = None
    try:
        max_price = float(max_price) if max_price is not None else None
    except (TypeError, ValueError):
        max_price = None

    products = await product_crud.get_products(
        db, limit=limit, search_query=name, min_price=min_price, max_price=max_price
    )
    return _serialize_products_for_llm(products)


async def _run_add_to_cart_tool(
    db: asyncpg.Connection, redis_client: Redis, user: Optional[dict], arguments: dict
) -> dict:
    if not user:
        return {"error": "login_required", "message": "Người dùng cần đăng nhập để thêm vào giỏ hàng."}

    try:
        product_id = int(arguments.get("product_id"))
    except (TypeError, ValueError):
        return {"error": "invalid_product_id"}

    try:
        quantity = max(1, min(int(arguments.get("quantity", 1)), MAX_CART_QUANTITY))
    except (TypeError, ValueError):
        quantity = 1

    product = await product_crud.get_product_by_id(db, product_id)
    if not product:
        return {"error": "product_not_found"}
    if (product.quantity or 0) < quantity:
        return {"error": "out_of_stock", "available_quantity": product.quantity or 0}

    await cart_crud.add_to_cart(db, user["id"], product_id, quantity, redis_client)
    return {
        "success": True,
        "product_name": product.name,
        "quantity_added": quantity,
        "price": product.final_price,
    }


async def _run_suggest_build_tool(db: asyncpg.Connection, arguments: dict) -> dict:
    try:
        budget_max = float(arguments["budget_max"]) if arguments.get("budget_max") is not None else None
    except (TypeError, ValueError):
        budget_max = None

    all_products = await product_crud.get_products(db, limit=BUILD_CANDIDATE_LIMIT)

    keyboards, switches, keycaps = [], [], []
    for p in all_products:
        category_name = p.category.name if p.category else ""
        name_lower = p.name.lower()
        if category_name in KEYBOARD_CATEGORY_NAMES:
            keyboards.append(p)
        elif category_name == SWITCH_KEYCAP_CATEGORY_NAME:
            if "keycap" in name_lower:
                keycaps.append(p)
            else:
                switches.append(p)

    def filter_by_budget(products):
        return [p for p in products if budget_max is None or (p.final_price or p.price) <= budget_max]

    return {
        "keyboards": _serialize_products_for_llm(filter_by_budget(keyboards)),
        "switches": _serialize_products_for_llm(filter_by_budget(switches)),
        "keycaps": _serialize_products_for_llm(filter_by_budget(keycaps)),
        "budget_max": budget_max,
    }


async def get_chatbot_response(
    question: str,
    db: asyncpg.Connection,
    redis_client: Redis,
    session_id: Optional[str] = None,
    user: Optional[dict] = None,
) -> schemas.ChatbotResponse:
    try:
        # Logged-in users always own their own history, keyed by their user id -
        # a client-supplied session_id is never trusted to read/write someone
        # else's conversation. Guests fall back to their own session_id, namespaced
        # separately so a guest id can never collide with a real user's history.
        if user:
            history_key = f"chatbot_history:user:{user['id']}"
        elif session_id:
            history_key = f"chatbot_history:anon:{session_id}"
        else:
            history_key = None

        conversation_history = []
        if history_key:
            cached_history = await redis_client.get(history_key)
            if cached_history:
                logger.debug(f"Found cached history for key {history_key}")
                conversation_history = json.loads(cached_history)

        conversation_history.append({"role": "user", "content": str(question)})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            payload = {
                "model": settings.LOCAL_LLM.MODEL,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0.3,
                "max_tokens": 1024,
            }
            logger.debug("Sending request to LLM (tool-call step).")
            response = await client.post(settings.LOCAL_LLM.API_URL, json=payload, headers=settings.LOCAL_LLM.HEADERS)
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]

            tool_calls = message.get("tool_calls")
            if tool_calls:
                messages.append(message)
                for tool_call in tool_calls:
                    func_name = tool_call["function"]["name"]
                    try:
                        arguments = json.loads(tool_call["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        arguments = {}

                    if func_name == "search_products":
                        tool_result = await _run_search_products_tool(db, arguments)
                    elif func_name == "add_to_cart":
                        tool_result = await _run_add_to_cart_tool(db, redis_client, user, arguments)
                    elif func_name == "suggest_build":
                        tool_result = await _run_suggest_build_tool(db, arguments)
                    else:
                        tool_result = {"error": f"Unknown function: {func_name}"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    })

                # Second call: let the LLM turn the tool result into a natural-language answer
                followup_payload = {
                    "model": settings.LOCAL_LLM.MODEL,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                }
                logger.debug("Sending request to LLM (final answer step).")
                followup_response = await client.post(
                    settings.LOCAL_LLM.API_URL, json=followup_payload, headers=settings.LOCAL_LLM.HEADERS
                )
                followup_response.raise_for_status()
                answer = str(followup_response.json()["choices"][0]["message"]["content"]).strip()
            else:
                answer = str(message.get("content") or "").strip()

        conversation_history.append({"role": "assistant", "content": answer})

        safe_history = [
            {"role": msg.get("role", "assistant"), "content": str(msg.get("content", ""))}
            for msg in conversation_history[-ChatbotSessionTime.MAX_HISTORY_LEN:]
        ]
        if history_key:
            await redis_client.set(
                history_key,
                json.dumps(safe_history, ensure_ascii=False),
                ex=int(ChatbotSessionTime.SESSION_TTL)
            )
            logger.debug(f"Updated conversation history for key {history_key}")

        return schemas.ChatbotResponse(answer=answer, history=safe_history)

    except Exception as e:
        logger.error(f"An unexpected error occurred in get_chatbot_response: {e}", exc_info=True)
        raise e
