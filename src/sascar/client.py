from __future__ import annotations
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
import requests
from src.config import SascarConfig

log = logging.getLogger(__name__)

_SOAP_URL = "https://sasintegra.sascar.com.br/SasIntegra/SasIntegraWSService"

_ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:sas="http://sasintegra.sascar.com.br/">
  <soapenv:Header/>
  <soapenv:Body>
    <sas:obterPacotePosicoesJSONComPlaca>
      <usuario>{usuario}</usuario>
      <senha>{senha}</senha>
      <quantidade>{quantidade}</quantidade>
    </sas:obterPacotePosicoesJSONComPlaca>
  </soapenv:Body>
</soapenv:Envelope>"""


class SascarClient:
    def __init__(self, config: SascarConfig) -> None:
        self._cfg = config
        self._session = requests.Session()

    def get_position_packets(self) -> List[Dict[str, Any]]:
        log.info("[%s] Consultando Sascar (cantidad=%d)...",
                 self._cfg.username, self._cfg.cantidad_posiciones)

        envelope = _ENVELOPE.format(
            usuario=self._cfg.username,
            senha=self._cfg.password,
            quantidade=self._cfg.cantidad_posiciones,
        )

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction":   '""',
        }

        try:
            resp = self._session.post(
                _SOAP_URL,
                data=envelope.encode("utf-8"),
                headers=headers,
                timeout=60,
            )
            if resp.status_code != 200:
                log.error("Sascar respondio %s: %s",
                          resp.status_code, resp.text[:2000])
                raise ConnectionError(f"Sascar error {resp.status_code}")
        except requests.RequestException as exc:
            raise ConnectionError(f"Error llamando a Sascar: {exc}") from exc

        packets = self._parse_response(resp.text)
        log.info("[%s] Paquetes recibidos: %d", self._cfg.username, len(packets))
        return packets

    def _parse_response(self, xml_text: str) -> List[Dict[str, Any]]:
        log.debug("Respuesta XML de Sascar: %s", xml_text[:500])
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            log.error("Error parseando XML: %s", exc)
            log.error("XML recibido: %s", xml_text[:1000])
            return []

        packets = []
        for elem in root.iter():
            if elem.tag.endswith("return") and elem.text:
                text = elem.text.strip()
                if not text:
                    continue
                try:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        data["eventos"] = self._normalize_events(
                            data.get("eventos") or [])
                        packets.append(data)
                except json.JSONDecodeError:
                    log.warning("JSON invalido en <return>: %s", text[:200])
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
