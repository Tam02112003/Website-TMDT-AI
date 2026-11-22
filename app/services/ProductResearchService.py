import httpx
import json
import asyncpg
from difflib import SequenceMatcher
from typing import Optional, List
from core.settings import settings
from core.app_config import logger
from schemas import schemas
from services.MarketSearchService import search_keyboard_market
from crud import category as category_crud
from crud import brand as brand_crud
from crud import product as product_crud

DUPLICATE_SIMILARITY_THRESHOLD = 0.8

LLM_TIMEOUT = httpx.Timeout(60.0)
MAX_CANDIDATES = 5

SYSTEM_PROMPT_TEMPLATE = (
    "Bạn là trợ lý nghiên cứu sản phẩm cho TamStore, cửa hàng bàn phím cơ. "
    "Bạn sẽ nhận được một danh sách các nguồn tin thật (tiêu đề, trích đoạn, link) từ "
    "tìm kiếm web, nói về các sản phẩm bàn phím/switch/keycap đang có trên thị trường, "
    "và danh sách tên các sản phẩm CỬA HÀNG ĐÃ CÓ SẴN. "
    "QUY TẮC BẮT BUỘC:\n"
    "1. CHỈ liệt kê sản phẩm thực sự được nhắc tới trong các nguồn. KHÔNG được tự bịa "
    "ra tên sản phẩm không có trong nguồn.\n"
    "2. TUYỆT ĐỐI KHÔNG đề xuất sản phẩm trùng hoặc gần giống (cùng model, chỉ khác "
    "cách viết) với bất kỳ sản phẩm nào trong danh sách 'cửa hàng đã có sẵn' được cung cấp.\n"
    "3. 'estimated_price' CHỈ điền khi nguồn có nêu giá cụ thể (đơn vị VNĐ, số nguyên). "
    "Nếu nguồn không nêu giá, để null - KHÔNG được đoán giá.\n"
    "4. 'description' LUÔN viết bằng TIẾNG VIỆT (kể cả khi nguồn là tiếng Anh - phải dịch "
    "và diễn đạt lại, không được chèn nguyên câu tiếng Anh), theo giọng văn bán hàng "
    "chuyên nghiệp của một cửa hàng bàn phím cơ - không phải một bản dịch thông số kỹ thuật "
    "khô khan. Cấu trúc gồm 2 phần:\n"
    "   a) Một đoạn giới thiệu ngắn (1-2 câu) nêu điểm nổi bật/công dụng chính, viết tự nhiên "
    "như copy bán hàng thật.\n"
    "   b) Danh sách 'Thông số nổi bật:' liệt kê từng dòng (cách nhau bằng '\\n- ') CHỈ những "
    "thông số thực sự có trong nguồn: loại switch (linear/tactile/clicky/magnetic), layout "
    "(full/TKL/60%...), kết nối (có dây/Bluetooth/2.4GHz), vật liệu keycap, hotswap, đèn LED, "
    "tần số quét.\n"
    "   KHÔNG tự thêm thông số không có trong nguồn - nếu nguồn không nói, bỏ qua chi tiết đó "
    "thay vì đoán. NẾU nguồn không có thông số cụ thể nào, BỎ HẲN phần 'Thông số nổi bật:' "
    "(không để tiêu đề trống) - chỉ cần đoạn giới thiệu. KHÔNG dùng văn phong liệt kê kiểu "
    "bảng dữ liệu thô (vd: 'Switch: Linear. Layout: TKL.') - phải là câu văn hoàn chỉnh, tự "
    "nhiên, đúng chính tả và ngữ pháp tiếng Việt.\n"
    "5. 'suggested_category' PHẢI là một trong các danh mục sau (chọn đúng tên, hoặc null "
    f"nếu không khớp cái nào): {{categories}}\n"
    "6. 'suggested_brand' nếu khớp với một trong các hãng sau thì dùng đúng tên đó, "
    f"ngược lại để null: {{brands}}\n"
    "7. Tối đa " + str(MAX_CANDIDATES) + " sản phẩm, chỉ lấy những sản phẩm có đủ thông tin "
    "tối thiểu (tên + mô tả).\n"
    "8. Trả về JSON với khóa 'candidates' là một mảng, mỗi phần tử có các khóa: "
    "'name', 'description', 'estimated_price', 'suggested_category', 'suggested_brand', "
    "'source_url'. KHÔNG thêm văn bản nào khác ngoài JSON."
)


def _format_sources_for_prompt(sources: list) -> str:
    if not sources:
        return "(Không tìm thấy nguồn nào.)"
    blocks = []
    for i, s in enumerate(sources, start=1):
        date_part = f" ({s['published_date']})" if s.get("published_date") else ""
        blocks.append(f"[Nguồn {i}]{date_part} {s['title']}\nURL: {s['url']}\nTrích đoạn: {s['content']}")
    return "\n\n".join(blocks)


def _is_duplicate_of_existing(candidate_name: str, existing_names: List[str]) -> bool:
    """Fuzzy name match (not just exact) so 'Keychron K8 Pro' and 'Keychron
    K8-Pro' are both caught, not just byte-identical strings."""
    candidate_lower = candidate_name.strip().lower()
    for existing in existing_names:
        existing_lower = existing.strip().lower()
        if candidate_lower == existing_lower:
            return True
        if SequenceMatcher(None, candidate_lower, existing_lower).ratio() >= DUPLICATE_SIMILARITY_THRESHOLD:
            return True
    return False


def _match_name(suggested: Optional[str], real_items: list) -> Optional[dict]:
    """Resolves an LLM-suggested category/brand name to a real DB row by
    case-insensitive exact match. Never trusts the LLM to supply an ID directly -
    it only ever gets to pick from names that actually exist."""
    if not suggested:
        return None
    suggested_lower = suggested.strip().lower()
    for item in real_items:
        if item.name.strip().lower() == suggested_lower:
            return {"id": item.id, "name": item.name}
    return None


async def research_product_candidates(db: asyncpg.Connection, topic: str, keywords: Optional[str] = None) -> dict:
    search_query = f"{topic} {keywords or ''} bàn phím cơ sản phẩm mới".strip()
    search_response = await search_keyboard_market(search_query)
    sources = search_response["results"]
    images = search_response["images"]

    categories = await category_crud.get_categories(db)
    brands = await brand_crud.get_brands(db)
    existing_names = await product_crud.get_all_product_names(db)

    if not sources:
        return {"candidates": [], "sources": [], "images": []}

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        categories=", ".join(c.name for c in categories) or "(không có danh mục nào)",
        brands=", ".join(b.name for b in brands) or "(không có hãng nào)",
    )

    existing_names_block = ", ".join(existing_names) if existing_names else "(cửa hàng chưa có sản phẩm nào)"
    user_prompt = (
        f"Chủ đề tìm kiếm: \"{topic}\".\n"
        + (f"Từ khóa: {keywords}.\n" if keywords else "")
        + f"\nSản phẩm cửa hàng đã có sẵn (KHÔNG đề xuất trùng với các tên này): {existing_names_block}\n"
        + "\nCác nguồn tin thật tìm được:\n\n"
        + _format_sources_for_prompt(sources)
    )

    try:
        payload = {
            "model": settings.LOCAL_LLM.MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.post(settings.LOCAL_LLM.API_URL, json=payload, headers=settings.LOCAL_LLM.HEADERS)
            response.raise_for_status()
            llm_content = response.json()["choices"][0]["message"]["content"].strip()

        parsed = json.loads(llm_content)
        raw_candidates = parsed.get("candidates", [])
        if not isinstance(raw_candidates, list):
            raise ValueError("LLM did not return a list of candidates.")

    except Exception as e:
        logger.error(f"Product research generation failed for topic '{topic}': {e}", exc_info=True)
        raise RuntimeError(f"Failed to generate product candidates: {e}")

    # Mutated as we go so two near-duplicate candidates from the same LLM
    # response don't both get inserted (not just de-duped against the catalog
    # as it was before this call started).
    known_names = list(existing_names)

    candidates = []
    for i, raw in enumerate(raw_candidates[:MAX_CANDIDATES]):
        name = str(raw.get("name") or "").strip()
        if not name:
            continue

        # Code-level duplicate guard - don't rely on the LLM alone to honor the
        # "don't suggest existing products" instruction.
        if _is_duplicate_of_existing(name, known_names):
            logger.info(f"Skipping product candidate '{name}' - too similar to an existing/already-queued product.")
            continue

        try:
            estimated_price = float(raw["estimated_price"]) if raw.get("estimated_price") is not None else None
        except (TypeError, ValueError):
            estimated_price = None

        category_match = _match_name(raw.get("suggested_category"), categories)
        brand_match = _match_name(raw.get("suggested_brand"), brands)
        image_url = images[i % len(images)]["url"] if images else None
        description = str(raw.get("description") or "")[:2000]

        # Persist immediately as a pending (inactive, zero-stock) product instead
        # of only returning it in the response - closing this dialog without an
        # extra manual "use this" click must not silently lose what was found.
        # estimated_price can be None (source didn't state one); 0 is a clearer
        # "needs review" signal than a made-up number, and is_active=False keeps
        # it off the storefront until an admin verifies price/stock and approves.
        created = await product_crud.create_product(db, schemas.ProductCreate(
            name=name[:255],
            description=description,
            price=estimated_price or 0.0,
            quantity=0,
            image_urls=[image_url] if image_url else None,
            is_active=False,
            is_ai_generated=True,
            category_id=category_match["id"] if category_match else None,
            brand_id=brand_match["id"] if brand_match else None,
        ))
        known_names.append(name)

        candidates.append({
            "id": created.id,
            "name": name[:255],
            "description": description,
            "estimated_price": estimated_price,
            "category_id": category_match["id"] if category_match else None,
            "category_name": category_match["name"] if category_match else None,
            "brand_id": brand_match["id"] if brand_match else None,
            "brand_name": brand_match["name"] if brand_match else None,
            "image_url": image_url,
            "source_url": str(raw.get("source_url") or ""),
        })

    return {
        "candidates": candidates,
        "sources": [{"title": s["title"], "url": s["url"]} for s in sources],
        "images": [{"url": img["url"], "description": img.get("description")} for img in images],
    }
