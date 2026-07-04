"""
src/config.py - Carga y valida la configuración de cuentas.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import List


@dataclass
class SascarConfig:
    username: str
    password: str
    wsdl_url: str = "https://sasintegra.sascar.com.br/SasIntegra/SasIntegraWSService?wsdl"
    cantidad_posiciones: int = 3000
    sascar_utc_offset_hours: int = -3  # Sascar usa UTC-3 (hora Brasil)


@dataclass
class ControlTConfig:
    base_url: str
    username: str
    password: str


@dataclass
class AccountConfig:
    account_id: str
    sascar: SascarConfig
    controlt: ControlTConfig
    enabled: bool = True
    description: str = ""


def load_accounts(path: str | None = None) -> List[AccountConfig]:
    path = path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "accounts.json"
    )
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    accounts = []
    for item in raw:
        accounts.append(AccountConfig(
            account_id=item["account_id"],
            enabled=item.get("enabled", True),
            description=item.get("description", ""),
            sascar=SascarConfig(
                username=item["sascar"]["username"],
                password=item["sascar"]["password"],
                wsdl_url=item["sascar"].get("wsdl_url",
                    "https://sasintegra.sascar.com.br/SasIntegra/SasIntegraWSService?wsdl"),
                cantidad_posiciones=int(item["sascar"].get("cantidad_posiciones", 3000)),
                sascar_utc_offset_hours=int(item["sascar"].get("sascar_utc_offset_hours", -3)),
            ),
            controlt=ControlTConfig(
                base_url=item["controlt"]["base_url"].rstrip("/"),
                username=item["controlt"]["username"],
                password=item["controlt"]["password"],
            )
        ))
    return accounts
