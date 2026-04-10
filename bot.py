import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

TOKEN = "8674017448:AAF0DE0OQMVFzGCGSKYV1P30Rfezd-LGTN0"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ======= КАТАЛОГ ТОВАРОВ =======
# Добавляй/меняй товары здесь
products = {
    "1": {"name": "Футболка оверсайз", "price": 1500, "desc": "Хлопок 100%, размеры S-XL\nЦвета: белый, чёрный, серый"},
    "2": {"name": "Джинсы slim fit",    "price": 3200, "desc": "Стрейч-деним, размеры 28-36\nЦвет: синий, чёрный"},
    "3": {"name": "Худи базовый",       "price": 2800, "desc": "Флис 300г, размеры S-XXL\nЦвета: чёрный, белый, бежевый"},
    "4": {"name": "Платье миди",        "price": 2500, "desc": "Вискоза, размеры XS-L\nЦвета: чёрный, красный"},
    "5": {"name": "Куртка-ветровка",    "price": 4500, "desc": "Нейлон, унисекс, размеры S-XL\nЦвета: оливковый, чёрный"},
}

# Контакт для заказа — замени на свой
ORDER_CONTACT = "@твой_ник"  # или номер телефона

# ======= КНОПКИ ГЛАВНОГО МЕНЮ =======
def main_menu():
    buttons = [
        [InlineKeyboardButton(text="👕 Каталог товаров", callback_data="catalog")],
        [InlineKeyboardButton(text="📦 Как сделать заказ", callback_data="how_to_order")],
        [InlineKeyboardButton(text="📞 Связаться с нами", callback_data="contact")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ======= КНОПКИ КАТАЛОГА =======
def catalog_menu():
    buttons = []
    for pid, item in products.items():
        buttons.append([InlineKeyboardButton(
            text=f"{item['name']} — {item['price']} ₽",
            callback_data=f"product_{pid}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ======= КНОПКА ТОВАРА =======
def product_menu(pid):
    buttons = [
        [InlineKeyboardButton(text="🛒 Заказать этот товар", callback_data=f"order_{pid}")],
        [InlineKeyboardButton(text="◀️ Назад к каталогу", callback_data="catalog")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ======= ОБРАБОТЧИКИ =======

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в наш магазин одежды 👗\n"
        "Выбери что тебя интересует:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 Наш каталог товаров\nВыбери товар чтобы узнать подробнее:",
        reply_markup=catalog_menu()
    )

@dp.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    pid = callback.data.split("_")[1]
    item = products.get(pid)
    if not item:
        await callback.answer("Товар не найден")
        return
    text = (
        f"📦 *{item['name']}*\n\n"
        f"💰 Цена: *{item['price']} ₽*\n\n"
        f"📝 {item['desc']}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=product_menu(pid))

@dp.callback_query(F.data.startswith("order_"))
async def order_product(callback: CallbackQuery):
    pid = callback.data.split("_")[1]
    item = products.get(pid)
    if not item:
        await callback.answer("Товар не найден")
        return
    text = (
        f"✅ Отлично! Ты хочешь заказать:\n"
        f"👕 *{item['name']}* — {item['price']} ₽\n\n"
        f"Напиши нам для оформления заказа:\n"
        f"👉 {ORDER_CONTACT}"
    )
    back_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к каталогу", callback_data="catalog")]
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_btn)

@dp.callback_query(F.data == "how_to_order")
async def how_to_order(callback: CallbackQuery):
    text = (
        "📦 *Как сделать заказ:*\n\n"
        "1️⃣ Выбери товар в каталоге\n"
        "2️⃣ Нажми кнопку «Заказать»\n"
        "3️⃣ Напиши нам в личку\n"
        "4️⃣ Укажи размер и способ доставки\n"
        "5️⃣ Оплати и жди посылку! 🎉\n\n"
        "Доставка по всей России 🚚"
    )
    back_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_btn)

@dp.callback_query(F.data == "contact")
async def contact(callback: CallbackQuery):
    text = (
        "📞 *Связаться с нами:*\n\n"
        f"Менеджер: {ORDER_CONTACT}\n\n"
        "Время работы: 9:00 — 21:00\n"
        "Ответим в течение часа 👍"
    )
    back_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_btn)

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "Главное меню — выбери что тебя интересует:",
        reply_markup=main_menu()
    )

# ======= ЗАПУСК =======
async def main():
    print("Бот запущен! Нажми Ctrl+C чтобы остановить.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
