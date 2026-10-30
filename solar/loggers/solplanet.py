"""Cliente da API local do dongle Wi-Fi Solplanet (AISWEI): JSON em http://<ip>:8484, sem autenticação."""

from dataclasses import dataclass
from datetime import datetime

import requests

TIMEOUT_S = 10
DISPOSITIVO_INVERSOR = 2


class FalhaLogger(Exception):
    pass


@dataclass(frozen=True)
class Leitura:
    lida_em: str
    potencia_w: float
    energia_dia_kwh: float
    energia_total_kwh: float
    temperatura_c: float
    tensao_ac_v: float
    frequencia_hz: float
    codigo_erro: int


def interpretar(bruto: dict) -> Leitura:
    """Converte o JSON do dongle (valores inteiros em décimos/centésimos) para unidades físicas."""
    try:
        return Leitura(
            lida_em=datetime.strptime(bruto["tim"], "%Y%m%d%H%M%S").isoformat(timespec="seconds"),
            potencia_w=float(bruto["pac"]),
            energia_dia_kwh=bruto["etd"] / 10,
            energia_total_kwh=bruto["eto"] / 10,
            temperatura_c=bruto["tmp"] / 10,
            tensao_ac_v=bruto["vac"][0] / 10,
            frequencia_hz=bruto["fac"] / 100,
            codigo_erro=int(bruto["err"]),
        )
    except (KeyError, IndexError, TypeError, ValueError) as erro:
        raise FalhaLogger("Resposta do logger em formato inesperado.") from erro


def ler_inversor(ip: str, sn: str, porta: int = 8484) -> Leitura:
    url = f"http://{ip}:{porta}/getdevdata.cgi"
    try:
        resposta = requests.get(url, params={"device": DISPOSITIVO_INVERSOR, "sn": sn}, timeout=TIMEOUT_S)
        resposta.raise_for_status()
        bruto = resposta.json()
    except (requests.RequestException, ValueError) as erro:
        raise FalhaLogger(f"Logger {ip} não respondeu (inversor desligado à noite ou fora da rede).") from erro
    return interpretar(bruto)
