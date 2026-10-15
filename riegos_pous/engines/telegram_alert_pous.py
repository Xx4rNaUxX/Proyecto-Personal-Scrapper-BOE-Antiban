"""
Centro de Mando en el Bolsillo - Alertas de Telegram para Riegos Pous, S.L.
=============================================================================
Módulo de Movilidad:
Envía notificaciones ejecutivas al móvil del Director General en tiempo real
cuando se detectan subvenciones del DOGV, chollos de bombas o subastas clave.
"""
import logging
from typing import Optional
import httpx

from core.models import Alerta, Prioridad, Vector

logger = logging.getLogger("riegos_pous.telegram")

class TelegramAlertPous:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        tg_cfg = cfg.get("telegram", {})
        self.enabled = tg_cfg.get("enabled", False)
        self.bot_token = tg_cfg.get("bot_token", "").strip()
        self.chat_id = tg_cfg.get("chat_id", "").strip()
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def esta_configurado(self) -> bool:
        """Verifica si las credenciales de Telegram están configuradas."""
        return bool(
            self.enabled and 
            self.bot_token and 
            self.chat_id and 
            "PEGA_AQUI" not in self.bot_token
        )

    async def enviar_alerta(self, alerta: Alerta) -> bool:
        """
        Envía un mensaje formateado al móvil del jefe.
        Filtra para enviar solo oportunidades de prioridad ALTA o CRÍTICA.
        Nunca bloquea ni propaga excepciones al orquestador.
        """
        if not self.esta_configurado():
            logger.debug("Telegram no configurado o inactivo. Notificación en móvil omitida.")
            return False

        if alerta.prioridad not in (Prioridad.CRITICA, Prioridad.ALTA):
            return False

        mensaje = self._formatear_mensaje(alerta)
        
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": mensaje,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(self.api_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"📱 [Telegram Pous] Alerta enviada con éxito al móvil del jefe: {alerta.titulo[:40]}")
                    return True
                else:
                    logger.warning(f"Aviso Telegram API: {resp.status_code} - {resp.text}")
                    return False
        except Exception as e:
            logger.warning(f"No se pudo enviar la alerta de Telegram: {e}")
            return False

    def _formatear_mensaje(self, alerta: Alerta) -> str:
        """Genera el texto con formato markdown optimizado para lectura en smartphone."""
        icono_prio = "🔴 *[CRÍTICA]*" if alerta.prioridad == Prioridad.CRITICA else "🟠 *[ALTA PRIORIDAD]*"
        
        # 1. Subvención DOGV / Generalitat
        if alerta.vector == Vector.DOGV:
            return (
                f"🏛️ *NUEVA SUBVENCIÓN GENERALITAT (DOGV)* {icono_prio}\n\n"
                f"*{alerta.titulo}*\n\n"
                f"💰 *Dotación / Financiación:* {alerta.valor_estimado:,.0f} €\n"
                f"{alerta.resumen}\n\n"
                f"👉 [Ver Convocatoria Oficial en DOGV]({alerta.url})\n"
                f"🏢 *Riegos Pous, S.L. - Sistema de Inteligencia*"
            )

        # 2. Suministros y Bombas en Liquidación
        elif alerta.vector == Vector.BOPI:
            return (
                f"📦 *CHOLLO DE SUMINISTROS / BOMBAS DETECTADO* {icono_prio}\n\n"
                f"*{alerta.titulo}*\n\n"
                f"💰 *Precio Liquidación:* {alerta.valor_estimado:,.2f} €\n"
                f"{alerta.resumen}\n\n"
                f"👉 [Enlace a Subasta Oficial]({alerta.url})\n"
                f"🏢 *Riegos Pous, S.L. - Radar de Stocks*"
            )

        # 3. Subastas BOE Fincas con Pozo
        elif alerta.vector == Vector.CONCURSAL:
            return (
                f"🚜 *SUBASTA BOE - FINCA CON POZO / MAQUINARIA* {icono_prio}\n\n"
                f"*{alerta.titulo}*\n\n"
                f"💰 *Valor estimado:* {alerta.valor_estimado:,.2f} €\n"
                f"{alerta.resumen}\n\n"
                f"👉 [Ficha Oficial del BOE]({alerta.url})\n"
                f"🏢 *Riegos Pous, S.L. - Radar Territorial*"
            )

        # 4. Licitaciones Públicas
        else:
            return (
                f"💧 *LICITACIÓN PÚBLICA HIDRÁULICA* {icono_prio}\n\n"
                f"*{alerta.titulo}*\n\n"
                f"💰 *Presupuesto Base:* {alerta.valor_estimado:,.2f} €\n"
                f"{alerta.resumen}\n\n"
                f"👉 [Expediente Oficial]({alerta.url})\n"
                f"🏢 *Riegos Pous, S.L.*"
            )

    async def enviar_mensaje_directo(self, texto: str) -> bool:
        """Permite enviar cualquier notificación o parte urgente al móvil del jefe."""
        if not self.esta_configurado():
            return False
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": texto,
                "parse_mode": "Markdown"
            }
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.post(self.api_url, json=payload)
                return r.status_code == 200
        except Exception:
            return False
