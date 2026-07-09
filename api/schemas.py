from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    id: int
    name: str
    product_count: int = 0


class PhotoOut(BaseModel):
    url: str


class ProductOut(BaseModel):
    id: int
    name: str
    brand: str | None = None
    size: str | None = None
    condition: str | None = None
    description: str | None = None
    price: float | None = None
    category_id: int | None = None
    stock: int = 0
    photos: list[str] = []
    is_favorite: bool = False
    in_cart: bool = False


class CartItemOut(BaseModel):
    product: ProductOut
    quantity: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: float


class OrderItemOut(BaseModel):
    product_name: str
    brand: str | None = None
    size: str | None = None
    price: float | None = None
    quantity: int


class OrderOut(BaseModel):
    id: int
    status: str
    status_label: str
    comment: str | None = None
    contact: str | None = None
    created_at: datetime
    items: list[OrderItemOut]
    total: float


class OrderCreate(BaseModel):
    comment: str | None = None
    contact: str | None = None


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
