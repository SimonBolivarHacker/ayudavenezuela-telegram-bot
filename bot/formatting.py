"""Formateo de mensajes (funciones puras, testeables sin red).

UX pensada para familiares en situación de estrés: cálida, clara y concisa.
No se vuelca información interna (grafos, scores, ids) ni se sobrecarga al usuario.
"""
from html import escape

from . import config

_ESTADO = {
    "buscado": "🔴 En búsqueda",
    "encontrado": "🟢 Encontrada",
    "hospitalizado": "🏥 Hospitalizada",
    "sin_dato": "⚪ Sin novedad",
}
_SEXO = {"M": "Hombre", "F": "Mujer", "X": "—"}


def _edad(edad) -> str:
    return f"{edad} años" if edad else "edad no indicada"


def _sexo(sexo) -> str:
    return _SEXO.get((sexo or "").upper(), "—")


def estado_badge(estado, posiblemente_resuelto: bool = False) -> str:
    base = _ESTADO.get((estado or "").lower(), "⚪ Sin novedad")
    if posiblemente_resuelto:
        base += " · <i>posible novedad</i>"
    return base


def _fuentes_unicas(reportes) -> list[str]:
    """Fuentes humanizadas (ya vienen humanizadas de la API), deduplicadas
    conservando el orden de aparición."""
    out: list[str] = []
    for r in reportes or []:
        f = r.get("fuente")
        if f and f not in out:
            out.append(f)
    return out


def result_line(item: dict) -> str:
    """Línea compacta de un resultado de búsqueda."""
    nombre = escape(item.get("nombre_completo") or "Sin nombre")
    partes = [f"👤 <b>{nombre}</b>"]
    meta = []
    if item.get("edad"):
        meta.append(_edad(item["edad"]))
    if item.get("sexo"):
        meta.append(_sexo(item["sexo"]))
    if meta:
        partes.append("   " + " · ".join(meta))
    ubic = item.get("posible_ubicacion")
    if ubic:
        partes.append(f"   📍 {escape(ubic)}")
    extra = f"   🔎 {item.get('n_reportes') or 0} reporte(s)"
    if item.get("posiblemente_resuelto"):
        extra += " · ⚠️ posible novedad"
    partes.append(extra)
    return "\n".join(partes)


def render_ficha(detail: dict) -> str:
    """Ficha concisa de una persona. Solo datos públicos y útiles para ubicarla."""
    nombre = escape(detail.get("nombre_completo") or "Sin nombre")
    lines = [
        f"👤 <b>{nombre}</b>",
        estado_badge(detail.get("estado"), detail.get("posiblemente_resuelto")),
    ]

    meta = []
    if detail.get("edad"):
        meta.append(_edad(detail["edad"]))
    if detail.get("sexo"):
        meta.append(_sexo(detail["sexo"]))
    if meta:
        lines.append(" · ".join(meta))

    ubic = detail.get("ubicacion") or {}
    if ubic.get("texto"):
        lines.append(f"📍 {escape(ubic['texto'])}")
        otras = [escape(o) for o in (ubic.get("otras") or []) if o][:2]
        if otras:
            lines.append("   también reportada en: " + ", ".join(otras))

    lines.append(f"🔎 {detail.get('n_reportes') or 0} reporte(s)")
    fuentes = _fuentes_unicas(detail.get("reportes"))
    if fuentes:
        lines.append("🗂 Fuentes: " + escape(", ".join(fuentes)))

    conns = detail.get("conexiones") or []
    if any(c.get("estado_operativo") in ("encontrado", "hospitalizado") for c in conns):
        lines.append(
            "\n⚠️ <b>Posible coincidencia con un caso ya localizado.</b> "
            "Revisa la ficha completa en la web."
        )

    lines.append(
        "\n🙏 Si tienes información sobre esta persona, repórtalo en la plataforma."
    )
    return "\n".join(lines)


def ficha_url(uid: str) -> str:
    return f"{config.WEB_PUBLIC_URL}/?uid={uid}"


def reportar_url() -> str:
    """Formulario para reportar a una persona como localizada. Por ahora solo
    abre el form; más adelante se puede enlazar a una ficha con parámetros."""
    return f"{config.WEB_PUBLIC_URL}/reportar.html"
