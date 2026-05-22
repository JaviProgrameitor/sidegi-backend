with open("routers/documents.py", "r", encoding="utf-8") as f:
    lineas = f.readlines()

for i, linea in enumerate(lineas):
    linea_lower = linea.lower()
    if "sello" in linea_lower or "hash" in linea_lower or "integridad" in linea_lower or "delete" in linea_lower:
        print(f"Línea {i+1}: {linea.strip()}")
