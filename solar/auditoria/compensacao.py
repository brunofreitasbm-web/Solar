"""Sobrou crédito no saldo, mas parte do consumo foi cobrada: a compensação deveria ter ido até
o consumo menos o custo de disponibilidade."""

import pandas as pd

from solar.auditoria import config as cfg
from solar.auditoria.achado import Achado, reais


def auditar(df: pd.DataFrame) -> list[Achado]:
    achados = []
    for _, f in df[~df["geradora"]].iterrows():
        nao_compensado = f["consumo_kwh"] - cfg.DISPONIBILIDADE_KWH - f["compensado_kwh"]
        if f["saldo_creditos_kwh"] <= cfg.TOLERANCIA_KWH or nao_compensado <= cfg.TOLERANCIA_KWH:
            continue
        custo = f" ({reais(nao_compensado * f['tarifa_kwh'])} a tarifa cheia)" if f["tarifa_kwh"] else ""
        achados.append(Achado(
            f["uc"], f["mes_ref"], "erro", "Crédito sobrando e consumo cobrado",
            f"Ficaram {f['saldo_creditos_kwh']:.0f} kWh de saldo, mas {nao_compensado:.0f} kWh de consumo "
            f"acima da disponibilidade não foram compensados{custo}.",
            "Reclame na Equatorial: há saldo suficiente, então a compensação deveria cobrir esse consumo.",
        ))
    return achados
