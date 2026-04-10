import asyncio
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import aiohttp
from aiogram.client.session.aiohttp import AiohttpSession

BOT_TOKEN = "8615838083:AAHQM2oyQDMkNMi4yqdSBBQeJ30OWeNDL7c"
ADMIN_ID = 6175936997
MANAGER_USERNAME = "X822MX"
PROXY_URL = ""

if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL, timeout=aiohttp.ClientTimeout(total=60))
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(storage=MemoryStorage())

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
    cur.execute("""CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER,
        product_id INTEGER,
        PRIMARY KEY (user_id, product_id))""")
    conn.commit()
    conn.close()
init_db()

def force_categories():
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        for cat in ["Омега", "Витамины", "Для похудения"]:
            try:
                cur.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    conn.close()
force_categories()

CAT_EMOJI = {"Омега": "🐟", "Витамины": "💊", "Для похудения": "🔥"}

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

class SearchState(StatesGroup):
    waiting_for_query = State()

class BroadcastState(StatesGroup):
    waiting_for_text = State()

def main_menu():
    kb = [
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🔍 Поиск")],
        [KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="❤️ Избранное")],
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="💬 Менеджер")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    kb = [
        [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="🗑 Удалить товар")],
        [KeyboardButton(text="📋 Заказы"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🏠 Меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ══════ START ══════
@dp.message(Command("start"))
async def start(message: types.Message):
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"Hey, {name}! 👋\n\n"
        "Добро пожаловать в Radiance\u200b.fit ✨\n\n"
        "Здесь ты найдёшь лучшие добавки\n"
        "для здоровья и энергии 💪\n\n"
        "Жми кнопки снизу 👇",
        reply_markup=main_menu()
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("⚙️ Админка", reply_markup=admin_menu())

@dp.message(F.text == "🏠 Меню")
async def back_to_main(message: types.Message):
    await message.answer("Radiance\u200b.fit ✨", reply_markup=main_menu())

# ══════ CATALOG ══════
@dp.message(F.text == "🛍 Каталог")
async def catalog(message: types.Message):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories")
    cats = cur.fetchall()
    buttons = []
    for cat_id, name in cats:
        emoji = CAT_EMOJI.get(name, "📁")
        cur.execute("SELECT COUNT(*) FROM products WHERE category_id=?", (cat_id,))
        count = cur.fetchone()[0]
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {name} ({count})",
            callback_data=f"cat_{cat_id}"
        )])
    conn.close()
    if not buttons:
        await message.answer("Каталог пока пуст 😔")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбирай категорию 👇", reply_markup=kb)

@dp.callback_query(F.data.startswith("cat_"))
async def show_products(call: types.CallbackQuery):
    cat_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat_row = cur.fetchone()
    cat_name = cat_row[0] if cat_row else "Товары"
    cur.execute("SELECT id, name, price FROM products WHERE category_id=?", (cat_id,))
    products = cur.fetchall()
    conn.close()
    if not products:
        await call.message.answer("Тут пока пусто 🤷‍♂️")
        await call.answer()
        return
    emoji = CAT_EMOJI.get(cat_name, "📁")
    keyboard = []
    for prod_id, name, price in products:
        price_fmt = f"{price:,}".replace(",", " ")
        keyboard.append([InlineKeyboardButton(
            text=f"{name} • {price_fmt}₽",
            callback_data=f"detail_{prod_id}"
        )])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cats")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await call.message.edit_text(f"{emoji} {cat_name}", reply_markup=reply_markup)
    await call.answer()

@dp.callback_query(F.data.startswith("detail_"))
async def show_product_detail(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT name, description, price, photo_file_id, category_id FROM products WHERE id=?", (product_id,))
    result = cur.fetchone()
    cur.execute("SELECT 1 FROM favorites WHERE user_id=? AND product_id=?", (user_id, product_id))
    is_fav = cur.fetchone() is not None
    conn.close()
    if not result:
        await call.answer("Товар не найден 😕")
        return
    name, desc, price, photo_id, cat_id = result
    price_fmt = f"{price:,}".replace(",", " ")
    text = f"✨ {name}\n\n{desc}\n\n💰 {price_fmt} ₽"
    fav_btn = "❤️" if is_fav else "🤍"
    fav_data = f"unfav_{product_id}" if is_fav else f"fav_{product_id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 В корзину", callback_data=f"add_{product_id}"),
            InlineKeyboardButton(text=fav_btn, callback_data=fav_data)
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_{cat_id}")]
    ])
    if photo_id:
        await call.message.answer_photo(photo=photo_id, caption=text, reply_markup=kb)
    else:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(call: types.CallbackQuery):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories")
    cats = cur.fetchall()
    buttons = []
    for cat_id, name in cats:
        emoji = CAT_EMOJI.get(name, "📁")
        cur.execute("SELECT COUNT(*) FROM products WHERE category_id=?", (cat_id,))
        count = cur.fetchone()[0]
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {name} ({count})",
            callback_data=f"cat_{cat_id}"
        )])
    conn.close()
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.edit_text("Выбирай категорию 👇", reply_markup=kb)
    await call.answer()

# ══════ CART ══════
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1", (user_id, product_id))
    conn.commit()
    conn.close()
    await call.answer("Добавлено ✅", show_alert=False)

@dp.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT p.id, p.name, p.price, c.quantity FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (user_id,))
    items = cur.fetchall()
    conn.close()
    if not items:
        await message.answer("Корзина пустая 🛒\n\nЗагляни в каталог!")
        return
    text = "🛒 Твоя корзина:\n\n"
    total = 0
    buttons = []
    for prod_id, name, price, qty in items:
        subtotal = price * qty
        total += subtotal
        sub_fmt = f"{subtotal:,}".replace(",", " ")
        text += f"  {name}  x{qty}  →  {sub_fmt}₽\n"
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"cartminus_{prod_id}"),
            InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cartplus_{prod_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"cartdel_{prod_id}")
        ])
    total_fmt = f"{total:,}".replace(",", " ")
    text += f"\n💰 Итого: {total_fmt}₽"
    buttons.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    buttons.append([InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("cartplus_"))
async def cart_plus(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id=? AND product_id=?", (user_id, product_id))
    conn.commit()
    conn.close()
    await call.answer("✅")
    await call.message.delete()
    fake_msg = call.message
    fake_msg.from_user = call.from_user
    await show_cart(fake_msg)

@dp.callback_query(F.data.startswith("cartminus_"))
async def cart_minus(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (user_id, product_id))
    row = cur.fetchone()
    if row and row[0] > 1:
        cur.execute("UPDATE cart SET quantity = quantity - 1 WHERE user_id=? AND product_id=?", (user_id, product_id))
    else:
        cur.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, product_id))
    conn.commit()
    conn.close()
    await call.answer("✅")
    await call.message.delete()
    fake_msg = call.message
    fake_msg.from_user = call.from_user
    await show_cart(fake_msg)

@dp.callback_query(F.data.startswith("cartdel_"))
async def cart_delete_item(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (user_id, product_id))
    conn.commit()
    conn.close()
    await call.answer("Удалено 🗑")
    await call.message.delete()
    fake_msg = call.message
    fake_msg.from_user = call.from_user
    await show_cart(fake_msg)

@dp.callback_query(F.data == "noop")
async def noop(call: types.CallbackQuery):
    await call.answer()

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(call: types.CallbackQuery):
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text("Корзина очищена 🧹")
    await call.answer()

# ══════ CHECKOUT ══════
@dp.callback_query(F.data == "checkout")
async def start_order(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📝 Как тебя зовут?")
    await state.set_state(OrderForm.waiting_for_name)
    await call.answer()

@dp.message(OrderForm.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📱 Номер телефона?")
    await state.set_state(OrderForm.waiting_for_phone)

@dp.message(OrderForm.waiting_for_phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("📍 Адрес доставки?")
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
        await message.answer("Корзина пуста 😕")
        await state.clear()
        return
    total_fmt = f"{total:,}".replace(",", " ")
    text = (
        f"📋 Проверь заказ:\n\n"
        f"👤 {data['name']}\n"
        f"📱 {data['phone']}\n"
        f"📍 {data['address']}\n\n"
    )
    for name, price, qty in items:
        s = f"{price*qty:,}".replace(",", " ")
        text += f"  {name} x{qty} → {s}₽\n"
    text += f"\n💰 Итого: {total_fmt}₽\n\nВсё верно?"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="confirm_order"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel_order")
        ]
    ])
    await message.answer(text, reply_markup=kb)
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
    order_text = f"👤 {data['name']}\n📱 {data['phone']}\n📍 {data['address']}\n\n"
    for name, price, qty in items:
        order_text += f"{name} x{qty} = {price*qty}₽\n"
    order_text += f"\n💰 Итого: {total}₽"
    cur.execute("INSERT INTO orders (user_id, order_data, total) VALUES (?, ?, ?)", (user_id, order_text, total))
    order_id = cur.lastrowid
    cur.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text(
        f"🎉 Заказ #{order_id} оформлен!\n\n"
        "Менеджер скоро свяжется с тобой 📞"
    )
    await bot.send_message(ADMIN_ID, f"🔔 Новый заказ #{order_id}\n\n{order_text}\n\nUser ID: {user_id}")
    await state.clear()
    await call.answer()

@dp.callback_query(F.data == "cancel_order", OrderForm.confirm)
async def cancel_order(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Отменено ✖️")
    await state.clear()
    await call.answer()

# ══════ FAVORITES ══════
@dp.callback_query(F.data.startswith("fav_"))
async def add_favorite(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO favorites (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    await call.answer("Добавлено в избранное ❤️", show_alert=False)

@dp.callback_query(F.data.startswith("unfav_"))
async def remove_favorite(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM favorites WHERE user_id=? AND product_id=?", (user_id, product_id))
    conn.commit()
    conn.close()
    await call.answer("Убрано 💔", show_alert=False)

@dp.message(F.text == "❤️ Избранное")
async def show_favorites(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT p.id, p.name, p.price FROM favorites f JOIN products p ON f.product_id = p.id WHERE f.user_id=?", (user_id,))
    items = cur.fetchall()
    conn.close()
    if not items:
        await message.answer("Пока пусто 🤍\n\nНажми 🤍 на товаре чтобы сохранить!")
        return
    keyboard = []
    for prod_id, name, price in items:
        price_fmt = f"{price:,}".replace(",", " ")
        keyboard.append([InlineKeyboardButton(
            text=f"❤️ {name} • {price_fmt}₽",
            callback_data=f"detail_{prod_id}"
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("Твоё избранное ❤️", reply_markup=kb)

# ══════ SEARCH ══════
@dp.message(F.text == "🔍 Поиск")
async def search_start(message: types.Message, state: FSMContext):
    await message.answer("🔍 Что ищешь? Напиши название:")
    await state.set_state(SearchState.waiting_for_query)

@dp.message(SearchState.waiting_for_query)
async def search_results(message: types.Message, state: FSMContext):
    query = message.text.lower()
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, price FROM products WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?",
                (f"%{query}%", f"%{query}%"))
    results = cur.fetchall()
    conn.close()
    await state.clear()
    if not results:
        await message.answer(f"Ничего не нашлось по «{message.text}» 😕\n\nПопробуй другой запрос!")
        return
    keyboard = []
    for prod_id, name, price in results:
        price_fmt = f"{price:,}".replace(",", " ")
        keyboard.append([InlineKeyboardButton(
            text=f"{name} • {price_fmt}₽",
            callback_data=f"detail_{prod_id}"
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(f"Нашлось {len(results)} 🔎", reply_markup=kb)

# ══════ MANAGER ══════
@dp.message(F.text == "💬 Менеджер")
async def contact_manager(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{MANAGER_USERNAME}")]
    ])
    await message.answer(
        "Наш менеджер поможет с:\n\n"
        "💊 Подбором добавок\n"
        "📦 Вопросами по заказу\n"
        "🤝 Персональной консультацией",
        reply_markup=kb
    )

# ══════ MY ORDERS ══════
@dp.message(F.text == "📦 Мои заказы")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, total, status, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (user_id,))
    orders = cur.fetchall()
    conn.close()
    if not orders:
        await message.answer("Заказов пока нет 📦\n\nВремя это исправить! 😉")
        return
    status_emoji = {"новый": "⏳", "собран": "📦", "отправлен": "🚚", "доставлен": "✅", "отменён": "❌"}
    text = "Твои заказы 📦\n\n"
    for order_id, total, status, created in orders:
        emoji = status_emoji.get(status, "📦")
        total_fmt = f"{total:,}".replace(",", " ")
        text += f"{emoji} #{order_id} • {total_fmt}₽ • {status}\n"
    await message.answer(text)

# ══════ ADMIN ══════
@dp.message(F.text == "📋 Заказы")
async def admin_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, order_data, total, created_at FROM orders WHERE status='новый' ORDER BY created_at DESC")
    orders = cur.fetchall()
    conn.close()
    if not orders:
        await message.answer("Новых заказов нет 👌")
        return
    for order_id, data, total, created in orders:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 Собран", callback_data=f"status_собран_{order_id}"),
                InlineKeyboardButton(text="🚚 Отправлен", callback_data=f"status_отправлен_{order_id}")
            ],
            [
                InlineKeyboardButton(text="✅ Доставлен", callback_data=f"status_доставлен_{order_id}"),
                InlineKeyboardButton(text="❌ Отменён", callback_data=f"status_отменён_{order_id}")
            ]
        ])
        await message.answer(f"🔔 Заказ #{order_id}\n{created}\n\n{data}", reply_markup=kb)

STATUS_MESSAGES = {
    "собран": "📦 Ваш заказ #{order_id} собран и готовится к отправке!",
    "отправлен": "🚚 Ваш заказ #{order_id} отправлен! Скоро будет у вас 🎉",
    "доставлен": "✅ Ваш заказ #{order_id} доставлен! Спасибо за покупку ❤️\n\nЕсли есть вопросы — пишите менеджеру 💬",
    "отменён": "❌ Ваш заказ #{order_id} отменён.\n\nЕсли это ошибка — свяжитесь с менеджером 💬",
}

@dp.callback_query(F.data.startswith("status_"))
async def change_order_status(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    parts = call.data.split("_")
    new_status = parts[1]
    order_id = int(parts[2])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
    conn.commit()
    conn.close()
    status_emoji = {"собран": "📦", "отправлен": "🚚", "доставлен": "✅", "отменён": "❌"}
    emoji = status_emoji.get(new_status, "📦")
    await call.message.edit_text(f"{emoji} Заказ #{order_id} → {new_status}")
    # Уведомление клиенту
    if row:
        user_id = row[0]
        msg = STATUS_MESSAGES.get(new_status, "").format(order_id=order_id)
        if msg:
            try:
                await bot.send_message(user_id, msg)
            except:
                pass
    await call.answer(f"Статус обновлён: {new_status}")

@dp.message(F.text == "➕ Добавить товар")
async def add_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Название товара:")
    await state.set_state(AddProduct.waiting_for_name)

@dp.message(AddProduct.waiting_for_name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Описание:")
    await state.set_state(AddProduct.waiting_for_description)

@dp.message(AddProduct.waiting_for_description)
async def add_product_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Цена (число):")
    await state.set_state(AddProduct.waiting_for_price)

@dp.message(AddProduct.waiting_for_price)
async def add_product_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи число!")
        return
    await state.update_data(price=int(message.text))
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories")
    cats = cur.fetchall()
    conn.close()
    if not cats:
        await message.answer("Нет категорий. /add_category Название")
        await state.clear()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{CAT_EMOJI.get(n, '📁')} {n}", callback_data=f"setcat_{c}")] for c, n in cats
    ])
    await message.answer("Категория:", reply_markup=kb)
    await state.set_state(AddProduct.waiting_for_category)

@dp.callback_query(AddProduct.waiting_for_category, F.data.startswith("setcat_"))
async def add_product_category(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[1])
    await state.update_data(category_id=cat_id)
    await call.message.answer("📸 Скинь фото товара:")
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
    await message.answer("Товар добавлен ✅")
    await state.clear()

@dp.message(F.text == "🗑 Удалить товар")
async def delete_product_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, price FROM products")
    products = cur.fetchall()
    conn.close()
    if not products:
        await message.answer("Товаров нет")
        return
    keyboard = []
    for prod_id, name, price in products:
        keyboard.append([InlineKeyboardButton(text=f"❌ {name} • {price}₽", callback_data=f"delprod_{prod_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("Что удалить?", reply_markup=kb)

@dp.callback_query(F.data.startswith("delprod_"))
async def delete_product(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    product_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (product_id,))
    cur.execute("DELETE FROM cart WHERE product_id=?", (product_id,))
    cur.execute("DELETE FROM favorites WHERE product_id=?", (product_id,))
    conn.commit()
    conn.close()
    await call.message.edit_text("Удалено 🗑")
    await call.answer()

@dp.message(Command("add_category"))
async def add_category_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /add_category Название")
        return
    cat_name = parts[1]
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
        conn.commit()
        await message.answer(f"Категория «{cat_name}» добавлена ✅")
    except sqlite3.IntegrityError:
        await message.answer("Такая уже есть 🤷‍♂️")
    finally:
        conn.close()

@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Напиши текст рассылки:")
    await state.set_state(BroadcastState.waiting_for_text)

@dp.message(BroadcastState.waiting_for_text)
async def send_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT user_id FROM cart UNION SELECT DISTINCT user_id FROM orders")
    users = cur.fetchall()
    conn.close()
    count = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, text)
            count += 1
        except:
            pass
    await message.answer(f"Отправлено: {count} 📨")
    await state.clear()

@dp.message(F.text == "📊 Статистика")
async def statistics(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='новый'")
    new_count = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(total), 0) FROM orders")
    revenue = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    prod_count = cur.fetchone()[0]
    conn.close()
    rev_fmt = f"{revenue:,}".replace(",", " ")
    await message.answer(
        f"📊 Статистика\n\n"
        f"📦 Заказов: {total_orders}\n"
        f"🆕 Новых: {new_count}\n"
        f"💰 Выручка: {rev_fmt}₽\n"
        f"🏷 Товаров: {prod_count}"
    )

async def main():
    print("✨ Radiance.fit bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
