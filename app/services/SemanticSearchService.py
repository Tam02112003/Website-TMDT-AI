from typing import List
import httpx
import json
import re
from redis.asyncio import Redis
from core.settings import settings
from core.app_config import logger
from schemas import schemas
from crud import product as product_crud
import asyncpg

MAX_KEYWORDS = 8
QUERY_EXPANSION_CACHE_TTL_SECONDS = 3600
EXPANSION_LLM_TIMEOUT = httpx.Timeout(15.0)

EXPANSION_SYSTEM_PROMPT = (
    "Bạn là công cụ mở rộng truy vấn tìm kiếm cho một cửa hàng bàn phím cơ. "
    "Người dùng sẽ nhập một câu mô tả nhu cầu bằng tiếng Việt (vd: 'bàn phím êm cho văn phòng'). "
    "Hãy trả về CHỈ một JSON object dạng {\"keywords\": [...]} liệt kê tối đa "
    f"{MAX_KEYWORDS} từ khóa/thuật ngữ liên quan (tên loại switch, layout, thương hiệu, công dụng, "
    "từ đồng nghĩa tiếng Việt lẫn tiếng Anh) có thể xuất hiện trong tên hoặc mô tả sản phẩm. "
    "Không giải thích gì thêm, không bịa thương hiệu không liên quan."
)


def _fallback_keywords(query: str) -> List[str]:
    words = re.findall(r"\w+", query.lower())
    return [w for w in words if len(w) > 1][:MAX_KEYWORDS]


async def _expand_query(query: str, redis_client: Redis) -> List[str]:
    cache_key = f"semantic_search:expand:{query.strip().lower()}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis read failed for semantic search expansion cache: {e}")

    keywords = _fallback_keywords(query)
    try:
        async with httpx.AsyncClient(timeout=EXPANSION_LLM_TIMEOUT) as client:
            payload = {
                "model": settings.LOCAL_LLM.MODEL,
                "messages": [
                    {"role": "system", "content": EXPANSION_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                "temperature": 0.2,
                "max_tokens": 256,
                "response_format": {"type": "json_object"},
            }
            response = await client.post(settings.LOCAL_LLM.API_URL, json=payload, headers=settings.LOCAL_LLM.HEADERS)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            llm_keywords = parsed.get("keywords")
            if isinstance(llm_keywords, list) and llm_keywords:
                keywords = [str(k)[:50] for k in llm_keywords][:MAX_KEYWORDS]
    except Exception as e:
        logger.warning(f"Semantic search query expansion via LLM failed, falling back to raw keywords: {e}")

    try:
        await redis_client.setex(cache_key, QUERY_EXPANSION_CACHE_TTL_SECONDS, json.dumps(keywords, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Redis write failed for semantic search expansion cache: {e}")

    return keywords


def _score_product(product: schemas.Product, keywords: List[str]) -> int:
    text = f"{product.name} {product.description or ''} {product.category.name if product.category else ''} {product.brand.name if product.brand else ''}".lower()
    return sum(1 for kw in keywords if kw.lower() in text)


async def semantic_search_products(
    db: asyncpg.Connection, redis_client: Redis, query: str, limit: int = 20
) -> List[schemas.Product]:
    keywords = await _expand_query(query, redis_client)
    if not keywords:
        return []

    candidates = await product_crud.get_products_by_keywords(db, keywords, limit=200)

    scored = [(p, _score_product(p, keywords)) for p in candidates]
    scored = [(p, score) for p, score in scored if score > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [p for p, _ in scored[:limit]]
