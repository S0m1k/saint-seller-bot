from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_session
from core.models import CartItem, Favorite, Product
from api.auth import get_current_user
from api.schemas import ProductOut
from api.serializers import serialize_product

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=list[ProductOut])
async def list_favorites(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    fav = await session.execute(select(Favorite.product_id).where(Favorite.user_id == user.telegram_id))
    fav_ids = {r[0] for r in fav.all()}
    if not fav_ids:
        return []
    cart = await session.execute(select(CartItem.product_id).where(CartItem.user_id == user.telegram_id))
    cart_ids = {r[0] for r in cart.all()}

    result = await session.execute(
        select(Product)
        .where(Product.id.in_(fav_ids), Product.is_active.is_(True))
        .options(selectinload(Product.photos))
        .order_by(Product.created_at.desc())
    )
    return [serialize_product(p, fav_ids, cart_ids) for p in result.scalars().all()]


@router.post("/{product_id}")
async def add_favorite(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    exists = await session.execute(
        select(Favorite).where(
            Favorite.user_id == user.telegram_id, Favorite.product_id == product_id
        )
    )
    if not exists.scalar_one_or_none():
        session.add(Favorite(user_id=user.telegram_id, product_id=product_id))
        await session.commit()
    return {"ok": True, "is_favorite": True}


@router.delete("/{product_id}")
async def remove_favorite(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    result = await session.execute(
        select(Favorite).where(
            Favorite.user_id == user.telegram_id, Favorite.product_id == product_id
        )
    )
    fav = result.scalar_one_or_none()
    if fav:
        await session.delete(fav)
        await session.commit()
    return {"ok": True, "is_favorite": False}
