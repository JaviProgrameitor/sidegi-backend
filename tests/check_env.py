import os

print("Buscando variables de entorno del sistema...")
for k, v in os.environ.items():
    kl = k.lower()
    if any(p in kl for p in ["pass", "secret", "db", "postgres", "supabase", "conn"]):
        # No imprimir el valor completo si es muy largo/sensible, o si es la service key, solo mostrar longitud e inicio
        val_str = str(v)
        if len(val_str) > 30:
            val_str = val_str[:10] + "..." + val_str[-10:]
        print(f"{k}: {val_str} (Longitud: {len(v)})")
