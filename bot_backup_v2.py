import asyncio
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import aiohttp
from aiogram.client.session.aiohttp import AiohttpSession

# ========== YOUR DATA ==========
BOT_TOKEN = "8615838083:AAHQM2oyQDMkNMi4yqdSBBQeJ30OWeNDL7c"
ADMIN_ID = 6175936997  # REPLACE WITH YOUR TELEGRAM ID (NUMBER)
PROXY_URL = ""        # IF NEED PROXY, SET "http://127.0.0.1:7890"
# ===============================

if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL, timeout=aiohttp.ClientTimeout(total=60))
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(storage=MemoryStorage())

# ----- DATABASE -----
def init_db():
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        category_id INTEGER,
        photo_file_id TEXT,
        FOREIGN KEY (category_id) REFERENCES categories (id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cart (
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, product_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        order_data TEXT,
        total INTEGER,
        status TEXT DEFAULT 'новый',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()
init_db()

# ----- FORCE UPDATE CATEGORIES (ONLY RUSSIAN, NO ENGLISH) -----
def force_categories():
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    # Удаляем все старые категории (включая английские)
    cur.execute("DELETE FROM categories")
    # Создаём только три нужные
    new_cats = ["Омега", "Витамины", "Для похудения"]
    for cat in new_cats:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
    conn.commit()
    conn.close()
force_categories()

# ----- FSM STATES -----
class AddProduct(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_category = State()
    waiting_for_photo = State()

class OrderForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()
    confirm = State()

# ----- KEYBOARDS -----
def main_menu():
    kb = [[KeyboardButton(text="🛍 Каталог")],
          [KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="📦 Мои заказы")],
          [KeyboardButton(text="💬 Контакты"), KeyboardButton(text="ℹ️ О нас")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    kb = [[KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="🗑 Удалить товар")],
          [KeyboardButton(text="📋 Новые заказы"), KeyboardButton(text="📊 Статистика")],
          [KeyboardButton(text="📢 Рассылка")],
          [KeyboardButton(text="🏠 Главное меню")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ----- HANDLERS -----
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🌿 *Добро пожаловать!*\n\n"
        "Здесь вы найдёте лучшие БАДы для здоровья.\n"
        "Выберите действие 👇",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Админ-панель:", reply_markup=admin_menu())
    else:
        await message.answer("У вас нет прав администратора.")

@dp.message(F.text == "🏠 Главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню", reply_markup=main_menu())

@dp.message(F.text == "🛍 Каталог")
async def catalog(message: types.Message):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories")
    cats = cur.fetchall()
    conn.close()
    if not cats:
        await message.answer("Категории пока пусты. Добавьте через админ-панель.")
        return
    # Эмодзи для категорий
    cat_emoji = {"Омега": "🐟", "Витамины": "💊", "Для похудения": "🔥"}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{cat_emoji.get(name, '📁')} {name}", callback_data=f"cat_{cat_id}")] for cat_id, name in cats
    ])
    await message.answer("📋 *Выберите категорию:*", reply_markup=kb, parse_mode="Markdown")

# ---------- СПИСОК ТОВАРОВ (КНОПКИ ПО 2 В СТРОКЕ) ----------
@dp.callback_query(F.data.startswith("cat_"))
async def show_products(call: types.CallbackQuery):
    cat_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, price FROM products WHERE category_id=?", (cat_id,))
    products = cur.fetchall()
    conn.close()
    if not products:
        await call.message.answer("В этой категории пока нет товаров.")
        await call.answer()
        return
    keyboard = []
    for prod_id, name, price in products:
        button_text = f"💎 {name} — {price}₽"
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"detail_{prod_id}")])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_to_cats")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await call.message.edit_text("🏷 *Товары:*", reply_markup=reply_markup, parse_mode="Markdown")
    await call.answer()

# ---------- КАРТОЧКА ТОВАРА С ФОТО ----------
@dp.callback_query(F.data.startswith("detail_"))
async def show_product_detail(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT name, description, price, photo_file_id FROM products WHERE id=?", (product_id,))
    result = cur.fetchone()
    conn.close()
    if not result:
        await call.message.answer("Товар не найден.")
        await call.answer()
        return
    name, desc, price, photo_id = result
    text = f"✨ *{name}*\n\n📝 {desc}\n\n💰 Цена: *{price}₽*"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 В корзину", callback_data=f"add_{product_id}"),
         InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_cat_{call.message.chat.id}")]
    ])
    if photo_id:
        await call.message.answer_photo(photo=photo_id, caption=text, parse_mode="Markdown", reply_markup=kb)
    else:
        await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(call: types.CallbackQuery):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories")
    cats = cur.fetchall()
    conn.close()
    cat_emoji = {"Омега": "🐟", "Витамины": "💊", "Для похудения": "🔥"}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{cat_emoji.get(name, '📁')} {name}", callback_data=f"cat_{cat_id}")] for cat_id, name in cats
    ])
    await call.message.edit_text("📋 *Выберите категорию:*", reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("back_to_cat_"))
async def back_to_category(call: types.CallbackQuery):
    await call.message.delete()
    await catalog(call.message)
    await call.answer()

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1", (user_id, product_id))
    conn.commit()
    conn.close()
    await call.answer("Товар добавлен в корзину!", show_alert=True)

@dp.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT p.id, p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (user_id,))
    items = cur.fetchall()
    conn.close()
    if not items:
        await message.answer("Корзина пуста.")
        return
    text = "🛒 *Ваша корзина:*\n\n"
    total = 0
    for prod_id, name, price, qty in items:
        total += price * qty
        text += f"{name} x{qty} = {price*qty} руб.\n"
    text += f"\n*Итого: {total} руб.*"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout"),
         InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(call: types.CallbackQuery):
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text("Корзина очищена.")
    await call.answer()

@dp.callback_query(F.data == "checkout")
async def start_order(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите ваше имя:")
    await state.set_state(OrderForm.waiting_for_name)
    await call.answer()

@dp.message(OrderForm.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш номер телефона:")
    await state.set_state(OrderForm.waiting_for_phone)

@dp.message(OrderForm.waiting_for_phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Введите адрес доставки:")
    await state.set_state(OrderForm.waiting_for_address)

@dp.message(OrderForm.waiting_for_address)
async def get_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    data = await state.get_data()
    user_id = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (user_id,))
    items = cur.fetchall()
    total = sum(price * qty for _, price, qty in items)
    conn.close()
    if not items:
        await message.answer("Ваша корзина пуста. Начните заказ заново.")
        await state.clear()
        return
    text = f"📝 *Проверьте ваш заказ:*\nИмя: {data['name']}\nТелефон: {data['phone']}\nАдрес: {data['address']}\n\nТовары:\n"
    for name, price, qty in items:
        text += f"{name} x{qty} = {price*qty} руб.\n"
    text += f"\n*Итого: {total} руб.*\n\nПодтверждаете заказ?"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, подтверждаю", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_order")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await state.set_state(OrderForm.confirm)

@dp.callback_query(F.data == "confirm_order", OrderForm.confirm)
async def confirm_order(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (user_id,))
    items = cur.fetchall()
    total = sum(price * qty for _, price, qty in items)
    order_text = f"Пользователь: {data['name']}\nТелефон: {data['phone']}\nАдрес: {data['address']}\n\nТовары:\n"
    for name, price, qty in items:
        order_text += f"{name} x{qty} = {price*qty} руб.\n"
    order_text += f"\nИтого: {total} руб."
    cur.execute("INSERT INTO orders (user_id, order_data, total) VALUES (?, ?, ?)", (user_id, order_text, total))
    order_id = cur.lastrowid
    cur.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text("✅ Заказ оформлен! Наш менеджер свяжется с вами.")
    await bot.send_message(ADMIN_ID, f"🆕 *НОВЫЙ ЗАКАЗ №{order_id}*\n\n{order_text}", parse_mode="Markdown")
    await state.clear()
    await call.answer()

@dp.callback_query(F.data == "cancel_order", OrderForm.confirm)
async def cancel_order(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Оформление заказа отменено.")
    await state.clear()
    await call.answer()

# ----- ADMIN HANDLERS -----
@dp.message(F.text == "📋 Новые заказы")
async def new_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, order_data, total, created_at FROM orders WHERE status='новый' ORDER BY created_at DESC")
    orders = cur.fetchall()
    conn.close()
    if not orders:
        await message.answer("Новых заказов нет.")
        return
    for order_id, data, total, created in orders:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Пометить обработанным", callback_data=f"mark_done_{order_id}")]
        ])
        await message.answer(f"📦 Заказ #{order_id}\nВремя: {created}\n{data}\n\nСтатус: новый", reply_markup=kb)

@dp.callback_query(F.data.startswith("mark_done_"))
async def mark_order_done(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Нет прав", show_alert=True)
        return
    order_id = int(call.data.split("_")[2])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status='обработан' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text(f"Заказ #{order_id} помечен как обработанный.")
    await call.answer()

@dp.message(F.text == "➕ Добавить товар")
async def add_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите название товара:")
    await state.set_state(AddProduct.waiting_for_name)

@dp.message(AddProduct.waiting_for_name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара:")
    await state.set_state(AddProduct.waiting_for_description)

@dp.message(AddProduct.waiting_for_description)
async def add_product_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите цену в рублях (только число):")
    await state.set_state(AddProduct.waiting_for_price)

@dp.message(AddProduct.waiting_for_price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число!")
        return
    await state.update_data(price=int(message.text))
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories")
    cats = cur.fetchall()
    conn.close()
    if not cats:
        await message.answer("Нет категорий. Сначала создайте категорию через /add_category")
        await state.clear()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"setcat_{cat_id}")] for cat_id, name in cats
    ])
    await message.answer("Выберите категорию:", reply_markup=kb)
    await state.set_state(AddProduct.waiting_for_category)

@dp.callback_query(AddProduct.waiting_for_category, F.data.startswith("setcat_"))
async def add_product_category(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[1])
    await state.update_data(category_id=cat_id)
    await call.message.answer("Теперь отправьте фото товара (одно фото)")
    await state.set_state(AddProduct.waiting_for_photo)
    await call.answer()

@dp.message(AddProduct.waiting_for_photo, F.photo)
async def add_product_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO products (name, description, price, category_id, photo_file_id) VALUES (?, ?, ?, ?, ?)",
                (data['name'], data['description'], data['price'], data['category_id'], photo_id))
    conn.commit()
    conn.close()
    await message.answer("✅ Товар добавлен!")
    await state.clear()

@dp.message(Command("add_category"))
async def add_category_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /add_category Название категории")
        return
    cat_name = parts[1]
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
        conn.commit()
        await message.answer(f"Категория '{cat_name}' добавлена.")
    except sqlite3.IntegrityError:
        await message.answer("Такая категория уже существует.")
    finally:
        conn.close()

@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Пришлите текст сообщения для рассылки (можно с эмодзи).")
    @dp.message(F.text)
    async def send_broadcast(msg: types.Message):
        if msg.from_user.id != ADMIN_ID:
            return
        text = msg.text
        conn = sqlite3.connect("shop.db")
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT user_id FROM cart UNION SELECT user_id FROM orders")
        users = cur.fetchall()
        conn.close()
        count = 0
        for (user_id,) in users:
            try:
                await bot.send_message(user_id, text)
                count += 1
            except:
                pass
        await msg.answer(f"Рассылка завершена. Отправлено {count} пользователям.")
        dp.message.handlers.pop()

@dp.message(F.text == "💬 Контакты")
async def contacts(message: types.Message):
    await message.answer(
        "📱 *Наши контакты:*\n\n"
        "💬 Telegram: @ваш_ник\n"
        "📞 Телефон: +7 999 123-45-67\n"
        "🕐 Работаем: 9:00 – 21:00",
        parse_mode="Markdown"
    )

@dp.message(F.text == "ℹ️ О нас")
async def about_us(message: types.Message):
    await message.answer(
        "🌿 *О нашем магазине*\n\n"
        "Мы предлагаем только качественные БАДы\n"
        "от проверенных производителей.\n\n"
        "✅ Сертифицированная продукция\n"
        "🚚 Доставка по всей России\n"
        "💬 Бесплатная консультация",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📊 Статистика")
async def statistics(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='новый'")
    new_orders_count = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(total), 0) FROM orders")
    total_revenue = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]
    conn.close()
    await message.answer(
        "📊 *Статистика магазина*\n\n"
        f"📦 Всего заказов: *{total_orders}*\n"
        f"🆕 Новых: *{new_orders_count}*\n"
        f"💰 Выручка: *{total_revenue}₽*\n"
        f"🏷 Товаров: *{total_products}*",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📦 Мои заказы")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, order_data, total, status, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    orders = cur.fetchall()
    conn.close()
    if not orders:
        await message.answer("У вас пока нет заказов.")
        return
    text = "📋 *Ваши заказы:*\n\n"
    for order_id, data, total, status, created in orders:
        text += f"Заказ #{order_id} от {created}\nСтатус: {status}\n{data}\n\n---\n"
    await message.answer(text[:4000], parse_mode="Markdown")

# ----- RUN -----
async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())