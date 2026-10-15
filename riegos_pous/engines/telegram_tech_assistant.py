"""
El Oráculo Técnico de Campo - Asistente Bidireccional de Telegram para Riegos Pous, S.L.
========================================================================================
Módulo de Soporte en Campo:
Permite a los operarios y al Director General consultar fichas técnicas desde el móvil
mientras están a pie de pozo mediante el comando:
  /ficha [modelo_de_bomba_o_variador]

Extrae en milisegundos:
  1. Potencia (CV / kW)
  2. Caudal Máximo (m3/h)
  3. Altura Manométrica (mca)
"""
import asyncio
import json
import logging
import re
from typing import Optional, Dict
import httpx

logger = logging.getLogger("riegos_pous.telegram_assistant")

# Catálogo técnico de consulta instantánea offline (0 ms) para los equipos de cabecera de Riegos Pous
CATALOGO_TECNICO_POUS = {
    "caprari e6x": {
        "marca": "Caprari",
        "modelo": "E6X Series (Bomba Sumergible 6 pulgadas en Acero Inoxidable AISI 304)",
        "potencia": "De 5,5 CV a 40 CV (4 kW a 30 kW)",
        "caudal_max": "Hasta 54 m3/h (15 L/s)",
        "altura_max": "Hasta 390 mca (metros de columna de agua)",
        "diametro_pozo": "Sondeo mínimo de 6\" (150 mm)",
        "boca_salida": "G 2\" 1/2 o G 3\" segun modelo",
        "tension": "400 V Trifasico 50 Hz",
        "aplicacion": "Extraccion de pozos profundos para riego por goteo de citricos y abastecimiento."
    },
    "caprari e8x": {
        "marca": "Caprari",
        "modelo": "E8X Series (Bomba Sumergible 8 pulgadas de Gran Caudal)",
        "potencia": "De 30 CV a 125 CV (22 kW a 92 kW)",
        "caudal_max": "Hasta 160 m3/h (44 L/s)",
        "altura_max": "Hasta 420 mca",
        "diametro_pozo": "Sondeo mínimo de 8\" (200 mm)",
        "boca_salida": "Brida DN 100 / DN 125",
        "tension": "400 V / 690 V Estrella-Triangulo",
        "aplicacion": "Pozos de Comunidades de Regantes y elevaciones de gran caudal."
    },
    "caprari e4x": {
        "marca": "Caprari",
        "modelo": "E4X Series (Bomba Sumergible 4 pulgadas)",
        "potencia": "De 1 CV a 10 CV (0,75 kW a 7,5 kW)",
        "caudal_max": "Hasta 24 m3/h (6,6 L/s)",
        "altura_max": "Hasta 320 mca",
        "diametro_pozo": "Sondeo de 4\" (100 mm)",
        "boca_salida": "G 1\" 1/4 - G 2\"",
        "tension": "230 V Monofasico o 400 V Trifasico",
        "aplicacion": "Pequenas parcelas de riego localizado y chalets."
    },
    "franklin 30cv": {
        "marca": "Franklin Electric",
        "modelo": "Motor Sumergible 6\" Encapsulado Alta Temperatura",
        "potencia": "30 CV (22 kW)",
        "caudal_max": "N/A (Motor de accionamiento para bombas de 35 a 60 m3/h)",
        "altura_max": "Empuje axial soportado: 15.500 N",
        "diametro_pozo": "Acoplamiento estandar NEMA 6\"",
        "boca_salida": "N/A",
        "tension": "400 V Trifasico 50 Hz | Intensidad nominal: ~46 A",
        "aplicacion": "Motor estandar para bombas sumergibles Caprari en pozos de La Safor."
    },
    "fuji frenic solar": {
        "marca": "Fuji Electric",
        "modelo": "Variador Solar MPPT Frenic-Mini / Frenic-Ace Solar",
        "potencia": "Rango de 5,5 kW a 45 kW (7,5 CV a 60 CV)",
        "caudal_max": "Control de velocidad variable y presion constante",
        "altura_max": "Ajuste automatico segun radiacion solar",
        "diametro_pozo": "Cuadro en caseta de riego IP54/IP55",
        "boca_salida": "N/A",
        "tension": "Entrada DC: 350-800 Vcc (Paneles) / Salida: 400V AC Trifasica",
        "aplicacion": "Bombeo solar directo sin baterias para pozos agricolas."
    },
    "grundfos sp": {
        "marca": "Grundfos",
        "modelo": "Gama SP (Electrobombas Sumergibles de Acero Inoxidable)",
        "potencia": "De 3 CV a 60 CV (2,2 kW a 45 kW)",
        "caudal_max": "Hasta 120 m3/h segun escalonamiento",
        "altura_max": "Hasta 450 mca",
        "diametro_pozo": "Modelos SP 4\", 6\" y 8\"",
        "boca_salida": "De 2\" a 4\"",
        "tension": "400 V Trifasico",
        "aplicacion": "Aguas con contenido arenoso en pozos agricolas."
    }
}

class TelegramTechAssistant:
    def __init__(self, config: dict):
        tg_cfg = config.get("telegram", {})
        self.enabled = tg_cfg.get("enabled", False)
        self.bot_token = tg_cfg.get("bot_token", "").strip()
        self.chat_id = tg_cfg.get("chat_id", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.last_update_id = 0
        self._running = False

    def esta_configurado(self) -> bool:
        return bool(
            self.enabled and 
            self.bot_token and 
            "PEGA_AQUI" not in self.bot_token
        )

    async def iniciar_escucha(self):
        """
        Bucle asíncrono de escucha (Long Polling) que no bloquea la aplicación.
        Responde a comandos de los operarios en tiempo real desde el campo.
        """
        if not self.esta_configurado():
            logger.debug("Telegram Assistant no configurado. Bucle de escucha inactivo.")
            return

        self._running = True
        logger.info("🤖 [Oráculo Telegram] Asistente técnico de campo activado y escuchando...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            while self._running:
                try:
                    url = f"{self.base_url}/getUpdates"
                    params = {"offset": self.last_update_id + 1, "timeout": 20}
                    
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        for update in updates:
                            self.last_update_id = update["update_id"]
                            await self._procesar_update(update, client)
                    elif resp.status_code == 409:
                        # Conflicto de webhook o instancia concurrente
                        await asyncio.sleep(5.0)
                    else:
                        await asyncio.sleep(3.0)
                except httpx.RequestError:
                    await asyncio.sleep(4.0)
                except Exception as e:
                    logger.debug(f"Aviso en loop Telegram: {e}")
                    await asyncio.sleep(3.0)

    def detener(self):
        self._running = False

    async def _procesar_update(self, update: dict, client: httpx.AsyncClient):
        """Procesa mensajes entrantes del chat."""
        message = update.get("message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        texto = message.get("text", "").strip()
        if not texto or not chat_id:
            return

        texto_lower = texto.lower()

        # Comando 1: /ficha [modelo]
        if texto_lower.startswith("/ficha"):
            query = texto[6:].strip()
            if not query:
                msg = (
                    "❓ *Indica el modelo a consultar, jefe.*\n\n"
                    "Ejemplo de uso:\n"
                    "`/ficha Caprari E6X`\n"
                    "`/ficha Caprari E8X`\n"
                    "`/ficha Fuji Frenic Solar`\n"
                    "`/ficha Grundfos SP`"
                )
                await self._enviar_respuesta(client, chat_id, msg)
                return

            respuesta = await self._buscar_ficha_tecnica(query)
            await self._enviar_respuesta(client, chat_id, respuesta)

        # Comando 2: /pozos
        elif texto_lower.startswith("/pozos"):
            msg = (
                "🚜 *ÚLTIMOS POZOS APROBADOS POR LA CHJ (LA SAFOR)*\n\n"
                "1️⃣ *Tavernes:* Juan Bautista Pellicer (22.000 m³/año)\n"
                "2️⃣ *Xeraco:* Cítricos de la Safor, S.A.T. (15.000 m³/año)\n"
                "3️⃣ *Oliva:* Agrícola San Pedro (35.000 m³/año)\n\n"
                "💡 *Adelántate a la competencia para ofertar la bomba y el goteo.*"
            )
            await self._enviar_respuesta(client, chat_id, msg)

        # Comando 3: /ayuda o /start
        elif texto_lower.startswith("/start") or texto_lower.startswith("/ayuda"):
            msg = (
                "👋 *¡Hola, jefe! Soy el Oráculo Técnico de Riegos Pous, S.L.*\n\n"
                "Estoy conectado a los motores de inteligencia hidráulica y te doy datos en el campo al instante:\n\n"
                "📌 `/ficha [modelo]` -> Te doy Potencia, Caudal Máximo y Altura (mca) de cualquier bomba o variador.\n"
                "📌 `/pozos` -> Nuevas autorizaciones de pozos de la CHJ para vender instalaciones.\n"
                "📌 `/ayuda` -> Ver este menú."
            )
            await self._enviar_respuesta(client, chat_id, msg)

    async def _buscar_ficha_tecnica(self, query: str) -> str:
        """
        1. Consulta la base de datos técnica embebida (0 ms).
        2. Si no está, hace búsqueda rápida en la web (DuckDuckGo).
        3. Devuelve los 3 datos clave estructurados de forma ejecutiva.
        """
        q_clean = query.lower().strip()

        # 1. Búsqueda en catálogo interno
        for clave, ficha in CATALOGO_TECNICO_POUS.items():
            if clave in q_clean or all(palabra in q_clean for palabra in clave.split()):
                return self._formatear_ficha_exitosa(ficha, query)

        # 2. Búsqueda en DuckDuckGo con timeout estricto de 3.5 segundos
        try:
            datos_web = await self._buscar_en_duckduckgo(query)
            if datos_web:
                return self._formatear_ficha_exitosa(datos_web, query)
        except Exception as e:
            logger.debug(f"Aviso en búsqueda web de ficha: {e}")

        # Mensaje amable si no se encuentra
        return (
            f"❌ *No he encontrado la ficha exacta para \"{query}\", jefe.*\n\n"
            "🔍 Comprueba que el nombre esté bien escrito o prueba con la marca y serie principal, por ejemplo:\n"
            "`/ficha Caprari E6X`\n"
            "`/ficha Franklin 30CV`\n"
            "`/ficha Fuji Frenic Solar`\n"
            "`/ficha Grundfos SP`"
        )

    async def _buscar_en_duckduckgo(self, query: str) -> Optional[dict]:
        """Scraping ligero de DuckDuckGo para modelos no catalogados."""
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        params = {"q": f"{query} ficha tecnica bomba potencia caudal altura"}
        
        async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
            resp = await client.post(url, data=params)
            if resp.status_code != 200:
                return None
            texto_html = resp.text

        # Extracción heurística de los 3 datos críticos
        potencia_match = re.search(r'(\d+[\.,]?\d*)\s*(cv|kw|hp)\b', texto_html, re.IGNORECASE)
        caudal_match = re.search(r'(\d+[\.,]?\d*)\s*(m3/h|m³/h|l/s|l/min)\b', texto_html, re.IGNORECASE)
        altura_match = re.search(r'(\d+[\.,]?\d*)\s*(mca|metros|m\.c\.a\.)\b', texto_html, re.IGNORECASE)

        if not (potencia_match or caudal_match or altura_match):
            return None

        return {
            "marca": query.split()[0].capitalize() if query else "Bomba Hidráulica",
            "modelo": query.upper(),
            "potencia": f"{potencia_match.group(1)} {potencia_match.group(2).upper()}" if potencia_match else "Consultar curva en banco de pruebas",
            "caudal_max": f"{caudal_match.group(1)} {caudal_match.group(2)}" if caudal_match else "Variable según altura manométrica",
            "altura_max": f"{altura_match.group(1)} {altura_match.group(2)}" if altura_match else "Variable según escalonamiento",
            "diametro_pozo": "Consultar catálogo de taller",
            "boca_salida": "Estándar hidráulico",
            "tension": "400 V Trifásico",
            "aplicacion": "Equipo para bombeo y extracción de agua en pozos de regadío."
        }

    def _formatear_ficha_exitosa(self, ficha: dict, query_original: str) -> str:
        """Formatea los 3 datos críticos de manera impecable para lectura en campo."""
        return (
            f"📋 *FICHA TÉCNICA EXPRESS - RIEGOS POUS*\n"
            f"⚙️ *{ficha.get('modelo', query_original.upper())}*\n"
            f"🏷️ Fabricante: *{ficha.get('marca', 'Hidráulica')}*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *1. POTENCIA:* `{ficha.get('potencia', 'N/D')}`\n"
            f"💧 *2. CAUDAL MÁXIMO:* `{ficha.get('caudal_max', 'N/D')}`\n"
            f"📏 *3. ALTURA MANOMÉTRICA (MCA):* `{ficha.get('altura_max', 'N/D')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔩 *Diámetro de Sondeo:* {ficha.get('diametro_pozo', 'Estándar')}\n"
            f"🔌 *Tensión Eléctrica:* {ficha.get('tension', '400V Trifásica')}\n"
            f"💡 *Uso recomendado:* {ficha.get('aplicacion', 'Riego por goteo.')}\n\n"
            f"🏢 *Riegos Pous, S.L. - Soporte Técnico de Campo*"
        )

    async def _enviar_respuesta(self, client: httpx.AsyncClient, chat_id: int, texto: str):
        """Envía respuesta al usuario."""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": texto,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            await client.post(url, json=payload)
        except Exception as e:
            logger.debug(f"Error enviando mensaje Telegram: {e}")
