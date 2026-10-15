"""
Vector 1: Arbitraje de Licitaciones Desiertas (PLACSP)
Engine real basado en la estructura XML confirmada del feed oficial.

Namespaces reales verificados contra el feed en producción:
  ATOM  : http://www.w3.org/2005/Atom
  CAC   : urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2
  CBC   : urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2
  CAC4  : urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2

ResultCode de TenderResult:
  3  = Desierta (ninguna oferta válida)
  8  = Adjudicada
  99 = Desistida / anulada
"""
import logging
from datetime import datetime
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

from core.models import Alerta, EstadoOportunidad, LicitacionDesierta, Prioridad, Vector
from core.http_client import HttpClient
from core.storage import Storage
from core.llm_brain import LocalBrain
from engines.pdf_extractor import extract_ppt_url, download_and_extract_text

logger = logging.getLogger("arbitraje.placsp")

# Namespaces REALES confirmados contra el feed de producción
ATOM    = "http://www.w3.org/2005/Atom"
CAC_EXT = "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2"
CBC     = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
CBC_EXT = "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2"
CAC     = "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"

# ResultCode confirmado para licitaciones DESIERTAS: "3"
RESULT_CODE_DESIERTA = "3"

# Palabras que invalidan el contrato (falsos positivos)
BLACKLIST_TITULO = [
    "acuerdo marco", "sistema dinámico", " sda ", "concesi",
    "lote ", " lot ", "convenio",
]

# Palabras físicas que eliminamos: no somos constructores ni carroceros
BLACKLIST_FISICO = [
    "vehículo", "camión", "furgon", "pick up", "pick-up", "autobús",
    "tractor", "maquinaria", "excavador", "retroexcavador", "hormigon",
    "paviment", "asfalt", "obra civil", "caseta", "pista de", "pádel",
    "instalación eléctrica", "fontanería", "saneamiento", "cubierta",
    "tejado", "fachada", "carpintería", "cerrajería", "piscina",
    "albañil", "andamio", "derribo", "demolici", "parque infantil",
    "mobiliario urb", "señalización vial", "semáforo", "jardinería",
    "limpieza viaria", "recogida de residu", "vigilancia y seguridad",
    "vigilancia de instalac",
]

# Prefijos CPV de interés (TI, software, consultoría, digitalización)
CPV_WHITELIST_PREFIXES = (
    "48",  # Software
    "72",  # Servicios TI
    "79",  # Servicios empresariales (consultoría)
    "73",  # I+D
    "64",  # Telecomunicaciones
    "32",  # Equipos comunicación
)

# Keywords en el título que confirman relevancia TI
TITLE_TI_KEYWORDS = [
    "digital", "software", "aplicaci", "sistema inform", "web",
    "portal", "plataforma", "datos", "ciberseguridad", "cloud",
    "nube", "erp", "crm", "licencia", "desarrollo", "programaci",
    "base de datos", "red ", "redes ", "infraestructura ti",
    "infraestructura tecnol", "mantenimiento inform", "soporte ti",
    "consultoría ti", "transformación digital", "administración electrónica",
    "sede electrónica", "automatizaci", "robótica", "inteligencia artificial",
    "machine learning", "gis", "sig ", "cartografía digital",
    "telemedic", "historia clínica digital", "e-learning",
]

from engines.base_engine import BaseEngine

class PlacspEngine(BaseEngine):
    def __init__(self, config: dict, http: HttpClient, storage: Storage, notifier=None):
        super().__init__(config, http, storage, notifier)
        self.config_placsp = config.get("placsp", {})
        self.enabled  = self.config_placsp.get("enabled", False)
        self.brain    = LocalBrain() # Fase 3: Conexión con Ollama

    async def run(self):
        if not self.enabled:
            return
        logger.info("[Vector 1] Iniciando escaneo PLACSP (Fase 3: Filtrado TI + Análisis LLM)...")
        t0        = datetime.now()
        total     = 0
        nuevos    = 0
        error_msg = ""

        try:
            for feed_url in self.config_placsp.get("atom_feeds", []):
                resultados = await self._procesar_feed(feed_url)
                for lic, entry_xml in resultados:
                    total += 1
                    try:
                        if self._es_viable(lic):
                            score = self._calcular_score(lic)
                            lic.viabilidad_score = score
                            lic.prioridad = Prioridad.CRITICA if score > 0.8 else (
                                            Prioridad.ALTA    if score > 0.6 else Prioridad.MEDIA)
                                            
                            # Fase 3: Descargar PDF y auditar con IA
                            url_pdf = await extract_ppt_url(entry_xml)
                            veredicto_ia = "No se encontró PDF"
                            if url_pdf:
                                logger.info(f"Descargando PPT para auditoría IA: {lic.id}")
                                texto_pdf = await download_and_extract_text(url_pdf, self.http)
                                if texto_pdf:
                                    analisis = await self.brain.analizar_pliego(texto_pdf)
                                    viable = analisis.get("veredicto_viable", False)
                                    riesgo = analisis.get("riesgo_tecnico", "Desconocido")
                                    hw = analisis.get("hardware_requerido", "Ninguno")
                                    sw = analisis.get("software_lenguajes", "Desconocido")
                                    
                                    # Fase 7: Margen de Subcontratación Freelance
                                    coste_freelance = float(analisis.get("estimacion_coste_freelance", lic.presupuesto_base * 0.5))
                                    margen_neto = lic.presupuesto_base - coste_freelance
                                    
                                    if not viable or margen_neto < 500:
                                        logger.warning(f"Descartado por IA (No Viable o Margen Bajo < 500€): {lic.id}")
                                        continue # Salta este contrato
                                        
                                    veredicto_ia = (
                                        f"Riesgo: {riesgo}. Viable: Sí. HW: {hw}. SW: {sw}\n"
                                        f"💰 Presupuesto Base: {lic.presupuesto_base:,.0f}€ | "
                                        f"👨‍💻 Freelance: -{coste_freelance:,.0f}€ | "
                                        f"🚀 BENEFICIO NETO: +{margen_neto:,.0f}€"
                                    )
                                    
                            alerta = Alerta(
                                id=f"placsp_{lic.id}",
                                vector=Vector.PLACSP,
                                titulo=f"Desierta: {lic.titulo[:100]}",
                                resumen=(
                                    f"Órgano: {lic.organo_contratacion}\n"
                                    f"🧠 Auditoría Subcontrata:\n{veredicto_ia}"
                                ),
                                prioridad=lic.prioridad,
                                valor_estimado=lic.presupuesto_base,
                                viabilidad_score=score,
                                url=lic.url_expediente,
                                datos_raw=str(lic.to_dict()),
                            )
                            if await self.storage.guardar_alerta(alerta):
                                nuevos += 1
                                logger.info(
                                    f"[+] {lic.id} | {lic.presupuesto_base:,.0f}€ | "
                                    f"{lic.organo_contratacion[:50]} | 🧠 {veredicto_ia}"
                                )
                    except Exception as e:
                        logger.error(f"Fallo crítico (Autosanación FASE 3) aislando expediente {lic.id}: {e}")
                        continue
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error en PLACSP engine: {e}", exc_info=True)
        finally:
            duracion = (datetime.now() - t0).total_seconds()
            await self.storage.registrar_escaneo(
                Vector.PLACSP, total, nuevos, duracion, error_msg
            )
            logger.info(
                f"[Vector 1] Fin: {total} procesados, {nuevos} nuevos "
                f"({duracion:.1f}s)"
            )

    # ------------------------------------------------------------------
    # Feed ATOM
    # ------------------------------------------------------------------

    async def _procesar_feed(self, url: str) -> List[Tuple[LicitacionDesierta, ET.Element]]:
        xml_bytes = await self.http.get(url, raw=True)
        if not xml_bytes:
            return []
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            logger.error(f"ParseError en XML: {e}")
            return []

        resultados = []
        for entry in root.findall(f"{{{ATOM}}}entry"):
            lic = self._parse_entry(entry)
            if lic:
                resultados.append((lic, entry))
        return resultados

    def _parse_entry(self, entry: ET.Element) -> Optional[LicitacionDesierta]:
        # ── 1. ID interno y URL del expediente ──────────────────────────
        id_elem = entry.find(f"{{{ATOM}}}id")
        if id_elem is None:
            return None
        exp_id = id_elem.text.strip().split("/")[-1]

        link_elem = entry.find(f"{{{ATOM}}}link")
        url_expediente = link_elem.attrib.get("href", "").strip() if link_elem is not None else ""

        # ── 2. Filtro rápido por summary ─────────────────────────────────
        summary = entry.find(f"{{{ATOM}}}summary")
        if summary is None or summary.text is None:
            return None
        if "Estado: RES" not in summary.text:
            return None

        # ── 3. Bloque ContractFolderStatus ───────────────────────────────
        cfs = entry.find(f"{{{CAC_EXT}}}ContractFolderStatus")
        if cfs is None:
            return None

        # ── 4. Código de resultado → solo DESIERTA (ResultCode=3) ────────
        result_block = cfs.find(f".//{{{CAC}}}TenderResult")
        if result_block is None:
            return None
        rc = result_block.find(f"{{{CBC}}}ResultCode")
        if rc is None or rc.text != RESULT_CODE_DESIERTA:
            return None

        # ── 5. Título + blacklist ─────────────────────────────────────────
        title_elem = entry.find(f"{{{ATOM}}}title")
        titulo = title_elem.text.strip() if title_elem is not None else ""
        titulo_lower = titulo.lower()
        if any(kw in titulo_lower for kw in BLACKLIST_TITULO):
            return None
            
        # ── 5.1 Blacklist Físico (Descartar obras y suministros no TI) ────
        if any(kw in titulo_lower for kw in BLACKLIST_FISICO):
            return None

        # ── 6. Presupuesto base ───────────────────────────────────────────
        budget = cfs.find(
            f".//{{{CAC_EXT}}}ProcurementProject/{{{CAC_EXT}}}BudgetAmount"
            f"/{{{CBC}}}TaxExclusiveAmount"
        )
        if budget is None:
            budget = cfs.find(f".//{{{CBC}}}TaxExclusiveAmount")
        presupuesto = float(budget.text) if budget is not None else 0.0

        # ── 7. Duración en meses ──────────────────────────────────────────
        dur_elem = cfs.find(f".//{{{CBC}}}DurationMeasure")
        meses = 1.0
        if dur_elem is not None and dur_elem.text:
            try:
                val  = float(dur_elem.text)
                unit = dur_elem.attrib.get("unitCode", "MON")
                if unit in ("ANN", "YEAR"): val *= 12
                elif unit == "DAY": val /= 30
                meses = max(1.0, val)
            except ValueError:
                pass

        # ── 8. FASE 2: FILTRO DE RENTABILIDAD (ROI) ──────────────────────
        # Exigimos mínimo 2.000€ mensuales para que compense nuestro tiempo y el del freelance.
        if presupuesto / meses < 2000.0:
            return None

        # ── 8.1 Extracción de CPV y Filtrado TI ───────────────────────────
        cpv_elem = cfs.find(f".//{{{CAC_EXT}}}ItemClassificationCode")
        cpv = cpv_elem.attrib.get('listURI', '').split('/')[-1] if cpv_elem is not None else ""
        
        # Filtro estricto TI:
        es_ti_por_cpv = cpv.startswith(CPV_WHITELIST_PREFIXES) if cpv else False
        es_ti_por_titulo = any(kw in titulo_lower for kw in TITLE_TI_KEYWORDS)
        if not (es_ti_por_cpv or es_ti_por_titulo):
            return None

        # ── 9. Tipo de contrato ───────────────────────────────────────────
        type_code = cfs.find(f".//{{{CAC_EXT}}}ProcurementProject/{{{CBC}}}TypeCode")
        tipos = {"1": "Obras", "2": "Servicios", "3": "Suministros"}
        tipo = tipos.get(type_code.text if type_code is not None else "", "N/D")

        # ── 10. Órgano de contratación ────────────────────────────────────
        party_name = cfs.find(f".//{{{CAC}}}Party/{{{CAC}}}PartyName/{{{CBC}}}Name")
        organo = party_name.text.strip() if party_name is not None else "Desconocido"

        return LicitacionDesierta(
            id=exp_id,
            titulo=titulo,
            organo_contratacion=organo,
            presupuesto_base=presupuesto,
            url_expediente=url_expediente,
            tipo_contrato=tipo,
            estado=EstadoOportunidad.DETECTADA,
        )

    # ------------------------------------------------------------------
    # Filtros de negocio
    # ------------------------------------------------------------------

    def _es_viable(self, lic: LicitacionDesierta) -> bool:
        pbl_min = self.config.get("min_presupuesto", 0)
        pbl_max = self.config.get("max_presupuesto", 1_000_000)
        return pbl_min <= lic.presupuesto_base <= pbl_max

    def _calcular_score(self, lic: LicitacionDesierta) -> float:
        """
        Heurística de puntuación 0.0 → 1.0:
          - Presupuesto más alto = más puntos (hasta 0.5)
          - Tipo Servicios / Suministros = preferidos (0.3)
          - Título contiene palabras tech = bonus (0.2)
        """
        score = 0.0
        pbl_max = self.config.get("max_presupuesto", 100_000)
        score += min(0.5, lic.presupuesto_base / pbl_max * 0.5)

        if lic.tipo_contrato in ("Servicios", "Suministros"):
            score += 0.3

        tech_kws = ["digital", "software", "informátic", "web", "sistem",
                    "aplicaci", "red ", "datos", "licenci"]
        if any(kw in lic.titulo.lower() for kw in tech_kws):
            score += 0.2

        return round(min(1.0, score), 2)
