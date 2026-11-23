from fastapi import APIRouter, Depends
from fastapi.responses import Response
import asyncpg

from core.pkgs.database import get_db
from core.app_config import settings
from crud import product as product_crud
from crud import news as news_crud

router = APIRouter(tags=["SEO"])

STATIC_PATHS = ["", "products", "news", "try-on"]


@router.get("/sitemap.xml")
async def sitemap(db: asyncpg.Connection = Depends(get_db)):
    base_url = settings.FRONTEND.URL.rstrip("/")
    urls = [f"{base_url}/{path}".rstrip("/") for path in STATIC_PATHS]

    products = await product_crud.get_products(db, skip=0, limit=10000)
    urls.extend(f"{base_url}/products/{p.slug or p.id}" for p in products)

    news_items = await news_crud.get_news(db, skip=0, limit=10000)
    urls.extend(f"{base_url}/news/{n.id}" for n in news_items)

    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        body.append(f"<url><loc>{url}</loc></url>")
    body.append("</urlset>")

    return Response(content="\n".join(body), media_type="application/xml")


@router.get("/robots.txt")
async def robots():
    base_url = settings.FRONTEND.URL.rstrip("/")
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {base_url}/sitemap.xml",
    ])
    return Response(content=body, media_type="text/plain")
