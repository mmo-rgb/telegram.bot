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

# ========== CONFIG ==========
BOT_TOKEN = "8615838083:AAHQM2oyQDMkNMi4yqdSBBQeJ30OWeNDL7c"
ADMIN_ID = 6175936997
MANAGER = "@radiancefit"
ADMIN_USERNAMES = ["radiancefit", "trapmentality1"]
PROXY_URL = ""
# =============================

if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL, timeout=aiohttp.ClientTimeout(total=60))
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(storage=MemoryStorage())

# ═══════════════════════════════════════
#                DATABASE
# ═══════════════════════════════════════
def init_db():
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        emoji TEXT DEFAULT '✦')""")
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
    cur.execute("""CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER,
        product_id INTEGER,
        PRIMARY KEY (user_id, product_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        order_data TEXT,
        total INTEGER,
        status TEXT DEFAULT 'новый',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    try:
        cur.execute("ALTER TABLE categories ADD COLUMN emoji TEXT DEFAULT '✦'")
    except:
        pass
    conn.commit()
    conn.close()

init_db()

def setup_default_categories():
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        cats = [("Коллагены", "✨"), ("БАДы", "💎"), ("Для похудения", "🍃"), ("Крема", "🧴")]
        for name, emoji in cats:
            cur.execute("INSERT OR IGNORE INTO categories (name, emoji) VALUES (?, ?)", (name, emoji))
        conn.commit()
    conn.close()

setup_default_categories()

def save_user(user):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user.id, user.username, user.first_name))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════
#              FSM STATES
# ═══════════════════════════════════════
class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    category = State()
    photo = State()

class OrderForm(StatesGroup):
    name = State()
    phone = State()
    address = State()
    confirm = State()

class BroadcastForm(StatesGroup):
    text = State()

class SearchForm(StatesGroup):
    query = State()

# ═══════════════════════════════════════
#              KEYBOARDS
# ═══════════════════════════════════════
def main_menu():
    kb = [
        [KeyboardButton(text="🪩 Каталог"), KeyboardButton(text="🔍 Поиск")],
        [KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="❤️ Избранное")],
        [KeyboardButton(text="🧾 Мои заказы"), KeyboardButton(text="✉️ Менеджер")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    kb = [
        [KeyboardButton(text="＋ Добавить товар"), KeyboardButton(text="✕ Удалить товар")],
        [KeyboardButton(text="🗂 Заказы"), KeyboardButton(text="📈 Статистика")],
        [KeyboardButton(text="📣 Рассылка"), KeyboardButton(text="↩️ На главную")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def fmt_price(n):
    return f"{n:,}".replace(",", " ")

# ═══════════════════════════════════════
#            MAIN HANDLERS
# ═══════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(message.from_user)
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"hey, {name} 👋\n\n"
        f"добро пожаловать в Radiance.fit ✨\n"
        f"здесь только топовые БАДы для твоего здоровья\n\n"
        f"жми кнопки внизу 👇",
        reply_markup=main_menu()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id == ADMIN_ID or (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        await message.answer("🔐 Админка:", reply_markup=admin_menu())

@dp.message(F.text == "↩️ На главную")
async def go_home(message: types.Message):
    await message.answer("🏠", reply_markup=main_menu())

# ═══════════════════════════════════════
#              CATALOG
# ═══════════════════════════════════════

@dp.message(F.text == "🪩 Каталог")
async def catalog(message: types.Message):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""SELECT c.id, c.name, c.emoji, COUNT(p.id)
                   FROM categories c LEFT JOIN products p ON p.category_id = c.id
                   GROUP BY c.id""")
    cats = cur.fetchall()
    conn.close()
    if not cats:
        await message.answer("пока пусто, скоро добавим 🫶")
        return
    buttons = []
    for cat_id, name, emoji, count in cats:
        e = emoji or "✦"
        buttons.append([InlineKeyboardButton(
            text=f"{e} {name}  •  {count} шт",
            callback_data=f"cat_{cat_id}"
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("выбирай категорию 👇", reply_markup=kb)

@dp.callback_query(F.data.startswith("cat_"))
async def show_category(call: types.CallbackQuery):
    cat_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat = cur.fetchone()
    cur.execute("SELECT id, name, price FROM products WHERE category_id=?", (cat_id,))
    products = cur.fetchall()
    conn.close()
    if not products:
        await call.answer("тут пока пусто 😅", show_alert=True)
        return
    cat_name = cat[0] if cat else "Товары"
    buttons = []
    for pid, name, price in products:
        buttons.append([InlineKeyboardButton(
            text=f"{name}  —  {fmt_price(price)}₽",
            callback_data=f"prod_{pid}"
        )])
    buttons.append([InlineKeyboardButton(text="‹ назад", callback_data="back_cats")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await call.message.edit_text(cat_name, reply_markup=kb)
    except:
        await call.message.answer(cat_name, reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "back_cats")
async def back_to_cats(call: types.CallbackQuery):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""SELECT c.id, c.name, c.emoji, COUNT(p.id)
                   FROM categories c LEFT JOIN products p ON p.category_id = c.id
                   GROUP BY c.id""")
    cats = cur.fetchall()
    conn.close()
    buttons = []
    for cat_id, name, emoji, count in cats:
        e = emoji or "✦"
        buttons.append([InlineKeyboardButton(
            text=f"{e} {name}  •  {count} шт",
            callback_data=f"cat_{cat_id}"
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await call.message.edit_text("выбирай категорию 👇", reply_markup=kb)
    except:
        pass
    await call.answer()

# ═══════════════════════════════════════
#           PRODUCT DETAIL
# ═══════════════════════════════════════

def product_kb(product_id, user_id, qty=1):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM favorites WHERE user_id=? AND product_id=?", (user_id, product_id))
    is_fav = cur.fetchone() is not None
    cur.execute("SELECT category_id FROM products WHERE id=?", (product_id,))
    row = cur.fetchone()
    cat_id = row[0] if row else 0
    conn.close()

    fav_text = "❤️" if is_fav else "🤍"
    buttons = [
        [
            InlineKeyboardButton(text="➖", callback_data=f"qty_{product_id}_m_{qty}"),
            InlineKeyboardButton(text=f"  {qty} шт  ", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"qty_{product_id}_p_{qty}"),
        ],
        [
            InlineKeyboardButton(text=f"🛒 в корзину", callback_data=f"addcart_{product_id}_{qty}"),
            InlineKeyboardButton(text=fav_text, callback_data=f"fav_{product_id}"),
        ],
        [InlineKeyboardButton(text="‹ назад", callback_data=f"cat_{cat_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def product_text(name, desc, price):
    return f"✨ {name}\n\n{desc or ''}\n\n💰 {fmt_price(price)}₽"

@dp.callback_query(F.data.startswith("prod_"))
async def show_product(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT name, description, price, photo_file_id FROM products WHERE id=?", (product_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        await call.answer("не найден 😢", show_alert=True)
        return
    name, desc, price, photo_id = row
    text = product_text(name, desc, price)
    kb = product_kb(product_id, call.from_user.id, qty=1)
    try:
        await call.message.delete()
    except:
        pass
    if photo_id:
        await call.message.answer_photo(photo=photo_id, caption=text, reply_markup=kb)
    else:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data.startswith("qty_"))
async def change_qty(call: types.CallbackQuery):
    parts = call.data.split("_")
    product_id = int(parts[1])
    action = parts[2]
    current_qty = int(parts[3])

    new_qty = min(current_qty + 1, 99) if action == "p" else max(current_qty - 1, 1)
    if new_qty == current_qty:
        await call.answer()
        return

    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT name, description, price, photo_file_id FROM products WHERE id=?", (product_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        await call.answer()
        return

    name, desc, price, photo_id = row
    text = product_text(name, desc, price)
    kb = product_kb(product_id, call.from_user.id, qty=new_qty)
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=text, reply_markup=kb)
        else:
            await call.message.edit_text(text, reply_markup=kb)
    except:
        pass
    await call.answer()

@dp.callback_query(F.data == "noop")
async def noop(call: types.CallbackQuery):
    await call.answer()

# ═══════════════════════════════════════
#              FAVORITES
# ═══════════════════════════════════════

@dp.callback_query(F.data.startswith("fav_"))
async def toggle_fav(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    uid = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM favorites WHERE user_id=? AND product_id=?", (uid, product_id))
    if cur.fetchone():
        cur.execute("DELETE FROM favorites WHERE user_id=? AND product_id=?", (uid, product_id))
        msg = "убрано из избранного"
    else:
        cur.execute("INSERT INTO favorites (user_id, product_id) VALUES (?, ?)", (uid, product_id))
        msg = "❤️ добавлено"
    conn.commit()
    conn.close()

    qty = 1
    if call.message.reply_markup:
        for row in call.message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("addcart_"):
                    qty = int(btn.callback_data.split("_")[2])

    kb = product_kb(product_id, uid, qty)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except:
        pass
    await call.answer(msg)

@dp.message(F.text == "❤️ Избранное")
async def show_favorites(message: types.Message):
    uid = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""SELECT p.id, p.name, p.price FROM favorites f
                   JOIN products p ON f.product_id = p.id
                   WHERE f.user_id=?""", (uid,))
    items = cur.fetchall()
    conn.close()
    if not items:
        await message.answer("тут пока пусто\nдобавляй через 🤍 на карточке товара")
        return
    buttons = []
    for pid, name, price in items:
        buttons.append([InlineKeyboardButton(
            text=f"❤️ {name}  —  {fmt_price(price)}₽",
            callback_data=f"prod_{pid}"
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("твоё избранное ❤️", reply_markup=kb)

# ═══════════════════════════════════════
#            CART + QUANTITY
# ═══════════════════════════════════════

@dp.callback_query(F.data.startswith("addcart_"))
async def add_to_cart(call: types.CallbackQuery):
    parts = call.data.split("_")
    product_id = int(parts[1])
    qty = int(parts[2])
    uid = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + ?""",
                (uid, product_id, qty, qty))
    conn.commit()
    conn.close()
    await call.answer(f"✅ {qty} шт добавлено в корзину!", show_alert=True)

@dp.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    await render_cart(message, message.from_user.id)

async def render_cart(target, uid, edit=False):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""SELECT p.id, p.name, p.price, c.quantity
                   FROM cart c JOIN products p ON c.product_id = p.id
                   WHERE c.user_id=?""", (uid,))
    items = cur.fetchall()
    conn.close()
    if not items:
        txt = "корзина пуста 🫠"
        if edit:
            try: await target.edit_text(txt)
            except: pass
        else:
            await target.answer(txt)
        return

    text = "🛒 твоя корзина:\n\n"
    total = 0
    buttons = []
    for pid, name, price, qty in items:
        sub = price * qty
        total += sub
        text += f"▸ {name} × {qty} = {fmt_price(sub)}₽\n"
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"cm_{pid}"),
            InlineKeyboardButton(text=f"{name} ({qty})", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cp_{pid}"),
            InlineKeyboardButton(text="🗑", callback_data=f"cd_{pid}"),
        ])

    text += f"\nитого: {fmt_price(total)}₽"
    buttons.append([InlineKeyboardButton(text=f"✅ оформить  •  {fmt_price(total)}₽", callback_data="checkout")])
    buttons.append([InlineKeyboardButton(text="🗑 очистить", callback_data="clear_cart")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: pass
    else:
        await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("cp_"))
async def cart_plus(call: types.CallbackQuery):
    pid = int(call.data.split("_")[1])
    uid = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE cart SET quantity = MIN(quantity + 1, 99) WHERE user_id=? AND product_id=?", (uid, pid))
    conn.commit()
    conn.close()
    await render_cart(call.message, uid, edit=True)
    await call.answer()

@dp.callback_query(F.data.startswith("cm_"))
async def cart_minus(call: types.CallbackQuery):
    pid = int(call.data.split("_")[1])
    uid = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT quantity FROM cart WHERE user_id=? AND product_id=?", (uid, pid))
    row = cur.fetchone()
    if row and row[0] <= 1:
        cur.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, pid))
    else:
        cur.execute("UPDATE cart SET quantity = quantity - 1 WHERE user_id=? AND product_id=?", (uid, pid))
    conn.commit()
    conn.close()
    await render_cart(call.message, uid, edit=True)
    await call.answer()

@dp.callback_query(F.data.startswith("cd_"))
async def cart_del(call: types.CallbackQuery):
    pid = int(call.data.split("_")[1])
    uid = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (uid, pid))
    conn.commit()
    conn.close()
    await render_cart(call.message, uid, edit=True)
    await call.answer("удалено 🗑")

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(call: types.CallbackQuery):
    uid = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    try: await call.message.edit_text("корзина очищена 🫧")
    except: pass
    await call.answer()

# ═══════════════════════════════════════
#              SEARCH
# ═══════════════════════════════════════

@dp.message(F.text == "🔍 Поиск")
async def search_start(message: types.Message, state: FSMContext):
    await message.answer("что ищешь? 🔍")
    await state.set_state(SearchForm.query)

@dp.message(SearchForm.query)
async def search_results(message: types.Message, state: FSMContext):
    q = f"%{message.text}%"
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, price FROM products WHERE name LIKE ? OR description LIKE ?", (q, q))
    items = cur.fetchall()
    conn.close()
    await state.clear()
    if not items:
        await message.answer("ничего не нашлось 😅")
        return
    buttons = []
    for pid, name, price in items:
        buttons.append([InlineKeyboardButton(text=f"{name} — {fmt_price(price)}₽", callback_data=f"prod_{pid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(f"нашлось {len(items)} 👇", reply_markup=kb)

# ═══════════════════════════════════════
#            CHECKOUT / ORDER
# ═══════════════════════════════════════

@dp.callback_query(F.data == "checkout")
async def checkout_start(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cart WHERE user_id=?", (uid,))
    if cur.fetchone()[0] == 0:
        await call.answer("корзина пуста!", show_alert=True)
        conn.close()
        return
    conn.close()
    await call.message.answer("📝 оформляем заказ\n\nкак тебя зовут?")
    await state.set_state(OrderForm.name)
    await call.answer()

@dp.message(OrderForm.name)
async def order_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📱 номер телефона")
    await state.set_state(OrderForm.phone)

@dp.message(OrderForm.phone)
async def order_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("📍 адрес доставки")
    await state.set_state(OrderForm.address)

@dp.message(OrderForm.address)
async def order_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    data = await state.get_data()
    uid = message.from_user.id

    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""SELECT p.name, p.price, c.quantity FROM cart c
                   JOIN products p ON c.product_id = p.id WHERE c.user_id=?""", (uid,))
    items = cur.fetchall()
    conn.close()

    if not items:
        await message.answer("корзина пуста 😅")
        await state.clear()
        return

    total = sum(p * q for _, p, q in items)
    text = f"📝 проверь заказ:\n\n👤 {data['name']}\n📱 {data['phone']}\n📍 {data['address']}\n\n"
    for name, price, qty in items:
        text += f"▸ {name} × {qty} = {fmt_price(price*qty)}₽\n"
    text += f"\nитого: {fmt_price(total)}₽\n\nвсё верно?"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ да, оформить", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ отмена", callback_data="cancel_order")],
    ])
    await message.answer(text, reply_markup=kb)
    await state.set_state(OrderForm.confirm)

@dp.callback_query(F.data == "confirm_order", OrderForm.confirm)
async def confirm_order(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = call.from_user.id

    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""SELECT p.name, p.price, c.quantity FROM cart c
                   JOIN products p ON c.product_id = p.id WHERE c.user_id=?""", (uid,))
    items = cur.fetchall()
    total = sum(p * q for _, p, q in items)

    order_text = f"👤 {data['name']}\n📱 {data['phone']}\n📍 {data['address']}\n\n"
    for name, price, qty in items:
        order_text += f"{name} × {qty} = {price*qty}₽\n"
    order_text += f"\nИтого: {total}₽"

    cur.execute("INSERT INTO orders (user_id, order_data, total) VALUES (?, ?, ?)", (uid, order_text, total))
    order_id = cur.lastrowid
    cur.execute("DELETE FROM cart WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

    await call.message.edit_text(
        f"✅ заказ №{order_id} оформлен!\n\n"
        f"менеджер скоро свяжется 🤝\n"
        f"или напиши сам: {MANAGER}"
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🔔 НОВЫЙ ЗАКАЗ №{order_id}\n\n{order_text}\n\n@{call.from_user.username or 'без ника'}"
        )
    except:
        pass
    await state.clear()
    await call.answer()

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("отменено, товары в корзине 👌")
    await state.clear()
    await call.answer()

# ═══════════════════════════════════════
#             MY ORDERS
# ═══════════════════════════════════════

STATUS_EMOJI = {"новый": "🆕", "собран": "📦", "отправлен": "🚚", "доставлен": "✅", "отменён": "❌", "обработан": "✅"}

@dp.message(F.text == "🧾 Мои заказы")
async def my_orders(message: types.Message):
    uid = message.from_user.id
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, total, status, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (uid,))
    orders = cur.fetchall()
    conn.close()
    if not orders:
        await message.answer("пока нет заказов 🛍")
        return
    text = "📦 твои заказы:\n\n"
    for oid, total, status, created in orders:
        e = STATUS_EMOJI.get(status, "❓")
        text += f"{e} №{oid}  •  {fmt_price(total)}₽  •  {status}\n"
    await message.answer(text)

# ═══════════════════════════════════════
#             CONTACTS
# ═══════════════════════════════════════

@dp.message(F.text == "✉️ Менеджер")
async def contact_manager(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 написать менеджеру", url=f"https://t.me/{MANAGER.replace('@', '')}")]
    ])
    await message.answer("наш менеджер на связи 🤝\nответит в течение часа", reply_markup=kb)

# ═══════════════════════════════════════
#          ADMIN — ORDERS
# ═══════════════════════════════════════

@dp.message(F.text == "🗂 Заказы")
async def admin_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID and not (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, order_data, total, status, created_at FROM orders WHERE status='новый' ORDER BY created_at DESC")
    orders = cur.fetchall()
    conn.close()
    if not orders:
        await message.answer("новых заказов нет 🎉")
        return
    for oid, data, total, status, created in orders:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 собран", callback_data=f"st_{oid}_собран"),
             InlineKeyboardButton(text="🚚 отправлен", callback_data=f"st_{oid}_отправлен")],
            [InlineKeyboardButton(text="✅ доставлен", callback_data=f"st_{oid}_доставлен"),
             InlineKeyboardButton(text="❌ отменён", callback_data=f"st_{oid}_отменён")],
        ])
        await message.answer(f"📦 Заказ №{oid}\n{created}\n\n{data}\n\nСтатус: {status}", reply_markup=kb)

@dp.callback_query(F.data.startswith("st_"))
async def set_status(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID and not (call.from_user.username and call.from_user.username.lower() in ADMIN_USERNAMES):
        return
    parts = call.data.split("_", 2)
    oid = int(parts[1])
    new_st = parts[2]

    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (new_st, oid))
    cur.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    conn.commit()
    conn.close()

    await call.message.edit_text(f"заказ №{oid} → {STATUS_EMOJI.get(new_st, '')} {new_st}")

    if row:
        notify = {
            "собран": "📦 твой заказ собран и готовится к отправке!",
            "отправлен": "🚚 заказ отправлен! скоро будет у тебя 🎉",
            "доставлен": "✅ доставлен! спасибо 🤝",
            "отменён": "❌ заказ отменён",
        }
        if new_st in notify:
            try: await bot.send_message(row[0], notify[new_st])
            except: pass
    await call.answer()

# ═══════════════════════════════════════
#        ADMIN — ADD / DELETE
# ═══════════════════════════════════════

@dp.message(F.text == "＋ Добавить товар")
async def add_product_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID and not (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        return
    await message.answer("название товара:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def ap_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("описание:")
    await state.set_state(AddProduct.description)

@dp.message(AddProduct.description)
async def ap_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("цена (число):")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def ap_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("введи число!")
        return
    await state.update_data(price=int(message.text))
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, emoji FROM categories")
    cats = cur.fetchall()
    conn.close()
    if not cats:
        await message.answer("нет категорий! /add_category Название")
        await state.clear()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{e or '✦'} {n}", callback_data=f"setcat_{c}")] for c, n, e in cats
    ])
    await message.answer("категория:", reply_markup=kb)
    await state.set_state(AddProduct.category)

@dp.callback_query(AddProduct.category, F.data.startswith("setcat_"))
async def ap_cat(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(call.data.split("_")[1]))
    await call.message.answer("📸 фото товара:")
    await state.set_state(AddProduct.photo)
    await call.answer()

@dp.message(AddProduct.photo, F.photo)
async def ap_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO products (name, description, price, category_id, photo_file_id) VALUES (?, ?, ?, ?, ?)",
                (data['name'], data['description'], data['price'], data['category_id'], message.photo[-1].file_id))
    conn.commit()
    conn.close()
    await message.answer(f"✅ {data['name']} добавлен!")
    await state.clear()

@dp.message(F.text == "✕ Удалить товар")
async def del_product_list(message: types.Message):
    if message.from_user.id != ADMIN_ID and not (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, price FROM products")
    prods = cur.fetchall()
    conn.close()
    if not prods:
        await message.answer("товаров нет")
        return
    buttons = [[InlineKeyboardButton(text=f"🗑 {n} — {p}₽", callback_data=f"dp_{i}")] for i, n, p in prods]
    await message.answer("какой удалить?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("dp_"))
async def del_product(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID and not (call.from_user.username and call.from_user.username.lower() in ADMIN_USERNAMES):
        return
    pid = int(call.data.split("_")[1])
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (pid,))
    cur.execute("DELETE FROM cart WHERE product_id=?", (pid,))
    cur.execute("DELETE FROM favorites WHERE product_id=?", (pid,))
    conn.commit()
    conn.close()
    await call.message.edit_text("удалено ✅")
    await call.answer()

@dp.message(Command("add_category"))
async def add_category(message: types.Message):
    if message.from_user.id != ADMIN_ID and not (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("/add_category Название")
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (parts[1],))
        conn.commit()
        await message.answer(f"✅ «{parts[1]}» добавлена")
    except sqlite3.IntegrityError:
        await message.answer("уже есть")
    finally:
        conn.close()

# ═══════════════════════════════════════
#        ADMIN — STATS & BROADCAST
# ═══════════════════════════════════════

@dp.message(F.text == "📈 Статистика")
async def statistics(message: types.Message):
    if message.from_user.id != ADMIN_ID and not (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders")
    t_ord = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='новый'")
    n_ord = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(total), 0) FROM orders")
    rev = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    t_prod = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users")
    t_users = cur.fetchone()[0]
    conn.close()
    await message.answer(
        f"📊 статистика\n\n"
        f"👥 юзеров: {t_users}\n"
        f"📦 заказов: {t_ord}\n"
        f"🆕 новых: {n_ord}\n"
        f"💰 выручка: {fmt_price(rev)}₽\n"
        f"🏷 товаров: {t_prod}"
    )

@dp.message(F.text == "📣 Рассылка")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID and not (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        return
    await message.answer("текст рассылки:")
    await state.set_state(BroadcastForm.text)

@dp.message(BroadcastForm.text)
async def broadcast_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID and not (message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES):
        await state.clear()
        return
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()
    count = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, message.text)
            count += 1
        except:
            pass
    await message.answer(f"✅ отправлено {count}/{len(users)}")
    await state.clear()

# ═══════════════════════════════════════
#               RUN
# ═══════════════════════════════════════

async def main():
    print("🚀 Radiance.fit bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
