"""
src/worker.py - Orquestador por cuenta.
Consulta Sascar, transforma y envía a ControlT.
"""
from __future__ import annotations
import json
import logging
from typing import Dict, Any, List
from src.config import AccountConfig
from src.controlt.client import ControlTClient
from src.sascar.client import SascarClient
from src.state_manager import StateManager
from src.transformer import transform_packet

log = logging.getLogger(__name__)


class AccountWorker:
    def __init__(self, account: AccountConfig, dry_run: bool = False) -> None:
        self._account  = account
        self._dry_run  = dry_run
        self._sascar   = SascarClient(account.sascar)
        self._controlt = ControlTClient(account.controlt)
        self._state    = StateManager(account.account_id)
        self._prefix   = f"[{account.account_id}]"

    def run(self) -> Dict[str, int]:
        log.info("%s Iniciando corrida. DryRun=%s", self._prefix, self._dry_run)
        metrics = {"enviados_ok": 0, "fallidos": 0, "omitidos": 0}

        try:
            all_packets = self._sascar.get_position_packets()
        except Exception as exc:
            log.error("%s Error consultando Sascar: %s", self._prefix, exc)
            return metrics

        if not all_packets:
            log.info("%s Sin paquetes recibidos de Sascar.", self._prefix)
            return metrics

        ultimo_id = self._state.get_last_packet_id()
        new_packets = [p for p in all_packets if int(p.get("idPacote") or 0) > ultimo_id]

        log.info("%s Paquetes recibidos: %d | Nuevos: %d (último ID=%d)",
                 self._prefix, len(all_packets), len(new_packets), ultimo_id)

        if not new_packets:
            log.info("%s No hay paquetes nuevos.", self._prefix)
            return metrics

        max_id = ultimo_id
        utc_offset = self._account.sascar.sascar_utc_offset_hours

        for packet in new_packets:
            id_paquete = int(packet.get("idPacote") or 0)
            placa_raw  = packet.get("placa", "?")

            payloads = transform_packet(packet, sascar_utc_offset_hours=utc_offset)

            if not payloads:
                metrics["omitidos"] += 1
                max_id = max(max_id, id_paquete)
                continue

            all_ok = True
            for payload in payloads:
                tipo = payload.get("typeEvent", "?")
                ok   = self._send(id_paquete, placa_raw, tipo, payload)
                if ok:
                    metrics["enviados_ok"] += 1
                else:
                    metrics["fallidos"] += 1
                    all_ok = False

            if all_ok:
                max_id = max(max_id, id_paquete)

        self._state.update_last_packet_id(max_id)
        log.info("%s Corrida finalizada. Enviados OK: %d | Fallidos: %d | Omitidos: %d",
                 self._prefix, metrics["enviados_ok"], metrics["fallidos"], metrics["omitidos"])
        return metrics

    def _send(self, id_paquete, placa, tipo, payload) -> bool:
        if self._dry_run:
            log.info("%s [DRY-RUN] Paquete=%d placa=%s tipo=%s",
                     self._prefix, id_paquete, placa, tipo)
            return True
        try:
            success, body = self._controlt.send_event(payload)
        except ConnectionError as exc:
            log.error("%s Paquete=%d → Error de red: %s", self._prefix, id_paquete, exc)
            return False
        if success:
            log.info("%s Paquete=%d placa=%s tipo=%s → OK (data=%s)",
                     self._prefix, id_paquete, placa, tipo, body.get("data"))
        else:
            log.error("%s Paquete=%d placa=%s tipo=%s → ERROR: %s",
                      self._prefix, id_paquete, placa, tipo, body.get("errors") or body)
        return success

    def close(self) -> None:
        self._controlt.close()
