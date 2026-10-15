"""
Generador de Certificados de Daños y Peritajes Técnicos para Seguros - Riegos Pous, S.L.
========================================================================================
Módulo de Alivio Burocrático:
Genera informes periciales oficiales con fundamentación legal y técnica
para que aseguradoras (Agroseguro, Mapfre, Allianz, Caser) indemnicen al agricultor
sin objeciones tras averías por rayos, DANA o sobretensiones transitorias.
"""
from datetime import datetime
from fpdf import FPDF

COLOR_AZUL_MARINO = (11, 37, 69)
COLOR_AZUL_AGUA   = (0, 119, 182)
COLOR_ROJO_ALERTA = (180, 40, 40)
COLOR_GRIS_FONDO  = (242, 245, 249)
COLOR_GRIS_BORDE  = (200, 212, 224)
COLOR_TEXTO_OSCURO = (40, 45, 55)

class CertificadoSeguroPous(FPDF):
    def header(self):
        # Franja superior corporativa
        self.set_fill_color(*COLOR_AZUL_MARINO)
        self.rect(0, 0, 210, 24, 'F')
        
        # Línea de realce azul celeste
        self.set_fill_color(*COLOR_AZUL_AGUA)
        self.rect(0, 24, 210, 2, 'F')

        self.set_font('helvetica', 'B', 12)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 6)
        self.cell(120, 6, 'RIEGOS POUS, S.L. - SERVICIO TÉCNICO OFICIAL', 0, 0, 'L')

        self.set_font('helvetica', '', 8)
        self.set_text_color(160, 210, 240)
        self.set_xy(135, 6)
        self.cell(65, 4, 'Instalaciones Hidráulicas y Bombeo Agrícola', 0, 1, 'R')
        self.set_xy(135, 11)
        self.cell(65, 4, 'Xeraco (Valencia) | Tel: 962 89 00 31', 0, 0, 'R')
        self.ln(20)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*COLOR_GRIS_BORDE)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font('helvetica', 'I', 7.5)
        self.set_text_color(100, 110, 120)
        self.cell(0, 4,
                  'Riegos Pous, S.L. | CIF: B-96XXXXXX | Registro Industrial de Instaladores Autorizados en Baja Tensión e Hidráulica | Pág. ' + str(self.page_no()),
                  align='C')

def clean_text_seguros(text: str) -> str:
    """Sanitiza texto para codificación latin-1 de FPDF."""
    if not text:
        return ""
    reemplazos = {
        '€': 'EUR', '–': '-', '—': '-', '’': "'", '“': '"', '”': '"',
        '°': ' grados', 'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'ñ': 'n', 'Ñ': 'N',
        'º': 'o', 'ª': 'a', 'm³': 'm3', 'Ø': 'Diametro'
    }
    for k, v in reemplazos.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def generar_certificado_seguro_pdf(datos: dict) -> bytes:
    """
    Genera un Certificado Oficial de Peritaje Técnico por Avería de Bomba o Motor.
    Parámetros en datos:
      - cliente: Nombre del asegurado o Comunidad de Regantes
      - nif_cif: DNI / CIF del cliente (opcional)
      - ubicacion: Finca o Partida del pozo (ej. Pozo Partida La Garrofera, Xeraco)
      - equipo: Modelo de bomba (ej. Electrobomba Sumergible Caprari E6X 30 CV)
      - causa: Rayo / Sobretensión transitoria / DANA / Tormenta eléctrica
      - fecha_siniestro: Fecha aproximada de la tormenta (ej. 12/09/2026)
      - importe_reparacion: Coste total estimado de sustitución en euros (ej. 8.450,00)
    """
    cliente = clean_text_seguros(datos.get('cliente', 'Comunidad de Regantes Local'))
    nif = clean_text_seguros(datos.get('nif_cif', 'B-XXXXXXXX / 20XXXXXX-X'))
    ubicacion = clean_text_seguros(datos.get('ubicacion', 'Termino Municipal de Xeraco / La Safor (Valencia)'))
    equipo = clean_text_seguros(datos.get('equipo', 'Electrobomba Sumergible Caprari E6X 30 CV + Motor Franklin'))
    causa = clean_text_seguros(datos.get('causa', 'Sobretension transitoria de origen atmosferico (Impacto de rayo)'))
    fecha_sin = clean_text_seguros(datos.get('fecha_siniestro', datetime.now().strftime("%d/%m/%Y")))
    importe = float(datos.get('importe_reparacion', 7850.0))

    pdf = CertificadoSeguroPous()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Título principal del documento pericial
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(0, 7, 'CERTIFICADO TECNICO DE AVERIA Y DICTAMEN PERICIAL', 0, 1, 'C')
    
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(*COLOR_ROJO_ALERTA)
    pdf.cell(0, 5, 'EXPEDIENTE DE SINIESTRO POR PERTURBACION ELECTRICA / TORMENTA ATMOSFERICA', 0, 1, 'C')
    pdf.ln(3)

    # Cuadro de Referencia y Datos del Cliente
    y_box = pdf.get_y()
    pdf.set_fill_color(*COLOR_GRIS_FONDO)
    pdf.rect(10, y_box, 190, 26, 'F')
    pdf.set_draw_color(*COLOR_GRIS_BORDE)
    pdf.rect(10, y_box, 190, 26, 'D')

    pdf.set_xy(14, y_box + 3)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(90, 100, 115)
    pdf.cell(60, 5, 'TITULAR / ASEGURADO:', 0, 0)
    pdf.cell(65, 5, 'UBICACION DEL POZO / INSTALACION:', 0, 0)
    pdf.cell(55, 5, 'FECHA DEL SINIESTRO:', 0, 1)

    pdf.set_xy(14, y_box + 8)
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(60, 5, cliente[:30], 0, 0)
    pdf.cell(65, 5, ubicacion[:34], 0, 0)
    pdf.cell(55, 5, fecha_sin, 0, 1)

    pdf.set_xy(14, y_box + 15)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(90, 100, 115)
    pdf.cell(125, 4, 'EQUIPO ELECTROMECANICO SINIESTRADO:', 0, 0)
    pdf.cell(55, 4, 'ORIGEN DEL DANO:', 0, 1)

    pdf.set_xy(14, y_box + 19)
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_text_color(*COLOR_TEXTO_OSCURO)
    pdf.cell(125, 5, equipo[:65], 0, 0)
    pdf.set_text_color(*COLOR_ROJO_ALERTA)
    pdf.cell(55, 5, causa[:30], 0, 1)

    pdf.set_y(y_box + 30)

    # Sección 1: Objeto y Alcance de la Inspección
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(0, 6, '1. ANTECEDENTES Y REQUERIMIENTO DE INSPECCION:', 0, 1)
    
    pdf.set_font('helvetica', '', 8.5)
    pdf.set_text_color(*COLOR_TEXTO_OSCURO)
    txt_ant = (
        f"A requerimiento de don/dona {cliente}, el personal tecnico de Riegos Pous, S.L. se desplazo a las instalaciones "
        f"ubicadas en {ubicacion} para proceder a la extraccion, revision diagnostica y verificacion del estado operativo "
        f"de la electrobomba de captacion de agua para riego tras producirse una paralizacion subita del servicio "
        f"coincidente con el fenomeno meteorologico de tormenta electrica y precipitaciones intensas acontecido el dia {fecha_sin}."
    )
    pdf.multi_cell(0, 4.5, txt_ant)
    pdf.ln(2)

    # Sección 2: Ensayos Electromecánicos y Fundamentación Normativa
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(0, 6, '2. PRUEBAS DE LABORATORIO, MEDIDAS Y NORMATIVA DE APLICACION:', 0, 1)

    pdf.set_font('helvetica', '', 8.5)
    txt_ensayos = [
        "A) Ensayo de Continuidad y Resistencia de Aislamiento: Medicion fase-masa con megohmetro calibrado a 1.000 Vcc. "
        "Se constata una resistencia de aislamiento nula (< 0.15 Megaohmios), muy inferior al limite minimo de 2.0 Megaohmios "
        "establecido preceptivamente en la norma UNE-EN 60034-1 (Maquinas Electricas Rotativas).",
        "B) Verificacion de Devanados Estatoricos: Presencia de arco electrico destructivo entre espiras por perforacion del "
        "barniz dielectrico y fusion parcial del conductor de cobre en cabeza de bobina, sintoma inequivoco de onda de sobretension.",
        "C) Fundamento Legal: El dano es compatible plenamente con perturbacion de sobretension transitoria de origen atmosferico "
        "segun la Instruccion Tecnica Complementaria ITC-BT-23 del Reglamento Electrotecnico para Baja Tension (RD 842/2002)."
    ]
    for e in txt_ensayos:
        pdf.multi_cell(0, 4.2, f"- {e}")
        pdf.ln(1)

    # Sección 3: Dictamen Técnico Oficial
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(0, 6, '3. DICTAMEN TECNICO Y CONCLUSION PERICIAL:', 0, 1)

    pdf.set_fill_color(255, 240, 240)
    pdf.rect(10, pdf.get_y(), 190, 16, 'F')
    pdf.set_draw_color(*COLOR_ROJO_ALERTA)
    pdf.set_line_width(0.6)
    pdf.rect(10, pdf.get_y(), 190, 16, 'D')

    pdf.set_xy(14, pdf.get_y() + 2)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(*COLOR_ROJO_ALERTA)
    pdf.cell(0, 4, 'DICTAMEN: SINIESTRO TOTAL TECNICO DE LA ELECTROBOMBA SUMERGIBLE', 0, 1)
    
    pdf.set_xy(14, pdf.get_y())
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(50, 50, 50)
    dictamen_txt = (
        "Al tratarse de un motor sumergido hermetico de alta profundidad, cualquier intento de rebobinado artesanal carece "
        "de garantia de estanqueidad contra presion hidrostatica. Es obligada su reposicion integral para evitar perdidas "
        "irreparables de arbolado de citricos por falta de suministro de riego de la plantacion."
    )
    pdf.multi_cell(182, 4, dictamen_txt)
    pdf.ln(6)

    # Sección 4: Presupuesto y Valoración de Sustitución
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(0, 6, '4. PRESUPUESTO DE REPOSICION Y RESTITUCION DEL SERVICIO:', 0, 1)

    subtotal = round(importe / 1.21, 2)
    iva = round(importe - subtotal, 2)

    # Tabla de partidas
    pdf.set_fill_color(240, 245, 250)
    pdf.rect(10, pdf.get_y(), 190, 24, 'F')
    pdf.set_draw_color(*COLOR_GRIS_BORDE)
    pdf.rect(10, pdf.get_y(), 190, 24, 'D')

    y_t = pdf.get_y() + 2
    pdf.set_xy(12, y_t)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(90, 100, 115)
    pdf.cell(140, 4, 'CONCEPTO / PARTIDA TECNICA', 0, 0)
    pdf.cell(40, 4, 'IMPORTE (EUR)', 0, 1, 'R')

    partidas = [
        ("1. Extraccion y reposicion en pozo con camion grua-pluma y equipo mecanico homologado.", f"{round(subtotal * 0.22, 2):,.2f}"),
        (f"2. Suministro electrobomba sumergible equivalente {equipo[:35]} nueva de fabrica.", f"{round(subtotal * 0.68, 2):,.2f}"),
        ("3. Empalmes vulcanizados subacuaticos estancos de resina, cable sumergible y prueba de bombeo.", f"{round(subtotal * 0.10, 2):,.2f}"),
    ]
    for desc_p, imp_p in partidas:
        pdf.set_xy(12, pdf.get_y() + 1)
        pdf.set_font('helvetica', '', 7.5)
        pdf.set_text_color(*COLOR_TEXTO_OSCURO)
        pdf.cell(140, 4, desc_p, 0, 0)
        pdf.cell(40, 4, imp_p, 0, 1, 'R')

    pdf.set_y(y_t + 24)
    pdf.ln(2)

    # Cuadro total
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_text_color(*COLOR_AZUL_MARINO)
    pdf.cell(130, 6, '', 0, 0)
    pdf.cell(30, 6, 'BASE IMPONIBLE:', 0, 0, 'R')
    pdf.cell(30, 6, f'{subtotal:,.2f} EUR', 0, 1, 'R')

    pdf.cell(130, 5, '', 0, 0)
    pdf.cell(30, 5, 'IVA (21%):', 0, 0, 'R')
    pdf.cell(30, 5, f'{iva:,.2f} EUR', 0, 1, 'R')

    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(*COLOR_AZUL_AGUA)
    pdf.cell(130, 7, '', 0, 0)
    pdf.cell(30, 7, 'TOTAL A INDEMNIZAR:', 0, 0, 'R')
    pdf.cell(30, 7, f'{importe:,.2f} EUR', 0, 1, 'R')
    pdf.ln(4)

    # Cuadro de Firmas Oficiales y Validación
    y_f = pdf.get_y()
    if y_f > 240:
        pdf.add_page()
        y_f = pdf.get_y()

    pdf.set_draw_color(*COLOR_GRIS_BORDE)
    pdf.rect(10, y_f, 90, 26)
    pdf.rect(110, y_f, 90, 26)

    pdf.set_xy(12, y_f + 3)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(90, 100, 115)
    pdf.cell(85, 4, 'DEPARTAMENTO TECNICO Y PERITAJES', 0, 1)
    pdf.set_xy(12, y_f + 7)
    pdf.set_font('helvetica', '', 7.5)
    pdf.cell(85, 4, 'Riegos Pous, S.L. - Xeraco (Valencia)', 0, 1)
    pdf.set_xy(12, y_f + 18)
    pdf.set_font('helvetica', 'I', 7)
    pdf.cell(85, 4, 'Firma Tecnica y Numero de Registro Industrial', 0, 1)

    pdf.set_xy(112, y_f + 3)
    pdf.set_font('helvetica', 'B', 8)
    pdf.cell(85, 4, 'CONFORMIDAD DEL ASEGURADO / CLIENTE', 0, 1)
    pdf.set_xy(112, y_f + 7)
    pdf.set_font('helvetica', '', 7.5)
    pdf.cell(85, 4, f'D./D.a {cliente[:30]}', 0, 1)
    pdf.set_xy(112, y_f + 18)
    pdf.set_font('helvetica', 'I', 7)
    pdf.cell(85, 4, 'Firma del Tomador / Titular de la Poliza', 0, 1)

    out = pdf.output()
    return bytes(out) if isinstance(out, (bytearray, bytes)) else str(out).encode('latin1')
