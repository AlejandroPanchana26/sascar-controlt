"""
src/sascar/client.py
====================
Cliente SOAP para el Web Service SasIntegra de Sascar / Michelin.
Usa obterPacotePosicoesJSONComPlaca para obtener posiciones con placa incluida.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List
from zeep import Client as ZeepClient
from zeep.helpers import serialize_object
from src.config import SascarConfig

log = logging.getLogger(__name__)


class SascarClient:
    def __init__(self, config: SascarConfig) -> None:
        self._cfg = config
        self._client: ZeepClient | None = None

    def _get_client(self) -> ZeepClient:
        if self._client is None:
            log.info("Conectando al WSDL de Sascar: %s", self._cfg.wsdl_url)
            self._client = ZeepClient(self._cfg.wsdl_url)
            log.info("Conexión WSDL establecida.")
        return self._client

    def get_position_packets(self) -> List[Dict[str, Any]]:
        client = self._get_client()
        log.info("[%s] Consultando obterPacotePosicoesJSONComPlaca (cantidad=%d)...",
                 self._cfg.username, self._cfg.cantidad_posiciones)

        raw = client.service.obterPacotePosicoesJSONComPlaca(
            usuario=self._cfg.username,
            senha=self._cfg.password,
            quantidade=self._cfg.cantidad_posiciones,
        )

        packets = self._parse_response(raw)
        log.info("[%s] Paquetes recibidos de Sascar: %d", self._cfg.username, len(packets))
        return packets

    def _parse_response(self, raw: Any) -> List[Dict[str, Any]]:
        raw_list = serialize_object(raw)
        if raw_list is None:
            return []
        if isinstance(raw_list, str):
            raw_list = [raw_list]
        if not isinstance(raw_list, list):
            return []

        packets = []
        for i, item in enumerate(raw_list):
            if isinstance(item, dict):
                item["eventos"] = self._normalize_events(item.get("eventos") or [])
                packets.append(item)
            elif isinstance(item, str) and item.strip():
                try:
                    data = json.loads(item)
                    data["eventos"] = self._normalize_events(data.get("eventos") or [])
                    packets.append(data)
                except json.JSONDecodeError:
                    log.warning("Paquete[%d] JSON inválido, se omite.", i)
        return packets

    @staticmethod
    def _normalize_events(raw: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        result = []
        for ev in raw:
            if isinstance(ev, dict) and "code" in ev:
                result.append({"code": int(ev["code"])})
            elif isinstance(ev, (int, float)):
                result.append({"code": int(ev)})
        return result
