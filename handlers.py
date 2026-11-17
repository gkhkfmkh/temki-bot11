import csv, io
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile
from config import settings
from keyboards import decision
from logic import calc_profit, parse_csv
from media_tools import make_product_card
from templates import buyer_message

router = Router()

class ProductFlow(StatesGroup):
    title=State(); category=State(); price=State(); cost=State(); stock=State(); description=State(); photo=State()
class DealFlow(StatesGroup):
    title=State(); category=State(); buy=State(); sell=State(); fee=State(); source=State(); url=State()
class OrderFlow(StatesGroup):
    external=State(); buyer=State(); product=State(); amount=State(); cost=State()
class PhotoFlow(StatesGroup):
    product_id=State()
class DeliveryFlow(StatesGroup):
    order_id=State()

def is_admin(uid): return uid == settings.admin_id
async def denied(m): await m.answer("Доступ закрыт: проверьте ADMIN_ID.")

@router.message(Command("start"))
async def start(m: Message):
    if not is_admin(m.from_user.id): return await denied(m)
    await m.answer(
        "<b>PLAYEROK PROFIT AI MAX</b>\n\n"
        "Панель управления цифровым магазином.\n"
        "Каталог • фото • карточки • черновики • закупки • заказы • сообщения покупателям • отчёты.\n\n"
        "Все покупки и публикации — только после вашего подтверждения. "
        "Внешние действия на Playerok не выполняются без документированной интеграции.\n\n"
        "Команды: /help"
    )

@router.message(Command("help"))
async def help_cmd(m: Message):
    if not is_admin(m.from_user.id): return await denied(m)
    await m.answer(
        "<b>Каталог и фото</b>\n/addproduct — добавить товар\n/products — список\n/photo ID — загрузить фото\n"
        "/makecard ID — сделать карточку товара\n/draft ID — создать черновик объявления\n/drafts — очередь публикаций\n\n"
        "<b>Закупки</b>\n/adddeal — добавить возможность\n/deals — список и подтверждения\n\n"
        "<b>Заказы и покупатели</b>\n/addorder — внести заказ вручную\n/orders — список\n/order ID — подробности\n"
        "/paid ID — отметить оплату\n/setdelivery ID — сохранить текст/инструкцию выдачи\n/deliver ID — подготовить сообщение выдачи\n/done ID — завершить заказ\n"
        "/templates — шаблоны сообщений\n\n"
        "<b>Аналитика</b>\n/importcsv — загрузить CSV\n/market — сводка цен\n/report — отчёт\n/export — выгрузить CSV\n/cancel — отменить ввод"
    )

@router.message(Command("cancel"))
async def cancel(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return await denied(m)
    await state.clear(); await m.answer("Текущий ввод отменён.")

# Product creation
@router.message(Command("addproduct"))
async def add_product(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return await denied(m)
    await state.set_state(ProductFlow.title); await m.answer("Название товара?")
@router.message(ProductFlow.title)
async def p_title(m: Message,state:FSMContext):
    await state.update_data(title=m.text[:200]); await state.set_state(ProductFlow.category); await m.answer("Категория?")
@router.message(ProductFlow.category)
async def p_cat(m:Message,state:FSMContext):
    await state.update_data(category=m.text[:100]); await state.set_state(ProductFlow.price); await m.answer("Цена продажи в ₽?")
@router.message(ProductFlow.price)
async def p_price(m:Message,state:FSMContext):
    try: v=float(m.text.replace(",","."))
    except: return await m.answer("Введите число.")
    if v<0: return await m.answer("Цена не может быть отрицательной.")
    await state.update_data(price=v); await state.set_state(ProductFlow.cost); await m.answer("Себестоимость в ₽?")
@router.message(ProductFlow.cost)
async def p_cost(m:Message,state:FSMContext):
    try: v=float(m.text.replace(",","."))
    except: return await m.answer("Введите число.")
    if v<0: return await m.answer("Себестоимость не может быть отрицательной.")
    await state.update_data(cost=v); await state.set_state(ProductFlow.stock); await m.answer("Количество на складе (целое число)?")
@router.message(ProductFlow.stock)
async def p_stock(m:Message,state:FSMContext):
    try: v=int(m.text)
    except: return await m.answer("Введите целое число.")
    if v<0: return await m.answer("Количество не может быть отрицательным.")
    await state.update_data(stock=v); await state.set_state(ProductFlow.description); await m.answer("Описание товара?")
@router.message(ProductFlow.description)
async def p_desc(m:Message,state:FSMContext):
    await state.update_data(description=m.text[:4000]); await state.set_state(ProductFlow.photo)
    await m.answer("Теперь отправьте фото товара. Если фото нет — напишите «пропустить».")
@router.message(ProductFlow.photo)
async def p_photo(m:Message,state:FSMContext,db,bot):
    d=await state.get_data(); photo_path=""
    if m.photo:
        Path(settings.media_dir).mkdir(parents=True,exist_ok=True)
        tgfile=await bot.get_file(m.photo[-1].file_id)
        photo_path=str(Path(settings.media_dir)/f"product_upload_{m.from_user.id}_{m.photo[-1].file_unique_id}.jpg")
        await bot.download_file(tgfile.file_path,photo_path)
    elif (m.text or "").strip().lower() not in ("пропустить","-","нет"):
        return await m.answer("Пришлите фотографию или напишите «пропустить».")
    pid=await db.execute("INSERT INTO products(title,category,description,price,cost,stock,photo_path) VALUES(?,?,?,?,?,?,?)",
        (d["title"],d["category"],d["description"],d["price"],d["cost"],d["stock"],photo_path))
    await db.log("created","product",pid)
    await state.clear()
    profit,roi=calc_profit(d["cost"],d["price"],settings.default_fee)
    await m.answer(f"Товар #{pid} добавлен: <b>{d['title']}</b>\nЦена {d['price']:.2f} ₽; себестоимость {d['cost']:.2f} ₽; остаток {d['stock']}.\nОценка прибыли до комиссии: {profit:.2f} ₽; ROI {roi:.1f}%.\nСоздать карточку: /makecard {pid}")

@router.message(Command("products"))
async def products(m:Message,db):
    if not is_admin(m.from_user.id): return await denied(m)
    rows=await db.all("SELECT * FROM products WHERE active=1 ORDER BY id DESC LIMIT 40")
    if not rows: return await m.answer("Каталог пуст. Используйте /addproduct.")
    for p in rows:
        await m.answer(f"#{p['id']} <b>{p['title']}</b>\n{p['category']} • {p['price']:.2f} ₽ • остаток {p['stock']}\nФото: {'есть' if p['photo_path'] else 'нет'}")

@router.message(Command("photo"))
async def photo_cmd(m:Message,state:FSMContext):
    if not is_admin(m.from_user.id): return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit(): return await m.answer("Формат: /photo ID")
    await state.update_data(product_id=int(parts[1])); await state.set_state(PhotoFlow.product_id)
    await m.answer("Теперь отправьте фотографию товара.")
@router.message(PhotoFlow.product_id,F.photo)
async def photo_receive(m:Message,state:FSMContext,db,bot):
    d=await state.get_data(); pid=d["product_id"]
    p=await db.one("SELECT id FROM products WHERE id=?",(pid,))
    if not p: await state.clear(); return await m.answer("Товар не найден.")
    Path(settings.media_dir).mkdir(parents=True,exist_ok=True)
    f=await bot.get_file(m.photo[-1].file_id)
    path=str(Path(settings.media_dir)/f"product_{pid}_{m.photo[-1].file_unique_id}.jpg")
    await bot.download_file(f.file_path,path)
    await db.execute("UPDATE products SET photo_path=? WHERE id=?",(path,pid))
    await db.log("photo_updated","product",pid)
    await state.clear(); await m.answer(f"Фото для товара #{pid} сохранено. Карточка: /makecard {pid}")

@router.message(Command("makecard"))
async def makecard(m:Message,db):
    if not is_admin(m.from_user.id): return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit(): return await m.answer("Формат: /makecard ID")
    p=await db.one("SELECT * FROM products WHERE id=?",(int(parts[1]),))
    if not p: return await m.answer("Товар не найден.")
    path=make_product_card(p["id"],p["title"],p["price"],p["photo_path"])
    await m.answer_photo(FSInputFile(path),caption=f"Карточка для товара #{p['id']}. Проверьте корректность изображения перед использованием.")

# Drafts
@router.message(Command("draft"))
async def make_draft(m:Message,db):
    if not is_admin(m.from_user.id): return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit(): return await m.answer("Формат: /draft ID")
    p=await db.one("SELECT * FROM products WHERE id=?",(int(parts[1]),))
    if not p: return await m.answer("Товар не найден.")
    did=await db.execute("INSERT INTO drafts(product_id,title,description,price) VALUES(?,?,?,?)",
        (p["id"],p["title"],p["description"],p["price"]))
    await db.log("created","draft",did)
    await m.answer(f"<b>Черновик #{did}</b>\n{p['title']}\nЦена: {p['price']:.2f} ₽\n\nПроверьте описание и правила площадки. Подтверждение фиксирует согласие, но не публикует объявление.",
                   reply_markup=decision("draft",did))
@router.message(Command("drafts"))
async def drafts(m:Message,db):
    if not is_admin(m.from_user.id): return await denied(m)
    rows=await db.all("SELECT * FROM drafts ORDER BY id DESC LIMIT 30")
    if not rows: return await m.answer("Черновиков пока нет.")
    for r in rows:
        await m.answer(f"#{r['id']} {r['title']} — {r['price']:.2f} ₽; статус: {r['status']}",
                       reply_markup=decision("draft",r["id"]) if r["status"]=="pending" else None)

# Deal approval
@router.message(Command("adddeal"))
async def add_deal(m:Message,state:FSMContext):
    if not is_admin(m.from_user.id): return await denied(m)
    await state.set_state(DealFlow.title); await m.answer("Название закупочной возможности?")
@router.message(DealFlow.title)
async def d_title(m:Message,state:FSMContext):
    await state.update_data(title=m.text[:200]); await state.set_state(DealFlow.category); await m.answer("Категория?")
@router.message(DealFlow.category)
async def d_cat(m:Message,state:FSMContext):
    await state.update_data(category=m.text[:100]); await state.set_state(DealFlow.buy); await m.answer("Цена закупки в ₽?")
@router.message(DealFlow.buy)
async def d_buy(m:Message,state:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:return await m.answer("Введите число.")
    if v<0:return await m.answer("Число не может быть отрицательным.")
    await state.update_data(buy=v); await state.set_state(DealFlow.sell); await m.answer("Ожидаемая цена продажи?")
@router.message(DealFlow.sell)
async def d_sell(m:Message,state:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:return await m.answer("Введите число.")
    if v<0:return await m.answer("Число не может быть отрицательным.")
    await state.update_data(sell=v); await state.set_state(DealFlow.fee); await m.answer("Резерв расходов/комиссии?")
@router.message(DealFlow.fee)
async def d_fee(m:Message,state:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:return await m.answer("Введите число.")
    if v<0:return await m.answer("Число не может быть отрицательным.")
    await state.update_data(fee=v); await state.set_state(DealFlow.source); await m.answer("Источник/поставщик (без паролей и секретов)?")
@router.message(DealFlow.source)
async def d_source(m:Message,state:FSMContext):
    await state.update_data(source=m.text[:200]); await state.set_state(DealFlow.url); await m.answer("Ссылка или «—»?")
@router.message(DealFlow.url)
async def d_url(m:Message,state:FSMContext,db):
    d=await state.get_data(); url="" if m.text.strip()=="—" else m.text.strip()[:500]
    did=await db.execute("INSERT INTO deals(title,category,buy_price,sell_price,fee,source,url) VALUES(?,?,?,?,?,?,?)",
        (d["title"],d["category"],d["buy"],d["sell"],d["fee"],d["source"],url))
    await db.log("created","deal",did)
    profit,roi=calc_profit(d["buy"],d["sell"],d["fee"]); await state.clear()
    await m.answer(f"<b>Возможность #{did}</b>\n{d['title']}\nЗакупка {d['buy']:.2f} ₽; продажа (оценка) {d['sell']:.2f} ₽; расходы {d['fee']:.2f} ₽\n"
                   f"Потенциал: <b>{profit:.2f} ₽</b>; ROI {roi:.1f}%\n\nПодтверждение не выполняет оплату.",
                   reply_markup=decision("deal",did))
@router.message(Command("deals"))
async def deals(m:Message,db):
    if not is_admin(m.from_user.id): return await denied(m)
    rows=await db.all("SELECT * FROM deals ORDER BY id DESC LIMIT 30")
    if not rows:return await m.answer("Закупочных возможностей пока нет.")
    for r in rows:
        profit,roi=calc_profit(r["buy_price"],r["sell_price"],r["fee"])
        await m.answer(f"#{r['id']} <b>{r['title']}</b>\nОценка {profit:.2f} ₽; ROI {roi:.1f}%; статус {r['status']}",
                       reply_markup=decision("deal",r["id"]) if r["status"]=="pending" else None)

@router.callback_query(F.data.startswith(("yes:","no:")))
async def decision_handler(c:CallbackQuery,db):
    if not is_admin(c.from_user.id): return await c.answer("Нет доступа",show_alert=True)
    action,kind,raw=c.data.split(":"); iid=int(raw)
    table={"deal":"deals","draft":"drafts"}.get(kind)
    if not table:return await c.answer("Неизвестный объект",show_alert=True)
    row=await db.one(f"SELECT status FROM {table} WHERE id=?",(iid,))
    if not row:return await c.answer("Не найдено",show_alert=True)
    if row["status"]!="pending":return await c.answer("Решение уже принято",show_alert=True)
    status="approved_by_owner" if action=="yes" else "rejected"
    await db.execute(f"UPDATE {table} SET status=?,decided_at=CURRENT_TIMESTAMP WHERE id=?",(status,iid))
    await db.log(action,kind,iid,"Подтверждение владельца; внешнее действие не запускалось")
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(("Решение сохранено: подтверждено." if action=="yes" else "Решение сохранено: отклонено.")
                           +" Внешняя покупка/публикация не выполнялась.")
    await c.answer("Сохранено")

# Orders
@router.message(Command("addorder"))
async def add_order(m:Message,state:FSMContext):
    if not is_admin(m.from_user.id):return await denied(m)
    await state.set_state(OrderFlow.external);await m.answer("Номер заказа на площадке (или —)?")
@router.message(OrderFlow.external)
async def o_ext(m:Message,state:FSMContext):
    await state.update_data(external=m.text[:100]);await state.set_state(OrderFlow.buyer);await m.answer("Имя/ник покупателя?")
@router.message(OrderFlow.buyer)
async def o_buyer(m:Message,state:FSMContext):
    await state.update_data(buyer=m.text[:100]);await state.set_state(OrderFlow.product);await m.answer("Название товара?")
@router.message(OrderFlow.product)
async def o_product(m:Message,state:FSMContext):
    await state.update_data(product=m.text[:200]);await state.set_state(OrderFlow.amount);await m.answer("Сумма заказа в ₽?")
@router.message(OrderFlow.amount)
async def o_amount(m:Message,state:FSMContext):
    try:v=float(m.text.replace(",","."))
    except:return await m.answer("Введите число.")
    if v<0:return await m.answer("Сумма не может быть отрицательной.")
    await state.update_data(amount=v);await state.set_state(OrderFlow.cost);await m.answer("Себестоимость товара в ₽?")
@router.message(OrderFlow.cost)
async def o_cost(m:Message,state:FSMContext,db):
    try:v=float(m.text.replace(",","."))
    except:return await m.answer("Введите число.")
    if v<0:return await m.answer("Сумма не может быть отрицательной.")
    d=await state.get_data()
    oid=await db.execute("INSERT INTO orders(external_id,buyer,product_title,amount,cost) VALUES(?,?,?,?,?)",
        ("" if d["external"]=="—" else d["external"],d["buyer"],d["product"],d["amount"],v))
    await db.log("created","order",oid)
    await state.clear()
    msg=buyer_message("welcome",d["buyer"],d["external"] if d["external"]!="—" else str(oid),d["product"])
    await m.answer(f"Заказ #{oid} записан.\nОценка результата: {d['amount']-v:.2f} ₽ до комиссий.\n\nЧерновик приветствия:\n<pre>{msg}</pre>\nИспользуйте /paid {oid} после проверки оплаты.")

@router.message(Command("orders"))
async def orders(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    rows=await db.all("SELECT * FROM orders ORDER BY id DESC LIMIT 30")
    if not rows:return await m.answer("Заказов пока нет.")
    for o in rows:
        await m.answer(f"#{o['id']} {o['product_title']} — {o['amount']:.2f} ₽; покупатель {o['buyer']}; статус {o['status']}")

@router.message(Command("order"))
async def order_detail(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit():return await m.answer("Формат: /order ID")
    o=await db.one("SELECT * FROM orders WHERE id=?",(int(parts[1]),))
    if not o:return await m.answer("Заказ не найден.")
    await m.answer(f"<b>Заказ #{o['id']}</b>\nПлощадка ID: {o['external_id'] or 'не указан'}\nПокупатель: {o['buyer']}\nТовар: {o['product_title']}\nСумма: {o['amount']:.2f} ₽\nСебестоимость: {o['cost']:.2f} ₽\nСтатус: {o['status']}\nЗаметка: {o['note'] or '—'}")

@router.message(Command("paid"))
async def paid(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit():return await m.answer("Формат: /paid ID")
    oid=int(parts[1]);o=await db.one("SELECT id,status FROM orders WHERE id=?",(oid,))
    if not o:return await m.answer("Заказ не найден.")
    if o["status"] not in ("new","problem"):return await m.answer(f"Текущий статус: {o['status']}.")
    await db.execute("UPDATE orders SET status='paid',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,))
    await db.log("marked_paid","order",oid,"Оплату проверил владелец вручную")
    await m.answer(f"Заказ #{oid} отмечен оплаченным. Подготовить сообщение выдачи: /deliver {oid}")

@router.message(Command("setdelivery"))
async def set_delivery(m:Message,state:FSMContext,db):
    if not is_admin(m.from_user.id):return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit():return await m.answer("Формат: /setdelivery ID")
    oid=int(parts[1]);o=await db.one("SELECT id,status FROM orders WHERE id=?",(oid,))
    if not o:return await m.answer("Заказ не найден.")
    await state.update_data(order_id=oid)
    await state.set_state(DeliveryFlow.order_id)
    await m.answer("Отправьте безопасную инструкцию/текст выдачи. Не отправляйте пароли, коды 2FA или чужие данные.")

@router.message(DeliveryFlow.order_id)
async def save_delivery(m:Message,state:FSMContext,db):
    d=await state.get_data();oid=d["order_id"]
    await db.execute("UPDATE orders SET delivery_text=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(m.text[:3000],oid))
    await db.log("delivery_text_saved","order",oid,"Текст сохранён локально")
    await state.clear()
    await m.answer(f"Текст выдачи сохранён для заказа #{oid}. После проверки оплаты используйте /deliver {oid}.")

@router.message(Command("deliver"))
async def deliver(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit():return await m.answer("Формат: /deliver ID")
    oid=int(parts[1]);o=await db.one("SELECT * FROM orders WHERE id=?",(oid,))
    if not o:return await m.answer("Заказ не найден.")
    if o["status"] not in ("paid","delivered"):return await m.answer("Сначала проверьте оплату и отметьте заказ командой /paid ID.")
    text=buyer_message("delivery",o["buyer"],o["external_id"] or str(oid),o["product_title"],o["delivery_text"])
    await db.log("delivery_message_prepared","order",oid,"Текст подготовлен; не отправлен на площадку")
    await m.answer(f"<b>Сообщение покупателю — заказ #{oid}</b>\n<pre>{text}</pre>\nСкопируйте текст и отправьте в чате заказа на площадке. Не вставляйте сюда пароли или коды 2FA.")

@router.message(Command("done"))
async def done(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    parts=m.text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].isdigit():return await m.answer("Формат: /done ID")
    oid=int(parts[1]);o=await db.one("SELECT id,status FROM orders WHERE id=?",(oid,))
    if not o:return await m.answer("Заказ не найден.")
    if o["status"] not in ("paid","delivered"):return await m.answer("Сначала отметьте оплату.")
    await db.execute("UPDATE orders SET status='done',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,))
    await db.log("completed","order",oid)
    await m.answer(f"Заказ #{oid} завершён в локальном учёте.")

@router.message(Command("templates"))
async def templates(m:Message):
    if not is_admin(m.from_user.id):return await denied(m)
    examples=[
        ("Приветствие",buyer_message("welcome","Покупатель","123","Цифровой товар")),
        ("Уточнение",buyer_message("clarify","Покупатель","123","Цифровой товар","Уточните нужный регион.")),
        ("Выдача",buyer_message("delivery","Покупатель","123","Цифровой товар","Инструкция по получению: [вставить безопасные инструкции]")),
        ("Завершение",buyer_message("complete","Покупатель","123","Цифровой товар")),
        ("Проблема",buyer_message("problem","Покупатель","123","Цифровой товар"))
    ]
    for title,body in examples: await m.answer(f"<b>{title}</b>\n<pre>{body}</pre>")

# CSV market analysis
@router.message(Command("importcsv"))
async def import_csv_help(m:Message):
    if not is_admin(m.from_user.id):return await denied(m)
    await m.answer("Отправьте CSV документом. Заголовки: title,price,category; опционально url,source,notes.")
@router.message(F.document)
async def csv_file(m:Message,bot,db):
    if not is_admin(m.from_user.id):return await denied(m)
    if not m.document.file_name.lower().endswith(".csv"):return
    if m.document.file_size and m.document.file_size>2_000_000:return await m.answer("Файл больше 2 МБ.")
    f=await bot.get_file(m.document.file_id);buf=io.BytesIO();await bot.download_file(f.file_path,buf)
    try: rows=parse_csv(buf.getvalue())
    except Exception as e:return await m.answer(f"Ошибка CSV: {e}")
    if not rows:return await m.answer("Подходящих строк нет.")
    async with await db.connect() as conn:
        await conn.executemany("INSERT INTO market_rows(title,category,price,url,source,notes) VALUES(?,?,?,?,?,?)",rows)
        await conn.commit()
    await db.log("csv_import","market",None,f"rows={len(rows)}")
    await m.answer(f"Импортировано {len(rows)} предложений. Сводка: /market")
@router.message(Command("market"))
async def market(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    rows=await db.all("SELECT category,COUNT(*) n,AVG(price) avgp,MIN(price) minp,MAX(price) maxp FROM market_rows GROUP BY category ORDER BY n DESC")
    if not rows:return await m.answer("Нет данных. Используйте /importcsv.")
    lines=["<b>Рыночная сводка из CSV</b>"]
    for r in rows:lines.append(f"{r['category']}: {r['n']} шт.; средняя {r['avgp']:.2f} ₽; диапазон {r['minp']:.2f}–{r['maxp']:.2f} ₽")
    lines.append("Это цены предложений из файла, не доказательство продаж.")
    await m.answer("\n".join(lines))

@router.message(Command("report"))
async def report(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    products=await db.one("SELECT COUNT(*) n,COALESCE(SUM(stock*cost),0) value FROM products WHERE active=1")
    orders=await db.all("SELECT * FROM orders WHERE status='done'")
    revenue=sum(o["amount"] for o in orders); costs=sum(o["cost"] for o in orders)
    deals=await db.one("SELECT COUNT(*) n FROM deals WHERE status='approved_by_owner'")
    drafts=await db.one("SELECT COUNT(*) n FROM drafts WHERE status='approved_by_owner'")
    await m.answer(
        "<b>Отчёт магазина</b>\n"
        f"Товаров в каталоге: {products['n']}\nОценка стоимости склада: {products['value']:.2f} ₽\n"
        f"Завершённых заказов: {len(orders)}\nВыручка по завершённым заказам: {revenue:.2f} ₽\n"
        f"Себестоимость: {costs:.2f} ₽\nРезультат до комиссий: {revenue-costs:.2f} ₽\n"
        f"Одобрено закупочных предложений: {deals['n']}\nОдобрено черновиков: {drafts['n']}\n\n"
        "Учитываются только заказы, которые вы вручную отметили завершёнными."
    )

@router.message(Command("export"))
async def export(m:Message,db):
    if not is_admin(m.from_user.id):return await denied(m)
    rows=await db.all("SELECT id,external_id,buyer,product_title,amount,cost,status,created_at FROM orders ORDER BY id")
    buf=io.StringIO();w=csv.writer(buf);w.writerow(["id","external_id","buyer","product_title","amount","cost","status","created_at"])
    for r in rows:w.writerow(list(r))
    data=BufferedInputFile(buf.getvalue().encode("utf-8-sig"), filename="orders_export.csv")
    await m.answer_document(data,caption="Экспорт локального журнала заказов.")
