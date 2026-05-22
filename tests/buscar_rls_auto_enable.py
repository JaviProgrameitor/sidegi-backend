import os

raiz = r"C:\Users\carde\Desktop\MUACK"
termino = "rls_auto_enable"

extensiones_interes = [".env", ".txt", ".json", ".py", ".md", ".sql", ".sh", ".bat", ".toml", ".js", ".ts"]

print(f"Buscando '{termino}' en {raiz}...")

for root, dirs, files in os.walk(raiz):
    dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "venv", ".venv", "__pycache__", ".idea", ".vscode", "vcpkg"]]
    for f in files:
        nombre, ext = os.path.splitext(f)
        if ext.lower() in extensiones_interes:
            ruta_completa = os.path.join(root, f)
            try:
                with open(ruta_completa, "r", encoding="utf-8", errors="ignore") as archivo:
                    contenido = archivo.read()
                    if termino in contenido:
                        lineas = contenido.splitlines()
                        for idx, linea in enumerate(lineas, 1):
                            if termino in linea:
                                print(f"Archivo: {os.path.relpath(ruta_completa, raiz)} (Línea {idx}): {linea.strip()}")
            except Exception as e:
                pass
print("Búsqueda finalizada.")
