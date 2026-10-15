"""
Core - Sistema de notificaciones (Telegram, Email, Console).
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from core.models import Alerta, Prioridad

logger = logging.getLogger("arbitraje.notifier")

# Emojis por prioridad para Telegram
_EMOJI = {
    Prioridad.CRITICA: "🔴",
    Prioridad.ALTA: "🟠",
    Prioridad.MEDIA: "🟡",
    Prioridad.BAJA: "🟢",
}

_VECTOR_NAMES = {
    "placsp": "📋 Licitación Desierta",
    "bopi": "™️ Marca Caducada",
    "concursal": "⚖️ Lote Concursal",
}


class Notifier:
    """Envía notificaciones por múltiples canales."""

    def __init__(self, config: dict):
        self.tg_config = config.get("telegram", {})
        self.email_config = config.get("email", {})

    async def notificar(self, alerta: Alerta):
        """Envía notificación por todos los canales habilitados."""
        tasks = [self._log_console(alerta)]

        if self.tg_config.get("enabled"):
            tasks.append(self._enviar_telegram(alerta))
        if self.email_config.get("enabled"):
            tasks.append(self._enviar_email(alerta))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _log_console(self, alerta: Alerta):
        """Log en consola con formato legible."""
        emoji = _EMOJI.get(alerta.prioridad, "⚪")
        vector_name = _VECTOR_NAMES.get(alerta.vector.value, alerta.vector.value)
        logger.info(
            f"\n{'='*60}\n"
            f"{emoji} {vector_name}\n"
            f"  Título: {alerta.titulo}\n"
            f"  Valor:  {alerta.valor_estimado:,.0f} €\n"
            f"  Score:  {alerta.viabilidad_score:.0%}\n"
            f"  URL:    {alerta.url}\n"
            f"{'='*60}"
        )

    async def _enviar_telegram(self, alerta: Alerta):
        """Envía mensaje a Telegram."""
        token = self.tg_config.get("bot_token", "")
        chat_id = self.tg_config.get("chat_id", "")
        if not token or not chat_id:
            return

        emoji = _EMOJI.get(alerta.prioridad, "⚪")
        vector_name = _VECTOR_NAMES.get(alerta.vector.value, alerta.vector.value)

        text = (
            f"{emoji} *{vector_name}*\n\n"
            f"*{alerta.titulo}*\n\n"
            f"{alerta.resumen}\n\n"
            f"💰 Valor estimado: *{alerta.valor_estimado:,.0f} €*\n"
            f"📊 Viabilidad: *{alerta.viabilidad_score:.0%}*\n"
        )
        if alerta.url:
            text += f"\n🔗 [Ver detalle]({alerta.url})"

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                })
        except Exception as e:
            logger.error(f"Error enviando Telegram: {e}")

    async def _enviar_email(self, alerta: Alerta):
        """Envía email de notificación."""
        cfg = self.email_config
        if not cfg.get("smtp_host"):
            return

        emoji = _EMOJI.get(alerta.prioridad, "⚪")
        vector_name = _VECTOR_NAMES.get(alerta.vector.value, alerta.vector.value)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{emoji} [{vector_name}] {alerta.titulo}"
        msg["From"] = cfg["username"]
        msg["To"] = cfg["to_address"]

        html = f"""
        <html><body style="font-family: sans-serif; padding: 20px;">
        <h2>{emoji} {vector_name}</h2>
        <h3>{alerta.titulo}</h3>
        <p>{alerta.resumen}</p>
        <table style="border-collapse: collapse;">
            <tr><td style="padding: 5px;"><b>Valor estimado:</b></td>
                <td style="padding: 5px;">{alerta.valor_estimado:,.0f} €</td></tr>
            <tr><td style="padding: 5px;"><b>Viabilidad:</b></td>
                <td style="padding: 5px;">{alerta.viabilidad_score:.0%}</td></tr>
        </table>
        {"<p><a href='" + alerta.url + "'>Ver detalle →</a></p>" if alerta.url else ""}
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg, cfg)
        except Exception as e:
            logger.error(f"Error enviando email: {e}")

    def _send_smtp(self, msg: MIMEMultipart, cfg: dict):
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.send_message(msg)
