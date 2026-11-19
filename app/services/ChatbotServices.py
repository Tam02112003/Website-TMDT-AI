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

MAX_SEARCH_LIMIT = 20

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
    }
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


async def get_chatbot_response(
    question: str,
    db: asyncpg.Connection,
    redis_client: Redis,
    session_id: Optional[str] = None
) -> schemas.ChatbotResponse:
    try:
        conversation_history = []
        if session_id:
            cached_history = await redis_client.get(f"chatbot_history:{session_id}")
            if cached_history:
                logger.debug(f"Found cached history for session {session_id}")
                conversation_history = json.loads(cached_history)

        conversation_history.append({"role": "user", "content": str(question)})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

        async with httpx.AsyncClient(timeout=None) as client:
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

        if session_id:
            trimmed = conversation_history[-ChatbotSessionTime.MAX_HISTORY_LEN:]
            safe_history = [
                {"role": msg.get("role", "assistant"), "content": str(msg.get("content", ""))}
                for msg in trimmed
            ]
            await redis_client.set(
                f"chatbot_history:{session_id}",
                json.dumps(safe_history, ensure_ascii=False),
                ex=int(ChatbotSessionTime.SESSION_TTL)
            )
            logger.debug(f"Updated conversation history for session {session_id}")

        return schemas.ChatbotResponse(answer=answer, history=conversation_history)

    except Exception as e:
        logger.error(f"An unexpected error occurred in get_chatbot_response: {e}", exc_info=True)
        raise e
