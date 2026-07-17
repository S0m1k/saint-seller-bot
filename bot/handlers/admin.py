import asyncio
import logging
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import async_session
from core.models import (
    Category,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductPhoto,
    User,
)
from bot.broadcast import broadcast
from bot.keyboards import admin as kb
from bot.media import save_product_photo
from bot.notifications import broadcast_new_product
from bot.stats import (
    collect_stats,
    fetch_users,
    format_stats,
    local_day_bounds_utc,
    users_to_xlsx,
)
from bot.states import AddCategory, AddProduct, Broadcast

logger = logging.getLogger(__name__)
router = Router()

PRODUCTS_PER_PAGE = 8
MENU_TEXT = "🛠 <b>Админ-панель Saint Seller</b>\n\nВыберите действие:"

# Фото альбомом прилетают отдельными апдейтами почти одновременно и обрабатываются
# как параллельные задачи aiogram — без блокировки чтение-изменение-запись состояния
# FSM гонится и теряет/дублирует фото. Лочим по пользователю, чтобы append был атомарным.
_photo_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return bool(event.from_user) and settings.is_admin(event.from_user.id)


# Все хэндлеры этого роутера доступны только администраторам.
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ----------------------------- Меню -----------------------------------------


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(MENU_TEXT, reply_markup=kb.admin_menu())


@router.callback_query(F.data == "adm:menu")
async def cb_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(MENU_TEXT, reply_markup=kb.admin_menu())
    await call.answer()


@router.callback_query(F.data == "adm:cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("Отменено.", reply_markup=kb.back_to_menu())
    await call.answer()


# ------------------------- Добавление товара --------------------------------


@router.callback_query(F.data == "adm:add_product")
async def cb_add_product(call: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        result = await session.execute(select(Category).order_by(Category.sort_order, Category.name))
        categories = result.scalars().all()

    if not categories:
        await call.message.edit_text(
            "Сначала добавьте хотя бы одну категорию.",
            reply_markup=kb.categories_manage([]),
        )
        await call.answer()
        return

    await state.set_state(AddProduct.category)
    await call.message.edit_text(
        "🗂 Выберите категорию для товара:",
        reply_markup=kb.categories_choose(categories),
    )
    await call.answer()


@router.callback_query(AddProduct.category, F.data.startswith("adm:pickcat:"))
async def cb_pick_category(call: CallbackQuery, state: FSMContext) -> None:
    category_id = int(call.data.split(":")[2])
    await state.update_data(category_id=category_id, photos=[])
    await state.set_state(AddProduct.name)
    await call.message.edit_text("✏️ Введите <b>название</b> товара:")
    await call.answer()


@router.message(AddProduct.name, F.text)
async def st_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProduct.brand)
    await message.answer("🏷 Введите <b>бренд</b>:", reply_markup=kb.skip_or_cancel("adm:skip:brand"))


@router.message(AddProduct.brand, F.text)
async def st_brand(message: Message, state: FSMContext) -> None:
    await state.update_data(brand=message.text.strip())
    await _ask_size(message, state)


@router.callback_query(AddProduct.brand, F.data == "adm:skip:brand")
async def st_brand_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(brand=None)
    await _ask_size(call.message, state)
    await call.answer()


async def _ask_size(message: Message, state: FSMContext) -> None:
    await state.set_state(AddProduct.size)
    await message.answer("📏 Введите <b>размер</b>:", reply_markup=kb.skip_or_cancel("adm:skip:size"))


@router.message(AddProduct.size, F.text)
async def st_size(message: Message, state: FSMContext) -> None:
    await state.update_data(size=message.text.strip())
    await _ask_condition(message, state)


@router.callback_query(AddProduct.size, F.data == "adm:skip:size")
async def st_size_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(size=None)
    await _ask_condition(call.message, state)
    await call.answer()


async def _ask_condition(message: Message, state: FSMContext) -> None:
    await state.set_state(AddProduct.condition)
    await message.answer(
        "✨ Введите <b>состояние</b> (например: новое, б/у 9/10):",
        reply_markup=kb.skip_or_cancel("adm:skip:condition"),
    )


@router.message(AddProduct.condition, F.text)
async def st_condition(message: Message, state: FSMContext) -> None:
    await state.update_data(condition=message.text.strip())
    await _ask_price(message, state)


@router.callback_query(AddProduct.condition, F.data == "adm:skip:condition")
async def st_condition_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(condition=None)
    await _ask_price(call.message, state)
    await call.answer()


async def _ask_price(message: Message, state: FSMContext) -> None:
    await state.set_state(AddProduct.price)
    await message.answer(
        "💰 Введите <b>цену</b> в рублях (только число):",
        reply_markup=kb.skip_or_cancel("adm:skip:price"),
    )


@router.message(AddProduct.price, F.text)
async def st_price(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(",", ".").replace(" ", "")
    try:
        price = round(float(raw), 2)
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректное число, например 4990 или пропустите.",
                             reply_markup=kb.skip_or_cancel("adm:skip:price"))
        return
    await state.update_data(price=price)
    await _ask_stock(message, state)


@router.callback_query(AddProduct.price, F.data == "adm:skip:price")
async def st_price_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(price=None)
    await _ask_stock(call.message, state)
    await call.answer()


async def _ask_stock(message: Message, state: FSMContext) -> None:
    await state.set_state(AddProduct.stock)
    await message.answer(
        "🔢 Введите <b>количество</b> (остаток на складе, только число).\n"
        "Пропустите — будет 1 шт.",
        reply_markup=kb.skip_or_cancel("adm:skip:stock"),
    )


@router.message(AddProduct.stock, F.text)
async def st_stock(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(" ", "")
    try:
        stock = int(raw)
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое число ≥ 0, например 1 или 5.",
                             reply_markup=kb.skip_or_cancel("adm:skip:stock"))
        return
    await state.update_data(stock=stock)
    await _ask_description(message, state)


@router.callback_query(AddProduct.stock, F.data == "adm:skip:stock")
async def st_stock_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(stock=1)
    await _ask_description(call.message, state)
    await call.answer()


async def _ask_description(message: Message, state: FSMContext) -> None:
    await state.set_state(AddProduct.description)
    await message.answer(
        "📝 Введите <b>описание</b>:",
        reply_markup=kb.skip_or_cancel("adm:skip:description"),
    )


@router.message(AddProduct.description, F.text)
async def st_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await _ask_photos(message, state)


@router.callback_query(AddProduct.description, F.data == "adm:skip:description")
async def st_description_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(description=None)
    await _ask_photos(call.message, state)
    await call.answer()


async def _ask_photos(message: Message, state: FSMContext) -> None:
    await state.set_state(AddProduct.photos)
    await message.answer(
        "📷 Отправьте одно или несколько <b>фото</b> товара.\n"
        "Когда закончите — нажмите «Готово».",
        reply_markup=kb.photos_done(),
    )


@router.message(AddProduct.photos, F.photo)
async def st_photo(message: Message, state: FSMContext) -> None:
    lock = _photo_locks[message.from_user.id]
    async with lock:
        data = await state.get_data()
        photos: list[dict] = data.get("photos", [])
        photos.append({"message_id": message.message_id, "file_id": message.photo[-1].file_id})
        await state.update_data(photos=photos)
        count = len(photos)
    await message.answer(f"Добавлено фото ({count}). Ещё или «Готово».",
                         reply_markup=kb.photos_done())


@router.message(AddProduct.photos)
async def st_photo_wrong(message: Message) -> None:
    await message.answer("Пришлите именно фото или нажмите «Готово».",
                         reply_markup=kb.photos_done())


@router.callback_query(AddProduct.photos, F.data == "adm:photos_done")
async def cb_photos_done(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    photos_data: list[dict] = data.get("photos", [])
    if not photos_data:
        await call.answer("Добавьте хотя бы одно фото", show_alert=True)
        return
    # Сортируем по message_id — гарантирует порядок отправки независимо от
    # того, в каком порядке фактически обработались параллельные апдейты.
    photos = [p["file_id"] for p in sorted(photos_data, key=lambda p: p["message_id"])]

    await call.message.edit_text("⏳ Сохраняю товар...")

    async with async_session() as session:
        product = Product(
            name=data["name"],
            brand=data.get("brand"),
            size=data.get("size"),
            condition=data.get("condition"),
            price=data.get("price"),
            stock=data.get("stock", 1),
            description=data.get("description"),
            category_id=data["category_id"],
            is_active=True,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)

        for i, file_id in enumerate(photos):
            try:
                rel_path = await save_product_photo(bot, file_id, product.id)
            except Exception as e:  # noqa: BLE001
                logger.warning("Не удалось скачать фото %s: %s", file_id, e)
                continue
            session.add(ProductPhoto(product_id=product.id, file_id=file_id,
                                     file_path=rel_path, sort_order=i))
        await session.commit()

        loaded = await session.execute(
            select(Product).where(Product.id == product.id).options(selectinload(Product.photos))
        )
        product = loaded.scalar_one()

    await state.clear()

    sent = await broadcast_new_product(bot, product)
    await call.message.edit_text(
        f"✅ Товар <b>«{product.name}»</b> добавлен.\n"
        f"Уведомление отправлено пользователям: <b>{sent}</b>.",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


# --------------------------- Категории --------------------------------------


async def _render_categories(target: Message) -> None:
    async with async_session() as session:
        result = await session.execute(select(Category).order_by(Category.sort_order, Category.name))
        categories = result.scalars().all()
    text = "🗂 <b>Категории</b>\n\nНажмите на категорию, чтобы удалить её."
    if not categories:
        text = "🗂 <b>Категории</b>\n\nПока нет ни одной категории."
    await target.edit_text(text, reply_markup=kb.categories_manage(categories))


@router.callback_query(F.data == "adm:categories")
async def cb_categories(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _render_categories(call.message)
    await call.answer()


@router.callback_query(F.data == "adm:addcat")
async def cb_addcat(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddCategory.name)
    await call.message.edit_text("✏️ Введите название новой категории:",
                                 reply_markup=kb.cancel_keyboard())
    await call.answer()


@router.message(AddCategory.name, F.text)
async def st_addcat(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    async with async_session() as session:
        exists = await session.execute(select(Category).where(func.lower(Category.name) == name.lower()))
        if exists.scalar_one_or_none():
            await message.answer("Такая категория уже есть. Введите другое название.")
            return
        session.add(Category(name=name))
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Категория «{name}» добавлена.", reply_markup=kb.back_to_menu())


@router.callback_query(F.data.startswith("adm:delcat:"))
async def cb_delcat(call: CallbackQuery) -> None:
    category_id = int(call.data.split(":")[2])
    async with async_session() as session:
        category = await session.get(Category, category_id)
        if category:
            await session.delete(category)
            await session.commit()
    await _render_categories(call.message)
    await call.answer("Категория удалена")


# ---------------------------- Товары ----------------------------------------


@router.callback_query(F.data.startswith("adm:products:"))
async def cb_products(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    page = int(call.data.split(":")[2])
    offset = page * PRODUCTS_PER_PAGE
    async with async_session() as session:
        result = await session.execute(
            select(Product).order_by(Product.created_at.desc())
            .offset(offset).limit(PRODUCTS_PER_PAGE + 1)
        )
        products = result.scalars().all()
    has_next = len(products) > PRODUCTS_PER_PAGE
    products = products[:PRODUCTS_PER_PAGE]

    text = "📦 <b>Товары</b>" if products else "📦 Товаров пока нет."
    await call.message.edit_text(text, reply_markup=kb.products_list_kb(products, page, has_next))
    await call.answer()


def _product_card(product: Product) -> str:
    lines = [f"<b>{product.name}</b>"]
    if product.brand:
        lines.append(f"Бренд: {product.brand}")
    if product.size:
        lines.append(f"Размер: {product.size}")
    if product.condition:
        lines.append(f"Состояние: {product.condition}")
    if product.price is not None:
        lines.append(f"Цена: {product.price:g} ₽")
    lines.append(f"В наличии: {product.stock} шт.")
    if product.description:
        lines.append(f"\n{product.description}")
    lines.append(f"\nСтатус: {'🟢 активен' if product.is_active else '🔴 скрыт'}")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("adm:product:"))
async def cb_product(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[2])
    async with async_session() as session:
        product = await session.get(Product, product_id)
    if not product:
        await call.answer("Товар не найден", show_alert=True)
        return
    await call.message.edit_text(_product_card(product), reply_markup=kb.product_actions(product))
    await call.answer()


@router.callback_query(F.data.startswith("adm:toggle:"))
async def cb_toggle(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[2])
    async with async_session() as session:
        product = await session.get(Product, product_id)
        if product:
            product.is_active = not product.is_active
            await session.commit()
            await session.refresh(product)
    await call.message.edit_text(_product_card(product), reply_markup=kb.product_actions(product))
    await call.answer("Готово")


@router.callback_query(F.data.startswith("adm:delprod:"))
async def cb_delprod(call: CallbackQuery) -> None:
    product_id = int(call.data.split(":")[2])
    async with async_session() as session:
        product = await session.get(Product, product_id)
        if product:
            await session.delete(product)
            await session.commit()
    await call.answer("Товар удалён")
    # вернуться к первой странице списка
    async with async_session() as session:
        result = await session.execute(
            select(Product).order_by(Product.created_at.desc()).limit(PRODUCTS_PER_PAGE + 1)
        )
        products = result.scalars().all()
    has_next = len(products) > PRODUCTS_PER_PAGE
    products = products[:PRODUCTS_PER_PAGE]
    text = "📦 <b>Товары</b>" if products else "📦 Товаров пока нет."
    await call.message.edit_text(text, reply_markup=kb.products_list_kb(products, 0, has_next))


# ---------------------------- Заказы ----------------------------------------


@router.callback_query(F.data == "adm:orders")
async def cb_orders(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with async_session() as session:
        result = await session.execute(
            select(Order)
            .where(Order.status.in_([OrderStatus.NEW, OrderStatus.CONFIRMED]))
            .order_by(Order.created_at.desc())
            .options(selectinload(Order.items), selectinload(Order.user))
            .limit(20)
        )
        orders = result.scalars().all()

    if not orders:
        await call.message.edit_text("🧾 Активных заказов нет.", reply_markup=kb.back_to_menu())
        await call.answer()
        return

    await call.message.edit_text("🧾 <b>Активные заказы</b>:", reply_markup=kb.back_to_menu())
    for order in orders:
        await call.message.answer(_order_text(order), reply_markup=kb.order_actions(order))
    await call.answer()


def _order_text(order: Order) -> str:
    u = order.user
    name = " ".join(filter(None, [u.first_name, u.last_name])) if u else "—"
    handle = f"@{u.username}" if u and u.username else f"id{order.user_id}"
    lines = [
        f"🧾 <b>Заказ #{order.id}</b> — {OrderStatus.LABELS.get(order.status, order.status)}",
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
    return "\n".join(lines)


async def _set_order_status(call: CallbackQuery, bot: Bot, new_status: str,
                            user_text: str) -> None:
    order_id = int(call.data.split(":")[2])
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if not order:
            await call.answer("Заказ не найден", show_alert=True)
            return
        order.status = new_status
        await session.commit()
        user_id = order.user_id

    await call.message.edit_text(
        call.message.html_text + f"\n\n<i>→ {OrderStatus.LABELS[new_status]}</i>"
    )
    try:
        await bot.send_message(user_id, user_text.format(order_id=order_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("Не удалось уведомить покупателя %s: %s", user_id, e)
    await call.answer("Статус обновлён")


@router.callback_query(F.data.startswith("adm:order_ok:"))
async def cb_order_ok(call: CallbackQuery, bot: Bot) -> None:
    await _set_order_status(
        call, bot, OrderStatus.CONFIRMED,
        "✅ Ваш заказ #{order_id} подтверждён! Скоро с вами свяжутся по деталям.",
    )


@router.callback_query(F.data.startswith("adm:order_done:"))
async def cb_order_done(call: CallbackQuery, bot: Bot) -> None:
    await _set_order_status(
        call, bot, OrderStatus.COMPLETED,
        "📦 Ваш заказ #{order_id} выполнен. Спасибо за покупку!",
    )


@router.callback_query(F.data.startswith("adm:order_no:"))
async def cb_order_no(call: CallbackQuery, bot: Bot) -> None:
    await _set_order_status(
        call, bot, OrderStatus.CANCELLED,
        "❌ Ваш заказ #{order_id} отменён. По вопросам напишите нам.",
    )


# ---------------------------- Рассылка --------------------------------------


@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Broadcast.collecting)
    await state.update_data(bc_text="", bc_photos=[])
    await call.message.edit_text(
        "📢 <b>Рассылка всем подписчикам</b>\n\n"
        "Пришлите <b>текст</b> и/или <b>фото</b> (можно несколько).\n"
        "Когда всё готово — нажмите «Готово, к отправке».",
        reply_markup=kb.broadcast_collecting(),
    )
    await call.answer()


@router.message(Broadcast.collecting, F.photo)
async def bc_photo(message: Message, state: FSMContext) -> None:
    lock = _photo_locks[message.from_user.id]
    async with lock:
        data = await state.get_data()
        photos: list[dict] = data.get("bc_photos", [])
        photos.append({"message_id": message.message_id, "file_id": message.photo[-1].file_id})
        upd = {"bc_photos": photos}
        if message.caption and not data.get("bc_text"):
            upd["bc_text"] = message.caption
        await state.update_data(**upd)
        count = len(photos)
    await message.answer(f"📷 Фото добавлено ({count}).", reply_markup=kb.broadcast_collecting())


@router.message(Broadcast.collecting, F.text)
async def bc_text(message: Message, state: FSMContext) -> None:
    await state.update_data(bc_text=message.text)
    await message.answer("📝 Текст сохранён.", reply_markup=kb.broadcast_collecting())


def _broadcast_payload(data: dict) -> tuple[str, list[str]]:
    text = data.get("bc_text", "") or ""
    photos = [
        p["file_id"]
        for p in sorted(data.get("bc_photos", []), key=lambda p: p["message_id"])
    ]
    return text, photos


@router.callback_query(Broadcast.collecting, F.data == "adm:bc_preview")
async def cb_bc_preview(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text, photos = _broadcast_payload(data)
    if not text and not photos:
        await call.answer("Сначала добавьте текст или фото", show_alert=True)
        return
    await state.set_state(Broadcast.confirm)

    from bot.broadcast import _send_to_user

    await call.message.answer("👇 <b>Предпросмотр рассылки:</b>")
    await _send_to_user(bot, call.from_user.id, text, photos)

    async with async_session() as session:
        count = (await session.execute(
            select(func.count(User.telegram_id)).where(User.is_active.is_(True))
        )).scalar_one()
    await call.message.answer(
        f"Отправить рассылку <b>{count}</b> активным подписчикам?",
        reply_markup=kb.broadcast_confirm(),
    )
    await call.answer()


@router.callback_query(Broadcast.confirm, F.data == "adm:bc_send")
async def cb_bc_send(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text, photos = _broadcast_payload(data)
    await state.clear()
    await call.message.edit_text("📤 Отправляю рассылку, это может занять время…")
    await call.answer()
    sent, failed = await broadcast(bot, text, photos)
    await call.message.answer(
        f"✅ <b>Рассылка завершена</b>\nДоставлено: <b>{sent}</b>\nНе доставлено: <b>{failed}</b>",
        reply_markup=kb.back_to_menu(),
    )


# ---------------------------- Статистика ------------------------------------


@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with async_session() as session:
        stats = await collect_stats(session)
    await call.message.edit_text(format_stats(stats), reply_markup=kb.stats_actions())
    await call.answer()


@router.callback_query(F.data.startswith("adm:export:"))
async def cb_export(call: CallbackQuery) -> None:
    scope = call.data.split(":")[2]
    await call.answer("Готовлю файл…")
    async with async_session() as session:
        if scope == "today":
            start, end = local_day_bounds_utc(0)
            users = await fetch_users(session, start, end)
            fname = "new_subscribers_today.xlsx"
        else:
            users = await fetch_users(session)
            fname = "subscribers.xlsx"
    if not users:
        await call.message.answer("Нет данных для выгрузки.")
        return
    document = BufferedInputFile(users_to_xlsx(users), filename=fname)
    await call.message.answer_document(document, caption=f"Записей: {len(users)}")
