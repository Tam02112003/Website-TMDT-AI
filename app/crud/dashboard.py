import asyncpg
import json
from datetime import date, timedelta
from typing import List
from core.utils.enums import OrderStatus
from schemas import schemas

# Orders in these statuses represent real, counted revenue - same definition
# used elsewhere (crud/order.py's get_all_purchase_history).
REVENUE_STATUSES = [OrderStatus.PAID.value, OrderStatus.PROCESSING.value, OrderStatus.DELIVERED.value]


async def get_summary(db: asyncpg.Connection, days: int) -> schemas.DashboardSummary:
    current = await db.fetchrow(
        """
        SELECT COALESCE(SUM(total_amount), 0) as revenue, COUNT(*) as orders
        FROM orders
        WHERE status = ANY($1::text[]) AND created_at >= NOW() - make_interval(days => $2::int)
        """,
        REVENUE_STATUSES, days,
    )
    previous = await db.fetchrow(
        """
        SELECT COALESCE(SUM(total_amount), 0) as revenue, COUNT(*) as orders
        FROM orders
        WHERE status = ANY($1::text[])
          AND created_at >= NOW() - make_interval(days => $2::int) * 2
          AND created_at < NOW() - make_interval(days => $2::int)
        """,
        REVENUE_STATUSES, days,
    )
    total_customers = await db.fetchval(
        """
        SELECT COUNT(DISTINCT user_id) FROM orders
        WHERE status = ANY($1::text[]) AND created_at >= NOW() - make_interval(days => $2::int)
        """,
        REVENUE_STATUSES, days,
    )
    pending_orders = await db.fetchval("SELECT COUNT(*) FROM orders WHERE status = $1", OrderStatus.PENDING.value)

    total_revenue = float(current["revenue"])
    total_orders = current["orders"]
    prev_revenue = float(previous["revenue"])
    prev_orders = previous["orders"]

    def pct_change(curr: float, prev: float):
        if prev <= 0:
            return None
        return round((curr - prev) / prev * 100, 1)

    return schemas.DashboardSummary(
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_customers=total_customers,
        avg_order_value=(total_revenue / total_orders) if total_orders else 0.0,
        pending_orders=pending_orders,
        revenue_change_pct=pct_change(total_revenue, prev_revenue),
        orders_change_pct=pct_change(total_orders, prev_orders),
    )


async def get_revenue_timeseries(db: asyncpg.Connection, days: int) -> List[schemas.RevenuePoint]:
    rows = await db.fetch(
        """
        SELECT DATE(created_at) as day, COALESCE(SUM(total_amount), 0) as revenue, COUNT(*) as order_count
        FROM orders
        WHERE status = ANY($1::text[]) AND created_at >= NOW() - make_interval(days => $2::int)
        GROUP BY DATE(created_at)
        """,
        REVENUE_STATUSES, days,
    )
    by_day = {row["day"]: row for row in rows}

    # Fill in every day in the range with 0s so the chart has a continuous x-axis,
    # not just the days that happened to have an order.
    today = date.today()
    points = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        row = by_day.get(day)
        points.append(schemas.RevenuePoint(
            day=day,
            revenue=float(row["revenue"]) if row else 0.0,
            order_count=row["order_count"] if row else 0,
        ))
    return points


async def get_top_products(db: asyncpg.Connection, days: int, limit: int = 5) -> List[schemas.TopProduct]:
    rows = await db.fetch(
        """
        SELECT p.id, p.name, p.image_urls, SUM(oi.quantity) as quantity_sold, SUM(oi.quantity * oi.price) as revenue
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id
        WHERE o.status = ANY($1::text[]) AND o.created_at >= NOW() - make_interval(days => $2::int)
        GROUP BY p.id, p.name, p.image_urls
        ORDER BY quantity_sold DESC
        LIMIT $3
        """,
        REVENUE_STATUSES, days, limit,
    )
    result = []
    for row in rows:
        image_url = None
        if row["image_urls"]:
            try:
                urls = json.loads(row["image_urls"])
                image_url = urls[0] if urls else None
            except json.JSONDecodeError:
                image_url = row["image_urls"]
        result.append(schemas.TopProduct(
            id=row["id"], name=row["name"], image_url=image_url,
            quantity_sold=row["quantity_sold"], revenue=float(row["revenue"]),
        ))
    return result


async def get_order_status_breakdown(db: asyncpg.Connection) -> List[schemas.OrderStatusCount]:
    rows = await db.fetch("SELECT status, COUNT(*) as count FROM orders GROUP BY status ORDER BY count DESC")
    return [schemas.OrderStatusCount(status=row["status"], count=row["count"]) for row in rows]


async def get_recent_orders(db: asyncpg.Connection, limit: int = 10) -> List[schemas.RecentOrder]:
    rows = await db.fetch(
        """
        SELECT o.id, o.order_code, u.username, o.total_amount, o.status, o.created_at
        FROM orders o
        LEFT JOIN users u ON u.id = o.user_id
        ORDER BY o.created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [schemas.RecentOrder(**dict(row)) for row in rows]
