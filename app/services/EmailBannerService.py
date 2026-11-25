import os
import textwrap
from io import BytesIO
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core.app_config import logger

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")

COLORS = {
    "bg": (22, 24, 28),
    "surface": (31, 34, 39),
    "surface_raised": (38, 42, 48),
    "border": (52, 57, 64),
    "ink": (236, 234, 228),
    "muted": (156, 163, 168),
    "jade": (63, 163, 140),
    "jade_bright": (85, 194, 168),
    "camel": (201, 162, 90),
    "danger": (226, 105, 91),
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{name}.ttf"), size)


_ALLOWED_EXTRA_CODEPOINTS = {0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x00A0}


def _sanitize_for_font(text: str) -> str:
    """Drops characters the Inter font has no glyph for (emoji, symbols, etc.),
    which Pillow would otherwise draw as empty "tofu" boxes. Browsers mask this
    by falling back to a system emoji font, but Pillow has no such fallback."""
    return "".join(ch for ch in text if ord(ch) < 0x2070 or ord(ch) in _ALLOWED_EXTRA_CODEPOINTS)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if _text_size(draw, trial, font)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines:
        last = lines[-1]
        while _text_size(draw, last + "…", font)[0] > max_width and len(last) > 1:
            last = last[:-1]
        remaining_words = len(words) > sum(len(l.split()) for l in lines)
        if remaining_words:
            lines[-1] = last.rstrip() + "…"
    return lines


def _fetch_image(url: str) -> Optional[Image.Image]:
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "TamStoreEmailBot/1.0 (+https://shop.tamnguyen.asia)"})
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"EmailBannerService: failed to fetch product image {url}: {e}")
        return None


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if src_ratio > target_ratio:
        new_height = img.height
        new_width = int(new_height * target_ratio)
    else:
        new_width = img.width
        new_height = int(new_width / target_ratio)
    left = (img.width - new_width) // 2
    top = (img.height - new_height) // 2
    cropped = img.crop((left, top, left + new_width, top + new_height))
    return cropped.resize((target_w, target_h), Image.LANCZOS)


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def generate_hero_banner(title: str, subtitle: str, max_discount: Optional[int] = None) -> bytes:
    title = _sanitize_for_font(title)
    subtitle = _sanitize_for_font(subtitle)
    width, height = 800, 280
    img = Image.new("RGB", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(img, "RGBA")

    # Soft jade glow accent, bottom-right
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((width - 420, -180, width + 180, 380), fill=(*COLORS["jade"], 70))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img.paste(glow, (0, 0), glow)
    draw = ImageDraw.Draw(img)

    brand_font = _font("SemiBold", 22)
    draw.text((40, 32), "TamStore", font=brand_font, fill=COLORS["jade_bright"])

    title_font = _font("ExtraBold", 36)
    if max_discount:
        discount_font = _font("ExtraBold", 110)
        discount_text = f"-{max_discount}%"
        draw.text((40, 70), discount_text, font=discount_font, fill=COLORS["camel"])
        dw, dh = _text_size(draw, discount_text, discount_font)
        title_y = 70 + dh + 32
    else:
        title_y = 110
    draw.text((40, title_y), title, font=title_font, fill=COLORS["ink"])

    subtitle_font = _font("Regular", 18)
    lines = _wrap_to_width(draw, subtitle, subtitle_font, max_width=500, max_lines=2)
    sy = title_y + 48
    for line in lines:
        draw.text((40, sy), line, font=subtitle_font, fill=COLORS["muted"])
        sy += 26

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_product_card(name: str, price: float, final_price: float, discount_percent: Optional[float], image_url: Optional[str], slug_or_id: str) -> bytes:
    name = _sanitize_for_font(name)
    width, height = 360, 460
    image_h = 220
    img = Image.new("RGB", (width, height), COLORS["surface"])
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=18, outline=COLORS["border"], width=2)

    product_img = _fetch_image(image_url) if image_url else None
    if product_img:
        cropped = _cover_crop(product_img, width - 4, image_h)
        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((2, 2, width - 3, image_h), radius=16, fill=255)
        mask_draw.rectangle((2, image_h - 20, width - 3, image_h), fill=255)
        tmp = Image.new("RGB", (width, height), COLORS["surface"])
        tmp.paste(cropped, (2, 2))
        img = Image.composite(tmp, img, mask)
        draw = ImageDraw.Draw(img)
    else:
        draw.rounded_rectangle((2, 2, width - 3, image_h), radius=16, fill=COLORS["surface_raised"])

    if discount_percent:
        badge_font = _font("Bold", 18)
        badge_text = f"-{int(discount_percent)}%"
        bw, bh = _text_size(draw, badge_text, badge_font)
        pad = 10
        bx0, by0 = width - bw - pad * 2 - 14, 14
        draw.rounded_rectangle((bx0, by0, bx0 + bw + pad * 2, by0 + bh + pad * 2), radius=10, fill=COLORS["danger"])
        draw.text((bx0 + pad, by0 + pad - 2), badge_text, font=badge_font, fill=(255, 255, 255))

    name_font = _font("SemiBold", 20)
    name_lines = _wrap_to_width(draw, name, name_font, max_width=width - 48, max_lines=2)
    ny = image_h + 20
    for line in name_lines:
        draw.text((24, ny), line, font=name_font, fill=COLORS["ink"])
        ny += 26

    price_y = image_h + 90
    if discount_percent and final_price < price:
        orig_font = _font("Regular", 16)
        orig_text = f"{price:,.0f} đ".replace(",", ".")
        draw.text((24, price_y), orig_text, font=orig_font, fill=COLORS["muted"])
        ow, oh = _text_size(draw, orig_text, orig_font)
        draw.line((24, price_y + oh // 2 + 2, 24 + ow, price_y + oh // 2 + 2), fill=COLORS["muted"], width=2)
        price_y += oh + 6

    final_font = _font("ExtraBold", 24)
    final_text = f"{final_price:,.0f} đ".replace(",", ".")
    draw.text((24, price_y), final_text, font=final_font, fill=COLORS["camel"])

    cta_font = _font("SemiBold", 16)
    cta_text = "Xem ngay"
    cw, ch = _text_size(draw, cta_text, cta_font)
    cta_y = height - ch - 36
    draw.rounded_rectangle((24, cta_y - 10, 24 + cw + 32, cta_y + ch + 10), radius=10, fill=COLORS["jade"])
    draw.text((24 + 16, cta_y - 2), cta_text, font=cta_font, fill=(13, 18, 16))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
