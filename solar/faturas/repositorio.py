import json

import pandas as pd

from solar import unidades
from solar.db import conexao
from solar.faturas.modelo import Fatura

COLUNAS_DB = (
    "uc", "mes_ref", "consumo_kwh", "injetado_kwh", "compensado_kwh", "saldo_creditos_kwh",
    "credito_rs", "tarifa_kwh", "total_rs", "bandeira", "arquivo", "origem",
    "vencimento", "emissao", "proxima_leitura", "consumo_rs", "fio_b_rs", "beneficio_rs",
    "bandeira_rs", "cip_rs", "multa_rs", "juros_rs", "outros_rs",
    "pix_copia_cola", "codigo_barras",
)


def salvar(fatura: Fatura) -> None:
    unidades.garantir(fatura.uc, fatura.endereco, fatura.tem_geracao)
    dados = {c: getattr(fatura, c) for c in COLUNAS_DB}
    dados["rateio_json"] = json.dumps(fatura.rateio)
    colunas = ", ".join(dados)
    marcadores = ", ".join(f":{c}" for c in dados)
    # Upsert (não REPLACE) para reimportar o PDF sem apagar o pagamento já marcado.
    atualizacoes = ", ".join(f"{c} = excluded.{c}" for c in dados if c not in ("uc", "mes_ref"))
    with conexao() as con:
        con.execute(
            f"INSERT INTO faturas ({colunas}) VALUES ({marcadores}) ON CONFLICT (uc, mes_ref) DO UPDATE SET {atualizacoes}",
            dados,
        )


def marcar_paga(uc: str, mes_ref: str, pago_em: str, valor_pago: float | None = None) -> None:
    with conexao() as con:
        con.execute("UPDATE faturas SET pago_em = ?, valor_pago = ? WHERE uc = ? AND mes_ref = ?",
                    (pago_em, valor_pago, uc, mes_ref))


def desmarcar_paga(uc: str, mes_ref: str) -> None:
    with conexao() as con:
        con.execute("UPDATE faturas SET pago_em = NULL, valor_pago = NULL WHERE uc = ? AND mes_ref = ?", (uc, mes_ref))


def tabela() -> pd.DataFrame:
    with conexao() as con:
        df = pd.read_sql_query(
            """SELECT f.*, u.apelido, u.geradora, u.data_pedido_conexao, u.kwp, u.lat, u.lon
               FROM faturas f JOIN unidades u USING (uc)
               ORDER BY f.mes_ref, f.uc""",
            con,
        )
    df["geradora"] = df["geradora"].astype(bool)
    df["rateio"] = df["rateio_json"].apply(lambda j: json.loads(j) if j else {})
    return df.drop(columns="rateio_json")


def excluir(fatura_id: int) -> None:
    with conexao() as con:
        con.execute("DELETE FROM faturas WHERE id = ?", (fatura_id,))
