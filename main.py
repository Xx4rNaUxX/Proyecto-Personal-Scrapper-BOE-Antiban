"""
Punto de entrada principal. Orquestador de escaneos y servidor web.
"""
import asyncio
import logging
import yaml
from pathlib import Path
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.storage import Storage
from core.http_client import HttpClient
from core.notifier import Notifier
from engines.placsp_engine import PlacspEngine
from engines.bopi_engine import BopiEngine
from engines.concursal_engine import ConcursalEngine
from engines.boe_engine import BoeEngine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("arbitraje.main")

async def run_scans(config: dict, http: HttpClient, storage: Storage, notifier: Notifier):
    logger.info("=== Iniciando ciclo de escaneo global (Patrón Strategy) ===")
    
    motores = [
        PlacspEngine(config, http, storage, notifier),
        BopiEngine(config, http, storage, notifier),
        ConcursalEngine(config, http, storage, notifier),
        BoeEngine(config, http, storage, notifier)
    ]
    
    # Ejecutamos todos los motores concurrentemente. Si uno falla, los demás siguen corriendo.
    await asyncio.gather(
        *[motor.run() for motor in motores],
        return_exceptions=True
    )
    logger.info("=== Ciclo global finalizado ===")

async def main():
    # Cargar config
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error("config.yaml no encontrado. Terminando.")
        return
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    # Inicializar servicios core
    storage = Storage(config.get('general', {}).get('database_path', 'data/arbitraje.db'))
    await storage.initialize()
    
    http = HttpClient()
    notifier = Notifier(config.get('notifications', {}))
    
    # Programador de tareas
    scheduler = AsyncIOScheduler()
    intervalo = config.get('general', {}).get('scan_interval_minutes', 30)
    
    scheduler.add_job(
        run_scans, 
        'interval', 
        minutes=intervalo, 
        args=[config, http, storage, notifier],
        next_run_time=datetime.now() # Ejecutar inmediatamente la primera vez
    )
    
    scheduler.start()
    
    # Iniciar servidor web en background
    dash_cfg = config.get('dashboard', {})
    host = dash_cfg.get('host', '127.0.0.1')
    port = dash_cfg.get('port', 8080)
    
    logger.info(f"Iniciando dashboard en http://{host}:{port}")
    config_uvicorn = uvicorn.Config("dashboard.app:app", host=host, port=port, log_level="warning")
    server = uvicorn.Server(config_uvicorn)
    
    try:
        await server.serve()
    except OSError as e:
        logger.error(f"❌ Error de red al iniciar el servidor (¿Está el puerto {port} en uso?): {e}")
        logger.error("Asegúrate de que no haya otra terminal ejecutando main.py.")
    except (KeyboardInterrupt, SystemExit):
        logger.info("Apagando...")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
    finally:
        logger.info("Cerrando conexiones y deteniendo el planificador de tareas...")
        scheduler.shutdown(wait=False)
        await http.close()
        await storage.close()

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
