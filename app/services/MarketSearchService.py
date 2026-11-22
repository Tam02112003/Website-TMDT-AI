from typing import List, Optional, TypedDict
import httpx
from core.settings import settings
from core.app_config import logger

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
SEARCH_TIMEOUT = httpx.Timeout(20.0)
MAX_RESULTS = 5
MAX_IMAGES = 6


class MarketSearchResult(TypedDict):
    title: str
    url: str
    content: str
    published_date: Optional[str]


class MarketImage(TypedDict):
    url: str
    description: Optional[str]


class MarketSearchResponse(TypedDict):
    results: List[MarketSearchResult]
    images: List[MarketImage]


async def search_keyboard_market(query: str) -> MarketSearchResponse:
    """
    Searches the live web for recent, real information (and real images) to
    ground an AI-generated news article - the LLM is never allowed to write
    "market news" purely from its static training data. Returns empty lists
    (never raises) if Tavily isn't configured or the request fails, so callers
    can degrade gracefully instead of blocking news generation entirely.
    """
    empty: MarketSearchResponse = {"results": [], "images": []}

    if not settings.TAVILY.API_KEY:
        logger.warning("TAVILY_API_KEY not configured - AI news generation will run ungrounded.")
        return empty

    payload = {
        "api_key": settings.TAVILY.API_KEY.get_secret_value(),
        "query": query,
        "search_depth": "advanced",
        "topic": "news",
        "max_results": MAX_RESULTS,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": True,
        "include_image_descriptions": True,
    }

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            response = await client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error(f"Tavily market search failed for query '{query}': {e}", exc_info=True)
        return empty

    results = [
        MarketSearchResult(
            title=str(item.get("title", ""))[:300],
            url=str(item.get("url", "")),
            content=str(item.get("content", ""))[:1500],
            published_date=item.get("published_date"),
        )
        for item in data.get("results", [])[:MAX_RESULTS]
    ]

    images = [
        MarketImage(url=str(img.get("url", "")), description=img.get("description"))
        for img in data.get("images", [])[:MAX_IMAGES]
        if img.get("url")
    ]

    return MarketSearchResponse(results=results, images=images)
