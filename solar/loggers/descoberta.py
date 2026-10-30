"""Reencontra um dongle que mudou de IP (DHCP sem reserva): varre a rede local atrás da porta da API
e só aceita o candidato cujo contador de energia continua o do inversor conhecido."""

import socket
from concurrent.futures import ThreadPoolExecutor

from solar.loggers.solplanet import FalhaLogger, ler_inversor

TIMEOUT_PORTA_S = 0.4
THREADS = 64
LIMITE_AVANCO_KWH = 1500  # separa inversores diferentes e tolera semanas sem leitura
TOLERANCIA_RECUO_KWH = 0.5


def prefixo_rede_local() -> str | None:
    """'192.168.1' da rede do computador (assume máscara /24). O connect em UDP não envia pacote."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0].rsplit(".", 1)[0]
        except OSError:
            return None


def _porta_aberta(ip: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(TIMEOUT_PORTA_S)
        return s.connect_ex((ip, porta)) == 0


def hosts_com_porta(prefixo: str, porta: int) -> list[str]:
    ips = [f"{prefixo}.{n}" for n in range(1, 255)]
    with ThreadPoolExecutor(THREADS) as pool:
        abertos = pool.map(lambda ip: _porta_aberta(ip, porta), ips)
    return [ip for ip, aberto in zip(ips, abertos) if aberto]


def eh_o_mesmo_inversor(energia_total_kwh: float, ultimo_total_kwh: float) -> bool:
    avanco = energia_total_kwh - ultimo_total_kwh
    return -TOLERANCIA_RECUO_KWH <= avanco <= LIMITE_AVANCO_KWH


def localizar(sn: str, ultimo_total_kwh: float, ip_atual: str, porta: int) -> str | None:
    prefixo = prefixo_rede_local()
    if prefixo is None:
        return None
    for ip in hosts_com_porta(prefixo, porta):
        if ip == ip_atual:
            continue
        try:
            leitura = ler_inversor(ip, sn, porta)
        except FalhaLogger:
            continue
        if eh_o_mesmo_inversor(leitura.energia_total_kwh, ultimo_total_kwh):
            return ip
    return None
