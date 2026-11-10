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
from ai_service import AIService

# Все рабочие пути привязаны к папке проекта, а не к текущей папке запуска.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

_db_path = Path(os.getenv("DB_PATH", "data/playerok.sqlite3"))
DB_PATH = str(_db_path if _db_path.is_absolute() else BASE_DIR / _db_path)

PHOTO_DIR = BASE_DIR / "storage" / "photos"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("playerok_manager")

db = Database(DB_PATH)
ai = AIService()
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

class AIEdit(StatesGroup):
    prompt = State()

class ReplyTest(StatesGroup):
    message = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Товары и черновики", callback_data="products"),
         InlineKeyboardButton(text="✨ Создать с ИИ", callback_data="new_ai")],
        [InlineKeyboardButton(text="💬 Автоответчик", callback_data="replies"),
         InlineKeyboardButton(text="♻️ Перевыставление", callback_data="restore")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
         InlineKeyboardButton(text="🧩 Шаблоны", callback_data="templates")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
         InlineKeyboardButton(text="❔ Помощь", callback_data="help")]
    ])

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True)

def product_actions(product_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Улучшить ИИ", callback_data=f"improve:{product_id}")],
        [InlineKeyboardButton(text="📋 Показать карточку", callback_data=f"show:{product_id}")],
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
        "Твоя панель управления товарами, ИИ-генерацией, шаблонами и статистикой.\n\n"
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
        "Создание товара: укажи игру, категорию, название, цену, факты и фотографии. "
        "ИИ не должен выдумывать свойства товара — проверяй карточку перед использованием."
    )
    await call.answer()

@dp.callback_query(F.data == "new_ai")
async def new_ai(call: CallbackQuery, state: FSMContext):
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
        await call.message.answer("Пока нет сохранённых товаров. Нажми «Создать с ИИ».")
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
    await message.answer("✨ ИИ готовит карточку. Это может занять несколько секунд…")
    try:
        generated = await ai.generate_listing(data)
    except Exception as e:
        log.exception("AI generation failed")
        generated = {
            "title": data["name"], "description": data["facts"],
            "features": [], "faq": [], "tags": [], "buyer_gets": data["facts"],
            "notes": "ИИ недоступен. Сохранён исходный текст."
        }
        await message.answer("⚠️ Не удалось подключиться к ИИ. Сохраняю исходные данные.")
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
        f"<i>Примечание ИИ: {g.get('notes','Проверь точность данных.')}</i>"
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

@dp.callback_query(F.data.startswith("improve:"))
async def improve(call: CallbackQuery, state: FSMContext):
    if not await guard_callback(call): return
    pid = int(call.data.split(":")[1])
    if not db.get_product(pid):
        await call.answer("Товар не найден", show_alert=True); return
    await state.update_data(product_id=pid)
    await state.set_state(AIEdit.prompt)
    await call.message.answer("Что именно улучшить? Например: «Сделай описание короче и добавь понятный список комплектации».")
    await call.answer()

@dp.message(AIEdit.prompt)
async def improve_prompt(message: Message, state: FSMContext):
    if not await guard_message(message): return
    data = await state.get_data()
    pid = data["product_id"]
    p = db.get_product(pid)
    await state.clear()
    try:
        updated = await ai.revise_listing(p, message.text.strip())
        db.update_listing(pid, updated)
        db.add_event("ai_revised", f"ИИ обновил черновик #{pid}", message.from_user.id)
        await message.answer(format_listing(updated, p), reply_markup=product_actions(pid))
    except Exception:
        log.exception("AI revise failed")
        await message.answer("Не удалось выполнить запрос ИИ. Проверь API-ключ и попробуй позже.")
    await message.answer("Главное меню:", reply_markup=menu_kb())

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

@dp.callback_query(F.data == "settings")
async def settings(call: CallbackQuery):
    if not await guard_callback(call): return
    s = db.get_settings()
    await call.message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        f"Режим ответов: {s.get('reply_mode','mixed')}\n"
        f"ИИ: {'включён' if ai.enabled else 'не настроен'}\n"
        f"База: {DB_PATH}\n\n"
        "Настрой API-ключ в файле .env. Никогда не отправляй его в Telegram или другим людям."
    )
    await call.answer()

@dp.message(Command("backup"))
async def backup(message: Message):
    if not await guard_message(message): return
    src = Path(DB_PATH)
    if not src.exists():
        await message.answer("База пока не создана.")
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
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
