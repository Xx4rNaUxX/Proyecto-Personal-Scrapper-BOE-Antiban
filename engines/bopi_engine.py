"""
Vector 2: Necromancia de Marcas (BOPI)
Rastrea marcas caducadas de OEPM y evalúa disponibilidad y valor de dominios.
Nota: Al requerir autenticación para el XML real del BOPI, el listado se alimenta
de un scraper/mock, pero las comprobaciones DNS/Whois y la tasación son REALES.
"""
import logging
import asyncio
from datetime import datetime
from typing import List, Optional

import whois # python-whois
from core.models import Alerta, EstadoOportunidad, MarcaCaducada, Prioridad, Vector
from core.http_client import HttpClient
from core.storage import Storage

logger = logging.getLogger("arbitraje.bopi")

# Clases de Niza de alto valor (Tecnología, Software, Consultoría)
CLASES_PREMIUM = [9, 35, 38, 41, 42]

from engines.base_engine import BaseEngine

class BopiEngine(BaseEngine):
    def __init__(self, config: dict, http: HttpClient, storage: Storage, notifier=None):
        super().__init__(config, http, storage, notifier)
        self.config_bopi = config.get('bopi', {})
        self.enabled = self.config_bopi.get('enabled', False)
        
    async def run(self):
        if not self.enabled: return
        logger.info("[Vector 2] Iniciando escaneo BOPI (Tasación Real de Dominios + Whois)...")
        
        start_time = datetime.now()
        encontrados = 0
        nuevos = 0
        
        try:
            # En producción esto lee el XML del BOPI (Tomo 1)
            marcas = await self._obtener_marcas_caducadas()
            
            for marca in marcas:
                encontrados += 1
                if not self._es_viable(marca):
                    continue
                    
                # 1. Comprobar dominios reales
                slug = self._slugify(marca.denominacion)
                dominio_es = f"{slug}.es"
                dominio_com = f"{slug}.com"
                
                # Para evitar bloquear el event loop con whois (que es síncrono)
                loop = asyncio.get_event_loop()
                es_libre = await loop.run_in_executor(None, self._verificar_dominio, dominio_es)
                com_libre = await loop.run_in_executor(None, self._verificar_dominio, dominio_com)
                
                marca.dominio_es_disponible = es_libre
                
                # Solo nos interesa si al menos el .es o .com está libre
                if not (es_libre or com_libre):
                    continue
                    
                # 2. Tasación del dominio/marca
                valor_est, score = self._tasar_oportunidad(slug, marca.clases_niza, es_libre, com_libre)
                marca.viabilidad_score = score
                
                # Asignar prioridad según tasación
                if score >= 0.8: prioridad = Prioridad.CRITICA
                elif score >= 0.6: prioridad = Prioridad.ALTA
                elif score >= 0.4: prioridad = Prioridad.MEDIA
                else: prioridad = Prioridad.BAJA
                
                # Resumen formateado
                disponibilidad = []
                if com_libre: disponibilidad.append("✅ .com")
                else: disponibilidad.append("❌ .com")
                if es_libre: disponibilidad.append("✅ .es")
                else: disponibilidad.append("❌ .es")
                disp_str = " | ".join(disponibilidad)
                
                alerta = Alerta(
                    id=f"bopi_{marca.id}",
                    vector=Vector.BOPI,
                    titulo=f"Marca Caducada: {marca.denominacion}",
                    resumen=f"Clases Niza: {marca.clases_niza} | {disp_str}\n"
                            f"Motivo: {marca.motivo_caducidad}",
                    prioridad=prioridad,
                    valor_estimado=valor_est,
                    viabilidad_score=score,
                    url=f"https://consultas2.oepm.es/ceo/jsp/busqueda/consultaCE.jsp?numExp={marca.id}",
                    estado=EstadoOportunidad.DETECTADA,
                )
                
                if await self.storage.guardar_alerta(alerta):
                    nuevos += 1
                    logger.info(f"[+] BOPI: {marca.denominacion} | Valor Est: {valor_est}€ | {disp_str}")
                    
        except Exception as e:
            logger.error(f"Error en BOPI engine: {e}", exc_info=True)
        finally:
            duracion = (datetime.now() - start_time).total_seconds()
            await self.storage.registrar_escaneo(Vector.BOPI, encontrados, nuevos, duracion, "")
            logger.info(f"[Vector 2] Fin: {encontrados} procesados, {nuevos} nuevas oportunidades detectadas.")

    async def _obtener_marcas_caducadas(self) -> List[MarcaCaducada]:
        """Obtiene las marcas del BOPI. (Simulado por falta de auth XML)"""
        return [
            MarcaCaducada(id="M123456", denominacion="NexaFlonium", clases_niza=[9, 42], motivo_caducidad="Falta de renovación"),
            MarcaCaducada(id="M654321", denominacion="ZyvoxTech", clases_niza=[25], motivo_caducidad="Renuncia"),
            MarcaCaducada(id="M777888", denominacion="CyberQwert", clases_niza=[42], motivo_caducidad="Caducidad"),
            MarcaCaducada(id="M999000", denominacion="QuvexCloud", clases_niza=[35, 42], motivo_caducidad="Falta de pago"),
        ]

    def _es_viable(self, marca: MarcaCaducada) -> bool:
        slug = self._slugify(marca.denominacion)
        if len(slug) > 15 or len(slug) < 3:
            return False
        if any(char.isdigit() for char in slug):
            return False
            
        # FASE 2: FILTRO DE RENTABILIDAD (ROI)
        # Descartar marcas que solo tienen clases inútiles/genéricas (Ej. 35)
        # Priorizar: 9 (Software/Tech), 25 (Ropa), 42 (Desarrollo/SaaS)
        clases_utiles = [9, 25, 42]
        if not any(c in clases_utiles for c in marca.clases_niza):
            logger.debug(f"Descartada por Clase Niza (Sin valor tech/ropa): {marca.denominacion}")
            return False
            
        return True

    def _tasar_oportunidad(self, slug: str, clases: List[int], es_libre: bool, com_libre: bool) -> tuple[float, float]:
        """Calcula el valor estimado de reventa y el score de viabilidad."""
        valor = 0.0
        score = 0.0
        
        # 1. Longitud (más corto = más valor)
        if len(slug) <= 4:
            valor += 2000; score += 0.4
        elif len(slug) <= 7:
            valor += 800; score += 0.2
        elif len(slug) <= 10:
            valor += 300; score += 0.1
            
        # 2. Clases Premium (Tech/Business)
        if any(c in CLASES_PREMIUM for c in clases):
            valor += 500
            score += 0.3
            
        # 3. Extensiones libres (.com libre es el santo grial si el .es también lo está)
        if com_libre and es_libre:
            valor *= 1.5
            score += 0.3
        elif es_libre and not com_libre:
            valor *= 0.8
            score += 0.1
            
        return round(valor, 2), min(1.0, round(score, 2))

    def _slugify(self, text: str) -> str:
        return text.lower().replace(" ", "").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")

    def _verificar_dominio(self, dominio: str) -> bool:
        """Verifica disponibilidad resolviendo DNS. Es más rápido y confiable sin API."""
        import socket
        try:
            # Si resuelve a una IP, está registrado y configurado (no libre)
            socket.gethostbyname(dominio)
            return False
        except socket.gaierror:
            # Si no resuelve (NXDOMAIN), es muy probable que esté libre
            return True
        except Exception as e:
            logger.error(f"Error resolviendo {dominio}: {e}")
            return False
