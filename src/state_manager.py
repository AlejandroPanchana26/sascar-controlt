"""
src/state_manager.py - Persiste el último idPacote procesado por cuenta.
Evita enviar registros duplicados a ControlT entre corridas.
"""
from __future__ import annotations
import json
import logging
import os
import threading

log = logging.getLogger(__name__)

_STATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "state"
)


class StateManager:
    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        self._path = os.path.join(_STATE_DIR, f"{account_id}.json")
        self._lock = threading.Lock()
        self._state = {}
        self._load()

    def get_last_packet_id(self) -> int:
        return int(self._state.get("ultimo_id_paquete", 0))

    def update_last_packet_id(self, new_id: int) -> None:
        if new_id > self.get_last_packet_id():
            with self._lock:
                self._state["ultimo_id_paquete"] = new_id
                self._save()

    def _load(self) -> None:
        os.makedirs(_STATE_DIR, exist_ok=True)
        if not os.path.exists(self._path):
            self._state = {"ultimo_id_paquete": 0}
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                self._state = json.load(fh)
        except Exception:
            self._state = {"ultimo_id_paquete": 0}

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2)
        except Exception as e:
            log.error("[%s] Error guardando estado: %s", self.account_id, e)
