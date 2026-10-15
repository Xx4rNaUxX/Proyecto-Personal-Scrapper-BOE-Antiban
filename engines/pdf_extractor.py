"""
Extrae y procesa los Pliegos de Prescripciones Técnicas (PPT) desde los PDFs
para su análisis mediante IA local.
"""
import io
import logging
import fitz  # PyMuPDF
from core.http_client import HttpClient
import xml.etree.ElementTree as ET

logger = logging.getLogger("arbitraje.pdf_extractor")

CAC_EXT = "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2"
CAC = "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"

async def extract_ppt_url(entry: ET.Element) -> str:
    """Extrae la URL del Pliego Técnico (PPT) del nodo ATOM entry."""
    # Buscamos TechnicalDocumentReference
    cfs = entry.find(f"{{{CAC_EXT}}}ContractFolderStatus")
    if cfs is None:
        return ""
        
    for tech_doc in cfs.findall(f".//{{{CAC}}}TechnicalDocumentReference"):
        attach = tech_doc.find(f"{{{CAC}}}Attachment/{{{CAC}}}ExternalReference/{{{CBC}}}URI")
        if attach is not None and attach.text:
            return attach.text.strip()
    return ""

async def download_and_extract_text(url: str, http: HttpClient) -> str:
    """Descarga el PDF y extrae los primeros 8000 caracteres de texto plano."""
    if not url:
        return ""
        
    try:
        # Descargar como bytes
        pdf_bytes = await http.get(url, raw=True)
        if not pdf_bytes:
            return ""
            
        # Leer con PyMuPDF (FASE 1: Procesamiento por chunks limitados)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_chunks = []
        
        max_pages = min(len(doc), 15) # Límite estricto para no saturar memoria RAM
        for page_num in range(max_pages):
            page = doc.load_page(page_num)
            chunk = page.get_text("text")
            if chunk:
                text_chunks.append(chunk)
                
            # Limitar tamaño final para no saturar la VRAM de Ollama (6GB max)
            if sum(len(c) for c in text_chunks) > 12000:
                break
                
        doc.close()
        return "\n".join(text_chunks).strip()[:12000]
        
    except Exception as e:
        logger.error(f"Error extrayendo PDF ({url}): {e}")
        return ""
