import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from database import Database
from handlers import router

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not settings.token or "ВСТАВЬТЕ" in settings.token:
        raise RuntimeError("Заполните TELEGRAM_BOT_TOKEN в .env")
    if settings.admin_id <= 0:
        raise RuntimeError("Заполните ADMIN_ID числовым Telegram ID")
    db = Database(settings.db_path)
    await db.initialize()
    bot = Bot(settings.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, db=db)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
