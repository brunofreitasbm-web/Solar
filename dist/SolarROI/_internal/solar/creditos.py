"""Saldo de créditos de energia por unidade e alerta de créditos perto de expirar (60 meses)."""

from datetime import date

import pandas as pd

from solar.config import VALIDADE_CREDITOS_MESES


def saldo_por_unidade(df_faturas: pd.DataFrame) -> pd.DataFrame:
    """Último saldo de créditos (kWh) informado na fatura mais recente de cada UC."""
    recentes = df_faturas.sort_values("mes_ref").groupby("uc", as_index=False).last()
    return recentes[["uc", "apelido", "geradora", "mes_ref", "saldo_creditos_kwh"]]


def _meses_ate_expirar(mes_credito: str, hoje: date) -> int:
    ano, mes = map(int, mes_credito.split("-"))
    meses_passados = (hoje.year - ano) * 12 + (hoje.month - mes)
    return VALIDADE_CREDITOS_MESES - meses_passados


def creditos_a_expirar(df_faturas: pd.DataFrame, meses_de_alerta: int = 6, hoje: date | None = None) -> pd.DataFrame:
    """Créditos gerados (injetado - compensado > 0, ou saldo crescente) que vencem dentro
    de `meses_de_alerta` meses, usando a regra de 60 meses de validade da Lei 14.300."""
    hoje = hoje or date.today()
    df = df_faturas.copy()
    df["credito_gerado_kwh"] = (df["injetado_kwh"] - df["compensado_kwh"]).clip(lower=0)
    df = df[df["credito_gerado_kwh"] > 0].copy()
    df["meses_para_expirar"] = df["mes_ref"].apply(lambda m: _meses_ate_expirar(m, hoje))
    expirando = df[df["meses_para_expirar"].between(0, meses_de_alerta)]
    return expirando[["uc", "apelido", "mes_ref", "credito_gerado_kwh", "meses_para_expirar"]].sort_values(
        "meses_para_expirar"
    )


def sugestao_rateio(saldos: pd.DataFrame) -> str:
    """Texto simples sugerindo redistribuir o rateio quando uma UC beneficiária tem saldo
    alto acumulado e outra geradora tem pouco saldo — sinal de rateio desbalanceado."""
    if saldos.empty:
        return "Sem faturas suficientes para sugerir rateio."
    maior = saldos.loc[saldos["saldo_creditos_kwh"].idxmax()]
    menor = saldos.loc[saldos["saldo_creditos_kwh"].idxmin()]
    if maior["saldo_creditos_kwh"] <= 0 or maior["uc"] == menor["uc"]:
        return "Saldos equilibrados entre as unidades."
    if maior["saldo_creditos_kwh"] > 3 * max(menor["saldo_creditos_kwh"], 1):
        return (
            f"{maior['apelido'] or maior['uc']} acumulou {maior['saldo_creditos_kwh']:.0f} kWh em créditos "
            f"enquanto {menor['apelido'] or menor['uc']} tem só {menor['saldo_creditos_kwh']:.0f} kWh — "
            "considere pedir à distribuidora para redistribuir o rateio entre as unidades."
        )
    return "Saldos equilibrados entre as unidades."
