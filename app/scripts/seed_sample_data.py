# -*- coding: utf-8 -*-
"""
Seed sample keyboard-shop data (categories, brands, products, news) into
whatever Postgres database is configured via the app's own settings
(app/env/.env.<ENV>). Safe to re-run: it truncates and re-inserts.

Usage:
    cd app
    python scripts/seed_sample_data.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')

import asyncpg

from core.settings import settings

IMG = {
    'generic_mech': 'https://upload.wikimedia.org/wikipedia/commons/d/df/Mechanical_keyboard_example.jpg',
    'generic_mech2': 'https://upload.wikimedia.org/wikipedia/commons/5/5a/Mechanical_Keyboard.jpg',
    'switch': 'https://upload.wikimedia.org/wikipedia/commons/9/98/MX_brown_key_switches.jpg',
    'mx_keys': 'https://upload.wikimedia.org/wikipedia/commons/7/78/Logitech_MX_Keys_YR0073_Wireless_Keyboard.jpg',
    'keychron_k8': 'https://upload.wikimedia.org/wikipedia/commons/8/8e/Keychron_K8_Non-Backlight_Wireless_Mechanical_Keyboard_with_Cherry_Profile_Double_-_Shot_PBT_Full_Set_Keycaps_-_Camel.jpg',
    'keycap_set': 'https://upload.wikimedia.org/wikipedia/commons/6/65/Cherry_Profile_Double_-_Shot_PBT_Full_Set_Keycaps_-_Camel.jpg',
}


async def main():
    ssl_mode = 'require' if settings.DB.HOST not in ('localhost', '127.0.0.1') else None
    conn = await asyncpg.connect(
        user=settings.DB.USER,
        password=settings.DB.PASSWORD.get_secret_value(),
        host=settings.DB.HOST,
        port=settings.DB.PORT,
        database=settings.DB.NAME,
        ssl=ssl_mode,
    )

    await conn.execute("TRUNCATE products, categories, brands, news RESTART IDENTITY CASCADE")

    cat_rows = await conn.fetch(
        "INSERT INTO categories (name) VALUES ($1),($2),($3),($4) RETURNING id, name",
        'Bàn phím cơ', 'Bàn phím không dây', 'Phụ kiện bàn phím', 'Switch & Keycap'
    )
    brand_rows = await conn.fetch(
        "INSERT INTO brands (name) VALUES ($1),($2),($3),($4) RETURNING id, name",
        'Keychron', 'Akko', 'Logitech', 'Durgod'
    )
    cat = {r['name']: r['id'] for r in cat_rows}
    brand = {r['name']: r['id'] for r in brand_rows}

    products = [
        ('Keychron K8 Pro', 'Bàn phím cơ 87 phím, kết nối Bluetooth/có dây, hỗ trợ hotswap switch.',
         1990000, 25, [IMG['keychron_k8']], cat['Bàn phím cơ'], brand['Keychron']),
        ('Akko 3098B Plus', 'Bàn phím cơ 98 phím, switch Akko CS, keycap PBT doubleshot.',
         1590000, 30, [IMG['generic_mech']], cat['Bàn phím cơ'], brand['Akko']),
        ('Logitech MX Keys', 'Bàn phím không dây cao cấp, phím lõm êm tay, pin dùng được lâu.',
         2290000, 20, [IMG['mx_keys']], cat['Bàn phím không dây'], brand['Logitech']),
        ('Durgod Taurus K320', 'Bàn phím cơ 87 phím, vỏ nhôm nguyên khối, switch Cherry MX.',
         2150000, 15, [IMG['generic_mech2']], cat['Bàn phím cơ'], brand['Durgod']),
        ('Bộ Keycap PBT Cherry Profile', 'Bộ 108 keycap PBT doubleshot, tương thích chuẩn Cherry/OEM.',
         450000, 50, [IMG['keycap_set']], cat['Switch & Keycap'], brand['Akko']),
        ('Switch Akko CS Jade Axis (45 switch)', 'Switch linear êm nhẹ, âm thanh trong, đã bôi trơn sẵn.',
         320000, 60, [IMG['switch']], cat['Switch & Keycap'], brand['Akko']),
        ('Kê tay bàn phím gỗ', 'Kê tay gỗ tự nhiên, chống mỏi cổ tay khi gõ lâu.',
         150000, 80, [IMG['generic_mech']], cat['Phụ kiện bàn phím'], brand['Keychron']),
    ]

    for name, desc, price, qty, images, cid, bid in products:
        await conn.execute(
            'INSERT INTO products (name, description, price, quantity, image_urls, category_id, brand_id) '
            'VALUES ($1,$2,$3,$4,$5,$6,$7)',
            name, desc, price, qty, json.dumps(images), cid, bid
        )
    print('Inserted', len(products), 'keyboard products')

    await conn.execute(
        "INSERT INTO news (title, content) VALUES ($1, $2)",
        'Ra mắt bộ sưu tập bàn phím cơ mới!',
        'Cùng khám phá các mẫu bàn phím cơ, switch và keycap mới về shop.'
    )
    print('Inserted 1 news')

    await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
