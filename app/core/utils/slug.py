import re
import unicodedata

_DASH_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Converts Vietnamese/accented text into a URL-safe slug, e.g.
    'Bàn phím cơ Keychron K8 Pro' -> 'ban-phim-co-keychron-k8-pro'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _DASH_RE.sub("-", ascii_text.lower()).strip("-")
    return slug or "san-pham"


def make_product_slug(name: str, product_id: int) -> str:
    return f"{slugify(name)}-{product_id}"
