from typing import Optional
import asyncpg
import httpx
import json
from datetime import datetime
import re
from core.settings import settings
from schemas import schemas
from redis.asyncio import Redis
from core.utils.enums import ChatbotSessionTime
from core.app_config import logger


async def get_chatbot_response(
    question: str,
    db: asyncpg.Connection,
    redis_client: Redis,
    session_id: Optional[str] = None
) -> schemas.ChatbotResponse:
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            conversation_history = []
            if session_id:
                cached_history = await redis_client.get(f"chatbot_history:{session_id}")
                if cached_history:
                    logger.debug(f"Found cached history for session {session_id}")
                    conversation_history = json.loads(cached_history)

            # luôn ép về str
            conversation_history.append({"role": "user", "content": str(question)})

            # 1. Request LLM to generate SQL
            sql_system_message = {
                "role": "system",
                "content": (
                    "Bạn là một chuyên gia SQL. Với lược đồ cơ sở dữ liệu sau cho bảng sản phẩm: "
                    "CREATE TABLE products ( "
                    "id SERIAL PRIMARY KEY, "
                    "name VARCHAR(255) NOT NULL, "
                    "description TEXT, "
                    "price FLOAT NOT NULL, "
                    "quantity INTEGER NOT NULL, "
                    "image_urls TEXT, "
                    "is_active BOOLEAN DEFAULT TRUE, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    "brand_id INTEGER, "
                    "category_id INTEGER, "
                    "release_date TIMESTAMP ); "
                    "Khi truy vấn, hãy chọn các cột cụ thể và **KHÔNG** bao gồm cột `description`. "
                    "Khi truy vấn theo tên sản phẩm, "
                    "hãy sử dụng toán tử ILIKE với ký tự đại diện (%) để tìm kiếm gần đúng và is_active = TRUE;. "
                    "Chỉ trả về một câu lệnh SQL hợp lệ. KHÔNG được trả lời bằng tiếng Việt, "
                    "KHÔNG thêm mô tả, KHÔNG format Markdown. "
                    "Ví dụ: Nếu người dùng hỏi 'áo phông', bạn sẽ trả lời "
                    "'SELECT id, name, price, quantity, image_urls, is_active, created_at, updated_at, release_date, brand_id, category_id FROM products WHERE name ILIKE '%áo phông%' AND is_active = TRUE;'. "
                    "Bây giờ, hãy tạo truy vấn SQL để lấy thông tin được yêu cầu từ bảng sản phẩm."
                )
            }

            sql_payload = {
                "model": settings.LOCAL_LLM.MODEL,
                "messages": [sql_system_message] + conversation_history,
                "temperature": 0.5,
                "max_tokens": 500,
                "stop": ["\n```"]
            }

            logger.debug("Sending request to LLM for SQL generation.")
            sql_response = await client.post(settings.LOCAL_LLM.API_URL, json=sql_payload)
            logger.info(f"Local LLM API SQL Response Status: {sql_response.status_code}")
            logger.debug(f"Local LLM API SQL Response Body: {sql_response.text}")
            sql_response.raise_for_status()

            try:
                sql_query_full_response = sql_response.json()["choices"][0]["message"]["content"].strip()
                logger.debug(f"Full LLM SQL Response Content: [{sql_query_full_response}]")
                match = re.search(r"```(?:\w+)?\s*([\s\S]*?)\s*```", sql_query_full_response)
                if match:
                    sql_query = match.group(1).strip()
                else:
                    sql_query = sql_query_full_response.replace("```sql", "").replace("```", "").strip()

                logger.debug(f"Cleaned SQL: [{sql_query}]")

                if not re.match(r"^(SELECT|INSERT|UPDATE|DELETE)\b", sql_query, re.IGNORECASE):
                    logger.warning(f"LLM did not return a valid SQL. Got: [{sql_query}]. Treating as natural language response.")
                    answer = str(sql_query)
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

            except json.JSONDecodeError as e:
                logger.error(f"Could not parse JSON from LLM API for SQL generation. Response: {sql_response.text}", exc_info=True)
                raise ValueError(f"Could not parse JSON from LLM API. Details: {e}")

            # 2. Execute SQL
            try:
                logger.debug(f"Executing SQL query: {sql_query}")
                raw_product_data = await db.fetch(sql_query)
                logger.debug(f"Raw Product Data fetched: {raw_product_data}")
            except Exception as e:
                logger.error(f"Failed to execute SQL query: '{sql_query}'. Error: {e}", exc_info=True)
                raise

            # 3. Convert data for LLM
            product_data_dicts = [dict(record) for record in raw_product_data]
            for record_dict in product_data_dicts:
                if 'description' in record_dict and record_dict['description']:
                    record_dict['description'] = (record_dict['description'][:200] + '...') if len(record_dict['description']) > 200 else record_dict['description']
                for key, value in record_dict.items():
                    if isinstance(value, datetime):
                        record_dict[key] = value.isoformat()
            logger.debug(f"Product Data after conversion and truncation: {product_data_dicts}")

            # 4. Call LLM for natural language response
            nl_payload = {
                "model": settings.LOCAL_LLM.MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"Bạn là chatbot trả lời về sản phẩm của cửa hàng Tamstore."
                            f" Dữ liệu sản phẩm mà bạn được phép dùng: {json.dumps(product_data_dicts)}."
                            f" Chỉ được sử dụng dữ liệu này để trả lời, không được suy đoán hoặc bịa thông tin khác."
                            f" Nếu câu hỏi vượt ngoài dữ liệu, hãy trả lời: 'Xin lỗi, tôi không có thông tin cho câu hỏi này.'"
                            f" Khi hiển thị sản phẩm, luôn tuân thủ định dạng:"
                            f"\nTên sản phẩm: [Tên sản phẩm]"
                            f"\nGiá: [Giá] VNĐ"
                            f"\nSố lượng còn: [Số lượng]"
                            f"\nẢnh sản phẩm: ![Ảnh sản phẩm]([URL hình ảnh])"
                            f"\n---"
                            f"\n không bịa thông tin."
                        )
                    }
                ] + conversation_history,
                "temperature": 0.5,
                "max_tokens": -1
            }

            logger.debug("Sending request to LLM for natural language generation.")
            nl_response = await client.post(settings.LOCAL_LLM.API_URL, json=nl_payload)
            logger.info(f"Local LLM API NL Response Status: {nl_response.status_code}")
            logger.debug(f"Local LLM API NL Response Body: {nl_response.text}")
            nl_response.raise_for_status()

            answer = str(nl_response.json()["choices"][0]["message"]["content"].strip())
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
