import httpx
import json
from typing import Optional, List
from core.settings import settings
from core.app_config import logger
from services.MarketSearchService import search_keyboard_market, MarketSearchResult

LLM_TIMEOUT = httpx.Timeout(60.0)

SYSTEM_PROMPT = (
    "Bạn là biên tập viên tin tức công nghệ cho TamStore, một cửa hàng bàn phím cơ. "
    "Bạn sẽ nhận được một danh sách các nguồn tin thật (tiêu đề, nội dung trích đoạn, "
    "đường link) lấy từ tìm kiếm web gần đây. "
    "QUY TẮC BẮT BUỘC:\n"
    "1. CHỈ sử dụng thông tin có trong các nguồn được cung cấp. KHÔNG được tự bịa ra "
    "tên sản phẩm, hãng, giá, hay số liệu không có trong nguồn.\n"
    "2. Nếu nguồn không đủ thông tin để viết chi tiết, hãy viết ngắn gọn với những gì "
    "thực sự có, không cố kéo dài bằng nội dung chung chung/bịa đặt.\n"
    "3. Viết bằng tiếng Việt, giọng văn báo chí, khách quan.\n"
    "4. Trả về HTML ngữ nghĩa cho phần nội dung: dùng <h2>/<h3> cho tiêu đề phụ, "
    "<p> cho đoạn văn, <ul><li> cho danh sách (ví dụ liệt kê thông số/xu hướng). "
    "KHÔNG dùng <html>/<body>, chỉ các thẻ nội dung.\n"
    "5. Chỉ trả về JSON với 2 khóa 'title' (chuỗi) và 'content' (chuỗi HTML). "
    "KHÔNG thêm văn bản nào khác ngoài JSON."
)


def _format_sources_for_prompt(sources: List[MarketSearchResult]) -> str:
    if not sources:
        return "(Không có nguồn nào được tìm thấy - hãy nói rõ trong bài là chưa có đủ thông tin mới, và chỉ viết những gì chắc chắn đúng.)"
    blocks = []
    for i, s in enumerate(sources, start=1):
        date_part = f" ({s['published_date']})" if s.get("published_date") else ""
        blocks.append(f"[Nguồn {i}]{date_part} {s['title']}\nURL: {s['url']}\nTrích đoạn: {s['content']}")
    return "\n\n".join(blocks)


async def generate_news_content(topic: str, keywords: Optional[str] = None, length: str = "dài như bài báo") -> dict:
    search_query = f"{topic} {keywords or ''} bàn phím cơ".strip()
    sources = await search_keyboard_market(search_query)

    try:
        user_prompt = (
            f"Chủ đề bài viết: \"{topic}\".\n"
            + (f"Từ khóa cần đưa vào nếu phù hợp: {keywords}.\n" if keywords else "")
            + f"Độ dài mong muốn: {length}.\n\n"
            + "Các nguồn tin thật tìm được:\n\n"
            + _format_sources_for_prompt(sources)
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": settings.LOCAL_LLM.MODEL,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.post(settings.LOCAL_LLM.API_URL, json=payload, headers=settings.LOCAL_LLM.HEADERS)
            response.raise_for_status()
            llm_response_content = response.json()["choices"][0]["message"]["content"].strip()

        news_data = json.loads(llm_response_content)
        if "title" not in news_data or "content" not in news_data:
            raise ValueError("Generated news content is missing 'title' or 'content'.")

        news_data["sources"] = [{"title": s["title"], "url": s["url"]} for s in sources]
        return news_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from LLM response for news generation: {e}")
        raise RuntimeError("AI did not return valid content. Please try again.")
    except httpx.RequestError as e:
        logger.error(f"HTTPX Request Error to LLM API: {e}", exc_info=True)
        raise RuntimeError(f"Could not connect to LLM API: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPX Status Error from LLM API: {e.response.text}", exc_info=True)
        raise RuntimeError(f"LLM API returned an error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during news generation: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate news content: {e}")
