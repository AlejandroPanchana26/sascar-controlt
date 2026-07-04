"""
src/transformer.py
==================
Convierte paquetes de Sascar al formato de ControlT HUB 2.0.

ZONA HORARIA:
  - Sascar expone los datos en UTC-3 (hora de Brasil)
  - ControlT requiere los datos en UTC-5 (hora de Colombia)
  - La conversión resta 2 horas: UTC-3 → UTC-5

USERNAME:
  - El campo 'username' que se envía a ControlT siempre es "sascar"
  - Este campo identifica al proveedor GPS en la plataforma ControlT
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Zona horaria destino ───────────────────────────────────────────────────
UTC_MINUS_5 = timezone(timedelta(hours=-5))

# ── Validación de placa ────────────────────────────────────────────────────
_PLATE_RE = re.compile(r"^[A-Za-z0-9 \-]{3,15}$")

# ── Tabla de rumbo (grados) ────────────────────────────────────────────────
_COURSE_MAP: List[Tuple[int, int, str]] = [
    (0,   44,  "N - Norte"),
    (45,  89,  "NE - Noreste"),
    (90,  134, "E - Este"),
    (135, 179, "SE - Sureste"),
    (180, 224, "S - Sur"),
    (225, 269, "SO - Suroeste"),
    (270, 314, "O - Oeste"),
    (315, 359, "NO - Noroeste"),
]

# ── Formatos de fecha de Sascar ────────────────────────────────────────────
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S.%f",
]


# ── Conversión de fecha ────────────────────────────────────────────────────

def to_utc5(value: Any, source_utc_offset_hours: int = -3) -> Optional[str]:
    """
    Convierte una fecha de Sascar a UTC-5 (Colombia).

    Sascar envía los datos en UTC-3 (hora de Brasil).
    UTC-3 → UTC-5 = restar 2 horas.

    Args:
        value: Fecha como string o datetime.
        source_utc_offset_hours: Offset UTC de Sascar. Por defecto -3 (Brasil).

    Returns:
        Fecha en formato "AAAA-MM-DDThh:mm:ss" en UTC-5.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        dt_naive = value
    else:
        text = str(value).split(".")[0].strip()
        dt_naive = None
        for fmt in _DATE_FORMATS:
            try:
                dt_naive = datetime.strptime(text, fmt.split(".")[0])
                break
            except ValueError:
                continue

    if dt_naive is None:
        log.warning("No se pudo parsear la fecha: %r", value)
        return None

    # Asignar timezone fuente (UTC-3 de Sascar)
    source_tz = timezone(timedelta(hours=source_utc_offset_hours))
    dt_aware = dt_naive.replace(tzinfo=source_tz)

    # Convertir a UTC-5 (Colombia)
    dt_utc5 = dt_aware.astimezone(UTC_MINUS_5)

    return dt_utc5.strftime("%Y-%m-%dT%H:%M:%S")


# ── Utilitarios ────────────────────────────────────────────────────────────

def direction_to_text(direcao: Any) -> str:
    if direcao is None:
        return ""
    try:
        degrees = int(direcao) % 360
    except (ValueError, TypeError):
        return ""
    for low, high, label in _COURSE_MAP:
        if low <= degrees <= high:
            return label
    return ""


def validate_plate(placa: Any) -> Optional[str]:
    if not placa:
        return None
    placa = str(placa).strip().upper()
    return placa if _PLATE_RE.match(placa) else None


def build_address(packet: Dict[str, Any]) -> str:
    partes = [
        str(packet.get("uf") or "").strip(),
        str(packet.get("cidade") or "").strip(),
        str(packet.get("rua") or "").strip(),
    ]
    return ", ".join(p for p in partes if p) or "N/A"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_base64_json(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


# ── Construcción de payloads ───────────────────────────────────────────────

def _build_gps_data_node(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Construye el nodo 'data' para evento GPS según doc ControlT HUB 2.0."""
    return {
        "Serial":       None,
        "Status":       1 if safe_int(packet.get("gps")) == 1 else 0,
        "Priority":     None,
        "Velocity":     safe_int(packet.get("velocidade"), 0),
        "Odometer":     safe_int(packet.get("odometro"), 0) or None,
        "Ignition":     safe_int(packet.get("ignicao")) == 1,
        "Battery":      None,
        "Altitude":     None,
        "Course":       direction_to_text(packet.get("direcao")),
        "Movil":        "0",
        "Temperature1": safe_float(packet.get("temperatura1")),
        "Temperature2": safe_float(packet.get("temperatura2")),
        "City":         str(packet.get("cidade") or "N/A").strip() or "N/A",
        "Department":   str(packet.get("uf") or "N/A").strip() or "N/A",
        "Address":      build_address(packet),
    }


def build_gps_event(
    packet: Dict[str, Any],
    placa: str,
    utc_offset: int,
) -> Dict[str, Any]:
    """
    Payload para /Register/Insert con typeEvent='01' (EventoGps).

    NOTA: El campo 'username' siempre es "sascar" — identifica al
    proveedor GPS en ControlT, no es la credencial de login.

    Las fechas se convierten de UTC-3 (Sascar/Brasil) a UTC-5 (Colombia).
    """
    return {
        "licensePlate":     placa,
        "latitude":         safe_float(packet.get("latitude")),
        "longitude":        safe_float(packet.get("longitude")),
        # Conversión UTC-3 (Sascar) → UTC-5 (Colombia)
        "dateEventGPS":     to_utc5(packet.get("dataPacote"),  utc_offset),
        "dateEventAVL":     to_utc5(packet.get("dataPosicao"), utc_offset),
        "typeEvent":        "01",
        "codeEvent":        "SASCAR-GPS",
        "descriptionEvent": "Posición GPS Sascar Michelin",
        "username":         "sascar",   # ← siempre "sascar"
        "data":             to_base64_json(_build_gps_data_node(packet)),
    }


def build_actuator_events(
    packet: Dict[str, Any],
    placa: str,
    utc_offset: int,
) -> List[Dict[str, Any]]:
    """
    Payloads para /Register/Insert con typeEvent='03' (Eventos actuadores).
    Uno por cada evento en el array 'eventos[]' del paquete Sascar.

    Código positivo = actuador ACTIVADO
    Código negativo = actuador DESACTIVADO
    """
    eventos = packet.get("eventos") or []
    if not eventos:
        return []

    date_gps = to_utc5(packet.get("dataPacote"),  utc_offset)
    date_avl = to_utc5(packet.get("dataPosicao"), utc_offset)
    payloads = []

    for ev in eventos:
        code = ev.get("code", 0) if isinstance(ev, dict) else int(ev)
        if code == 0:
            continue
        activated = code > 0
        abs_code  = abs(code)

        data_node = {
            "ActuadorCode": abs_code,
            "State":        "ACTIVADO" if activated else "DESACTIVADO",
            "Latitude":     safe_float(packet.get("latitude")),
            "Longitude":    safe_float(packet.get("longitude")),
            "Velocity":     safe_int(packet.get("velocidade"), 0),
            "Ignition":     safe_int(packet.get("ignicao")) == 1,
            "City":         str(packet.get("cidade") or "N/A").strip() or "N/A",
            "Department":   str(packet.get("uf") or "N/A").strip() or "N/A",
            "Address":      build_address(packet),
        }

        payloads.append({
            "licensePlate":     placa,
            "latitude":         safe_float(packet.get("latitude")),
            "longitude":        safe_float(packet.get("longitude")),
            "dateEventGPS":     date_gps,
            "dateEventAVL":     date_avl,
            "typeEvent":        "03",
            "codeEvent":        str(abs_code),
            "descriptionEvent": f"Actuador {abs_code} {'activado' if activated else 'desactivado'}",
            "username":         "sascar",   # ← siempre "sascar"
            "data":             to_base64_json(data_node),
        })

    return payloads


def transform_packet(
    packet: Dict[str, Any],
    sascar_utc_offset_hours: int = -3,
) -> List[Dict[str, Any]]:
    """
    Convierte un paquete de Sascar en la lista de payloads para ControlT.

    Retorna:
      []              → placa inválida, se descarta
      [gps]           → 1 evento GPS, sin actuadores
      [gps, ev1, ...] → 1 GPS + N eventos de actuadores
    """
    placa = validate_plate(packet.get("placa"))
    if placa is None:
        log.warning(
            "Paquete %s: placa inválida (%r), se omite.",
            packet.get("idPacote"), packet.get("placa")
        )
        return []

    payloads = [build_gps_event(packet, placa, sascar_utc_offset_hours)]
    payloads.extend(build_actuator_events(packet, placa, sascar_utc_offset_hours))
    return payloads
