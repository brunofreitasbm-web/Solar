"""Créditos recebidos = compensado + saldo - saldo anterior. Nunca pode ser negativo, e para
uma beneficiária deve acompanhar o que as geradoras injetaram vezes o percentual do rateio."""

import pandas as pd

from solar.auditoria import config as cfg
from solar.auditoria.achado import Achado


def com_recebidos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["uc", "mes_ref"]).copy()
    saldo_anterior = df.groupby("uc")["saldo_creditos_kwh"].shift()
    df["recebido_kwh"] = df["compensado_kwh"] + df["saldo_creditos_kwh"] - saldo_anterior
    return df


def _esperado_kwh(df: pd.DataFrame) -> pd.Series:
    injetado = df[df["geradora"]].set_index(["uc", "mes_ref"])["injetado_kwh"]

    def esperado(f) -> float:
        return sum(injetado.get((uc, f["mes_ref"]), 0.0) * pct / 100 for uc, pct in f["rateio"].items())

    return df.apply(esperado, axis=1)


def _saldo_negativo(df: pd.DataFrame) -> list[Achado]:
    caiu = df[df["recebido_kwh"] < -cfg.TOLERANCIA_KWH]
    return [Achado(
        f["uc"], f["mes_ref"], "erro", "Saldo de créditos caiu mais do que a energia compensada",
        f"O saldo foi de {f['saldo_creditos_kwh'] - f['recebido_kwh'] + f['compensado_kwh']:.0f} kWh para "
        f"{f['saldo_creditos_kwh']:.0f} kWh com {f['compensado_kwh']:.0f} kWh compensados: "
        f"faltam {-f['recebido_kwh']:.0f} kWh na conta.",
        "Peça à Equatorial o extrato de créditos (SCEE) da unidade e confira os lançamentos do mês.",
    ) for _, f in caiu.iterrows()]


def _recebido_abaixo_do_rateio(df: pd.DataFrame) -> list[Achado]:
    achados = []
    beneficiarias = df[~df["geradora"]].copy()
    beneficiarias["esperado_kwh"] = _esperado_kwh(df).reindex(beneficiarias.index)
    for uc, g in beneficiarias.groupby("uc"):
        janela = g.tail(cfg.JANELA_CREDITOS_MESES)
        if len(janela) < cfg.JANELA_CREDITOS_MESES or janela["recebido_kwh"].isna().any():
            continue
        esperado, recebido = janela["esperado_kwh"].sum(), janela["recebido_kwh"].sum()
        if esperado > 0 and recebido < esperado * (1 - cfg.TOLERANCIA_RECEBIDO):
            achados.append(Achado(
                uc, janela["mes_ref"].iloc[-1], "aviso", "Recebeu menos crédito do que o rateio indica",
                f"Nos últimos {cfg.JANELA_CREDITOS_MESES} meses as geradoras injetaram o equivalente a "
                f"{esperado:.0f} kWh para esta unidade pelo rateio, mas chegaram {recebido:.0f} kWh.",
                "Confira se o rateio protocolado está vigente e peça à Equatorial o demonstrativo de injeção.",
            ))
    return achados


def auditar(df: pd.DataFrame) -> list[Achado]:
    df = com_recebidos(df)
    return _saldo_negativo(df) + _recebido_abaixo_do_rateio(df)
