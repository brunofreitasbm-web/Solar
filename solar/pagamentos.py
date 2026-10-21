"""Faturas já carregadas que ainda não foram marcadas como pagas."""

from datetime import date

import pandas as pd

COLUNAS = ["uc", "unidade", "mes_ref", "vencimento", "total_rs", "dias", "vencida"]


def a_pagar(df: pd.DataFrame, nomes: dict[str, str], hoje: date | None = None) -> pd.DataFrame:
    """Última fatura de cada unidade sem pagamento registrado. As antigas não entram:
    o histórico anterior ao controle de pagamento não tem como ser conferido."""
    hoje = hoje or date.today()
    if df.empty or "pago_em" not in df:
        return pd.DataFrame(columns=COLUNAS)
    ultimas = df.sort_values("mes_ref").groupby("uc").tail(1)
    abertas = ultimas[ultimas["pago_em"].isna() & ultimas["vencimento"].fillna("").astype(bool)]
    linhas = []
    for l in abertas.itertuples():
        venc = date.fromisoformat(l.vencimento)
        dias = (venc - hoje).days
        linhas.append({"uc": l.uc, "unidade": nomes.get(l.uc, l.uc), "mes_ref": l.mes_ref, "vencimento": venc,
                       "total_rs": float(l.total_rs), "dias": dias, "vencida": dias < 0})
    if not linhas:
        return pd.DataFrame(columns=COLUNAS)
    return pd.DataFrame(linhas).sort_values("vencimento").reset_index(drop=True)
