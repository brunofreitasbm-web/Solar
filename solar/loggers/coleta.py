"""Coleta periódica dos data loggers cadastrados.

Uso:
  python -m solar.loggers.coleta adicionar "Usina 1" 192.168.0.50 AP00100522440448
  python -m solar.loggers.coleta uma-vez
  python -m solar.loggers.coleta rodar
"""

import argparse
import time

from solar.loggers import repositorio
from solar.loggers.solplanet import FalhaLogger, ler_inversor

INTERVALO_S = 300


def coletar_todos() -> None:
    for logger in repositorio.listar_loggers():
        try:
            leitura = ler_inversor(logger["ip"], logger["sn"], logger["porta"])
        except FalhaLogger as erro:
            print(f"[{logger['nome']}] {erro}")
            continue
        repositorio.gravar_leitura(logger["sn"], leitura)
        print(f"[{logger['nome']}] {leitura.potencia_w:.0f} W · {leitura.energia_dia_kwh:.1f} kWh hoje")


def rodar_continuo() -> None:
    while True:
        coletar_todos()
        time.sleep(INTERVALO_S)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta de data loggers Solplanet")
    sub = parser.add_subparsers(dest="comando", required=True)
    add = sub.add_parser("adicionar")
    add.add_argument("nome")
    add.add_argument("ip")
    add.add_argument("sn")
    add.add_argument("--porta", type=int, default=8484)
    sub.add_parser("uma-vez")
    sub.add_parser("rodar")
    args = parser.parse_args()

    if args.comando == "adicionar":
        repositorio.cadastrar_logger(args.sn, args.nome, args.ip, args.porta)
        print(f"Logger '{args.nome}' cadastrado.")
    elif args.comando == "uma-vez":
        coletar_todos()
    else:
        rodar_continuo()


if __name__ == "__main__":
    main()
