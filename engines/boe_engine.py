import logging
import asyncio
from datetime import datetime
from typing import List

from engines.base_engine import BaseEngine
from core.models import Alerta, EstadoOportunidad, Prioridad, Vector
from core.llm_brain import LocalBrain

logger = logging.getLogger("arbitraje.boe")

class BoeEngine(BaseEngine):
    def __init__(self, config: dict, http, storage, notifier=None):
        super().__init__(config, http, storage, notifier)
        self.config_boe = config.get('boe', {})
        self.enabled = self.config_boe.get('enabled', True)
        self.max_deposito = self.config_boe.get('max_deposito', 3000.0)
        self.brain = LocalBrain()
        
    async def run(self):
        if not self.enabled: return
        logger.info("[Vector 4] Iniciando Francotirador de Embargos BOE...")
        
        start_time = datetime.now()
        encontrados = 0
        nuevos = 0
        
        try:
            # Simulamos el feed XML de subastas.boe.es
            lotes = await self._obtener_feed_subastas()
            
            for lote in lotes:
                encontrados += 1
                try:
                    # 1. Filtro CPU (Depósito)
                    deposito = lote.get('deposito', 999999)
                    if deposito > self.max_deposito:
                        logger.debug(f"Descartado por depósito alto: {lote['id']}")
                        continue
                        
                    # 2. Análisis LLM de Cargas Ocultas
                    texto_edicto = lote.get('texto_cargas', '')
                    analisis = await self.brain.analizar_cargas(texto_edicto)
                    
                    cargas_euros = analisis.get("cargas_anteriores_euros", 0.0)
                    riesgo = analisis.get("riesgo_juridico", "Alto")
                    
                    if cargas_euros > 0.0 or riesgo.lower() == "alto":
                        logger.warning(f"Embargo Peligroso (Cargas: {cargas_euros}€). Descartado: {lote['id']}")
                        continue
                        
                    # Es una oportunidad limpia
                    valor_subasta = lote.get("valor_subasta", 0.0)
                    alerta = Alerta(
                        id=f"boe_{lote['id']}",
                        vector=Vector.CONCURSAL, # Reutilizamos o mapeamos a boe si lo creamos
                        titulo=f"Subasta Limpia: {lote['titulo']}",
                        resumen=(
                            f"🧠 Análisis IA: Cargas {cargas_euros}€ | Riesgo: {riesgo}\n"
                            f"Activos: {analisis.get('descripcion_activos', 'Bienes')}"
                        ),
                        prioridad=Prioridad.CRITICA,
                        valor_estimado=valor_subasta,
                        viabilidad_score=1.0, # Sin cargas y poco depósito = ROI altísimo
                        url=f"https://subastas.boe.es/detalleSubasta.php?idSub={lote['id']}",
                        estado=EstadoOportunidad.DETECTADA,
                    )
                    
                    if await self.storage.guardar_alerta(alerta):
                        nuevos += 1
                        logger.info(f"[+] BOE Chollo Detectado: {lote['titulo']} | Valor: {valor_subasta}€")
                except Exception as e:
                    logger.error(f"Fallo aislando lote {lote.get('id')}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error en BOE engine: {e}", exc_info=True)
        finally:
            duracion = (datetime.now() - start_time).total_seconds()
            await self.storage.registrar_escaneo(Vector.CONCURSAL, encontrados, nuevos, duracion, "")
            logger.info(f"[Vector 4] Fin BOE: {encontrados} procesados, {nuevos} chollos limpios.")

    async def _obtener_feed_subastas(self) -> List[dict]:
        """Simula la descarga y parseo del XML diario del BOE."""
        return [
            {
                "id": "SUB-111",
                "titulo": "BMW M4 Coupé 2021",
                "deposito": 1500.0,
                "valor_subasta": 45000.0,
                "texto_cargas": "El vehículo se transmite libre de cargas según constancia registral. No constan embargos adicionales."
            },
            {
                "id": "SUB-222",
                "titulo": "Piso 90m2 Valencia",
                "deposito": 2500.0,
                "valor_subasta": 120000.0,
                "texto_cargas": "Consta hipoteca a favor de BBVA por importe principal de 85.000 euros más intereses y costas."
            },
            {
                "id": "SUB-333",
                "titulo": "Maquinaria Industrial (Torno CNC)",
                "deposito": 5000.0, # Será descartado por CPU filter
                "valor_subasta": 20000.0,
                "texto_cargas": "Libre de cargas."
            }
        ]
