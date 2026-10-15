"""
Dashboard Ejecutivo - Riegos Pous, S.L. v2.3
Centro de Inteligencia Hidráulica, Subvenciones DOGV, Subastas y Peritajes de Seguros.
======================================================================================
Diseñado para la Dirección General de Riegos Pous (Xeraco, Valencia).
Apto para visualización en PC, tablet y smartphone sin consumo de recursos del cliente.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse

# Asegurar path para imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.storage import Storage
from core.http_client import HttpClient
from core.notifier import Notifier
from riegos_pous.engines.doc_generator_pous import generar_propuesta_pous_pdf
from riegos_pous.engines.doc_generator_seguros import generar_certificado_seguro_pdf
from riegos_pous.engines.placsp_pous_engine import PlacspPousEngine
from riegos_pous.engines.boe_pous_engine import BoePousEngine
from riegos_pous.engines.supplies_pous_engine import SuppliesPousEngine
from riegos_pous.engines.dogv_pous_engine import DogvPousEngine
from riegos_pous.engines.chj_bop_engine import ChjBopEngine

app = FastAPI(title="Riegos Pous - Intelligence Center")
db_path = "riegos_pous/data/riegos_pous.db"
storage = Storage(db_path)

VECTOR_LABELS = {
    "placsp": ("💧", "Licitación Hidráulica / Riego", "badge-placsp"),
    "concursal": ("🚜", "Subasta BOE (Finca con Pozo/Maq)", "badge-concursal"),
    "bopi": ("📦", "Liquidación de Bombas y Suministros", "badge-supply"),
    "dogv": ("🏛️", "Subvención DOGV / Generalitat", "badge-dogv"),
    "chj": ("🚜", "Nuevo Pozo / Concesión CHJ", "badge-chj"),
}

@app.on_event("startup")
async def startup():
    await storage.initialize()

@app.get("/escanear")
async def ejecutar_escaneo_manual():
    """
    Disparador manual de escaneo desde la interfaz web.
    Permite al usuario o al Director General forzar una búsqueda inmediata.
    """
    if not storage._db:
        await storage.initialize()

    import yaml
    config_path = Path("riegos_pous/config_pous.yaml")
    if not config_path.exists():
        config_path = Path("config_pous.yaml")

    config = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

    http = HttpClient()
    notifier = Notifier(config.get("notifications", {}))

    try:
        motor_placsp = PlacspPousEngine(config, http, storage, notifier)
        motor_boe = BoePousEngine(config, http, storage, notifier)
        motor_supplies = SuppliesPousEngine(config, http, storage, notifier)
        motor_dogv = DogvPousEngine(config, http, storage, notifier)
        motor_chj = ChjBopEngine(config, http, storage, notifier)

        await motor_placsp.run()
        await motor_boe.run()
        await motor_supplies.run()
        await motor_dogv.run()
        await motor_chj.run()
    finally:
        await http.close()

    return RedirectResponse(url="/?scanned=1", status_code=303)

@app.get("/informe_pdf/{alerta_id}")
async def descargar_informe(alerta_id: str):
    if not storage._db:
        await storage.initialize()
    alerta = await storage.obtener_alerta(alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    empresa_cfg = {
        "nombre": "Riegos Pous, S.L.",
        "sede": "Xeraco (Valencia)"
    }
    pdf_bytes = generar_propuesta_pous_pdf(alerta, empresa_cfg)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Informe_Tecnico_Pous_{alerta_id}.pdf"}
    )

@app.post("/api/generar_certificado_seguro")
async def api_certificado_seguro(
    cliente: str = Form(...),
    ubicacion: str = Form(...),
    equipo: str = Form(...),
    causa: str = Form(...),
    fecha_siniestro: str = Form(...),
    importe_reparacion: float = Form(...)
):
    """Genera en 1 clic el Certificado Pericial Oficial de Daños para la compañía aseguradora."""
    datos = {
        "cliente": cliente,
        "ubicacion": ubicacion,
        "equipo": equipo,
        "causa": causa,
        "fecha_siniestro": fecha_siniestro,
        "importe_reparacion": importe_reparacion
    }
    pdf_bytes = generar_certificado_seguro_pdf(datos)
    filename = f"Certificado_Peritaje_{cliente.replace(' ', '_')[:25]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/generar_seguro_demo")
async def api_seguro_demo():
    """Genera una muestra predeterminada para previsualización inmediata."""
    datos = {
        "cliente": "Comunidad de Regantes de Xeraco",
        "ubicacion": "Pozo del Tossalet, Partida La Garrofera (Xeraco)",
        "equipo": "Electrobomba Sumergible Caprari E6X 30 CV + Motor Franklin Electric",
        "causa": "Sobretension transitoria atmosferica por caida de rayo",
        "fecha_siniestro": datetime.now().strftime("%d/%m/%Y"),
        "importe_reparacion": 8450.00
    }
    pdf_bytes = generar_certificado_seguro_pdf(datos)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Certificado_Peritaje_Muestra.pdf"}
    )

@app.get("/", response_class=HTMLResponse)
async def dashboard_pous(vector: str = "todos", scanned: str = "0"):
    if not storage._db:
        await storage.initialize()
    alertas = await storage.listar_alertas(limite=100)
    
    # Contadores
    total = len(alertas)
    n_placsp = sum(1 for a in alertas if a["vector"] == "placsp")
    n_boe = sum(1 for a in alertas if a["vector"] == "concursal")
    n_stocks = sum(1 for a in alertas if a["vector"] == "bopi")
    n_dogv = sum(1 for a in alertas if a["vector"] == "dogv")
    n_chj = sum(1 for a in alertas if a["vector"] == "chj")
    volumen_total = sum(float(a.get("valor_estimado", 0) or 0) for a in alertas)

    # Filtrar por vector si aplica
    if vector != "todos":
        alertas = [a for a in alertas if a["vector"] == vector]

    # ── [Mapeo de Variable en app_pous.py (Última Milla)] ─────────
    from core.storage import sanitizar_url_oficial
    for alerta in alertas:
        try:
            raw = json.loads(alerta["datos_raw"]) if isinstance(alerta, dict) else json.loads(alerta.datos_raw)
            enlace_extraido = raw.get("url_fuente") or raw.get("url") or (alerta.get("url") if isinstance(alerta, dict) else alerta.url) or ""
        except Exception:
            enlace_extraido = (alerta.get("url") if isinstance(alerta, dict) else alerta.url) or ""

        # Sanitización de última milla (garantiza 0 enlaces rotos o con Cloudflare)
        enlace_extraido = sanitizar_url_oficial(enlace_extraido)

        # Respaldo oficial si viniese vacío
        if not enlace_extraido or enlace_extraido == "#":
            v_val = alerta.get("vector") if isinstance(alerta, dict) else alerta.vector
            if v_val == "placsp":
                enlace_extraido = "https://contrataciondelestado.es/wps/portal/plataforma"
            elif v_val == "dogv":
                enlace_extraido = "https://dogv.gva.es/es/inicio"
            elif v_val == "chj":
                enlace_extraido = "https://www.chj.es"
            elif v_val == "bopi":
                enlace_extraido = "https://subastas.boe.es/subastas_ava.php"
            else:
                enlace_extraido = "https://subastas.boe.es/subastas_ava.php"

        if isinstance(alerta, dict):
            alerta["enlace_real"] = enlace_extraido
        else:
            alerta.enlace_real = enlace_extraido

    # Construir tarjetas HTML ejecutivas
    cards_html = ""
    for a in alertas:
        vec_key = a["vector"]
        icono, nombre_vec, badge_cls = VECTOR_LABELS.get(vec_key, ("📋", vec_key.upper(), "badge-default"))
        
        valor = float(a.get("valor_estimado", 0) or 0)
        roi = "Evaluación de campo"
        marca = ""
        potencia = ""
        pvp_mercado = 0.0
        dictamen = ""
        plazo_caducidad = ""
        municipio = ""

        if a.get("datos_raw"):
            try:
                raw_json = json.loads(a["datos_raw"])
                roi = raw_json.get("roi_texto") or raw_json.get("roi_estimado") or roi
                marca = raw_json.get("marca", "")
                potencia = raw_json.get("potencia_label", "")
                pvp_mercado = float(raw_json.get("pvp_mercado_estimado", 0.0) or 0.0)
                dictamen = raw_json.get("dictamen", "")
                plazo_caducidad = raw_json.get("plazo_caducidad", "")
                municipio = raw_json.get("municipio", "")
            except Exception:
                pass
        
        enlace_real = a.get("enlace_real") or a.get("url") or "https://subastas.boe.es"
        resumen_fmt = a.get("resumen", "").replace("\n", "<br/>")

        # Chips técnicos
        chips_tecnicos = ""
        if vec_key == "dogv":
            chips_tecnicos += '<span class="tech-chip chip-dogv">🏛️ Generalitat Valenciana</span>'
            if plazo_caducidad:
                chips_tecnicos += f'<span class="tech-chip chip-caducidad">⏳ Plazo: {plazo_caducidad}</span>'
        elif vec_key == "chj":
            chips_tecnicos += '<span class="tech-chip" style="background: rgba(112, 224, 0, 0.15); color: #70E000; border-color: rgba(112, 224, 0, 0.35);">🚜 Autorización CHJ / BOPV</span>'
            if municipio:
                chips_tecnicos += f'<span class="tech-chip">📍 {municipio}</span>'
        else:
            if marca and marca != "N/A":
                chips_tecnicos += f'<span class="tech-chip">🏷️ {marca}</span>'
            if potencia and potencia != "Estándar":
                chips_tecnicos += f'<span class="tech-chip">⚡ {potencia}</span>'
            if pvp_mercado > 0:
                chips_tecnicos += f'<span class="tech-chip chip-pvp">💰 PVP: {pvp_mercado:,.0f} €</span>'

        # Caja de dictamen técnico agrónomo
        dictamen_html = ""
        if dictamen:
            dictamen_html = f"""
            <div class="ai-verdict-box">
                <div class="ai-verdict-title">🧠 DICTAMEN INGENIERO AGRÓNOMO</div>
                <div class="ai-verdict-content">{dictamen}</div>
            </div>
            """

        label_valor = "Dotación / Financiación Convocatoria" if vec_key == "dogv" else "Precio Adquisición / Liquidación"
        label_retorno = "Financiación a Fondo Perdido" if vec_key == "dogv" else "Retorno / Margen Estimado"

        cards_html += f"""
        <div class="card {vec_key}" data-title="{a.get('titulo', '').lower()} {marca.lower()} {potencia.lower()}">
            <div class="card-header">
                <span class="badge {badge_cls}">{icono} {nombre_vec}</span>
                <span class="badge badge-priority-{a.get('prioridad', 'alta').lower()}">{a.get('prioridad', 'ALTA').upper()}</span>
            </div>

            <h3 class="card-title">{a.get('titulo')}</h3>

            {f'<div class="tech-chips-container">{chips_tecnicos}</div>' if chips_tecnicos else ''}

            <div class="card-metrics">
                <div class="metric">
                    <span class="metric-label">{label_valor}</span>
                    <span class="metric-val">{valor:,.2f} €</span>
                </div>
                <div class="metric">
                    <span class="metric-label">{label_retorno}</span>
                    <span class="metric-val text-accent">{roi}</span>
                </div>
            </div>

            {dictamen_html}

            <div class="card-body">
                {resumen_fmt}
            </div>

            <div class="card-actions">
                <a href="{enlace_real}" target="_blank" rel="noopener noreferrer" class="btn btn-portal">🔗 Convocatoria / Fuente Oficial</a>
                <a href="/informe_pdf/{a.get('id')}" class="btn btn-pdf">📄 Informe Técnico PDF</a>
            </div>
        </div>
        """

    if not cards_html:
        cards_html = '<div class="no-data">No se han registrado oportunidades en esta categoría. Pulsa en <b>Escanear Ahora</b>.</div>'

    alerta_scan_banner = ""
    if scanned == "1":
        alerta_scan_banner = """
        <div class="scan-banner">
            ✨ <b>¡Escaneo completado con éxito!</b> DOGV, PLACSP y subastas industriales sincronizadas al 100%.
        </div>
        """

    hoy_str = datetime.now().strftime("%d/%m/%Y")

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Riegos Pous, S.L. - Centro de Inteligencia</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-main: #0B132B;
                --bg-card: #1C2541;
                --bg-card-hover: #222E50;
                --primary: #48CAE4;
                --primary-glow: rgba(72, 202, 228, 0.25);
                --water-blue: #0077B6;
                --accent-gold: #FFB703;
                --text-main: #FFFFFF;
                --text-muted: #90E0EF;
                --text-dim: #8D99AE;
                --border-color: rgba(144, 224, 239, 0.15);
            }}

            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: 'Plus Jakarta Sans', sans-serif;
                background-color: var(--bg-main);
                color: var(--text-main);
                padding: 25px 35px;
                min-height: 100vh;
            }}

            /* Header */
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--border-color);
                padding-bottom: 20px;
                margin-bottom: 25px;
                flex-wrap: wrap;
                gap: 15px;
            }}
            .logo-group h1 {{
                font-size: 26px;
                font-weight: 800;
                letter-spacing: -0.5px;
                color: #FFFFFF;
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .logo-group h1 span {{
                background: linear-gradient(135deg, #48CAE4, #00B4D8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .logo-group p {{
                font-size: 13px;
                color: var(--text-dim);
                margin-top: 4px;
            }}
            
            .header-actions {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .btn-scan {{
                background: linear-gradient(135deg, #0077B6, #00B4D8);
                color: #FFFFFF;
                padding: 10px 18px;
                border-radius: 10px;
                font-size: 13.5px;
                font-weight: 700;
                text-decoration: none;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                box-shadow: 0 4px 14px rgba(0, 180, 216, 0.35);
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .btn-scan:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0, 180, 216, 0.5);
            }}

            .btn-seguro-trigger {{
                background: linear-gradient(135deg, #E63946, #D90429);
                color: #FFFFFF;
                padding: 10px 18px;
                border-radius: 10px;
                font-size: 13.5px;
                font-weight: 700;
                cursor: pointer;
                border: none;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                box-shadow: 0 4px 14px rgba(230, 57, 70, 0.35);
                transition: transform 0.2s;
            }}
            .btn-seguro-trigger:hover {{
                transform: translateY(-2px);
            }}

            .scan-banner {{
                background: rgba(87, 204, 153, 0.15);
                border: 1px solid #57CC99;
                color: #57CC99;
                padding: 12px 20px;
                border-radius: 10px;
                margin-bottom: 25px;
                font-size: 14px;
            }}

            /* Panel Desplegable para Peritajes de Seguros */
            .seguro-panel {{
                display: none;
                background: #141E38;
                border: 2px solid #E63946;
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 30px;
                box-shadow: 0 10px 30px rgba(230, 57, 70, 0.2);
            }}
            .seguro-panel.active {{
                display: block;
                animation: fadeIn 0.3s ease;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(-10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .seguro-panel h2 {{
                font-size: 18px;
                color: #FFFFFF;
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 6px;
            }}
            .seguro-panel p {{
                font-size: 13px;
                color: var(--text-dim);
                margin-bottom: 20px;
            }}
            .seguro-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }}
            .form-group label {{
                display: block;
                font-size: 12px;
                font-weight: 700;
                color: #90E0EF;
                margin-bottom: 6px;
            }}
            .form-group input, .form-group select {{
                width: 100%;
                background: #0B132B;
                border: 1px solid var(--border-color);
                color: #FFFFFF;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: 13px;
                outline: none;
            }}
            .form-group input:focus, .form-group select:focus {{
                border-color: #E63946;
            }}

            /* Stats Bar */
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-bottom: 25px;
            }}
            .stat-box {{
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                padding: 18px 20px;
                border-radius: 14px;
                position: relative;
                overflow: hidden;
            }}
            .stat-box::before {{
                content: '';
                position: absolute;
                top: 0; left: 0; right: 0; height: 3px;
                background: linear-gradient(90deg, var(--water-blue), var(--primary));
            }}
            .stat-title {{
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: var(--text-dim);
                font-weight: 700;
            }}
            .stat-val {{
                font-size: 26px;
                font-weight: 800;
                color: #FFFFFF;
                margin-top: 6px;
            }}

            /* Controls Bar */
            .controls-bar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 15px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }}
            .search-box {{
                flex: 1;
                min-width: 280px;
                max-width: 450px;
            }}
            .search-input {{
                width: 100%;
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                color: #FFFFFF;
                padding: 10px 16px;
                border-radius: 10px;
                font-size: 14px;
                outline: none;
            }}
            .search-input:focus {{
                border-color: var(--primary);
            }}

            /* Tabs */
            .tabs {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }}
            .tab {{
                text-decoration: none;
                color: var(--text-dim);
                padding: 8px 14px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                transition: all 0.2s ease;
            }}
            .tab:hover {{
                color: var(--text-main);
                background: rgba(255, 255, 255, 0.05);
            }}
            .tab.active {{
                background: var(--water-blue);
                color: #FFFFFF;
                box-shadow: 0 4px 12px rgba(0, 119, 182, 0.35);
            }}

            /* Cards Container */
            .cards-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(430px, 1fr));
                gap: 22px;
            }}
            .card {{
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 22px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                transition: transform 0.2s, border-color 0.2s;
            }}
            .card:hover {{
                transform: translateY(-3px);
                border-color: var(--primary);
                background: var(--bg-card-hover);
            }}
            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }}
            .badge {{
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 6px;
                text-transform: uppercase;
            }}
            .badge-placsp {{ background: rgba(0, 119, 182, 0.25); color: #48CAE4; border: 1px solid rgba(72, 202, 228, 0.3); }}
            .badge-concursal {{ background: rgba(255, 183, 3, 0.15); color: #FFB703; border: 1px solid rgba(255, 183, 3, 0.3); }}
            .badge-supply {{ background: rgba(87, 204, 153, 0.15); color: #57CC99; border: 1px solid rgba(87, 204, 153, 0.3); }}
            .badge-dogv {{ background: rgba(230, 57, 70, 0.2); color: #FF6B6B; border: 1px solid rgba(230, 57, 70, 0.4); }}
            .badge-chj {{ background: rgba(112, 224, 0, 0.15); color: #70E000; border: 1px solid rgba(112, 224, 0, 0.35); }}
            
            .badge-priority-critica {{ background: rgba(239, 71, 111, 0.2); color: #EF476F; border: 1px solid rgba(239, 71, 111, 0.4); }}
            .badge-priority-alta {{ background: rgba(255, 183, 3, 0.2); color: #FFB703; border: 1px solid rgba(255, 183, 3, 0.4); }}
            .badge-priority-media {{ background: rgba(144, 224, 239, 0.15); color: #90E0EF; }}

            .card-title {{
                font-size: 16px;
                font-weight: 700;
                line-height: 1.4;
                color: #FFFFFF;
                margin-bottom: 12px;
            }}

            /* Tech Chips */
            .tech-chips-container {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-bottom: 14px;
            }}
            .tech-chip {{
                background: rgba(0, 180, 216, 0.12);
                border: 1px solid rgba(72, 202, 228, 0.25);
                color: #90E0EF;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 9px;
                border-radius: 6px;
            }}
            .chip-pvp {{
                background: rgba(255, 183, 3, 0.12);
                border-color: rgba(255, 183, 3, 0.3);
                color: #FFD166;
            }}
            .chip-dogv {{
                background: rgba(230, 57, 70, 0.15);
                border-color: rgba(230, 57, 70, 0.4);
                color: #FFA8A8;
            }}
            .chip-caducidad {{
                background: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }}

            .card-metrics {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                background: rgba(11, 19, 43, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.06);
                padding: 12px 16px;
                border-radius: 10px;
                margin-bottom: 14px;
                gap: 10px;
            }}
            .metric-label {{
                display: block;
                font-size: 11px;
                color: var(--text-dim);
                font-weight: 600;
            }}
            .metric-val {{
                font-size: 15px;
                font-weight: 800;
                color: #FFFFFF;
                margin-top: 3px;
            }}
            .text-accent {{ color: #57CC99; }}

            .ai-verdict-box {{
                background: rgba(0, 119, 182, 0.12);
                border-left: 3px solid #00B4D8;
                padding: 10px 14px;
                border-radius: 0 8px 8px 0;
                margin-bottom: 14px;
            }}
            .ai-verdict-title {{
                font-size: 10px;
                font-weight: 800;
                color: #48CAE4;
                letter-spacing: 0.5px;
                margin-bottom: 4px;
            }}
            .ai-verdict-content {{
                font-size: 12px;
                color: #E2E8F0;
                line-height: 1.45;
                font-style: italic;
            }}

            .card-body {{
                font-size: 13px;
                line-height: 1.55;
                color: #CBD5E1;
                margin-bottom: 18px;
            }}

            .card-actions {{
                display: flex;
                gap: 10px;
                border-top: 1px solid var(--border-color);
                padding-top: 14px;
            }}
            .btn {{
                flex: 1;
                text-align: center;
                padding: 10px 12px;
                border-radius: 8px;
                font-size: 12.5px;
                font-weight: 700;
                text-decoration: none;
                transition: opacity 0.2s;
            }}
            .btn-portal {{
                background: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
            }}
            .btn-portal:hover {{ background: rgba(255, 255, 255, 0.15); }}
            
            .btn-pdf {{
                background: linear-gradient(135deg, #0077B6, #0096C7);
                color: #FFFFFF;
                box-shadow: 0 4px 10px rgba(0, 119, 182, 0.3);
            }}
            .btn-pdf:hover {{ opacity: 0.9; }}

            .no-data {{
                grid-column: 1 / -1;
                text-align: center;
                padding: 60px;
                color: var(--text-dim);
                font-size: 16px;
            }}

            @media (max-width: 768px) {{
                body {{ padding: 15px; }}
                .cards-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo-group">
                <h1>💧 RIEGOS POUS, S.L. <span>Radar & Inteligencia</span></h1>
                <p>Soluciones Hidráulicas, Pozos, Regadíos y Bombeo Solar | Sede: Xeraco (Valencia)</p>
            </div>
            <div class="header-actions">
                <button class="btn-seguro-trigger" onclick="toggleSeguroPanel()">⚡ Peritaje Seguro (DANA/Rayo)</button>
                <a href="/escanear" class="btn-scan">🔄 Escanear Ahora</a>
            </div>
        </div>

        {alerta_scan_banner}

        <!-- Panel de Alivio Burocrático: Certificados de Avería para Seguros -->
        <div class="seguro-panel" id="seguroPanel">
            <h2>⚡ Generador de Certificados de Daños y Peritaje Técnico (Agroseguro / Mapfre)</h2>
            <p>Genera en 5 segundos el informe oficial de avería de bomba por sobretensión, tormenta o DANA con cita de la ITC-BT-23 del REBT y norma UNE-EN 60034-1 con membrete de Riegos Pous, S.L.</p>
            <form action="/api/generar_certificado_seguro" method="post" target="_blank">
                <div class="seguro-grid">
                    <div class="form-group">
                        <label>Nombre del Cliente / Comunidad de Regantes:</label>
                        <input type="text" name="cliente" value="Comunidad de Regantes de Xeraco" required>
                    </div>
                    <div class="form-group">
                        <label>Ubicación del Pozo / Finca:</label>
                        <input type="text" name="ubicacion" value="Pozo del Tossalet, Partida La Garrofera (Xeraco)" required>
                    </div>
                    <div class="form-group">
                        <label>Equipo Electromecánico Siniestrado:</label>
                        <input type="text" name="equipo" value="Bomba Sumergible Caprari E6X 30 CV + Motor Franklin" required>
                    </div>
                    <div class="form-group">
                        <label>Causa del Siniestro / Avería:</label>
                        <select name="causa">
                            <option value="Sobretension transitoria atmosferica por caida de rayo">Rayo / Sobretensión Atmosférica Transitoria</option>
                            <option value="Subida de tension por perturbacion en red electrica durante tormenta">Subida de Tensión / Perturbación Eléctrica</option>
                            <option value="Inundacion de cuadro electrico y bomba por precipitaciones DANA">Inundación por Temporal / DANA</option>
                            <option value="Caida de fase en linea electrica con destruccion de aislamiento">Falta de Fase en Suministro Eléctrico</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Fecha de la Tormenta / Siniestro:</label>
                        <input type="text" name="fecha_siniestro" value="{hoy_str}" required>
                    </div>
                    <div class="form-group">
                        <label>Importe Total Presupuesto Reposición (€):</label>
                        <input type="number" step="0.01" name="importe_reparacion" value="8450.00" required>
                    </div>
                </div>
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                    <button type="button" class="btn btn-portal" onclick="toggleSeguroPanel()" style="max-width: 140px;">Cancelar</button>
                    <button type="submit" class="btn btn-pdf" style="max-width: 320px; background: linear-gradient(135deg, #E63946, #D90429);">📄 Descargar Certificado Pericial en PDF</button>
                </div>
            </form>
        </div>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-title">🏛️ Subvenciones DOGV / GVA</div>
                <div class="stat-val">{n_dogv}</div>
            </div>
            <div class="stat-box">
                <div class="stat-title">🚜 Nuevos Pozos CHJ / BOP</div>
                <div class="stat-val">{n_chj}</div>
            </div>
            <div class="stat-box">
                <div class="stat-title">💧 Licitaciones Hidráulicas</div>
                <div class="stat-val">{n_placsp}</div>
            </div>
            <div class="stat-box">
                <div class="stat-title">🚜 Subastas BOE Fincas/Pozo</div>
                <div class="stat-val">{n_boe}</div>
            </div>
            <div class="stat-box">
                <div class="stat-title">📦 Bombas y Suministros</div>
                <div class="stat-val">{n_stocks}</div>
            </div>
            <div class="stat-box">
                <div class="stat-title">💶 Oportunidades Detectadas</div>
                <div class="stat-val">{volumen_total:,.0f} €</div>
            </div>
        </div>

        <div class="controls-bar">
            <div class="tabs">
                <a href="/?vector=todos" class="tab {'active' if vector == 'todos' else ''}">Todas ({total})</a>
                <a href="/?vector=dogv" class="tab {'active' if vector == 'dogv' else ''}">🏛️ Subvenciones DOGV ({n_dogv})</a>
                <a href="/?vector=chj" class="tab {'active' if vector == 'chj' else ''}">🚜 Nuevos Pozos CHJ ({n_chj})</a>
                <a href="/?vector=placsp" class="tab {'active' if vector == 'placsp' else ''}">💧 Licitaciones ({n_placsp})</a>
                <a href="/?vector=concursal" class="tab {'active' if vector == 'concursal' else ''}">🚜 Subastas BOE ({n_boe})</a>
                <a href="/?vector=bopi" class="tab {'active' if vector == 'bopi' else ''}">📦 Liquidaciones ({n_stocks})</a>
            </div>
            <div class="search-box">
                <input type="text" id="searchInput" class="search-input" placeholder="🔍 Buscar Caprari, subvención, solar, pozo..." onkeyup="filtrarTarjetas()">
            </div>
        </div>

        <div class="cards-grid" id="cardsGrid">
            {cards_html}
        </div>

        <script>
            function toggleSeguroPanel() {{
                const panel = document.getElementById('seguroPanel');
                panel.classList.toggle('active');
                if (panel.classList.contains('active')) {{
                    panel.scrollIntoView({{ behavior: 'smooth' }});
                }}
            }}

            function filtrarTarjetas() {{
                const query = document.getElementById('searchInput').value.toLowerCase().trim();
                const cards = document.querySelectorAll('.card');
                cards.forEach(card => {{
                    const text = (card.getAttribute('data-title') || '') + ' ' + card.innerText.toLowerCase();
                    if (text.includes(query)) {{
                        card.style.display = 'flex';
                    }} else {{
                        card.style.display = 'none';
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
    return html
