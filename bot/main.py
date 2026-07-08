"""Arranque del bot. Modo polling por defecto (sin ingress); webhook opcional."""
import logging

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # en producción la config viene por env, no hace falta .env
    pass

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from . import config
from .api_client import DesaparecidosAPI
from .handlers import router
from .ratelimit import RateLimiter


async def _run_webhook(bot: Bot, dp: Dispatcher, **data):
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    if config.WEBHOOK_BASE:
        await bot.set_webhook(config.WEBHOOK_BASE + config.WEBHOOK_PATH, drop_pending_updates=True)
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot, **data)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=config.WEBHOOK_PORT)
    await site.start()
    await asyncio.Event().wait()


async def _amain():
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("desap_bot")

    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN no configurado")

    bot = Bot(config.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    api = DesaparecidosAPI()
    limiter = RateLimiter(config.RATE_PER_MIN)
    log.info("Bot iniciando en modo %s (API=%s)", config.TG_MODE, config.DESAPARECIDOS_API_URL)

    try:
        if config.TG_MODE == "webhook":
            await _run_webhook(bot, dp, api=api, limiter=limiter)
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, api=api, limiter=limiter)
    finally:
        await api.aclose()
        await bot.session.close()


def main():
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
