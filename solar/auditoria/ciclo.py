from datetime import date

import pandas as pd

from solar.auditoria import config as cfg
from solar.auditoria.achado import Achado


def _meses_seguidos(anterior: str, atual: str) -> bool:
    a_ano, a_mes = map(int, anterior.split("-"))
    ano, mes = map(int, atual.split("-"))
    return (ano - a_ano) * 12 + mes - a_mes == 1


def auditar(df: pd.DataFrame) -> list[Achado]:
    """A fatura é emitida na data da leitura, então o ciclo é a distância entre duas emissões seguidas."""
    achados = []
    for uc, g in df[df["emissao"].astype(bool)].sort_values("mes_ref").groupby("uc"):
        for anterior, f in zip(g.itertuples(), g.iloc[1:].itertuples()):
            if not _meses_seguidos(anterior.mes_ref, f.mes_ref):
                continue
            dias = (date.fromisoformat(f.emissao) - date.fromisoformat(anterior.emissao)).days
            if cfg.CICLO_MIN_DIAS <= dias <= cfg.CICLO_MAX_DIAS:
                continue
            achados.append(Achado(
                uc, f.mes_ref, "aviso", f"Ciclo de leitura de {dias} dias",
                f"Entre as duas últimas leituras passaram {dias} dias (esperado entre {cfg.CICLO_MIN_DIAS} e "
                f"{cfg.CICLO_MAX_DIAS}). Ciclo curto ou longo distorce consumo e compensação do mês.",
                "Compare kWh por dia com os outros meses antes de concluir que o consumo mudou.",
            ))
    return achados
