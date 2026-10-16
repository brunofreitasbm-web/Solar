"""Análise de expansão: a demanda já supera a geração? Quanto vale (e custa) ampliar?"""

from dataclasses import dataclass

import numpy_financial as npf
import pandas as pd

from solar import config
from solar.projecao import producao_anual_equivalente

MESES_VIDA_UTIL = config.VIDA_UTIL_ANOS * 12


@dataclass
class Demanda:
    producao_kwh_mes: float              # média anual equivalente das usinas
    demanda_kwh_mes: float               # consumo compensável médio dos últimos 12 meses
    crescimento_kwh_mes_por_ano: float   # quanto a demanda cresce por ano (tendência linear)
    meses_ate_faltar: int | None         # 0 = já falta; None = não falta em 10 anos

    @property
    def sobra_kwh_mes(self) -> float:
        return self.producao_kwh_mes - self.demanda_kwh_mes

    def lacuna_em(self, meses: int, degradacao_anual: float) -> float:
        """Demanda que ficaria sem cobertura daqui a `meses` meses (kWh/mês)."""
        producao = self.producao_kwh_mes * (1 - degradacao_anual) ** (meses / 12)
        demanda = self.demanda_kwh_mes + self.crescimento_kwh_mes_por_ano * meses / 12
        return max(demanda - producao, 0.0)


def _demanda_mensal(df: pd.DataFrame) -> pd.Series:
    """Consumo que pode ser compensado: o que passa do custo de disponibilidade em cada unidade."""
    compensavel = (df["consumo_kwh"] - config.DISPONIBILIDADE_KWH).clip(lower=0)
    return compensavel.groupby(df["mes_ref"]).sum()


def analisar_demanda(df: pd.DataFrame, degradacao_anual: float, fatores: dict[int, float] | None = None) -> Demanda | None:
    demanda = _demanda_mensal(df).tail(12)
    producao = producao_anual_equivalente(df, fatores)
    if len(demanda) < 6 or producao <= 0:
        return None

    x = pd.Series(range(len(demanda)), index=demanda.index, dtype=float)
    inclinacao = ((x - x.mean()) * (demanda - demanda.mean())).sum() / ((x - x.mean()) ** 2).sum()
    resultado = Demanda(producao, float(demanda.mean()), float(inclinacao * 12), None)
    for k in range(0, 121):
        if resultado.lacuna_em(k, degradacao_anual) > 0:
            resultado.meses_ate_faltar = k
            break
    return resultado


@dataclass
class ResultadoExpansao:
    capex: float
    kwh_mes: float
    economia_mes_inicial: float
    parcela_mensal: float | None
    juros_total: float
    payback_meses: int | None
    vpl: float
    tir_anual: float | None


def simular_expansao(
    kwp: float,
    custo_por_kwp: float,
    rendimento_kwh_kwp_mes: float,
    valor_kwh: float,
    reajuste_anual: float,
    degradacao_anual: float,
    taxa_desconto_anual: float,
    juros_mensal: float | None = None,
    parcelas: int = 48,
    entrada_pct: float = 0.0,
    kwh_uteis_mes: float | None = None,
) -> ResultadoExpansao:
    """Fluxo mensal por 25 anos. À vista (`juros_mensal=None`) ou financiado: a parcela
    entra no fluxo e só a energia útil (limitada pela demanda descoberta) gera economia."""
    capex = kwp * custo_por_kwp
    kwh_mes = kwp * rendimento_kwh_kwp_mes
    if kwh_uteis_mes is not None:
        kwh_mes = min(kwh_mes, kwh_uteis_mes)

    if juros_mensal is None:
        entrada, parcela = capex, None
    else:
        entrada = capex * entrada_pct
        financiado = capex - entrada
        parcela = float(-npf.pmt(juros_mensal, parcelas, financiado)) if financiado > 0 else 0.0

    fluxo = [-entrada]
    for mes in range(1, MESES_VIDA_UTIL + 1):
        economia = kwh_mes * valor_kwh * ((1 + reajuste_anual) * (1 - degradacao_anual)) ** (mes / 12)
        fluxo.append(economia - (parcela if parcela and mes <= parcelas else 0.0))

    taxa_mensal = (1 + taxa_desconto_anual) ** (1 / 12) - 1
    tir_mensal = npf.irr(fluxo)
    acumulado, payback = 0.0, None
    for mes, valor in enumerate(fluxo):
        acumulado += valor
        if payback is None and acumulado >= 0 and mes > 0:
            payback = mes
    return ResultadoExpansao(
        capex=capex, kwh_mes=kwh_mes, economia_mes_inicial=kwh_mes * valor_kwh,
        parcela_mensal=parcela, juros_total=(parcela * parcelas - (capex - entrada)) if parcela else 0.0,
        payback_meses=payback, vpl=float(npf.npv(taxa_mensal, fluxo)),
        tir_anual=float((1 + tir_mensal) ** 12 - 1) if tir_mensal == tir_mensal else None,
    )
