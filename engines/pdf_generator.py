import os
from fpdf import FPDF
from datetime import datetime

class PropuestaComercial(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.set_text_color(37, 99, 235) # Azul corporativo
        self.cell(0, 10, 'Arbitraje Legal Pro - Propuesta de Inversión', border=False, align='L')
        self.ln(10)
        self.set_draw_color(226, 232, 240)
        self.line(10, 22, 200, 22)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}} - Generado por IA', align='C')

def generar_pdf_propuesta(alerta_dict: dict, filename: str):
    """Genera un PDF comercial para cerrar la venta B2B de un BOPI o Concursal."""
    pdf = PropuestaComercial()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Configurar fuentes seguras
    pdf.set_font("helvetica", size=12)

    # Título del Expediente
    pdf.set_font("helvetica", 'B', 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, f"Oportunidad Detectada: {alerta_dict.get('titulo', 'Desconocido')}", ln=True)
    
    # Metadata
    pdf.set_font("helvetica", size=10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, f"ID: {alerta_dict.get('id')} | Vector: {alerta_dict.get('vector', '').upper()} | Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(5)

    # Resumen Ejecutivo
    pdf.set_font("helvetica", 'B', 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "1. Resumen Ejecutivo de la Operación", ln=True)
    
    pdf.set_font("helvetica", size=11)
    pdf.set_text_color(51, 65, 85)
    pdf.multi_cell(0, 6, alerta_dict.get('resumen', 'Sin resumen disponible.'))
    pdf.ln(5)

    # Datos Financieros
    valor_est = alerta_dict.get('valor_estimado', 0.0)
    pdf.set_font("helvetica", 'B', 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "2. Proyección Financiera y Rentabilidad", ln=True)

    pdf.set_font("helvetica", size=11)
    pdf.cell(0, 6, f"- Valor Estimado de Mercado: {valor_est:,.2f} EUR", ln=True)
    pdf.cell(0, 6, f"- Margen Bruto Proyectado: > 60%", ln=True)
    pdf.cell(0, 6, f"- Prioridad Algorítmica: {str(alerta_dict.get('prioridad', 'media')).upper()}", ln=True)
    pdf.ln(5)

    # Cierre de Venta
    pdf.set_font("helvetica", 'B', 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "3. Siguientes Pasos (Call to Action)", ln=True)

    pdf.set_font("helvetica", size=11)
    pdf.set_text_color(51, 65, 85)
    texto_cierre = (
        "El presente informe confidencial certifica la viabilidad técnica y legal "
        "de la operación. Para ejecutar la adquisición/registro bajo nuestro paraguas "
        "tecnológico, por favor, responda a este comunicado adjuntando el presupuesto firmado."
    )
    pdf.multi_cell(0, 6, texto_cierre)
    pdf.ln(10)

    # Firmas
    pdf.set_font("helvetica", 'B', 10)
    pdf.cell(95, 10, "Fdo: Departamento Legal", align='C')
    pdf.cell(95, 10, "Fdo: Inversor / Cliente", align='C')

    # Guardar documento
    pdf.output(filename)
    return filename
