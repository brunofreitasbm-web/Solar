"""Coleta periódica dos data loggers cadastrados.

Uso:
  python -m solar.loggers.coleta adicionar "Usina 1" 192.168.0.50 AP00100522440448
  python -m solar.loggers.coleta importar C:\\caminho\\solar.db
  python -m solar.loggers.coleta uma-vez
  python -m solar.loggers.coleta rodar
"""

import argparse
import time

from solar.loggers import descoberta, repositorio
from solar.loggers.solplanet import FalhaLogger, ler_inversor

INTERVALO_S = 300
INTERVALO_BUSCA_S = 1800  # a varredura é cara; à noite o inversor desliga e nada seria achado

_ultima_busca: dict[str, float] = {}


def _reencontrar(logger: dict):
    """Se o dongle mudou de IP, acha o novo, grava e devolve a leitura; senão None."""
    agora = time.monotonic()
    if agora - _ultima_busca.get(logger["sn"], -INTERVALO_BUSCA_S) < INTERVALO_BUSCA_S:
        return None
    _ultima_busca[logger["sn"]] = agora
    ultima = repositorio.ultima_leitura(logger["sn"])
    if not ultima:
        return None
    novo_ip = descoberta.localizar(logger["sn"], ultima["energia_total_kwh"], logger["ip"], logger["porta"])
    if not novo_ip:
        return None
    repositorio.atualizar_ip(logger["sn"], novo_ip)
    return ler_inversor(novo_ip, logger["sn"], logger["porta"])


def coletar_todos() -> dict[str, str | None]:
    """Lê cada logger cadastrado e grava a leitura. Devolve {nome: mensagem de erro ou None}."""
    resultado: dict[str, str | None] = {}
    for logger in repositorio.listar_loggers():
        try:
            leitura = ler_inversor(logger["ip"], logger["sn"], logger["porta"])
        except FalhaLogger as erro:
            try:
                leitura = _reencontrar(logger)
            except FalhaLogger:
                leitura = None
            if leitura is None:
                resultado[logger["nome"]] = str(erro)
                continue
        repositorio.gravar_leitura(logger["sn"], leitura)
        resultado[logger["nome"]] = None
    return resultado


def _coletar_e_imprimir() -> None:
    for nome, erro in coletar_todos().items():
        print(f"[{nome}] {erro or 'ok'}")


def rodar_continuo() -> None:
    while True:
        _coletar_e_imprimir()
        time.sleep(INTERVALO_S)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta de data loggers Solplanet")
    sub = parser.add_subparsers(dest="comando", required=True)
    add = sub.add_parser("adicionar")
    add.add_argument("nome")
    add.add_argument("ip")
    add.add_argument("sn")
    add.add_argument("--porta", type=int, default=8484)
    imp = sub.add_parser("importar")
    imp.add_argument("banco")
    sub.add_parser("uma-vez")
    sub.add_parser("rodar")
    args = parser.parse_args()

    if args.comando == "adicionar":
        repositorio.cadastrar_logger(args.sn, args.nome, args.ip, args.porta)
        print(f"Logger '{args.nome}' cadastrado.")
    elif args.comando == "importar":
        print(f"{repositorio.importar_loggers(args.banco)} logger(s) importado(s).")
    elif args.comando == "uma-vez":
        _coletar_e_imprimir()
    else:
        rodar_continuo()


if __name__ == "__main__":
    main()
