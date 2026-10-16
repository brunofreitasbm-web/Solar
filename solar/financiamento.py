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
