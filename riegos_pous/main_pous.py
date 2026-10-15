"""
RIEGOS POUS, S.L. - Orquestador Principal v2.2
Punto de entrada para el sistema de inteligencia de negocio, licitaciones y subastas.
====================================================================================
"""
import sys
from pathlib import Path
from datetime import datetime
import asyncio
import logging
import yaml
import uvicorn
import webbrowser
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Añadir raíz al PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from core.storage import Storage
from core.http_client import HttpClient
from core.notifier import Notifier
from riegos_pous.engines.placsp_pous_engine import PlacspPousEngine
from riegos_pous.engines.boe_pous_engine import BoePousEngine
from riegos_pous.engines.supplies_pous_engine import SuppliesPousEngine
from riegos_pous.engines.dogv_pous_engine import DogvPousEngine
from riegos_pous.engines.chj_bop_engine import ChjBopEngine
from riegos_pous.engines.telegram_alert_pous import TelegramAlertPous
from riegos_pous.engines.telegram_tech_assistant import TelegramTechAssistant

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("riegos_pous.main")

async def run_pous_scans(config: dict, http: HttpClient, storage: Storage, notifier: Notifier):
    logger.info("💧 === Iniciando escaneo de oportunidades para RIEGOS POUS, S.L. ===")
    
    # Notificador a Telegram para el móvil del Director General
    telegram_bot = TelegramAlertPous(config)

    motores = [
        PlacspPousEngine(config, http, storage, notifier),
        BoePousEngine(config, http, storage, notifier),
        SuppliesPousEngine(config, http, storage, notifier),
        DogvPousEngine(config, http, storage, notifier),
        ChjBopEngine(config, http, storage, notifier),
    ]
    
    await asyncio.gather(
        *[motor.run() for motor in motores],
        return_exceptions=True
    )

    # Notificar alertas críticas pendientes al móvil si Telegram está activo
    if telegram_bot.esta_configurado():
        alertas_recientes = await storage.listar_alertas(limite=5)
        for al_dict in alertas_recientes:
            from core.models import Alerta, Prioridad, Vector, EstadoOportunidad
            # Envío seguro
            try:
                al_obj = Alerta(
                    id=al_dict["id"],
                    vector=Vector(al_dict["vector"]),
                    titulo=al_dict["titulo"],
                    resumen=al_dict["resumen"],
                    valor_estimado=al_dict["valor_estimado"],
                    prioridad=Prioridad(al_dict["prioridad"]),
                    url=al_dict.get("url", "")
                )
                await telegram_bot.enviar_alerta(al_obj)
            except Exception:
                pass

    logger.info("✅ === Escaneo Riegos Pous finalizado con éxito ===")

async def abrir_navegador_con_retraso(url: str, delay: float = 1.0):
    """Abre el navegador web de forma sincronizada una vez que uvicorn ya está escuchando peticiones."""
    await asyncio.sleep(delay)
    logger.info(f"🌐 Acceso web listo. Abriendo automáticamente: {url}")
    webbrowser.open(url)

async def main():
    config_path = Path("riegos_pous/config_pous.yaml")
    if not config_path.exists():
        config_path = Path("config_pous.yaml")
        
    if not config_path.exists():
        logger.error(f"No se encontró config_pous.yaml en {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Inicializar Base de Datos propia
    db_path = config.get("general", {}).get("database_path", "riegos_pous/data/riegos_pous.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    storage = Storage(db_path)
    await storage.initialize()

    http = HttpClient()
    notifier = Notifier(config.get("notifications", {}))

    # Programador recurrente de fondo
    scheduler = AsyncIOScheduler()
    intervalo = config.get("general", {}).get("scan_interval_minutes", 30)
    scheduler.add_job(
        run_pous_scans,
        'interval',
        minutes=intervalo,
        args=[config, http, storage, notifier]
    )
    scheduler.start()

    # Configuración del servidor Dashboard
    dash_cfg = config.get("dashboard", {})
    host = dash_cfg.get("host", "127.0.0.1")
    port = dash_cfg.get("port", 8090)
    url_dashboard = f"http://{host}:{port}"

    logger.info(f"🚀 Iniciando Dashboard de Riegos Pous en {url_dashboard}")

    # 1. Tarea en segundo plano: abrir navegador en el momento exacto
    asyncio.create_task(abrir_navegador_con_retraso(url_dashboard, delay=0.8))

    # 2. Tarea en segundo plano: ejecutar escaneo inicial sin bloquear la apertura web
    asyncio.create_task(run_pous_scans(config, http, storage, notifier))

    # 3. Tarea en segundo plano: Oráculo Técnico de Campo en Telegram (/ficha [modelo])
    telegram_assistant = TelegramTechAssistant(config)
    asyncio.create_task(telegram_assistant.iniciar_escucha())

    config_uvicorn = uvicorn.Config(
        "riegos_pous.dashboard.app_pous:app",
        host=host,
        port=port,
        log_level="warning"
    )
    server = uvicorn.Server(config_uvicorn)

    try:
        await server.serve()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Apagando Riegos Pous Engine...")
    finally:
        telegram_assistant.detener()
        scheduler.shutdown(wait=False)
        await http.close()
        await storage.close()

if __name__ == "__main__":
    asyncio.run(main())
