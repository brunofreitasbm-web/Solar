"""ROI consolidado: payback, retorno acumulado, TIR, VPL e projeção de 25 anos."""

import numpy_financial as npf
import pandas as pd

from solar import config
from solar.projecao import ModeloEconomia, serie_futura


def serie_acumulada(resumo: pd.DataFrame, investimento: float) -> pd.DataFrame:
    df = resumo.sort_values("mes_ref").copy()
    df["economia_acumulada_rs"] = df["economia_rs"].cumsum()
    df["saldo_rs"] = df["economia_acumulada_rs"] - investimento
    df["roi_pct"] = (df["economia_acumulada_rs"] / investimento - 1) * 100 if investimento else 0.0
    return df


def mes_payback(df_acumulado: pd.DataFrame) -> str | None:
    pagos = df_acumulado[df_acumulado["saldo_rs"] >= 0]
    return pagos.iloc[0]["mes_ref"] if not pagos.empty else None


def tir_mensal(investimento: float, economias_mensais: list[float]) -> float | None:
    """TIR mensal do fluxo [-investimento, economia_mes_1, economia_mes_2, ...]."""
    fluxo = [-investimento, *economias_mensais]
    if investimento <= 0 or not economias_mensais:
        return None
    try:
        taxa = npf.irr(fluxo)
    except Exception:
        return None
    return taxa if taxa is not None and not pd.isna(taxa) else None


def vpl(investimento: float, economias_mensais: list[float], taxa_desconto_anual: float) -> float:
    taxa_mensal = (1 + taxa_desconto_anual) ** (1 / 12) - 1
    fluxo = [-investimento, *economias_mensais]
    return npf.npv(taxa_mensal, fluxo)


def mes_payback_projetado(
    resumo: pd.DataFrame,
    investimento: float,
    degradacao_anual: float = config.PADRAO_DEGRADACAO_ANUAL,
    reajuste_tarifa_anual: float = config.PADRAO_REAJUSTE_TARIFA_ANUAL,
    meses_base: int = 12,
    modelo: ModeloEconomia | None = None,
    escalar_fio_b: bool = True,
) -> str | None:
    """Mês em que a economia acumulada alcança o investimento, partindo do que já foi
    economizado e projetando o resto (média recente, ou `modelo` com Fio B e sazonalidade)."""
    if resumo.empty or investimento <= 0:
        return None
    acumulado = resumo["economia_rs"].sum()
    if acumulado >= investimento:
        acumulada = resumo["economia_rs"].cumsum()
        return resumo.loc[acumulada >= investimento, "mes_ref"].iloc[0]
    futuro = serie_futura(resumo, 600, reajuste_tarifa_anual, degradacao_anual, modelo, escalar_fio_b, meses_base)
    for mes, economia in futuro:
        acumulado += economia
        if acumulado >= investimento:
            return str(mes)
    return None
