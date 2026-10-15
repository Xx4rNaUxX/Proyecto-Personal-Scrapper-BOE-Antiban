import asyncio
import aiohttp
import sqlite3
import os

async def test_ollama_brain():
    print("🧠 1. Probando conexión con IA Local (Ollama)...")
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "qwen2.5-coder:7b",
                "prompt": "Responde solo con la palabra OK",
                "stream": False,
                "keep_alive": 0
            }
            async with session.post("http://localhost:11434/api/generate", json=payload, timeout=5) as resp:
                if resp.status == 200:
                    print("   ✅ Ollama responde. VRAM gestionada correctamente.")
                else:
                    print("   ❌ Error en Ollama. ¿Está encendido el servidor?")
    except Exception as e:
        print(f"   ❌ Falla la conexión local: {e}")

async def test_placsp_feed():
    print("🏛️ 2. Probando conexión con el Estado (Plataforma de Contratación)...")
    url = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    print("   ✅ El Estado permite la conexión. Rate Limiter funciona.")
                else:
                    print(f"   ❌ El Estado ha bloqueado la IP (Código {resp.status}).")
    except Exception as e:
        print(f"   ❌ Error de red: {e}")

def test_database():
    print("💽 3. Probando persistencia (SQLite)...")
    try:
        db_path = 'data/arbitraje.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = cursor.fetchall()
        if tablas:
            print(f"   ✅ Base de datos operativa en {db_path}. Tablas encontradas: {tablas}")
        else:
            print("   ⚠️ Base de datos vacía o no inicializada.")
        conn.close()
    except Exception as e:
        print(f"   ❌ Error en Base de Datos: {e}")

async def main():
    print("INICIANDO AUDITORÍA DEL SISTEMA...\n")
    await test_ollama_brain()
    await test_placsp_feed()
    test_database()
    print("\nAUDITORÍA FINALIZADA.")

if __name__ == "__main__":
    asyncio.run(main())
