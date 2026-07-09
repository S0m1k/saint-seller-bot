from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_session
from core.models import CartItem, Favorite, Product
from api.auth import get_current_user
from api.schemas import CartItemOut, CartOut
from api.serializers import serialize_product

router = APIRouter(prefix="/api/cart", tags=["cart"])


async def _build_cart(session: AsyncSession, user_id: int) -> CartOut:
    result = await session.execute(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(selectinload(CartItem.product).selectinload(Product.photos))
        .order_by(CartItem.created_at.desc())
    )
    items = result.scalars().all()

    fav = await session.execute(select(Favorite.product_id).where(Favorite.user_id == user_id))
    fav_ids = {r[0] for r in fav.all()}

    out_items: list[CartItemOut] = []
    total = 0.0
    for it in items:
        if not it.product or not it.product.is_active:
            continue
        product = serialize_product(it.product, fav_ids, {it.product_id})
        out_items.append(CartItemOut(product=product, quantity=it.quantity))
        if it.product.price is not None:
            total += float(it.product.price) * it.quantity
    return CartOut(items=out_items, total=round(total, 2))


@router.get("", response_model=CartOut)
async def get_cart(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    return await _build_cart(session, user.telegram_id)


@router.post("/{product_id}", response_model=CartOut)
async def add_to_cart(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    product = await session.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Товар не найден")

    result = await session.execute(
        select(CartItem).where(
            CartItem.user_id == user.telegram_id, CartItem.product_id == product_id
        )
    )
    item = result.scalar_one_or_none()
    if item:
        item.quantity += 1
    else:
        session.add(CartItem(user_id=user.telegram_id, product_id=product_id, quantity=1))
    await session.commit()
    return await _build_cart(session, user.telegram_id)


@router.patch("/{product_id}", response_model=CartOut)
async def set_quantity(
    product_id: int,
    quantity: int = Body(embed=True, ge=0),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    result = await session.execute(
        select(CartItem).where(
            CartItem.user_id == user.telegram_id, CartItem.product_id == product_id
        )
    )
    item = result.scalar_one_or_none()
    if item:
        if quantity <= 0:
            await session.delete(item)
        else:
            item.quantity = quantity
        await session.commit()
    return await _build_cart(session, user.telegram_id)


@router.delete("/{product_id}", response_model=CartOut)
async def remove_from_cart(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    result = await session.execute(
        select(CartItem).where(
            CartItem.user_id == user.telegram_id, CartItem.product_id == product_id
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await session.delete(item)
        await session.commit()
    return await _build_cart(session, user.telegram_id)
