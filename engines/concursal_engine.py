"""
Vector 3: Radar Concursal y Subastas BOE
Rastrea liquidaciones de empresas tecnológicas y evalúa el margen
de reventa del hardware y activos digitales.
Nota: El feed simula la extracción del BOE (que carece de API estructurada abierta),
pero el motor de Tasación de Hardware (Depreciación y Paletizado) es 100% REAL.
"""
import logging
from datetime import datetime
from typing import List, Tuple
import re

from core.models import Alerta, EstadoOportunidad, LoteConcursal, Prioridad, Vector
from core.http_client import HttpClient
from core.storage import Storage

logger = logging.getLogger("arbitraje.concursal")

# Base de datos simplificada de retención de valor en hardware de segunda mano (%)
HARDWARE_DEPRECIATION = {
    "macbook": 0.65,      # Apple retiene valor muy bien
    "iphone": 0.60,
    "dell xps": 0.50,
    "thinkpad": 0.45,
    "servidor": 0.15,     # Servidores se deprecian masivamente tras 5 años
    "switch": 0.20,
    "cisco": 0.25,
    "impresora": 0.05,    # Chatarra prácticamente
    "monitor": 0.35,
    "rtx": 0.55,          # GPUs retienen valor
}

from engines.base_engine import BaseEngine

class ConcursalEngine(BaseEngine):
    def __init__(self, config: dict, http: HttpClient, storage: Storage, notifier=None):
        super().__init__(config, http, storage, notifier)
        self.config_concursal = config.get('concursal', {})
        self.enabled = self.config_concursal.get('enabled', False)
        
    async def run(self):
        if not self.enabled: return
        logger.info("[Vector 3] Iniciando Radar Concursal BOE (Algoritmo de Tasación Hardware Activo)...")
        
        start_time = datetime.now()
        encontrados = 0
        nuevos = 0
        
        try:
            # Extracción del Portal de Subastas (Simulado)
            lotes = await self._extraer_lotes_boe()
            
            for lote in lotes:
                encontrados += 1
                
                # Algoritmo de Tasación de Activos
                valor_mercado, costes_logistica, desglose = self._tasar_lote_hardware(lote.titulo)
                lote.valor_mercado_estimado = valor_mercado
                
                # Cálculo de Margen Neto
                margen_neto = valor_mercado - lote.precio_actual - costes_logistica
                
                # Solo nos interesan lotes con más de 500€ de beneficio neto
                if margen_neto > 500:
                    lote.margen_estimado = margen_neto
                    
                    if margen_neto > 3000:
                        score = 0.95; prioridad = Prioridad.CRITICA
                    elif margen_neto > 1500:
                        score = 0.8; prioridad = Prioridad.ALTA
                    else:
                        score = 0.6; prioridad = Prioridad.MEDIA
                        
                        alerta = Alerta(
                        id=f"boe_{lote.id}",
                        vector=Vector.CONCURSAL,
                        titulo=f"Liquidación BOE: {lote.titulo}",
                        resumen=(
                            f"💶 Precio Actual BOE: {lote.precio_actual:,.0f}€ | "
                            f"📦 Valor Mercado 2a Mano: {valor_mercado:,.0f}€\n"
                            f"🚚 Logística Est.: -{costes_logistica:,.0f}€ | "
                            f"🚀 MARGEN NETO: +{margen_neto:,.0f}€\n"
                            f"🔍 Análisis: {desglose}"
                        ),
                        prioridad=prioridad,
                        valor_estimado=margen_neto,
                        viabilidad_score=score,
                        url=f"https://subastas.boe.es/detalleSubasta.php?idSub={lote.id}",
                        estado=EstadoOportunidad.DETECTADA,
                    )
                    
                    if await self.storage.guardar_alerta(alerta):
                        nuevos += 1
                        logger.info(f"[+] CONCURSAL: {lote.titulo} | Margen Neto: {margen_neto:,.0f}€")
                        
        except Exception as e:
            logger.error(f"Error en Concursal engine: {e}", exc_info=True)
        finally:
            duracion = (datetime.now() - start_time).total_seconds()
            await self.storage.registrar_escaneo(Vector.CONCURSAL, encontrados, nuevos, duracion, "")
            logger.info(f"[Vector 3] Fin: {encontrados} procesados, {nuevos} oportunidades rentables detectadas.")

    async def _extraer_lotes_boe(self) -> List[LoteConcursal]:
        """Obtiene lotes del portal de subastas del BOE. (Feed estructurado para demo)"""
        return [
            LoteConcursal(
                id="SUB-JA-2026-112233",
                titulo="Lote informático: 10x MacBook Pro M2, 5x Monitores Dell 4K, 1x Switch Cisco",
                categoria="BIENES MUEBLES - EQUIPOS INFORMÁTICOS",
                precio_salida=2000.0,
                precio_actual=2500.0,
                tramo_actual=2,
                valor_mercado_estimado=0.0 
            ),
            LoteConcursal(
                id="SUB-JA-2026-998877",
                titulo="Mobiliario y Servidor antiguo: Mesas oficina, Sillas, 2x Servidor HP ProLiant G6",
                categoria="BIENES MUEBLES",
                precio_salida=500.0,
                precio_actual=300.0,
                tramo_actual=1,
                valor_mercado_estimado=0.0
            ),
            LoteConcursal(
                id="SUB-JA-2026-554433",
                titulo="Lote minería cripto incautado: 20x GPU RTX 3080 Ti, Placas Base, Fuentes 1000W",
                categoria="BIENES MUEBLES - EQUIPOS INFORMÁTICOS",
                precio_salida=1000.0,
                precio_actual=1500.0,
                tramo_actual=3,
                valor_mercado_estimado=0.0 
            )
        ]

    def _tasar_lote_hardware(self, descripcion: str) -> Tuple[float, float, str]:
        """
        Analiza el título, detecta hardware, aplica depreciación y estima costes logísticos (palets).
        Retorna: (Valor Mercado €, Coste Logística €, Razón Texto)
        """
        desc_lower = descripcion.lower()
        valor_total = 0.0
        logistica = 0.0
        hallazgos = []
        
        # Algoritmo de regex para encontrar multiplicadores (ej: 10x MacBook)
        # 1. MacBooks
        macs = re.search(r'(\d+)x\s*macbook', desc_lower)
        if macs or "macbook" in desc_lower:
            qty = int(macs.group(1)) if macs else 1
            v_nuevo = 1800 * qty
            v_mercado = v_nuevo * HARDWARE_DEPRECIATION["macbook"]
            valor_total += v_mercado
            logistica += 10 * qty # Envío por caja pequeña
            hallazgos.append(f"{qty} MacBooks (Valor ret: {HARDWARE_DEPRECIATION['macbook']*100}%)")
            
        # 2. Servidores
        srv = re.search(r'(\d+)x\s*servidor', desc_lower)
        if srv or "servidor" in desc_lower:
            qty = int(srv.group(1)) if srv else 1
            v_nuevo = 3000 * qty
            v_mercado = v_nuevo * HARDWARE_DEPRECIATION["servidor"]
            valor_total += v_mercado
            logistica += 150 * qty # Requiere paletizado
            hallazgos.append(f"{qty} Servidores (Chatarra digital, retiene solo {HARDWARE_DEPRECIATION['servidor']*100}%)")

        # 3. GPUs
        gpu = re.search(r'(\d+)x\s*gpu rtx', desc_lower) or re.search(r'(\d+)x\s*rtx', desc_lower)
        if gpu or "rtx" in desc_lower:
            qty = int(gpu.group(1)) if gpu else 1
            v_nuevo = 800 * qty
            v_mercado = v_nuevo * HARDWARE_DEPRECIATION["rtx"]
            valor_total += v_mercado
            logistica += 5 * qty # Caja pequeña
            hallazgos.append(f"{qty} GPUs RTX (Alta demanda minería/gaming)")
            
        # Si no hay nada de valor, devolvemos chatarra
        if valor_total == 0:
            return 100.0, 50.0, "Chatarra tecnológica indeterminada."
            
        return valor_total, logistica, " | ".join(hallazgos)
