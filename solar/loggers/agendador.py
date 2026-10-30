"""Coleta em segundo plano enquanto o app está aberto: uma thread por processo, sem configuração."""

import threading
import time

from solar.loggers.coleta import INTERVALO_S, coletar_todos

_trava = threading.Lock()
_thread: threading.Thread | None = None


def _laco() -> None:
    while True:
        try:
            coletar_todos()
        except Exception:  # um erro de banco não pode matar a coleta pelo resto da sessão
            pass
        time.sleep(INTERVALO_S)


def iniciar() -> None:
    global _thread
    with _trava:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_laco, name="coleta-loggers", daemon=True)
            _thread.start()
