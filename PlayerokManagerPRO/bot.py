import asyncio
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from dotenv import load_dotenv

from database import Database

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DB_PATH = os.getenv("DB_PATH", "data/playerok.sqlite3")
PHOTO_DIR = Path("storage/photos")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler("logs/bot.log", encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger("playerok_manager")

db = Database(DB_PATH)
dp = Dispatcher()

class ProductForm(StatesGroup):
    game = State()
    category = State()
    name = State()
    price = State()
    facts = State()
    photos = State()

class ReplyForm(StatesGroup):
    trigger = State()
    answer = State()

class ReplyTest(StatesGroup):
    message = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Товары и черновики", callback_data="products"),
         InlineKeyboardButton(text="➕ Создать карточку", callback_data="new_card")],
        [InlineKeyboardButton(text="💬 Автоответчик", callback_data="replies"),
         InlineKeyboardButton(text="♻️ Перевыставление", callback_data="restore")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
         InlineKeyboardButton(text="🔎 Поиск", callback_data="search")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
         InlineKeyboardButton(text="❔ Помощь", callback_data="help")]
    ])

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True)

def product_actions(product_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Показать карточку", callback_data=f"show:{product_id}")],
        [InlineKeyboardButton(text="📤 Подготовить текст для Playerok", callback_data=f"export:{product_id}")],
        [InlineKeyboardButton(text="🗑 Удалить черновик", callback_data=f"delete:{product_id}")],
        [InlineKeyboardButton(text="🌐 Открыть Playerok", url="https://playerok.com/profile/Artemasts/products")]
    ])

async def guard_message(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к панели управления.")
        return False
    return True

async def guard_callback(call: CallbackQuery) -> bool:
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return False
    return True

@dp.message(CommandStart())
async def start(message: Message):
    if not await guard_message(message):
        return
    await message.answer(
        "👋 <b>Playerok Manager PRO</b>\n\n"
        "Твоя панель управления карточками товаров, шаблонами ответов и статистикой.\n"
        "Работает без ИИ и внешних AI-ключей.\n\n"
        "⚠️ Новые товары публикуются вручную на Playerok. "
        "Модуль перевыставления предназначен только для разрешённых площадкой сценариев.",
        reply_markup=menu_kb()
    )

@dp.message(Command("menu"))
async def menu(message: Message):
    if await guard_message(message):
        await message.answer("Главное меню:", reply_markup=menu_kb())

@dp.message(F.text == "Отмена")
async def cancel(message: Message, state: FSMContext):
    if not await guard_message(message):
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=menu_kb())

@dp.callback_query(F.data == "help")
async def help_cb(call: CallbackQuery):
    if not await guard_callback(call): return
    await call.message.answer(
        "<b>Команды</b>\n/start — главное меню\n/menu — открыть меню\n"
        "/backup — создать резервную копию\n\n"
        "Создание карточки: /new — пошаговое заполнение.\n"
        "/products — список карточек; /stats — статистика; /search текст — поиск.\n"
        "/backup — резервная копия базы. Новое объявление размещается вручную на Playerok."
    )
    await call.answer()

@dp.callback_query(F.data == "new_card")
async def new_card(call: CallbackQuery, state: FSMContext):
    if not await guard_callback(call): return
    await state.clear()
    await state.set_state(ProductForm.game)
    await call.message.answer("🎮 Напиши игру или приложение:", reply_markup=cancel_kb())
    await call.answer()

@dp.callback_query(F.data == "products")
async def products(call: CallbackQuery):
    if not await guard_callback(call): return
    rows = db.list_products(20)
    if not rows:
        await call.message.answer("Пока нет сохранённых товаров. Нажми «Создать карточку».")
    else:
        await call.message.answer(f"📦 <b>Твои последние товары: {len(rows)}</b>")
        for p in rows:
            text = f"#{p['id']} · <b>{p['name']}</b>\n🎮 {p['game']} · 💰 {p['price']} ₽\nСтатус: {p['status']}"
            await call.message.answer(text, reply_markup=product_actions(p["id"]))
    await call.answer()

@dp.message(ProductForm.game)
async def form_game(message: Message, state: FSMContext):
    if not await guard_message(message): return
    await state.update_data(game=message.text.strip())
    await state.set_state(ProductForm.category)
    await message.answer("Выбери или напиши категорию товара:", reply_markup=cancel_kb())

@dp.message(ProductForm.category)
async def form_category(message: Message, state: FSMContext):
    if not await guard_message(message): return
    await state.update_data(category=message.text.strip())
    await state.set_state(ProductForm.name)
    await message.answer("Как называется товар? Можно написать черновое название:")

@dp.message(ProductForm.name)
async def form_name(message: Message, state: FSMContext):
    if not await guard_message(message): return
    await state.update_data(name=message.text.strip())
    await state.set_state(ProductForm.price)
    await message.answer("Укажи цену в рублях (только число):")

@dp.message(ProductForm.price)
async def form_price(message: Message, state: FSMContext):
    if not await guard_message(message): return
    raw = message.text.strip().replace(",", ".")
    try:
        price = float(raw)
        if price <= 0 or price > 100000000: raise ValueError()
    except ValueError:
        await message.answer("Введи корректную цену числом, например 500.")
        return
    await state.update_data(price=price)
    await state.set_state(ProductForm.facts)
    await message.answer(
        "Напиши факты о товаре: что получает покупатель, состояние, комплект, условия передачи, "
        "ограничения и важные детали. Не указывай пароли или личные данные."
    )

@dp.message(ProductForm.facts)
async def form_facts(message: Message, state: FSMContext):
    if not await guard_message(message): return
    await state.update_data(facts=message.text.strip(), photos=[])
    await state.set_state(ProductForm.photos)
    await message.answer("📷 Пришли фотографии по одной. Когда закончишь, напиши «Готово». Можно пропустить.")

@dp.message(ProductForm.photos, F.photo)
async def form_photo(message: Message, state: FSMContext, bot: Bot):
    if not await guard_message(message): return
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 10:
        await message.answer("Максимум 10 фотографий. Напиши «Готово».")
        return
    file = await bot.get_file(message.photo[-1].file_id)
    filename = f"{message.from_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    path = PHOTO_DIR / filename
    await bot.download_file(file.file_path, destination=path)
    photos.append(str(path))
    await state.update_data(photos=photos)
    await message.answer(f"Фото сохранено ({len(photos)}/10). Ещё фото или «Готово».")

@dp.message(ProductForm.photos)
async def form_finish(message: Message, state: FSMContext):
    if not await guard_message(message): return
    if message.text.strip().lower() not in {"готово", "готов", "пропустить"}:
        await message.answer("Пришли фотографию или напиши «Готово».")
        return
    data = await state.get_data()
    await state.clear()
    generated = {
        "title": data["name"],
        "description": data["facts"],
        "features": [], "faq": [], "tags": [],
        "buyer_gets": data["facts"],
        "notes": "Карточка сформирована из введённых тобой данных без ИИ. Проверь точность перед публикацией."
    }
    pid = db.add_product(
        game=data["game"], category=data["category"], name=generated.get("title") or data["name"],
        price=data["price"], facts=data["facts"], listing=generated,
        photos=data.get("photos", []), status="Черновик"
    )
    db.add_event("draft_created", f"Создан черновик #{pid}", message.from_user.id)
    await message.answer(format_listing(generated, data))
    await message.answer("Черновик сохранён. Проверь факты, цену и изображения перед публикацией.", reply_markup=product_actions(pid))
    await message.answer("Главное меню:", reply_markup=menu_kb())

def format_listing(g, d):
    features = "\n".join(f"• {x}" for x in g.get("features", [])) or "—"
    faq = "\n".join(f"В: {x.get('q','')}\nО: {x.get('a','')}" for x in g.get("faq", [])) or "—"
    tags = ", ".join(g.get("tags", [])) or "—"
    return (
        f"✨ <b>{g.get('title', d['name'])}</b>\n"
        f"🎮 Игра: {d['game']}\n📂 Категория: {d['category']}\n💰 Цена: {d['price']} ₽\n\n"
        f"<b>Описание</b>\n{g.get('description', '')}\n\n"
        f"<b>Преимущества</b>\n{features}\n\n"
        f"<b>Покупатель получает</b>\n{g.get('buyer_gets', '')}\n\n"
        f"<b>FAQ</b>\n{faq}\n\n"
        f"<b>Ключевые слова</b>\n{tags}\n\n"
        f"<i>Примечание: {g.get('notes','Проверь точность данных.')}</i>"
    )

@dp.callback_query(F.data.startswith("show:"))
async def show_product(call: CallbackQuery):
    if not await guard_callback(call): return
    pid = int(call.data.split(":")[1])
    p = db.get_product(pid)
    if not p:
        await call.answer("Товар не найден", show_alert=True); return
    await call.message.answer(format_listing(p["listing"], p))
    await call.answer()

@dp.callback_query(F.data.startswith("delete:"))
async def delete_product(call: CallbackQuery):
    if not await guard_callback(call): return
    pid = int(call.data.split(":")[1])
    db.delete_product(pid)
    db.add_event("draft_deleted", f"Удалён черновик #{pid}", call.from_user.id)
    await call.message.answer(f"Черновик #{pid} удалён из локальной базы.")
    await call.answer()

@dp.callback_query(F.data.startswith("export:"))
async def export_product(call: CallbackQuery):
    if not await guard_callback(call): return
    pid = int(call.data.split(":")[1])
    p = db.get_product(pid)
    if not p:
        await call.answer("Товар не найден", show_alert=True); return
    listing = p["listing"]
    text = (
        f"{listing.get('title', p['name'])}\n\n"
        f"{listing.get('description', p['facts'])}\n\n"
        f"Что получает покупатель: {listing.get('buyer_gets', p['facts'])}\n\n"
        f"Цена: {p['price']:g} ₽\nКатегория: {p['category']}"
    )
    await call.message.answer("<b>Текст для ручного размещения на Playerok:</b>\n\n" + text[:3900])
    await call.answer()

@dp.callback_query(F.data == "replies")
async def replies_menu(call: CallbackQuery):
    if not await guard_callback(call): return
    settings = db.get_settings()
    rows = db.list_replies()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить сценарий", callback_data="reply_add")],
        [InlineKeyboardButton(text=f"Режим: {settings.get('reply_mode','mixed')}", callback_data="reply_mode")],
        [InlineKeyboardButton(text="📚 Мои сценарии", callback_data="reply_list")],
        [InlineKeyboardButton(text="🧪 Проверить фразу", callback_data="reply_test")]
    ])
    await call.message.answer(
        f"💬 <b>Автоответчик</b>\nРежим: {settings.get('reply_mode','mixed')}\nСценариев: {len(rows)}\n\n"
        "Важно: без разрешённого подключения к сообщениям Playerok бот хранит сценарии и подбирает ответы здесь, "
        "но не читает и не отправляет сообщения на площадке сам.",
        reply_markup=kb
    )
    await call.answer()

@dp.callback_query(F.data == "reply_add")
async def reply_add(call: CallbackQuery, state: FSMContext):
    if not await guard_callback(call): return
    await state.set_state(ReplyForm.trigger)
    await call.message.answer("Напиши ключевую фразу или слово, например: «как получить»")
    await call.answer()

@dp.message(ReplyForm.trigger)
async def reply_trigger(message: Message, state: FSMContext):
    if not await guard_message(message): return
    await state.update_data(trigger=message.text.strip())
    await state.set_state(ReplyForm.answer)
    await message.answer("Теперь напиши ответ покупателю:")

@dp.message(ReplyForm.answer)
async def reply_answer(message: Message, state: FSMContext):
    if not await guard_message(message): return
    data = await state.get_data()
    await state.clear()
    db.add_reply(data["trigger"], message.text.strip())
    db.add_event("reply_added", f"Добавлен ответ для «{data['trigger']}»", message.from_user.id)
    await message.answer("✅ Сценарий сохранён.", reply_markup=menu_kb())

@dp.callback_query(F.data == "reply_list")
async def reply_list(call: CallbackQuery):
    if not await guard_callback(call): return
    rows = db.list_replies()
    if not rows:
        await call.message.answer("Сценариев пока нет.")
    else:
        for r in rows[:30]:
            await call.message.answer(f"🔑 <b>{r['trigger']}</b>\n{r['answer']}")
    await call.answer()

@dp.callback_query(F.data == "reply_mode")
async def reply_mode(call: CallbackQuery):
    if not await guard_callback(call): return
    current = db.get_settings().get("reply_mode", "mixed")
    new = "manual" if current == "mixed" else "mixed"
    db.set_setting("reply_mode", new)
    await call.message.answer(f"Режим изменён на: {new}")
    await call.answer()

@dp.callback_query(F.data == "reply_test")
async def reply_test(call: CallbackQuery, state: FSMContext):
    if not await guard_callback(call): return
    await state.set_state(ReplyTest.message)
    await call.message.answer("Напиши пример сообщения покупателя:")
    await call.answer()

@dp.message(ReplyTest.message, F.text)
async def reply_test_message(message: Message, state: FSMContext):
    if not await guard_message(message): return
    await state.clear()
    match = db.match_reply(message.text)
    if match:
        await message.answer(f"💬 Подходящий ответ:\n\n{match['answer']}\n\n(Черновик ответа — проверь перед отправкой.)")
    else:
        await message.answer("Подходящий сценарий не найден. Можно добавить новый в разделе автоответчика.")

@dp.callback_query(F.data == "restore")
async def restore_menu(call: CallbackQuery):
    if not await guard_callback(call): return
    await call.message.answer(
        "♻️ <b>Перевыставление проданных товаров</b>\n\n"
        "Playerok разрешает автоматическое перевыставление проданных товаров. "
        "В этой версии модуль ведёт список товаров, которые ты пометил для восстановления, "
        "и напоминает проверить их штатную настройку «Оставить в продаже» на площадке.\n\n"
        "Автоматическое управление аккаунтом через неофициальные сессионные токены не включено."
    )
    await call.answer()

@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    if not await guard_callback(call): return
    s = db.stats()
    await call.message.answer(
        "📊 <b>Статистика Manager PRO</b>\n\n"
        f"Черновиков: {s['products']}\n"
        f"Сценариев ответов: {s['replies']}\n"
        f"Событий в журнале: {s['events']}\n"
        f"Сумма цен черновиков: {s['draft_value']:.2f} ₽\n\n"
        "Это локальная статистика Manager PRO, а не подтверждённые продажи Playerok."
    )
    await call.answer()

@dp.callback_query(F.data == "templates")
async def templates(call: CallbackQuery):
    if not await guard_callback(call): return
    await call.message.answer(
        "🧩 Шаблоны пока формируются из сохранённых карточек. "
        "Открой «Товары и черновики», чтобы повторно использовать описание и структуру."
    )
    await call.answer()

@dp.callback_query(F.data == "search")
async def search_help(call: CallbackQuery):
    if not await guard_callback(call): return
    await call.message.answer("🔎 Для поиска напиши команду: /search название_или_игра")
    await call.answer()

@dp.callback_query(F.data == "settings")
async def settings(call: CallbackQuery):
    if not await guard_callback(call): return
    s = db.get_settings()
    await call.message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        f"Режим ответов: {s.get('reply_mode','mixed')}\n"
        "ИИ: отключён (бот полностью работает без AI API)\n"
        f"База: {DB_PATH}\n\n"
        "Новые объявления создавай вручную на Playerok. Не передавай боту пароль, cookies или коды входа."
    )
    await call.answer()

@dp.message(Command("new"))
async def new_command(message: Message, state: FSMContext):
    if not await guard_message(message): return
    await state.clear()
    await state.set_state(ProductForm.game)
    await message.answer("🎮 Напиши игру или приложение:", reply_markup=cancel_kb())

@dp.message(Command("products"))
async def products_command(message: Message):
    if not await guard_message(message): return
    rows = db.list_products(30)
    if not rows:
        await message.answer("Карточек пока нет. Создать: /new")
        return
    for p in rows:
        await message.answer(
            f"#{p['id']} · <b>{p['name']}</b>\n{p['game']} / {p['category']}\n"
            f"Цена: {p['price']:g} ₽ · {p['status']}",
            reply_markup=product_actions(p['id'])
        )

@dp.message(Command("stats"))
async def stats_command(message: Message):
    if not await guard_message(message): return
    s = db.stats()
    await message.answer(
        "📊 <b>Статистика Manager PRO</b>\n\n"
        f"Карточек: {s['products']}\nШаблонов ответов: {s['replies']}\n"
        f"Записей журнала: {s['events']}\nСумма цен черновиков: {s['draft_value']:.2f} ₽\n\n"
        "Это данные локальной панели, не статистика продаж Playerok."
    )

@dp.message(Command("search"))
async def search_command(message: Message):
    if not await guard_message(message): return
    query = message.text.partition(" ")[2].strip().lower()
    if not query:
        await message.answer("Использование: /search название или игра")
        return
    rows = db.list_products(500)
    found = [p for p in rows if query in p['name'].lower() or query in p['game'].lower() or query in p['facts'].lower()]
    if not found:
        await message.answer("Ничего не найдено.")
        return
    for p in found[:20]:
        await message.answer(f"#{p['id']} · <b>{p['name']}</b> · {p['price']:g} ₽", reply_markup=product_actions(p['id']))

@dp.message(Command("backup"))
async def backup(message: Message):
    if not await guard_message(message): return
    src = Path(DB_PATH)
    if not src.exists():
        await message.answer("База пока не создана.")
        return
    Path("backups").mkdir(exist_ok=True)
    dest = Path("backups") / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
    shutil.copy2(src, dest)
    await message.answer_document(dest.open("rb"), caption="✅ Резервная копия базы данных.")

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не указан BOT_TOKEN в .env")
    if not ADMIN_IDS:
        raise RuntimeError("Не указан ADMIN_IDS в .env")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    log.info("Playerok Manager PRO started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
