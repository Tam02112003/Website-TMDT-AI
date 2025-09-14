import re
import httpx
import json
from typing import Optional
from core.settings import settings
from core.app_config import logger

async def generate_news_content(topic: str, keywords: Optional[str] = None, length: str = "dài như bài báo") -> dict:
    try:
        prompt = f"Viết một bài báo tin tức bằng tiếng Việt về chủ đề \"{topic}\". "
        if keywords:
            prompt += f"Bao gồm các từ khóa sau: {keywords}. "
        prompt += f"Độ dài bài viết {length}. "
        prompt += "Hãy cung cấp một tiêu đề và nội dung bài viết. "
        prompt += "Chỉ trả về JSON với các khóa 'title' và 'content'. KHÔNG thêm bất kỳ văn bản nào khác ngoài JSON."

        messages = [
            {"role": "system", "content": "Bạn là một nhà báo AI chuyên nghiệp, tạo ra các bài báo tin tức hấp dẫn và chính xác."}, 
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": settings.LOCAL_LLM.MODEL,
            "messages": messages,
            "temperature": 0.7, # A bit higher temperature for more creative news generation
            "max_tokens": -1 # No limit for news length
        }

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(settings.LOCAL_LLM.API_URL, json=payload)
            response.raise_for_status() # Raise an exception for HTTP errors

            llm_response_content = response.json()["choices"][0]["message"]["content"].strip()
            logger.debug(f"Raw LLM response for news: {llm_response_content}")

            # Attempt to parse JSON from the LLM's response
            try:
                news_data = json.loads(llm_response_content)
                if "title" in news_data and "content" in news_data:
                    return news_data
                else:
                    logger.error(f"LLM response missing 'title' or 'content' keys: {llm_response_content}")
                    raise ValueError("Generated news content is not in the expected format (missing title or content).")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from LLM response: {llm_response_content}")
                # Fallback if LLM doesn't return perfect JSON
                # Try to extract title, content, and image_url heuristically
                title_match = re.search(r'"title"\s*:\s*"([^"]*)"', llm_response_content)
                content_match = re.search(r'"content"\s*:\s*"([^"]*)"', llm_response_content)
                
                logger.debug(f"Heuristic extraction - title_match: {title_match}")
                logger.debug(f"Heuristic extraction - content_match: {content_match}")

                if title_match and content_match:
                    return {"title": title_match.group(1), "content": content_match.group(1)}
                else:
                    raise ValueError("LLM did not return valid JSON and heuristic extraction failed.")

    except httpx.RequestError as e:
        logger.error(f"HTTPX Request Error to LLM API: {e}", exc_info=True)
        raise RuntimeError(f"Could not connect to LLM API: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPX Status Error from LLM API: {e.response.text}", exc_info=True)
        raise RuntimeError(f"LLM API returned an error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during news generation: {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate news content: {e}")
