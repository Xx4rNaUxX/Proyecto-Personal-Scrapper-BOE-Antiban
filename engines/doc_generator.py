"""
Generador de Documentos Legales - Art. 168.a.1º LCSP
Genera el escrito formal de manifestación de interés en Word (.docx)
listo para firmar y presentar en el registro electrónico.
"""
import io
import os
import logging
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger("arbitraje.docgen")

OUTPUT_DIR = Path("data/escritos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generar_escrito_168(licitacion: dict, solicitante: dict) -> str:
    """
    Genera un escrito .docx de manifestación de interés al amparo
    del Art. 168.a.1º LCSP para una licitación desierta.

    Args:
        licitacion: dict con datos del contrato (id, titulo, organo,
                    presupuesto_base, url_expediente, tipo_contrato)
        solicitante: dict con datos del interesado (nombre, nif,
                     domicilio, email, telefono)

    Returns:
        Ruta absoluta al fichero .docx generado.
    """
    doc = Document()

    # Márgenes
    for section in doc.sections:
        section.top_margin    = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin   = Inches(1.2)
        section.right_margin  = Inches(1.2)

    # ── Cabecera ──────────────────────────────────────────────────────
    _add_heading(doc, f"AL ÓRGANO DE CONTRATACIÓN DE:\n{licitacion.get('organo_contratacion', '').upper()}")

    doc.add_paragraph()

    # Datos del solicitante
    nombre   = solicitante.get("nombre", "[NOMBRE / RAZÓN SOCIAL]")
    nif      = solicitante.get("nif", "[NIF/CIF]")
    domicilio = solicitante.get("domicilio", "[DOMICILIO]")
    email    = solicitante.get("email", "[EMAIL]")
    telefono = solicitante.get("telefono", "[TELÉFONO]")

    p = doc.add_paragraph()
    p.add_run(
        f"D./Dña. ______________________________, con DNI/NIE ____________________, "
        f"actuando en nombre y representación de "
    )
    p.add_run(f"{nombre}").bold = True
    p.add_run(
        f", con NIF/CIF {nif}, domicilio social en {domicilio}, "
        f"correo electrónico {email} y teléfono {telefono},"
    )
    p.paragraph_format.first_line_indent = Inches(0.3)

    doc.add_paragraph()

    # Comparece
    _add_section_title(doc, "COMPARECE Y EXPONE:")
    doc.add_paragraph()

    fecha_res  = licitacion.get("fecha_resolucion", datetime.now().strftime("%d/%m/%Y"))
    exp_id     = licitacion.get("id", "[EXPEDIENTE]")
    titulo_con = licitacion.get("titulo", "[OBJETO DEL CONTRATO]")
    pbl        = licitacion.get("presupuesto_base", 0)
    url        = licitacion.get("url_expediente", "[URL PLACSP]")
    tipo       = licitacion.get("tipo_contrato", "Servicios")

    # Primero
    _add_ordinal(doc, "PRIMERO")
    p1 = doc.add_paragraph(
        f"Que con fecha {fecha_res} se ha publicado en la Plataforma de Contratación "
        f"del Sector Público (PLACSP) la resolución por la cual se declara "
    )
    p1.add_run("DESIERTO").bold = True
    p1.add_run(
        f" el procedimiento de licitación para la adjudicación del contrato "
        f"de {tipo.upper()} denominado "
    )
    r = p1.add_run(f'"{titulo_con}"')
    r.bold = True
    p1.add_run(
        f" (Expediente: {exp_id}), cuyo Presupuesto Base de Licitación (PBL) "
        f"asciende a {pbl:,.2f} € (IVA excluido). "
        f"(Referencia PLACSP: {url})"
    )

    # Segundo
    _add_ordinal(doc, "SEGUNDO")
    doc.add_paragraph(
        "Que el Artículo 168.a.1º de la Ley 9/2017, de 8 de noviembre, "
        "de Contratos del Sector Público (LCSP), establece que los órganos de "
        "contratación podrán adjudicar contratos acudiendo al procedimiento "
        "negociado sin publicidad cuando:\n\n"
        "«No se haya presentado ninguna oferta o las ofertas presentadas no sean "
        "adecuadas [...] siempre que las condiciones iniciales del contrato no se "
        "modifiquen sustancialmente»."
    )

    # Tercero
    _add_ordinal(doc, "TERCERO")
    doc.add_paragraph(
        f"Que {nombre} es un operador económico con plena capacidad de obrar, "
        "debidamente inscrito en el correspondiente Registro Mercantil, con la "
        "experiencia técnica y económica necesaria para la ejecución del objeto "
        "contractual descrito en los Pliegos de Cláusulas Administrativas "
        "Particulares (PCAP) y de Prescripciones Técnicas (PPT) que rigieron el "
        "procedimiento declarado desierto, cuyas condiciones acepta íntegramente "
        "sin reserva alguna."
    )

    doc.add_paragraph()

    # Solicitud
    _add_section_title(doc, "POR TODO LO EXPUESTO, SOLICITA:")
    doc.add_paragraph()

    doc.add_paragraph(
        "Que se tenga por presentado este escrito, se sirva admitirlo y, "
        "en méritos de lo dispuesto en el artículo 168.a.1º de la LCSP, "
        "SE ACUERDE EL INICIO del correspondiente Procedimiento Negociado "
        "Sin Publicidad para la adjudicación del contrato referenciado, "
        "invitando a esta representación a participar en el mismo mediante "
        "el envío de los Pliegos actualizados y la correspondiente solicitud "
        "de oferta económica."
    )

    doc.add_paragraph()

    # Firma
    ciudad_hoy = datetime.now().strftime("%d de %B de %Y").replace(
        "January","enero").replace("February","febrero").replace(
        "March","marzo").replace("April","abril").replace(
        "May","mayo").replace("June","junio").replace(
        "July","julio").replace("August","agosto").replace(
        "September","septiembre").replace("October","octubre").replace(
        "November","noviembre").replace("December","diciembre")

    p_firma = doc.add_paragraph(f"En _________________, a {ciudad_hoy}.")
    p_firma.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.add_paragraph()
    doc.add_paragraph()

    p_sign = doc.add_paragraph("Fdo.: _________________________")
    p_sign.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p2 = doc.add_paragraph(f"Representante Legal de {nombre}")
    p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Advertencia legal al pie
    doc.add_paragraph()
    p_note = doc.add_paragraph(
        "⚠️  IMPORTANTE: Este documento debe presentarse a través del Registro "
        "Electrónico de la Administración competente, adjuntando DNI/NIE o "
        "Escritura de poderes y, en su caso, declaración responsable o DEUC "
        "(Documento Europeo Único de Contratación). Revise el pliego antes de "
        "enviarlo."
    )
    p_note.runs[0].font.size = Pt(8)
    p_note.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    # Guardar fichero
    filename = f"escrito_168_{exp_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    filepath = OUTPUT_DIR / filename
    doc.save(str(filepath))
    logger.info(f"Escrito generado: {filepath}")
    return str(filepath)


# ── Helpers de estilo ─────────────────────────────────────────────────

def _add_heading(doc: Document, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)

def _add_section_title(doc: Document, text: str):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)

def _add_ordinal(doc: Document, ordinal: str):
    p = doc.add_paragraph()
    run = p.add_run(f"{ordinal}.-")
    run.bold = True
    run.font.size = Pt(11)
