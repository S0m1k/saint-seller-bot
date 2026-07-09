from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_session
from core.models import CartItem, Category, Favorite, Product
from api.auth import get_current_user
from api.schemas import CategoryOut, ProductOut
from api.serializers import serialize_product

router = APIRouter(prefix="/api", tags=["catalog"])


async def _user_flag_ids(session: AsyncSession, user_id: int) -> tuple[set[int], set[int]]:
    fav = await session.execute(select(Favorite.product_id).where(Favorite.user_id == user_id))
    cart = await session.execute(select(CartItem.product_id).where(CartItem.user_id == user_id))
    return {r[0] for r in fav.all()}, {r[0] for r in cart.all()}


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    count_col = func.count(Product.id).filter(Product.is_active.is_(True))
    result = await session.execute(
        select(Category, count_col)
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.name)
    )
    return [
        CategoryOut(id=cat.id, name=cat.name, product_count=cnt or 0)
        for cat, cnt in result.all()
    ]


@router.get("/brands", response_model=list[str])
async def list_brands(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    result = await session.execute(
        select(Product.brand)
        .where(Product.is_active.is_(True), Product.brand.is_not(None), Product.brand != "")
        .distinct()
        .order_by(Product.brand)
    )
    return [r[0] for r in result.all()]


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    category_id: int | None = None,
    brand: str | None = None,
    search: str | None = None,
    favorites: bool = Query(default=False, description="Только избранное"),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    fav_ids, cart_ids = await _user_flag_ids(session, user.telegram_id)

    stmt = (
        select(Product)
        .where(Product.is_active.is_(True))
        .options(selectinload(Product.photos))
        .order_by(Product.created_at.desc())
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if brand:
        stmt = stmt.where(Product.brand == brand)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.brand.ilike(like)))
    if favorites:
        if not fav_ids:
            return []
        stmt = stmt.where(Product.id.in_(fav_ids))

    stmt = stmt.offset(page * page_size).limit(page_size)
    result = await session.execute(stmt)
    products = result.scalars().all()
    return [serialize_product(p, fav_ids, cart_ids) for p in products]


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    result = await session.execute(
        select(Product)
        .where(Product.id == product_id, Product.is_active.is_(True))
        .options(selectinload(Product.photos))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    fav_ids, cart_ids = await _user_flag_ids(session, user.telegram_id)
    return serialize_product(product, fav_ids, cart_ids)
