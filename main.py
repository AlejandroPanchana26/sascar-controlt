"""
main.py - Integración Sascar Michelin → ControlT HUB 2.0

Uso:
  python main.py              # una sola corrida
  python main.py --loop 300   # loop cada 300 segundos (5 minutos)
  python main.py --dry-run    # simula sin enviar a ControlT
"""
from __future__ import annotations
import argparse
import logging
import logging.handlers
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from src.config import AccountConfig, load_accounts
from src.worker import AccountWorker

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_STOP = False


def setup_logging(verbose: bool = False) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    root = logging.getLogger()
    root.setLevel(level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    fh = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "integracion.log"),
        maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)
    root.addHandler(fh)


log = logging.getLogger("main")


def _handle_stop(signum, frame):
    global _STOP
    log.warning("Señal de parada recibida. Finalizando al terminar el ciclo...")
    _STOP = True


signal.signal(signal.SIGINT, _handle_stop)
signal.signal(signal.SIGTERM, _handle_stop)


def run_cycle(workers: List[AccountWorker], cycle_num: int) -> None:
    log.info("======= Ciclo #%d — %d cuenta(s) en paralelo =======",
             cycle_num, len(workers))
    with ThreadPoolExecutor(max_workers=len(workers),
                            thread_name_prefix="worker") as executor:
        futures = {executor.submit(w.run): w for w in workers}
        for future in as_completed(futures):
            worker = futures[future]
            try:
                m = future.result()
                log.info("[%s] Métricas: enviados_ok=%d | fallidos=%d | omitidos=%d",
                         worker._account.account_id,
                         m.get("enviados_ok", 0),
                         m.get("fallidos", 0),
                         m.get("omitidos", 0))
            except Exception as exc:
                log.exception("[%s] Error: %s", worker._account.account_id, exc)
    log.info("======= Ciclo #%d completado =======", cycle_num)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", type=int, default=0,
                        help="Ejecuta en bucle cada N segundos.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sin enviar datos a ControlT.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    log.info("=" * 60)
    log.info("  Integración Sascar Michelin → ControlT HUB 2.0")
    log.info("=" * 60)

    try:
        all_accounts: List[AccountConfig] = load_accounts()
    except Exception as exc:
        log.critical("Error de configuración: %s", exc)
        return 1

    enabled = [a for a in all_accounts if a.enabled]
    if not enabled:
        log.critical("No hay cuentas habilitadas en accounts.json.")
        return 1

    log.info("Cuentas activas: %d → %s", len(enabled), [a.account_id for a in enabled])
    if args.dry_run:
        log.warning("*** MODO DRY-RUN: no se envía nada a ControlT ***")

    workers = [AccountWorker(a, dry_run=args.dry_run) for a in enabled]

    if args.loop > 0:
        log.info("Modo continuo: cada %d segundos.", args.loop)
        cycle = 1
        while not _STOP:
            run_cycle(workers, cycle)
            cycle += 1
            if _STOP:
                break
            log.info("Esperando %d segundos...", args.loop)
            for _ in range(args.loop):
                if _STOP:
                    break
                time.sleep(1)
    else:
        run_cycle(workers, 1)

    for w in workers:
        w.close()
    log.info("Proceso finalizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
