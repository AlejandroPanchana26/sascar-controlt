"""
src/controlt/client.py
======================
Cliente REST para el HUB 2.0 de ControlT.
Cachea el token (válido 24h) para no re-autenticar en cada corrida.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.config import ControlTConfig

log = logging.getLogger(__name__)
_TOKEN_BUFFER_MINUTES = 10
_RETRY_STATUS = [500, 502, 503, 504]


class ControlTClient:
    def __init__(self, config: ControlTConfig) -> None:
        self._cfg = config
        self._token: str | None = None
        self._token_type: str = "bearer"
        self._token_expires_at: datetime | None = None
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=1.5,
                      status_forcelist=_RETRY_STATUS,
                      allowed_methods=["POST"], raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _is_token_valid(self) -> bool:
        if not self._token or not self._token_expires_at:
            return False
        remaining = (self._token_expires_at - datetime.now()).total_seconds() / 60
        return remaining > _TOKEN_BUFFER_MINUTES

    def _authenticate(self) -> None:
        url = f"{self._cfg.base_url}/Account/Auth"
        log.info("Autenticando contra ControlT HUB: %s", url)
        resp = self._session.post(
            url,
            json={"username": self._cfg.username, "password": self._cfg.password},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_type = data.get("token_type", "bearer")
        expires_min = int(data.get("expires_in", 1440))
        self._token_expires_at = datetime.now() + timedelta(minutes=expires_min)
        log.info("Token ControlT obtenido. Válido por %d minutos.", expires_min)

    def _get_auth_header(self) -> Dict[str, str]:
        if not self._is_token_valid():
            self._authenticate()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def send_event(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        url = f"{self._cfg.base_url}/Register/Insert"
        for attempt in range(2):
            headers = self._get_auth_header()
            try:
                resp = self._session.post(url, headers=headers, json=payload, timeout=30)
            except requests.RequestException as exc:
                raise ConnectionError(f"Error de red: {exc}") from exc

            if resp.status_code == 401 and attempt == 0:
                log.warning("Token rechazado, re-autenticando...")
                self._token = None
                continue
            break

        try:
            body = resp.json()
        except ValueError:
            body = {"success": False, "errors": [resp.text]}

        success = resp.status_code == 200 and bool(body.get("success", False))
        return success, body

    def close(self) -> None:
        self._session.close()
