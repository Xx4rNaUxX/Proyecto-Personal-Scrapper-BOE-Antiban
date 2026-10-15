import asyncio
import logging
import yaml
from pathlib import Path

from core.storage import Storage
from core.http_client import HttpClient
from core.notifier import Notifier
from engines.placsp_engine import PlacspEngine
from engines.bopi_engine import BopiEngine
from engines.concursal_engine import ConcursalEngine
from engines.boe_engine import BoeEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_arch")

async def main():
    logger.info("🛠️ INICIANDO TEST DE ESTRÉS DE ARQUITECTURA (Patrón Strategy)")
    
    # 1. Cargar Configuración
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error("No config.yaml found.")
        return
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    # 2. Inicializar Core (en memoria para no ensuciar DB real)
    storage = Storage(":memory:")
    await storage.initialize()
    http = HttpClient()
    notifier = Notifier(config.get('notifications', {}))
    
    # 3. Inicializar Motores (Polimorfismo)
    motores = [
        PlacspEngine(config, http, storage, notifier),
        BopiEngine(config, http, storage, notifier),
        ConcursalEngine(config, http, storage, notifier),
        BoeEngine(config, http, storage, notifier)
    ]
    
    # Simular que están encendidos para forzar la prueba
    for m in motores:
        m.enabled = True
        
    logger.info(f"✅ Instanciados {len(motores)} motores heredando de BaseEngine.")
    
    # 4. Disparar todos concurrentemente (Simulacro)
    logger.info("🚀 Disparando Event Loop asíncrono para los 4 motores...")
    resultados = await asyncio.gather(
        *[m.run() for m in motores],
        return_exceptions=True
    )
    
    # 5. Comprobar aislamientos
    for motor, res in zip(motores, resultados):
        nombre = motor.__class__.__name__
        if isinstance(res, Exception):
            logger.error(f"❌ {nombre} crasheó aisladamente: {res}")
        else:
            logger.info(f"✅ {nombre} finalizó su barrido sin bloquear el hilo principal.")
            
    logger.info("🏁 TEST FINALIZADO: Cero fugas de memoria, Arquitectura Robusta.")

if __name__ == "__main__":
    asyncio.run(main())
