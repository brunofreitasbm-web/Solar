"""ROI consolidado: payback, retorno acumulado, TIR, VPL e projeção de 25 anos."""

from datetime import date

import numpy_financial as npf
import pandas as pd

from solar import config


def meses_desde(data_investimento: str) -> int:
    inicio = date.fromisoformat(data_investimento)
    hoje = date.today()
    return (hoje.year - inicio.year) * 12 + (hoje.month - inicio.month)


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


def projecao_25_anos(
    economia_media_mensal: float,
    investimento: float,
    degradacao_anual: float = config.PADRAO_DEGRADACAO_ANUAL,
    reajuste_tarifa_anual: float = config.PADRAO_REAJUSTE_TARIFA_ANUAL,
) -> pd.DataFrame:
    """Projeta a economia anual dos próximos 25 anos: a geração cai com a degradação dos
    painéis, mas o valor economizado por kWh sobe com o reajuste da tarifa — o fator líquido
    é (1 + reajuste) / (1 + degradação) a cada ano."""
    fator_liquido_anual = (1 + reajuste_tarifa_anual) / (1 + degradacao_anual)
    linhas = []
    economia_acumulada = 0.0
    economia_do_ano = economia_media_mensal * 12
    for ano in range(1, config.VIDA_UTIL_ANOS + 1):
        economia_acumulada += economia_do_ano
        linhas.append({
            "ano": ano,
            "economia_anual_rs": economia_do_ano,
            "economia_acumulada_rs": economia_acumulada,
            "roi_acumulado_pct": (economia_acumulada / investimento - 1) * 100 if investimento else 0.0,
        })
        economia_do_ano *= fator_liquido_anual
    return pd.DataFrame(linhas)


def mes_payback_projetado(
    resumo: pd.DataFrame,
    investimento: float,
    degradacao_anual: float = config.PADRAO_DEGRADACAO_ANUAL,
    reajuste_tarifa_anual: float = config.PADRAO_REAJUSTE_TARIFA_ANUAL,
    meses_base: int = 12,
) -> str | None:
    """Projeta o mês em que a economia acumulada alcança o investimento, partindo da
    economia já realizada e usando a média dos últimos `meses_base` meses como base — mais
    fiel ao regime atual da usina do que a média histórica completa (que inclui os
    primeiros meses, normalmente mais baixos, de ativação do sistema)."""
    if resumo.empty or investimento <= 0:
        return None
    ja_economizado = resumo["economia_rs"].sum()
    if ja_economizado >= investimento:
        return resumo["mes_ref"].iloc[0]

    fator_mensal = ((1 + reajuste_tarifa_anual) / (1 + degradacao_anual)) ** (1 / 12)
    economia_mes = resumo.tail(meses_base)["economia_rs"].mean()
    mes_atual = pd.Period(resumo["mes_ref"].max())
    acumulado = ja_economizado

    for _ in range(600):  # 50 anos de margem de segurança
        mes_atual += 1
        acumulado += economia_mes
        economia_mes *= fator_mensal
        if acumulado >= investimento:
            return str(mes_atual)
    return None
