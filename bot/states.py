from aiogram.fsm.state import State, StatesGroup


class AddProduct(StatesGroup):
    category = State()
    name = State()
    brand = State()
    size = State()
    condition = State()
    price = State()
    description = State()
    photos = State()


class AddCategory(StatesGroup):
    name = State()
