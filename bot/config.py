"""Configuración por variables de entorno (patrón del ecosistema terremoto)."""
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

DESAPARECIDOS_API_URL = (
    os.getenv("DESAPARECIDOS_API_URL")
    or "http://desaparecidos-web.desaparecidos.svc.cluster.local:8780"
).rstrip("/")

WEB_PUBLIC_URL = (
    os.getenv("WEB_PUBLIC_URL") or "https://busqueda.ayudavenezuela.online"
).rstrip("/")

TG_MODE = os.getenv("TG_MODE", "polling").lower()
WEBHOOK_BASE = (os.getenv("WEBHOOK_BASE") or "").rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/tg/webhook")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8081"))

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
RESULTS_PER_PAGE = int(os.getenv("RESULTS_PER_PAGE", "5"))
RATE_PER_MIN = int(os.getenv("RATE_PER_MIN", "15"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
