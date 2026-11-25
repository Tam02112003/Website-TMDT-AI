import asyncpg

from core.app_config import logger, settings
from core.email_sender import send_email_batch
from crud import product as product_crud
from crud import user as user_crud
from router.auth import create_unsubscribe_token
from services.CloudinaryService import upload_image_from_bytes
from services.EmailBannerService import generate_hero_banner, generate_product_card

CAMPAIGN_IMAGE_FOLDER = "email_campaigns"
MAX_PRODUCTS = 6


def _build_campaign_html(hero_url: str, product_items: list[dict], unsubscribe_url: str, max_discount: int) -> str:
    base_url = settings.FRONTEND.URL.rstrip("/")

    def product_cell(item: dict) -> str:
        return f"""
        <td style="padding:8px;" width="50%">
            <a href="{base_url}/products/{item['slug_or_id']}" target="_blank">
                <img src="{item['image_url']}" width="100%" alt="{item['name']}" style="display:block;border:0;border-radius:12px;">
            </a>
        </td>
        """

    rows = ""
    for i in range(0, len(product_items), 2):
        pair = product_items[i:i + 2]
        cells = "".join(product_cell(p) for p in pair)
        if len(pair) == 1:
            cells += '<td style="padding:8px;" width="50%"></td>'
        rows += f"<tr>{cells}</tr>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background-color:#16181C;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#16181C;">
            <tr>
                <td align="center" style="padding:24px 12px;">
                    <table role="presentation" width="800" cellpadding="0" cellspacing="0" style="max-width:800px;width:100%;">
                        <tr>
                            <td style="font-family:Arial,sans-serif;text-align:center;padding:0 16px 16px;">
                                <p style="margin:0 0 6px;font-size:22px;font-weight:bold;color:#ECEAE4;">
                                    🔥 TamStore giảm đến {max_discount}% cho bàn phím cơ
                                </p>
                                <p style="margin:0;font-size:14px;color:#9CA3A8;">
                                    Nếu không thấy hình ảnh bên dưới, hãy
                                    <a href="{base_url}/products" style="color:#55C2A8;text-decoration:underline;">bấm vào đây để xem ưu đãi</a>.
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td>
                                <a href="{base_url}/products" target="_blank">
                                    <img src="{hero_url}" width="100%" alt="TamStore - Giảm đến {max_discount}% cho bàn phím cơ" style="display:block;border:0;border-radius:16px;">
                                </a>
                            </td>
                        </tr>
                        <tr><td style="height:16px;line-height:16px;font-size:0;">&nbsp;</td></tr>
                        <tr>
                            <td>
                                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                    {rows}
                                </table>
                            </td>
                        </tr>
                        <tr><td style="height:24px;line-height:24px;font-size:0;">&nbsp;</td></tr>
                        <tr>
                            <td align="center" style="font-family:Arial,sans-serif;font-size:12px;color:#9CA3A8;padding:0 20px;">
                                <p style="margin:0 0 8px;">Bạn nhận được email này vì đã đăng ký tài khoản tại TamStore.</p>
                                <p style="margin:0;"><a href="{unsubscribe_url}" style="color:#55C2A8;text-decoration:underline;">Hủy đăng ký nhận email khuyến mãi</a></p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def _build_campaign_text(product_items: list[dict], unsubscribe_url: str, max_discount: int) -> str:
    base_url = settings.FRONTEND.URL.rstrip("/")
    lines = [
        f"TamStore giam den {max_discount}% cho ban phim co",
        f"Xem tat ca uu dai: {base_url}/products",
        "",
        "San pham dang giam gia:",
    ]
    for item in product_items:
        lines.append(f"- {item['name']}: {base_url}/products/{item['slug_or_id']}")
    lines += ["", f"Huy dang ky nhan email khuyen mai: {unsubscribe_url}"]
    return "\n".join(lines)


async def send_promo_campaign(db: asyncpg.Connection) -> dict:
    products = await product_crud.get_discounted_products(db, limit=MAX_PRODUCTS)
    if not products:
        raise ValueError("Không có sản phẩm nào đang giảm giá để gửi email khuyến mãi.")

    max_discount = int(max(p.discount_percent or 0 for p in products))

    hero_bytes = generate_hero_banner(
        title="SALE CUỐI TUẦN",
        subtitle="Giảm giá sốc cho hàng loạt bàn phím cơ, switch và phụ kiện chính hãng.",
        max_discount=max_discount,
    )
    hero_url = await upload_image_from_bytes(hero_bytes, folder=CAMPAIGN_IMAGE_FOLDER)

    product_items = []
    for p in products:
        card_bytes = generate_product_card(
            name=p.name,
            price=p.price,
            final_price=p.final_price or p.price,
            discount_percent=p.discount_percent,
            image_url=p.image_urls[0] if p.image_urls else None,
            slug_or_id=p.slug or str(p.id),
        )
        card_url = await upload_image_from_bytes(card_bytes, folder=CAMPAIGN_IMAGE_FOLDER)
        product_items.append({"image_url": card_url, "name": p.name, "slug_or_id": p.slug or str(p.id)})

    recipients = await user_crud.get_subscribed_users(db)
    if not recipients:
        return {"recipients": 0, "products_included": len(products), "sent": 0, "failed": 0}

    base_url = settings.FRONTEND.URL.rstrip("/")
    emails = []
    for recipient in recipients:
        token = create_unsubscribe_token(recipient["id"])
        unsubscribe_url = f"{_api_base_url()}/auth/unsubscribe?token={token}"
        html = _build_campaign_html(hero_url, product_items, unsubscribe_url, max_discount)
        text = _build_campaign_text(product_items, unsubscribe_url, max_discount)
        emails.append({
            "to_email": recipient["email"],
            "subject": f"🔥 Giảm đến {max_discount}% - Ưu đãi có hạn tại TamStore",
            "html": html,
            "text": text,
        })

    result = send_email_batch(emails)
    logger.info(f"Promo campaign sent: {result['sent']} ok, {result['failed']} failed, {len(recipients)} total recipients.")
    return {
        "recipients": len(recipients),
        "products_included": len(products),
        "sent": result["sent"],
        "failed": result["failed"],
    }


def _api_base_url() -> str:
    """Public base URL of this API (where /auth/unsubscribe is served),
    distinct from settings.FRONTEND.URL which points at the React app.
    Derived from GOOGLE.REDIRECT_URI, which already points at this API's
    own /auth/google/callback route."""
    return settings.GOOGLE.REDIRECT_URI.rsplit("/auth/google/callback", 1)[0]
