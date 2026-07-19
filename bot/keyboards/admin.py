from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.models import Category, Order, OrderStatus, Product


def admin_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить товар", callback_data="adm:add_product")
    kb.button(text="📦 Товары", callback_data="adm:products:0")
    kb.button(text="🗂 Категории", callback_data="adm:categories")
    kb.button(text="🧾 Заказы", callback_data="adm:orders")
    kb.button(text="📢 Рассылка", callback_data="adm:broadcast")
    kb.button(text="📊 Статистика", callback_data="adm:stats")
    kb.adjust(1)
    return kb.as_markup()


def broadcast_collecting() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово, к отправке", callback_data="adm:bc_preview")
    kb.button(text="✖️ Отмена", callback_data="adm:cancel")
    kb.adjust(1)
    return kb.as_markup()


def broadcast_confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Отправить всем", callback_data="adm:bc_send")
    kb.button(text="✖️ Отмена", callback_data="adm:cancel")
    kb.adjust(1)
    return kb.as_markup()


def stats_actions() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Все подписчики (Excel)", callback_data="adm:export:all")
    kb.button(text="📥 Новые за сегодня (Excel)", callback_data="adm:export:today")
    kb.button(text="⬅️ В меню", callback_data="adm:menu")
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="adm:menu")
    return kb.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Отмена", callback_data="adm:cancel")
    return kb.as_markup()


def categories_choose(categories: list[Category]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in categories:
        kb.button(text=cat.name, callback_data=f"adm:pickcat:{cat.id}")
    kb.button(text="✖️ Отмена", callback_data="adm:cancel")
    kb.adjust(1)
    return kb.as_markup()


def skip_or_cancel(skip_cb: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Пропустить", callback_data=skip_cb)
    kb.button(text="✖️ Отмена", callback_data="adm:cancel")
    kb.adjust(2)
    return kb.as_markup()


def photos_done() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово, сохранить", callback_data="adm:photos_done")
    kb.button(text="✖️ Отмена", callback_data="adm:cancel")
    kb.adjust(1)
    return kb.as_markup()


def confirm_delete_category(category_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить", callback_data=f"adm:delcat_yes:{category_id}")
    kb.button(text="⬅️ Отмена", callback_data="adm:categories")
    kb.adjust(1)
    return kb.as_markup()


def confirm_delete_product(product_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить", callback_data=f"adm:delprod_yes:{product_id}")
    kb.button(text="⬅️ Отмена", callback_data=f"adm:product:{product_id}")
    kb.adjust(1)
    return kb.as_markup()


def categories_manage(categories: list[Category]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in categories:
        kb.button(text=f"🗑 {cat.name}", callback_data=f"adm:delcat:{cat.id}")
    kb.button(text="➕ Добавить категорию", callback_data="adm:addcat")
    kb.button(text="⬅️ В меню", callback_data="adm:menu")
    kb.adjust(1)
    return kb.as_markup()


def products_list_kb(products: list[Product], page: int, has_next: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in products:
        mark = "🟢" if p.is_active else "🔴"
        kb.button(text=f"{mark} {p.name}", callback_data=f"adm:product:{p.id}")
    kb.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:products:{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:products:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:menu"))
    return kb.as_markup()


def product_actions(product: Product) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    toggle = "🔴 Скрыть" if product.is_active else "🟢 Показать"
    kb.button(text=toggle, callback_data=f"adm:toggle:{product.id}")
    kb.button(text="🗑 Удалить", callback_data=f"adm:delprod:{product.id}")
    kb.button(text="⬅️ К списку", callback_data="adm:products:0")
    kb.adjust(2, 1)
    return kb.as_markup()


def order_actions(order: Order) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if order.status == OrderStatus.NEW:
        kb.button(text="✅ Подтвердить", callback_data=f"adm:order_ok:{order.id}")
        kb.button(text="❌ Отменить", callback_data=f"adm:order_no:{order.id}")
    elif order.status == OrderStatus.CONFIRMED:
        kb.button(text="📦 Выполнен", callback_data=f"adm:order_done:{order.id}")
        kb.button(text="❌ Отменить", callback_data=f"adm:order_no:{order.id}")
    kb.adjust(2)
    return kb.as_markup()
