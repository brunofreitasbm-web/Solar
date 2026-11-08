"""Compara a geração medida pelos inversores com a energia injetada que a Equatorial faturou, ciclo a ciclo.

A geração do ciclo vem do contador acumulado do inversor (fim do ciclo menos início), por isso lacunas na
coleta no meio do período não atrapalham — só importam leituras perto das datas de leitura do medidor."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from solar.loggers import repositorio

TOLERANCIA_DIAS_MARCO = 1
MARGEM_INCONSISTENCIA = 0.05
CICLO_MIN_DIAS, CICLO_MAX_DIAS = 20, 40


@dataclass(frozen=True)
class Ciclo:
    mes_ref: str
    inicio: date
    fim: date
    injetado_kwh: float
    geracao_kwh: float | None
    situacao: str  # "ok" | "inconsistente" | "sem_dados"

    @property
    def autoconsumo_kwh(self) -> float | None:
        if self.geracao_kwh is None or self.situacao != "ok":
            return None
        return max(self.geracao_kwh - self.injetado_kwh, 0.0)


def situacao(injetado_kwh: float, geracao_kwh: float | None) -> str:
    """Injetar mais do que o inversor gerou é impossível: aponta medidor, ciclo desalinhado ou logger que não cobre a usina."""
    if geracao_kwh is None:
        return "sem_dados"
    return "inconsistente" if injetado_kwh > geracao_kwh * (1 + MARGEM_INCONSISTENCIA) else "ok"


def _contador_no_dia(sn: str, dia: date) -> float | None:
    """Contador total no fim do dia, aceitando a última leitura de até TOLERANCIA_DIAS_MARCO dias antes."""
    leitura = repositorio.ultima_leitura_ate(sn, f"{dia.isoformat()}T23:59:59")
    if not leitura:
        return None
    if datetime.fromisoformat(leitura["lida_em"]).date() < dia - timedelta(days=TOLERANCIA_DIAS_MARCO):
        return None
    return leitura["energia_total_kwh"]


def geracao_no_periodo(sns: list[str], inicio: date, fim: date) -> float | None:
    """Soma dos inversores no período; None se algum não tem marco nas duas pontas (a soma parcial enganaria)."""
    if not sns:
        return None
    total = 0.0
    for sn in sns:
        antes, depois = _contador_no_dia(sn, inicio), _contador_no_dia(sn, fim)
        if antes is None or depois is None or depois < antes:
            return None
        total += depois - antes
    return total


def ciclos_da_unidade(uc: str, faturas: pd.DataFrame) -> list[Ciclo]:
    """Um ciclo por par de faturas consecutivas: a data de emissão coincide com a leitura do medidor."""
    sns = [l["sn"] for l in repositorio.listar_loggers() if l["uc"] == uc]
    do_uc = faturas[(faturas["uc"] == uc) & faturas["emissao"].notna() & (faturas["emissao"] != "")]
    do_uc = do_uc.sort_values("mes_ref").reset_index(drop=True)
    ciclos = []
    for i in range(1, len(do_uc)):
        inicio, fim = date.fromisoformat(do_uc.loc[i - 1, "emissao"]), date.fromisoformat(do_uc.loc[i, "emissao"])
        if not CICLO_MIN_DIAS <= (fim - inicio).days <= CICLO_MAX_DIAS:
            continue
        injetado = float(do_uc.loc[i, "injetado_kwh"])
        geracao = geracao_no_periodo(sns, inicio, fim)
        ciclos.append(Ciclo(do_uc.loc[i, "mes_ref"], inicio, fim, injetado, geracao, situacao(injetado, geracao)))
    return ciclos[::-1]
