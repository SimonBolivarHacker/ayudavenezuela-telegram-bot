"""Handlers de aiogram: /start, /buscar, texto libre y callbacks."""
import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from . import config, formatting
from .api_client import DesaparecidosAPI
from .ratelimit import RateLimiter

log = logging.getLogger("desap_bot.handlers")
router = Router()

# Estado mínimo de paginación por chat: chat_id -> {"term", "items", "page"}.
_SESSIONS: dict[int, dict] = {}

_CAPTION_MAX = 1024

WELCOME = (
    "🕊️ <b>Buscador de personas desaparecidas — Venezuela</b>\n\n"
    "Escríbeme el <b>nombre y apellido</b>, o la <b>cédula</b>, de la persona que "
    "estás buscando y te muestro las fichas que tenemos registradas.\n\n"
    "También puedes usar <code>/buscar &lt;nombre&gt;</code>."
)


def _results_keyboard(items: list, page: int, per_page: int) -> InlineKeyboardMarkup:
    start = page * per_page
    rows: list[list[InlineKeyboardButton]] = []
    for it in items[start:start + per_page]:
        nombre = (it.get("nombre_completo") or "Ver ficha")[:40]
        rows.append([InlineKeyboardButton(text=f"👤 {nombre}", callback_data=f"ficha:{it['uid']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Anterior", callback_data="pg:prev"))
    if start + per_page < len(items):
        nav.append(InlineKeyboardButton(text="Siguiente ▶", callback_data="pg:next"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_page(session: dict):
    items, page, per = session["items"], session["page"], config.RESULTS_PER_PAGE
    start = page * per
    total = len(items)
    header = f"Encontré <b>{total}</b> ficha(s) para «{escape(session['term'])}»"
    if total > per:
        header += f" — mostrando {start + 1}-{min(start + per, total)}"
    body = "\n\n".join(formatting.result_line(it) for it in items[start:start + per])
    return f"{header}\n\n{body}\n\nToca una persona para ver su ficha 👇", _results_keyboard(items, page, per)


async def _do_search(message: Message, term: str, api: DesaparecidosAPI, limiter: RateLimiter):
    if not limiter.allow(message.from_user.id):
        await message.answer("Estás buscando muy rápido 🙏 espera unos segundos e intenta de nuevo.")
        return
    term = (term or "").strip()
    if len(term) < 2:
        await message.answer("Escríbeme al menos 2 letras del nombre, o la cédula 🙏")
        return

    results = await api.search(term)
    if results is None:
        await message.answer("Ahora mismo tenemos mucha demanda 😔 intenta de nuevo en un momento.")
        return
    if not results:
        await message.answer(
            f"No encontré fichas para «{escape(term)}». "
            "Prueba con otra forma del nombre o revisa la ortografía."
        )
        return

    session = {"term": term, "items": results, "page": 0}
    _SESSIONS[message.chat.id] = session
    text, kb = _render_page(session)
    await message.answer(text, reply_markup=kb, disable_web_page_preview=True)


@router.message(CommandStart())
async def on_start(message: Message):
    await message.answer(WELCOME)


@router.message(Command("buscar"))
async def on_buscar(message: Message, command: CommandObject, api: DesaparecidosAPI, limiter: RateLimiter):
    await _do_search(message, command.args or "", api, limiter)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, api: DesaparecidosAPI, limiter: RateLimiter):
    await _do_search(message, message.text, api, limiter)


@router.callback_query(F.data.in_({"pg:next", "pg:prev"}))
async def on_page(cb: CallbackQuery):
    session = _SESSIONS.get(cb.message.chat.id)
    if not session:
        await cb.answer("La búsqueda expiró, envíamela de nuevo 🙏", show_alert=True)
        return
    per = config.RESULTS_PER_PAGE
    if cb.data == "pg:next" and (session["page"] + 1) * per < len(session["items"]):
        session["page"] += 1
    elif cb.data == "pg:prev" and session["page"] > 0:
        session["page"] -= 1
    text, kb = _render_page(session)
    try:
        await cb.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:  # p.ej. "message is not modified"
        log.debug("edit_text ignorado: %s", e)
    await cb.answer()


@router.callback_query(F.data.startswith("ficha:"))
async def on_ficha(cb: CallbackQuery, api: DesaparecidosAPI, limiter: RateLimiter):
    if not limiter.allow(cb.from_user.id):
        await cb.answer("Espera un momento e intenta de nuevo 🙏", show_alert=True)
        return
    uid = cb.data.split(":", 1)[1]
    await cb.answer("Cargando ficha…")

    detail = await api.detail(uid)
    if not detail:
        await cb.message.answer("No pude cargar esa ficha 😔 intenta de nuevo en un momento.")
        return

    text = formatting.render_ficha(detail)
    # Web App: la ficha se abre dentro de Telegram (webview), sin sacar a la
    # persona de la app. Requiere URL https (la tenemos) y solo funciona en
    # botones inline de chats privados, que es como se usa este bot.
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🌐 Ver ficha completa",
            web_app=WebAppInfo(url=formatting.ficha_url(uid)),
        ),
    ]])

    photo = await api.fetch_photo(detail.get("foto"))
    if photo and len(text) <= _CAPTION_MAX:
        try:
            await cb.message.answer_photo(
                BufferedInputFile(photo, filename="foto.jpg"), caption=text, reply_markup=kb
            )
            return
        except Exception as e:
            log.info("answer_photo falló, fallback a texto: %s", e)

    await cb.message.answer(text, reply_markup=kb, disable_web_page_preview=True)
