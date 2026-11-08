"""Ponto de entrada do Solar ROI: o executável clicável e o iniciar_solar.bat chamam daqui."""

import multiprocessing
import sys

from solar import desktop


def main() -> int:
    multiprocessing.freeze_support()
    return desktop.main()


if __name__ == "__main__":
    sys.exit(main())

