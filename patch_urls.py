import sqlite3

def parchear_urls():
    db_path = 'data/arbitraje.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Parchear URLs de BOPI
    cursor.execute("SELECT id FROM alertas WHERE vector = 'bopi'")
    bopis = cursor.fetchall()
    for (id_bopi,) in bopis:
        marca_id = id_bopi.replace("bopi_", "")
        nueva_url = f"https://consultas2.oepm.es/ceo/jsp/busqueda/consultaCE.jsp?numExp={marca_id}"
        cursor.execute("UPDATE alertas SET url = ? WHERE id = ?", (nueva_url, id_bopi))
        
    # Parchear URLs de Concursal
    cursor.execute("SELECT id FROM alertas WHERE vector = 'concursal'")
    concursales = cursor.fetchall()
    for (id_conc,) in concursales:
        lote_id = id_conc.replace("boe_", "").replace("conc_", "") # Maneja ambos prefijos por si acaso
        nueva_url = f"https://subastas.boe.es/detalleSubasta.php?idSub={lote_id}"
        cursor.execute("UPDATE alertas SET url = ? WHERE id = ?", (nueva_url, id_conc))
        
    conn.commit()
    conn.close()
    print("✅ URLs parcheadas en la base de datos.")

if __name__ == '__main__':
    parchear_urls()
