import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import get_session
from core.models import CartItem, Order, OrderItem, OrderStatus, Product, User
from api.auth import get_current_user
from api.schemas import OrderCreate, OrderItemOut, OrderOut
from bot.instance import get_bot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orders", tags=["orders"])


def _serialize_order(order: Order) -> OrderOut:
    items = [
        OrderItemOut(
            product_name=it.product_name,
            brand=it.brand,
            size=it.size,
            price=float(it.price) if it.price is not None else None,
            quantity=it.quantity,
        )
        for it in order.items
    ]
    total = sum((it.price or 0) * it.quantity for it in items)
    return OrderOut(
        id=order.id,
        status=order.status,
        status_label=OrderStatus.LABELS.get(order.status, order.status),
        comment=order.comment,
        contact=order.contact,
        created_at=order.created_at,
        items=items,
        total=round(float(total), 2),
    )


async def _notify_admins(order: Order, user: User) -> None:
    bot = get_bot()
    if bot is None:
        logger.warning("Заказ #%s создан, но бот недоступен для уведомления", order.id)
        return

    name = " ".join(filter(None, [user.first_name, user.last_name])) or "—"
    handle = f"@{user.username}" if user.username else f"id{user.telegram_id}"
    lines = [
        f"🛒 <b>Новый заказ #{order.id}</b>",
        f"Покупатель: {name} ({handle})",
    ]
    if order.contact:
        lines.append(f"Контакт: {order.contact}")
    if order.comment:
        lines.append(f"Комментарий: {order.comment}")
    lines.append("\n<b>Состав:</b>")
    total = 0.0
    for it in order.items:
        piece = f"• {it.product_name}"
        extra = " ".join(filter(None, [it.brand, it.size]))
        if extra:
            piece += f" ({extra})"
        piece += f" ×{it.quantity}"
        if it.price is not None:
            piece += f" — {it.price:g} ₽"
            total += float(it.price) * it.quantity
        lines.append(piece)
    if total:
        lines.append(f"\n<b>Итого: {total:g} ₽</b>")
    lines.append("\nПодтвердите заказ в /admin → 🧾 Заказы.")
    text = "\n".join(lines)

    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, e)


@router.get("", response_model=list[OrderOut])
async def list_orders(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user.telegram_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return [_serialize_order(o) for o in result.scalars().all()]


@router.post("", response_model=OrderOut)
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    result = await session.execute(
        select(CartItem)
        .where(CartItem.user_id == user.telegram_id)
        .options(selectinload(CartItem.product))
    )
    cart_items = result.scalars().all()
    valid = [ci for ci in cart_items if ci.product and ci.product.is_active]
    if not valid:
        raise HTTPException(status_code=400, detail="Корзина пуста")

    order = Order(
        user_id=user.telegram_id,
        status=OrderStatus.NEW,
        comment=payload.comment,
        contact=payload.contact or user.phone,
    )
    session.add(order)
    await session.flush()  # получить order.id

    for ci in valid:
        p: Product = ci.product
        session.add(OrderItem(
            order_id=order.id,
            product_id=p.id,
            product_name=p.name,
            brand=p.brand,
            size=p.size,
            price=p.price,
            quantity=ci.quantity,
        ))

    # очистить корзину
    for ci in cart_items:
        await session.delete(ci)

    await session.commit()

    # перечитать заказ со снимком позиций
    result = await session.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    order = result.scalar_one()

    await _notify_admins(order, user)
    return _serialize_order(order)
