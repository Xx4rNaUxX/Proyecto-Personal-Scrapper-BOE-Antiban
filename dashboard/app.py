"""
Dashboard Web en FastAPI - Renderizado dinámico sin fichero en disco.
Los enlaces usan la URL almacenada en la BD o, si está vacía, el portal público del vector.
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from core.storage import Storage

try:
    from engines.doc_generator import generar_escrito_168
    DOC_GEN_AVAILABLE = True
except ImportError:
    DOC_GEN_AVAILABLE = False

try:
    from engines.pdf_generator import generar_pdf_propuesta
    PDF_GEN_AVAILABLE = True
except ImportError:
    PDF_GEN_AVAILABLE = False

app = FastAPI(title="Arbitraje Legal Dashboard")
storage = Storage("data/arbitraje.db")

VECTOR_ICONS = {
    "placsp": "📋",
    "bopi": "™️",
    "concursal": "⚖️",
}

VECTOR_NOMBRES = {
    "placsp": "Licitación Desierta",
    "bopi": "Marca BOPI",
    "concursal": "Liquidación Concursal",
}

# URL pública garantizada por vector (página de inicio, sin deep-link)
VECTOR_FALLBACK = {
    "placsp": "https://contrataciondelestado.es",
    "bopi": "https://www.oepm.es/es/signos_distintivos/",
    "concursal": "https://subastas.boe.es/",
}

@app.on_event("startup")
async def startup():
    await storage.initialize()

@app.get("/generar_doc/{alerta_id}")
async def descargar_documento(alerta_id: str):
    if not DOC_GEN_AVAILABLE:
        raise HTTPException(status_code=501, detail="Generador de documentos no disponible")
        
    alerta = await storage.obtener_alerta(alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
        
    # Mock data for the user
    solicitante = {
        "nombre": "TU EMPRESA S.L. / AUTÓNOMO",
        "nif": "B12345678",
        "domicilio": "C/ Principal 123, 28000 Madrid",
        "email": "contacto@tuempresa.es",
        "telefono": "600000000"
    }
    
    # Adapt to the expected dict
    licitacion = {
        "id": alerta.get("id", "").replace("placsp_", ""),
        "titulo": alerta.get("titulo", "Licitación Desierta"),
        "organo_contratacion": alerta.get("resumen", "").split("Órgano: ")[-1] if "Órgano: " in alerta.get("resumen", "") else "Órgano de Contratación",
        "presupuesto_base": alerta.get("valor_estimado", 0.0),
        "url_expediente": alerta.get("url", ""),
        "tipo_contrato": "Servicios"
    }
    
    doc_path = generar_escrito_168(licitacion, solicitante)
    if not os.path.exists(doc_path):
        raise HTTPException(status_code=500, detail="Error al generar el documento")
        
    return FileResponse(
        path=doc_path, 
        filename=os.path.basename(doc_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@app.get("/generar_pdf/{alerta_id}")
async def descargar_pdf_comercial(alerta_id: str):
    if not PDF_GEN_AVAILABLE:
        raise HTTPException(status_code=501, detail="Generador de PDF no disponible")
    
    alerta = await storage.obtener_alerta(alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
        
    os.makedirs("docs_generados", exist_ok=True)
    file_path = f"docs_generados/Propuesta_{alerta_id}.pdf"
    
    generar_pdf_propuesta(alerta, file_path)
    
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=f"Propuesta_{alerta_id}.pdf", media_type="application/pdf")
    raise HTTPException(status_code=500, detail="Error al generar PDF")

from engines.sales_agent import SalesAgent
sales_agent = SalesAgent()

@app.get("/generar_email/{alerta_id}")
async def generar_email_endpoint(alerta_id: str):
    alerta = await storage.obtener_alerta(alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
        
    vector = alerta.get("vector", "")
    titulo = alerta.get("titulo", "")
    resumen = alerta.get("resumen", "")
    valor = alerta.get("valor_estimado", 0.0)
    
    email = await sales_agent.generar_cold_email(vector, titulo, resumen, float(valor))
    
    # Extraer asunto y cuerpo limpiamente (asumiendo formato "📧 ASUNTO: X \n\n Y")
    partes = email.split("\n\n", 1)
    asunto_raw = partes[0].replace("📧 ASUNTO:", "").strip() if len(partes) > 0 else "Oportunidad B2B"
    cuerpo_raw = partes[1].strip() if len(partes) > 1 else email
    
    import urllib.parse
    asunto_encoded = urllib.parse.quote(asunto_raw)
    cuerpo_encoded = urllib.parse.quote(cuerpo_raw)
    
    # Renderizamos una pequeña vista HTML para el borrador del email
    html_content = f"""
    <html>
        <head>
            <title>Borrador de Cold Email (Generado por IA)</title>
            <style>
                body {{ font-family: system-ui; background: #0f172a; color: white; padding: 2rem; }}
                .email-box {{ background: #1e293b; padding: 2rem; border-radius: 8px; border: 1px solid #334155; white-space: pre-wrap; font-size: 1.1rem; }}
                .btn {{ background: #10b981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 15px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h2>🤖 IA de Ventas (Fase 6) - Borrador de Cold Email</h2>
            <div class="email-box">{email}</div>
            <br>
            <a href="javascript:history.back()" class="btn">Volver al Dashboard</a>
            <a href="mailto:competidor@ejemplo.com?subject={asunto_encoded}&body={cuerpo_encoded}" class="btn" style="background:#3b82f6;">📧 Enviar por Correo</a>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


from pydantic import BaseModel
class CRMUpdate(BaseModel):
    estado_crm: str

@app.post("/api/crm/{alerta_id}")
async def actualizar_crm(alerta_id: str, payload: CRMUpdate):
    exito = await storage.actualizar_estado_crm(alerta_id, payload.estado_crm)
    if not exito:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return {"status": "ok", "estado_crm": payload.estado_crm}


import csv
from io import StringIO
from fastapi.responses import StreamingResponse

@app.get("/api/export")
async def exportar_csv():
    alertas = await storage.listar_alertas(limite=1000)
    
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["ID", "Vector", "Título", "Valor Estimado", "Prioridad", "Estado CRM", "Fecha Creación"])
    
    for a in alertas:
        writer.writerow([
            a["id"], a["vector"], a["titulo"], 
            a["valor_estimado"], a["prioridad"], 
            a.get("estado_crm", "Pendiente"), a["fecha_creacion"]
        ])
        
    stream.seek(0)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=leads_arbitraje.csv"
    return response


@app.get("/", response_class=HTMLResponse)
async def read_root():
    stats = await storage.estadisticas()
    alertas = await storage.listar_alertas(limite=50)

    filas_html = ""
    for a in alertas:
        icon   = VECTOR_ICONS.get(a["vector"], "📌")
        nombre = VECTOR_NOMBRES.get(a["vector"], a["vector"])
        url    = (a.get("url") or "").strip() or VECTOR_FALLBACK.get(a["vector"], "#")

        badge_color = {"critica":"#dc2626","alta":"#ea580c","media":"#ca8a04","baja":"#16a34a"}.get(a["prioridad"],"#6b7280")
        badge_bg    = {"critica":"#fef2f2","alta":"#fff7ed","media":"#fefce8","baja":"#f0fdf4"}.get(a["prioridad"],"#f4f4f5")
        resumen_corto = (a["resumen"] or "")[:90]
        
        # Botones dinámicos según Fase y Vector
        btn_actuar = ""
        if a["vector"] == "placsp":
            btn_actuar = f'<a href="/generar_doc/{a["id"]}" class="btn-action">📝 Generar Escrito (Legal)</a>'
        elif a["vector"] in ["bopi", "concursal"]:
            btn_actuar = (
                f'<a href="/generar_email/{a["id"]}" class="btn-action" style="background: linear-gradient(135deg, #3b82f6, #2563eb);">🤖 IA: Redactar Venta</a> '
                f'<a href="/generar_pdf/{a["id"]}" class="btn-action" style="background: linear-gradient(135deg, #10b981, #059669); margin-left: 5px;">📄 Generar PDF Propuesta</a>'
            )

        # Selector CRM
        estado_crm = a.get("estado_crm", "Pendiente")
        opciones_crm = ["Pendiente", "Email Enviado", "Negociando", "Ganada", "Descartada"]
        opciones_html = "".join([f'<option value="{op}" {"selected" if op == estado_crm else ""}>{op}</option>' for op in opciones_crm])
        select_crm = f'<select onchange="actualizarCRM(\'{a["id"]}\', this.value)" style="background:#1e293b; color:white; border:1px solid #334155; padding:4px; border-radius:4px; font-size:0.9em; outline:none; cursor:pointer;">{opciones_html}</select>'

        filas_html += f"""
        <tr>
          <td><span title="{nombre}">{icon} {nombre}</span></td>
          <td><strong>{a["titulo"]}</strong><br><small style="color:#64748b">{resumen_corto}</small></td>
          <td><span style="background:{badge_bg};color:{badge_color};padding:3px 10px;border-radius:999px;font-size:.8em;font-weight:600">{a["prioridad"].upper()}</span></td>
          <td>{a["valor_estimado"]:,.0f} €</td>
          <td style="font-size:.85em;color:#64748b">{select_crm}</td>
          <td>
            <div style="display:flex;gap:8px;align-items:center">
                <a href="{url}" target="_blank" rel="noopener"
                   style="background:#2563eb;color:white;padding:5px 12px;border-radius:6px;text-decoration:none;font-size:.85em;white-space:nowrap">
                   🔗 Ver Portal</a>
                {btn_actuar}
            </div>
          </td>
        </tr>"""

    valor_total = stats.get("valor_total_estimado") or 0
    nuevas_24h  = stats.get("nuevas_24h") or 0
    pv          = stats.get("por_vector", {})
    v1, v2, v3  = pv.get("placsp",0), pv.get("bopi",0), pv.get("concursal",0)
    total       = sum(pv.values())

    cuerpo_tabla = filas_html if alertas else (
        "<tr><td colspan='6' style='text-align:center;padding:60px;color:#94a3b8;font-size:1.1rem'>"
        "⏳ El motor está activo. Esperando primer ciclo de escaneo…</td></tr>"
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Arbitraje Legal · Panel Avanzado</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root {{
      --bg-color: #0b0f19;
      --surface: rgba(30, 41, 59, 0.6);
      --glass-border: rgba(255, 255, 255, 0.08);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --success: #10b981;
    }}
    body{{font-family:'Inter', sans-serif;background:var(--bg-color);color:var(--text-main);min-height:100vh;
          background-image: radial-gradient(circle at top right, rgba(59, 130, 246, 0.15), transparent 40%),
                            radial-gradient(circle at bottom left, rgba(16, 185, 129, 0.1), transparent 40%);
          background-attachment: fixed;}}
    header{{background:rgba(15, 23, 42, 0.7);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
            border-bottom:1px solid var(--glass-border);padding:20px 40px;display:flex;align-items:center;gap:18px;
            position:sticky;top:0;z-index:100}}
    header h1{{font-family:'Outfit',sans-serif;font-size:1.6rem;font-weight:800;letter-spacing:-.5px;
               background:linear-gradient(90deg, #60a5fa, #a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
    header small{{opacity:.8;font-size:.85rem;color:var(--text-muted)}}
    
    .btn{{background:var(--accent);color:white;border:none;padding:10px 22px;border-radius:10px;
          cursor:pointer;font-size:.9rem;font-weight:600;text-decoration:none;display:inline-block;
          transition:all 0.3s ease;box-shadow:0 4px 15px rgba(59,130,246,0.3);}}
    .btn:hover{{background:var(--accent-hover);transform:translateY(-2px);box-shadow:0 6px 20px rgba(59,130,246,0.4);}}
    
    .btn-action{{background:var(--success);color:white;padding:6px 14px;border-radius:8px;text-decoration:none;
                 font-size:.85em;font-weight:600;transition:all 0.3s;box-shadow:0 2px 10px rgba(16,185,129,0.2);}}
    .btn-action:hover{{background:#059669;transform:translateY(-1px);box-shadow:0 4px 15px rgba(16,185,129,0.3);}}
    
    .container{{padding:35px 40px;max-width:1400px;margin:0 auto}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px;margin-bottom:40px}}
    
    .card{{background:var(--surface);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
           border:1px solid var(--glass-border);border-radius:16px;padding:24px;
           transition:transform 0.3s, box-shadow 0.3s;}}
    .card:hover{{transform:translateY(-5px);box-shadow:0 10px 30px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1);}}
    .card h3{{font-family:'Outfit',sans-serif;font-size:.8rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;
              color:var(--text-muted);margin-bottom:12px}}
    .card .val{{font-family:'Outfit',sans-serif;font-size:2.4rem;font-weight:800;color:var(--text-main)}}
    .card .sub{{font-size:.85rem;color:var(--text-muted);margin-top:6px}}
    
    h2{{margin-bottom:20px;font-family:'Outfit',sans-serif;font-size:1.4rem;font-weight:600}}
    
    .table-container{{background:var(--surface);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
                      border:1px solid var(--glass-border);border-radius:16px;overflow:hidden;
                      box-shadow:0 10px 30px rgba(0,0,0,0.3);}}
    table{{width:100%;border-collapse:collapse;}}
    th{{background:rgba(0,0,0,0.2);color:var(--text-muted);font-size:.75rem;font-weight:600;
        text-transform:uppercase;letter-spacing:1px;padding:16px 20px;text-align:left;border-bottom:1px solid var(--glass-border)}}
    td{{padding:16px 20px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:middle;font-size:.9rem}}
    tr{{transition:background 0.2s;}}
    tr:hover td{{background:rgba(255,255,255,0.03);}}
    
    .badge {{padding:4px 12px;border-radius:999px;font-size:.75em;font-weight:600;letter-spacing:0.5px;}}
    .badge-critica {{background:rgba(220,38,38,0.15);color:#fca5a5;border:1px solid rgba(220,38,38,0.3);}}
    .badge-alta {{background:rgba(234,88,12,0.15);color:#fdba74;border:1px solid rgba(234,88,12,0.3);}}
    .badge-media {{background:rgba(202,138,4,0.15);color:#fde047;border:1px solid rgba(202,138,4,0.3);}}
    .badge-baja {{background:rgba(22,163,74,0.15);color:#86efac;border:1px solid rgba(22,163,74,0.3);}}
    
    .search-box {{
        width: 100%;
        padding: 16px 24px;
        margin-bottom: 24px;
        background: var(--surface);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border);
        border-radius: 12px;
        color: white;
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        transition: all 0.3s;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }}
    .search-box:focus {{
        outline: none;
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3), 0 4px 15px rgba(0,0,0,0.3);
    }}
    .search-box::placeholder {{
        color: #94a3b8;
    }}
  </style>
  <script>
    async function actualizarCRM(id, nuevoEstado) {{
        try {{
            const res = await fetch(`/api/crm/${{id}}`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ estado_crm: nuevoEstado }})
            }});
            if(!res.ok) alert('Error al actualizar el estado CRM');
        }} catch(e) {{
            alert('Fallo de conexión al servidor');
        }}
    }}

    function filtrarTabla() {{
        const input = document.getElementById('searchBar');
        const filter = input.value.toLowerCase();
        const table = document.getElementById('oportunidadesTable');
        const tr = table.getElementsByTagName('tr');

        for (let i = 1; i < tr.length; i++) {{ // Start at 1 to skip table header
            const tds = tr[i].getElementsByTagName('td');
            let rowContainsFilter = false;
            for(let j = 0; j < tds.length; j++) {{
                if (tds[j]) {{
                    const txtValue = tds[j].textContent || tds[j].innerText;
                    if (txtValue.toLowerCase().indexOf(filter) > -1) {{
                        rowContainsFilter = true;
                        break;
                    }}
                }}
            }}
            tr[i].style.display = rowContainsFilter ? "" : "none";
        }}
    }}
  </script>
</head>
<body>
  <header>
    <div style="font-size:2rem;filter:drop-shadow(0 0 10px rgba(96,165,250,0.5))">⚖️</div>
    <div>
      <h1>Arbitraje Legal Pro</h1>
      <small>Algoritmos de detección de ineficiencias del Estado Español</small>
    </div>
    <a class="btn" href="/api/export" style="margin-left:auto; background:#10b981;">📥 Exportar CSV</a>
    <a class="btn" href="/" style="margin-left:10px;">↻ Actualizar Feed</a>
  </header>

  <div class="container">
    <div class="grid">
      <div class="card">
        <h3>Valor Potencial Total</h3>
        <div class="val">{valor_total:,.0f} €</div>
        <div class="sub">Capital expuesto capturado</div>
      </div>
      <div class="card">
        <h3>Oportunidades</h3>
        <div class="val">{total}</div>
        <div class="sub">Nuevas 24h: <span style="color:var(--success)">+{nuevas_24h}</span></div>
      </div>
      <div class="card">
        <h3>📋 Licitaciones Desiertas</h3>
        <div class="val">{v1}</div>
        <div class="sub">Vector 1 · Ley de Contratos</div>
      </div>
      <div class="card">
        <h3>™️ Marcas Caducadas</h3>
        <div class="val">{v2}</div>
        <div class="sub">Vector 2 · OEPM</div>
      </div>
    </div>

    <h2>Últimas Anomalías Detectadas</h2>
    <input type="text" id="searchBar" class="search-box" onkeyup="filtrarTabla()" placeholder="🔍 Buscar por palabra clave, estado CRM, precio, título, etc...">
    <div class="table-container">
      <table id="oportunidadesTable">
        <thead>
          <tr>
            <th>Vector</th>
            <th>Objeto de la anomalía</th>
            <th>Prioridad</th>
            <th>Valor Est.</th>
            <th>Estado</th>
            <th>Acción Inmediata</th>
          </tr>
        </thead>
        <tbody>{cuerpo_tabla}</tbody>
      </table>
    </div>
  </div>
</body>
</html>"""
    response = HTMLResponse(content=html)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = "0"
    return response
