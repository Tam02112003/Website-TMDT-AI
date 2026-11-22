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


async def search_keyboard_market(query: str, topic: str = "news") -> MarketSearchResponse:
    """
    Searches the live web for recent, real information (and real images) to
    ground an AI-generated news article or product research - the LLM is never
    allowed to write "market news"/product specs purely from its static
    training data. Returns empty lists (never raises) if Tavily isn't
    configured or the request fails, so callers can degrade gracefully instead
    of blocking generation entirely.

    `topic` should be "news" for time-sensitive market-news content, or
    "general" for product listings/reviews - Tavily's "news" mode biases
    toward news-article sources and can pull completely unrelated current-events
    noise (car prices, music releases, etc.) for a vague/generic query that
    doesn't read as news-shaped.
    """
    empty: MarketSearchResponse = {"results": [], "images": []}

    if not settings.TAVILY.API_KEY:
        logger.warning("TAVILY_API_KEY not configured - AI generation will run ungrounded.")
        return empty

    payload = {
        "api_key": settings.TAVILY.API_KEY.get_secret_value(),
        "query": query,
        "search_depth": "advanced",
        "topic": topic,
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
