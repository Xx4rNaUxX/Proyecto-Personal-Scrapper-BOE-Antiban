"""
Generador de Informes Técnicos - Riegos Pous, S.L.
====================================================
MEJORAS INYECTADAS v2.0:
  [1] ROI calculado automáticamente desde datos_raw si no viene explícito
  [2] Tabla de métricas técnicas: marca, potencia, ROI porcentual y ahorro en EUR
  [3] Semáforo visual de prioridad (rojo=crítica, naranja=alta, amarillo=media)
  [4] Sección de dictamen técnico separada del resumen
  [5] Limpieza de texto reforzada con más reemplazos de emojis y caracteres especiales
  [6] Manejo seguro de datos_raw malformados (try/except en parseo JSON)
"""
import json
import os
from fpdf import FPDF
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# Paleta corporativa Riegos Pous
# ─────────────────────────────────────────────────────────────
COLOR_AZUL_MARINO  = (11, 37, 69)
COLOR_AZUL_AGUA    = (0, 119, 182)
COLOR_CELESTE      = (144, 224, 239)
COLOR_VERDE_ROI    = (46, 125, 50)
COLOR_ROJO_ALERTA  = (198, 40, 40)
COLOR_NARANJA      = (230, 119, 0)
COLOR_GRIS_TEXTO   = (50, 50, 50)
COLOR_GRIS_LABEL   = (100, 110, 120)
COLOR_FONDO_TABLA  = (240, 244, 248)
COLOR_BORDE_TABLA  = (200, 210, 220)

PRIORIDAD_COLORES = {
    "critica": COLOR_ROJO_ALERTA,
    "alta":    COLOR_NARANJA,
    "media":   (180, 130, 0),
    "baja":    (100, 120, 100),
}

EMOJIS_MAP = {
    '💧': '[AGUA]',    '🚜': '[MAQ]',     '📦': '[STOCK]',   '🌾': '[FINCA]',
    '⚡': '[ELEC]',    '🏛️': '',          '📋': '',          '💰': '',
    '📍': '',          '🔍': '',          '💡': '',          '⚙️': '',
    '🏷️': '',          '🏢': '',          '✨': '',          '✅': '',
    '⚖️': '',          '☀️': '[SOLAR]',   '🍊': '[CITRICO]', '🚰': '[AGUA]',
    '🌊': '[AGUA]',   '📄': '',          '🔗': '',          '🤖': '',
    '™️': '',          '🔔': '',          '⚠️': '[AVISO]',
}


class InformeTecnicoPous(FPDF):
    """[MEJORA 3] Header y footer corporativos con semáforo de prioridad."""

    def __init__(self, prioridad: str = "alta"):
        super().__init__()
        self._prioridad = prioridad.lower()

    def header(self):
        # Barra de color según prioridad (semáforo)
        color = PRIORIDAD_COLORES.get(self._prioridad, COLOR_AZUL_AGUA)
        self.set_fill_color(*color)
        self.rect(0, 0, 210, 4, 'F')

        # Fondo azul marino principal
        self.set_fill_color(*COLOR_AZUL_MARINO)
        self.rect(0, 4, 210, 22, 'F')

        self.set_font('helvetica', 'B', 13)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 7)
        self.cell(130, 8, 'RIEGOS POUS, S.L. - SISTEMA DE INTELIGENCIA', 0, 0, 'L')

        self.set_font('helvetica', '', 8)
        self.set_text_color(*COLOR_CELESTE)
        self.set_xy(140, 7)
        self.cell(60, 4, f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
        self.set_xy(140, 11)
        self.cell(60, 4, 'Xeraco (Valencia) | www.riegospous.com', 0, 0, 'R')
        self.ln(22)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*COLOR_AZUL_AGUA)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font('helvetica', 'I', 7.5)
        self.set_text_color(*COLOR_GRIS_LABEL)
        self.cell(0, 4,
                  f'Riegos Pous, S.L. | Av. de Valencia 26-32, 46770 Xeraco (Valencia) | '
                  f'Pag. {self.page_no()} | Documento generado automaticamente por el Sistema de Inteligencia',
                  align='C')


def clean_text(text: str) -> str:
    """[MEJORA 5] Limpieza robusta de texto para compatibilidad latin-1 de FPDF."""
    if not text:
        return ""
    for emoji, reemplazo in EMOJIS_MAP.items():
        text = text.replace(emoji, reemplazo)
    # Caracteres tipográficos
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u20ac', 'EUR').replace('€', 'EUR')
    text = text.replace('\u00b3', '3').replace('m³', 'm3')
    text = text.replace('\u00ba', 'o').replace('°', ' grados')
    return text.encode('latin-1', 'replace').decode('latin-1')


def _parsear_datos_raw(alerta_dict: dict) -> dict:
    """[MEJORA 6] Extrae datos_raw de forma segura, sin romper si el JSON es inválido."""
    raw = {}
    datos_raw = alerta_dict.get("datos_raw") or ""
    if isinstance(datos_raw, str) and datos_raw.strip():
        try:
            raw = json.loads(datos_raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return raw


def _calcular_roi_si_falta(raw: dict, valor: float) -> str:
    """[MEJORA 1] Calcula ROI automáticamente si no existe en datos_raw."""
    if raw.get("roi_texto"):
        return clean_text(raw["roi_texto"])
    if raw.get("roi_estimado"):
        return clean_text(raw["roi_estimado"])

    pvp = raw.get("pvp_mercado_estimado", 0)
    if pvp > 0 and valor > 0:
        margen = pvp - valor
        pct = (margen / pvp) * 100
        return f"PVP mercado: {pvp:,.0f} EUR | Margen: {margen:,.0f} EUR ({pct:.0f}%)"

    # Fallback: estimación por categoría
    if valor > 0:
        margen_est = valor * 0.40
        return f"Margen estimado: {margen_est:,.0f} EUR (40% sobre precio adquisicion)"

    return "Pendiente de valoracion de campo"


def generar_propuesta_pous_pdf(alerta_dict: dict, empresa_cfg: dict = None) -> bytes:
    """
    Genera un informe técnico ejecutivo en PDF para el Director General de Riegos Pous.
    Entrada: dict con los campos de la alerta (id, titulo, resumen, valor_estimado, datos_raw, prioridad, url)
    Salida: bytes del PDF listo para descarga o impresión.
    """
    raw = _parsear_datos_raw(alerta_dict)
    prioridad = alerta_dict.get("prioridad", "alta").lower()
    val = float(alerta_dict.get("valor_estimado", 0) or 0)
    roi_texto = _calcular_roi_si_falta(raw, val)

    pdf = InformeTecnicoPous(prioridad=prioridad)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── TÍTULO DEL EXPEDIENTE ──────────────────────────────
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    titulo = clean_text(alerta_dict.get('titulo', 'Informe de Oportunidad'))
    pdf.multi_cell(0, 7, f'EXPEDIENTE: {titulo}')
    pdf.ln(3)

    # Línea decorativa
    pdf.set_draw_color(*COLOR_AZUL_AGUA)
    pdf.set_line_width(1.0)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # ── [MEJORA 2] TABLA DE MÉTRICAS ECONÓMICAS Y TÉCNICAS ─
    y_start = pdf.get_y()
    pdf.set_fill_color(*COLOR_FONDO_TABLA)
    pdf.rect(10, y_start, 190, 32, 'F')
    pdf.set_draw_color(*COLOR_BORDE_TABLA)
    pdf.rect(10, y_start, 190, 32, 'D')

    # Fila 1: Labels
    pdf.set_xy(14, y_start + 3)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(*COLOR_GRIS_LABEL)
    pdf.cell(55, 5, 'PRECIO ADQUISICION:', 0, 0)
    pdf.cell(80, 5, 'RETORNO ESTIMADO / ROI:', 0, 0)
    pdf.cell(45, 5, 'PRIORIDAD:', 0, 1)

    # Fila 2: Valores
    pdf.set_xy(14, y_start + 10)
    pdf.set_font('helvetica', 'B', 15)
    pdf.set_text_color(*COLOR_AZUL_AGUA)
    pdf.cell(55, 8, f'{val:,.2f} EUR', 0, 0)

    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_VERDE_ROI)
    pdf.cell(80, 8, roi_texto[:58], 0, 0)

    col_p = PRIORIDAD_COLORES.get(prioridad, COLOR_AZUL_AGUA)
    pdf.set_text_color(*col_p)
    pdf.set_font('helvetica', 'B', 13)
    pdf.cell(45, 8, prioridad.upper(), 0, 1)

    # Fila 3: Datos técnicos (marca, potencia)
    pdf.set_xy(14, y_start + 21)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(*COLOR_GRIS_LABEL)
    marca = raw.get("marca", "")
    tipo = raw.get("tipo_equipo", "")
    potencia_cv = raw.get("potencia_cv")
    potencia_kw = raw.get("potencia_kw")
    potencia_kva = raw.get("potencia_kva")
    potencia_str = ""
    if potencia_cv:
        potencia_str += f"{potencia_cv:.0f} CV"
    if potencia_kw:
        potencia_str += f" / {potencia_kw:.0f} kW"
    if potencia_kva:
        potencia_str += f" / {potencia_kva:.0f} kVA"

    if marca or tipo:
        ficha_tecnica = f"Equipo: {tipo or 'N/A'} | Marca: {marca or 'N/A'}"
        if potencia_str:
            ficha_tecnica += f" | Potencia: {potencia_str}"
        pdf.multi_cell(0, 4, clean_text(ficha_tecnica))

    pdf.set_y(y_start + 35)
    pdf.ln(2)

    # ── SECCIÓN 1: DESCRIPCIÓN Y DETALLES ─────────────────
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(0, 6, '1. DESCRIPCION TECNICA DEL ACTIVO / LICITACION:', 0, 1)
    pdf.ln(1)

    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(*COLOR_GRIS_TEXTO)
    resumen_raw = clean_text(alerta_dict.get('resumen', 'Sin detalles adicionales.'))
    for line in resumen_raw.split('\n'):
        stripped = line.strip()
        if stripped:
            pdf.multi_cell(0, 5, stripped)
            pdf.ln(1)
    pdf.ln(3)

    # ── [MEJORA 4] SECCIÓN 2: DICTAMEN TÉCNICO (del LLM o pre-escrito) ──
    dictamen = clean_text(raw.get("dictamen", ""))
    if dictamen:
        pdf.set_fill_color(235, 245, 255)
        pdf.rect(10, pdf.get_y(), 190, 12, 'F')
        pdf.set_draw_color(*COLOR_AZUL_AGUA)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 13, pdf.get_y() + 12)
        pdf.set_xy(15, pdf.get_y() + 2)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(*COLOR_AZUL_MARINO)
        pdf.cell(0, 4, 'DICTAMEN TECNICO (Sistema de Inteligencia Riegos Pous):', 0, 1)
        pdf.set_xy(15, pdf.get_y())
        pdf.set_font('helvetica', 'I', 9)
        pdf.set_text_color(0, 80, 140)
        pdf.multi_cell(182, 5, dictamen)
        pdf.ln(5)

    # ── SECCIÓN 3: ESPECIFICACIONES ADICIONALES ────────────
    especificaciones = clean_text(raw.get("especificaciones", ""))
    if especificaciones:
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(*COLOR_AZUL_MARINO)
        pdf.cell(0, 6, '2. ESPECIFICACIONES TECNICAS:', 0, 1)
        pdf.set_font('helvetica', '', 9)
        pdf.set_text_color(*COLOR_GRIS_TEXTO)
        pdf.multi_cell(0, 5, especificaciones)
        pdf.ln(3)

    # ── SECCIÓN FINAL: PLAN DE ACTUACIÓN ──────────────────
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(0, 6, '3. PLAN DE ACCION RECOMENDADO PARA RIEGOS POUS, S.L.:', 0, 1)
    pdf.ln(1)

    pdf.set_font('helvetica', '', 8.5)
    pdf.set_text_color(*COLOR_GRIS_TEXTO)
    pasos = [
        "A) VERIFICACION DE CAMPO: Desplazamiento de tecnico para comprobar caudal, potencia electrica, "
        "estado mecanico o titularidad registral del activo.",
        "B) VALORACION DE STOCK PROPIO: Comprobar disponibilidad en almacen de Xeraco de equipos "
        "complementarios (Caprari/Grundfos, variadores, tuberia PE, cuadros de maniobra).",
        "C) CALCULO DE OFERTA COMPETITIVA: Preparar presupuesto de adquisicion + instalacion + margen "
        "comercial para presentar al cliente o al organo judicial.",
        "D) PRESENTACION OFICIAL: Tramitacion telematica con Certificado Digital de Riegos Pous, S.L. "
        "en la plataforma oficial (PLACSP / BOE / Sede Electronica).",
    ]
    for p in pasos:
        pdf.multi_cell(0, 5, f'- {p}')
        pdf.ln(1)

    pdf.ln(6)

    # ── ENLACE FUENTE OFICIAL ──────────────────────────────
    url = alerta_dict.get("url", "")
    if url:
        pdf.set_font('helvetica', 'B', 8.5)
        pdf.set_text_color(*COLOR_AZUL_AGUA)
        pdf.cell(0, 5, f'Fuente oficial: {url[:90]}', 0, 1)
        pdf.ln(6)

    # ── CUADRO DE FIRMAS ───────────────────────────────────
    y_firm = pdf.get_y()
    if y_firm > 250:  # Si quedan pocas líneas, nueva página
        pdf.add_page()
        y_firm = pdf.get_y()

    pdf.set_draw_color(*COLOR_BORDE_TABLA)
    pdf.set_line_width(0.5)
    pdf.rect(10, y_firm, 90, 30)
    pdf.rect(110, y_firm, 90, 30)

    for x, texto_b, texto_n in [
        (12, 'DPTO. TECNICO Y LICITACIONES', 'Riegos Pous, S.L. - Xeraco (Valencia)'),
        (112, 'CONFORME DIRECCION GENERAL', 'Firma y Sello de la Empresa'),
    ]:
        pdf.set_xy(x, y_firm + 4)
        pdf.set_font('helvetica', 'B', 8)
        pdf.set_text_color(*COLOR_GRIS_LABEL)
        pdf.cell(85, 4, texto_b, 0, 1)
        pdf.set_xy(x, y_firm + 9)
        pdf.set_font('helvetica', '', 7.5)
        pdf.cell(85, 4, texto_n, 0, 1)
        pdf.set_xy(x, y_firm + 20)
        pdf.set_draw_color(*COLOR_BORDE_TABLA)
        pdf.line(x, y_firm + 26, x + 80, y_firm + 26)

    # ── OUTPUT ─────────────────────────────────────────────
    out = pdf.output()
    return bytes(out) if isinstance(out, (bytearray, bytes)) else str(out).encode('latin1')
