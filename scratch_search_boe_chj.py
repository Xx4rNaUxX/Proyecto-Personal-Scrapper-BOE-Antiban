import httpx
import xml.etree.ElementTree as ET

ATOM = "http://www.w3.org/2005/Atom"
url = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)

root = ET.fromstring(r.content)
entries = root.findall(f"{{{ATOM}}}entry")
for e in entries[:3]:
    print("Links in entry:")
    for l in e.findall(f"{{{ATOM}}}link"):
        print(" ", l.attrib)
    print("Id in entry:", getattr(e.find(f"{{{ATOM}}}id"), 'text', ''))
