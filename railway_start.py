"""
railway_start.py
================
Punto de entrada para Railway.
Lee credenciales desde variables de entorno, genera config/accounts.json
y lanza el worker en modo continuo cada 300 segundos (5 minutos).

Variables de entorno requeridas en Railway:
  SASCAR_USERNAME_01  → Usuario de Sascar / Michelin
  SASCAR_PASSWORD_01  → Contraseña de Sascar / Michelin
  CONTROLT_USERNAME   → Usuario del HUB ControlT
  CONTROLT_PASSWORD   → Contraseña del HUB ControlT
"""

import json
import os
import subprocess
import sys


def build_accounts():
    accounts = []

    u1 = os.environ.get("SASCAR_USERNAME_01", "")
    p1 = os.environ.get("SASCAR_PASSWORD_01", "")
    cu = os.environ.get("CONTROLT_USERNAME", "")
    cp = os.environ.get("CONTROLT_PASSWORD", "")

    if not u1 or not cu:
        print("ERROR: Faltan variables de entorno.")
        print("  Requeridas: SASCAR_USERNAME_01, SASCAR_PASSWORD_01,")
        print("              CONTROLT_USERNAME, CONTROLT_PASSWORD")
        sys.exit(1)

    accounts.append({
        "account_id": "sascar_cuenta_01",
        "enabled": True,
        "description": "Sascar Michelin - Railway",
        "sascar": {
            "username": u1,
            "password": p1,
            "wsdl_url": "https://sasintegra.sascar.com.br/SasIntegra/SasIntegraWSService?wsdl",
            "cantidad_posiciones": 3000,
            # Sascar expone los datos en UTC-3 (hora de Brasil).
            # El código convierte automáticamente UTC-3 → UTC-5 (Colombia).
            "sascar_utc_offset_hours": -3
        },
        "controlt": {
            "base_url": "https://hub.controlt.com.co",
            "username": cu,
            "password": cp
        }
    })

    # Cuenta 2 (opcional)
    u2 = os.environ.get("SASCAR_USERNAME_02", "")
    p2 = os.environ.get("SASCAR_PASSWORD_02", "")
    if u2:
        accounts.append({
            "account_id": "sascar_cuenta_02",
            "enabled": True,
            "sascar": {
                "username": u2,
                "password": p2,
                "wsdl_url": "https://sasintegra.sascar.com.br/SasIntegra/SasIntegraWSService?wsdl",
                "cantidad_posiciones": 3000,
                "sascar_utc_offset_hours": -3
            },
            "controlt": {
                "base_url": "https://hub.controlt.com.co",
                "username": cu,
                "password": cp
            }
        })

    return accounts


def main():
    print("=" * 55)
    print("  Sascar Michelin → ControlT HUB 2.0 | Railway")
    print("=" * 55)

    accounts = build_accounts()
    os.makedirs("config", exist_ok=True)
    with open("config/accounts.json", "w", encoding="utf-8") as fh:
        json.dump(accounts, fh, indent=2, ensure_ascii=False)

    print(f"✅ {len(accounts)} cuenta(s) configurada(s):")
    for a in accounts:
        print(f"   - {a['account_id']} ({a['sascar']['username']})")
    print(f"   Zona horaria: UTC-3 (Sascar) → UTC-5 (Colombia)")
    print(f"   Intervalo: cada 300 segundos (5 minutos)")

    print("\n🚀 Iniciando worker...\n")
    subprocess.run(
        [sys.executable, "main.py", "--loop", "300"],
        check=True
    )


if __name__ == "__main__":
    main()
