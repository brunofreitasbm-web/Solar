"""Fluxo de caixa real quando o investimento é financiado: compara a economia de cada mês
com a parcela daquele mês, em vez de medir o ROI só contra o valor total investido."""

from datetime import date

import pandas as pd

from solar.configuracoes import Configuracoes


def _primeiro_dia_do_mes(mes_ref: str) -> date:
    ano, mes = map(int, mes_ref.split("-"))
    return date(ano, mes, 1)


def _mes_da_parcela(numero: int, inicio: date) -> str:
    total_meses = (inicio.year * 12 + inicio.month - 1) + (numero - 1)
    return f"{total_meses // 12:04d}-{total_meses % 12 + 1:02d}"


def parcelas_por_mes(cfg: Configuracoes) -> dict[str, float]:
    """{mes_ref: valor da parcela} para cada mês em que há parcela do financiamento."""
    if not cfg.parcela_mensal or not cfg.qtd_parcelas or not cfg.data_primeira_parcela:
        return {}
    inicio = date.fromisoformat(cfg.data_primeira_parcela)
    return {_mes_da_parcela(n, inicio): cfg.parcela_mensal for n in range(1, cfg.qtd_parcelas + 1)}


def fluxo_com_financiamento(resumo_mensal: pd.DataFrame, cfg: Configuracoes) -> pd.DataFrame:
    """Para cada mês: economia, parcela (0 fora do período financiado) e o saldo líquido
    (economia − parcela) — mostra se a usina já está se pagando mês a mês, mesmo antes de
    o financiamento terminar."""
    parcelas = parcelas_por_mes(cfg)
    df = resumo_mensal.copy()
    df["parcela_rs"] = df["mes_ref"].map(parcelas).fillna(0.0)
    df["saldo_liquido_rs"] = df["economia_rs"] - df["parcela_rs"]
    df["saldo_liquido_acumulado_rs"] = df["saldo_liquido_rs"].cumsum()
    return df


def mes_parcelas_termina(cfg: Configuracoes) -> str | None:
    parcelas = parcelas_por_mes(cfg)
    return max(parcelas) if parcelas else None


def mes_ponto_equilibrio(
    resumo_mensal: "pd.DataFrame",
    cfg: Configuracoes,
    degradacao_anual: float | None = None,
    reajuste_tarifa_anual: float | None = None,
    meses_base: int = 12,
) -> str | None:
    """Projeta o mês em que o saldo líquido acumulado (economia menos parcelas pagas)
    deixa de ser negativo — diferente do payback total, que ignora o custo mensal do
    financiamento. Usa a média de economia dos últimos `meses_base` meses como base,
    crescendo com o reajuste de tarifa e caindo com a degradação dos painéis."""
    if resumo_mensal.empty:
        return None
    from solar import config as config_padrao
    degradacao_anual = config_padrao.PADRAO_DEGRADACAO_ANUAL if degradacao_anual is None else degradacao_anual
    reajuste_tarifa_anual = config_padrao.PADRAO_REAJUSTE_TARIFA_ANUAL if reajuste_tarifa_anual is None else reajuste_tarifa_anual

    fluxo = fluxo_com_financiamento(resumo_mensal, cfg)
    saldo = fluxo["saldo_liquido_acumulado_rs"].iloc[-1]
    if saldo >= 0:
        return fluxo["mes_ref"].iloc[-1]

    parcelas = parcelas_por_mes(cfg)
    fator_mensal = ((1 + reajuste_tarifa_anual) / (1 + degradacao_anual)) ** (1 / 12)
    economia_mes = resumo_mensal.tail(meses_base)["economia_rs"].mean()
    mes_atual = pd.Period(resumo_mensal["mes_ref"].max())

    for _ in range(600):
        mes_atual += 1
        saldo += economia_mes - parcelas.get(str(mes_atual), 0.0)
        economia_mes *= fator_mensal
        if saldo >= 0:
            return str(mes_atual)
    return None
