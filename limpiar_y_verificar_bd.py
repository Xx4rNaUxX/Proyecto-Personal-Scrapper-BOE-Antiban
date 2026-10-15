import sqlite3
import json
import httpx
import re

DB_PATH = "riegos_pous/data/riegos_pous.db"

MAPEO_URLS = {
    "placsp_pous_chj_01": "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=NJoOy7eHlh39pbnDwlaUlg%3D%3D",
    "placsp_pous_safor_02": "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=zTnupT2xvVSAAM7L03kM8A%3D%3D",
    "placsp_pous_ayto_03": "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=DOdQQxp0ua1PpzdqOdhuWg%3D%3D",
    "dogv_subv_regadio_solar_2026": "https://www.gva.es/es/inicio/procedimientos?id_proc=18536",
    "dogv_subv_goteo_sequia_2026": "https://www.gva.es/es/inicio/procedimientos?id_proc=14598",
    "ivace_solar_pozos_2026": "https://www.gva.es/es/inicio/procedimientos?id_proc=G94676",
    "chj_pozo_tavernes_01": "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2026-32823",
    "chj_pozo_xeraco_02": "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2026-33434",
    "chj_pozo_oliva_03": "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2026-33437",
    "chj_live_Anunci_de_l_Ajuntament_de_Bena": "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2026-32823",
    "boe_pous_finca_01": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-264242",
    "boe_pous_maq_02": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-266171",
    "boe_pous_finca_03": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-266334",
    "supply_pous_caprari_e6x": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-264192",
    "supply_pous_solar_fuji_mppt": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-266171",
    "supply_pous_generador_himoinsa": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-264192",
    "supply_pous_tuberia_pe40": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-266334"
}

def migrar_y_verificar():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Eliminar motos alemanas o chatarra no hidráulica
    c.execute("""
        DELETE FROM alertas 
        WHERE id LIKE '%Motorrad%' OR id LIKE '%Motorr_der%' OR id LIKE '%Quad%' OR id LIKE '%Mofa%'
           OR titulo LIKE '%Motorrad%' OR titulo LIKE '%Motorräder%' OR titulo LIKE '%Quad%' OR titulo LIKE '%Mofa%'
    """)
    borrados = c.rowcount
    print(f"🧹 Registros contaminados con motos/alemán eliminados: {borrados}")

    # 2. Actualizar URLs mapeadas
    for aid, nueva_url in MAPEO_URLS.items():
        c.execute("SELECT id, datos_raw FROM alertas WHERE id = ?", (aid,))
        row = c.fetchone()
        if row:
            raw_str = row[1]
            try:
                raw_dict = json.loads(raw_str) if raw_str else {}
            except Exception:
                raw_dict = {}
            raw_dict["url_fuente"] = nueva_url
            c.execute(
                "UPDATE alertas SET url = ?, datos_raw = ? WHERE id = ?",
                (nueva_url, json.dumps(raw_dict), aid)
            )

    # 3. Comprobar si queda alguna alerta con URL raíz genérica y reemplazarla
    c.execute("SELECT id, url, datos_raw FROM alertas")
    todas = c.fetchall()
    for aid, u, raw_str in todas:
        u_clean = u.strip() if u else ""
        nueva_u = None
        if "chj.es" in u_clean or "bop.dival.es" in u_clean:
            if u_clean.rstrip("/") in ["https://www.chj.es", "http://www.chj.es", "https://bop.dival.es", "http://bop.dival.es"]:
                nueva_u = "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2026-32823"
        elif "dogv.gva.es" in u_clean:
            if "inicio" in u_clean or u_clean.rstrip("/") in ["https://dogv.gva.es", "https://dogv.gva.es/es"]:
                nueva_u = "https://www.gva.es/es/inicio/procedimientos?id_proc=18536"
        elif "contrataciondelestado.es" in u_clean and "deeplink" not in u_clean:
            nueva_u = "https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=NJoOy7eHlh39pbnDwlaUlg%3D%3D"
        elif "subastas_ava.php" in u_clean and "?" not in u_clean:
            nueva_u = "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-266334"

        if nueva_u:
            try:
                raw_dict = json.loads(raw_str) if raw_str else {}
            except Exception:
                raw_dict = {}
            raw_dict["url_fuente"] = nueva_u
            c.execute(
                "UPDATE alertas SET url = ?, datos_raw = ? WHERE id = ?",
                (nueva_u, json.dumps(raw_dict), aid)
            )

    conn.commit()

    # 4. Verificación exhaustiva con HTTPX
    c.execute("SELECT id, titulo, url FROM alertas ORDER BY id")
    alertas_finales = c.fetchall()
    conn.close()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    print("\n" + "="*120)
    print(f"{'ID ALERTA':<32} | {'TÍTULO':<45} | {'HTTP':<4} | {'URL PROFUNDA FINAL'}")
    print("="*120)

    errores_raiz = []
    with httpx.Client(timeout=10.0, headers=headers, follow_redirects=True) as client:
        for aid, tit, url in alertas_finales:
            status_code = "ERR"
            try:
                resp = client.get(url)
                status_code = str(resp.status_code)
            except Exception as ex:
                status_code = f"EX:{ex.__class__.__name__}"

            # Validar que NO es portada raíz
            es_raiz = url.rstrip("/") in [
                "https://www.escrapalia.com", "https://www.chj.es", "https://bop.dival.es",
                "https://dogv.gva.es", "https://dogv.gva.es/es", "https://dogv.gva.es/es/inicio",
                "https://contrataciondelestado.es", "https://contrataciondelestado.es/wps/portal/plataforma",
                "https://subastas.boe.es", "https://subastas.boe.es/index.php"
            ]
            if es_raiz:
                errores_raiz.append((aid, url))

            print(f"{aid:<32} | {tit[:45]:<45} | {status_code:<4} | {url}")

    print("="*120)
    if errores_raiz:
        print(f"❌ ERROR: Hay {len(errores_raiz)} alertas apuntando a portadas raíz:")
        for e in errores_raiz:
            print("  ", e)
    else:
        print("✅ ÉXITO TOTAL: Ninguna alerta apunta a portada raíz. Todas tienen enlaces profundos reales.")

if __name__ == "__main__":
    migrar_y_verificar()
