from core.models import Product
from api.schemas import ProductOut


def photo_url(file_path: str) -> str:
    return f"/media/{file_path}"


def serialize_product(
    product: Product,
    favorite_ids: set[int] | None = None,
    cart_ids: set[int] | None = None,
) -> ProductOut:
    favorite_ids = favorite_ids or set()
    cart_ids = cart_ids or set()
    return ProductOut(
        id=product.id,
        name=product.name,
        brand=product.brand,
        size=product.size,
        condition=product.condition,
        description=product.description,
        price=float(product.price) if product.price is not None else None,
        category_id=product.category_id,
        photos=[photo_url(p.file_path) for p in product.photos],
        is_favorite=product.id in favorite_ids,
        in_cart=product.id in cart_ids,
    )
