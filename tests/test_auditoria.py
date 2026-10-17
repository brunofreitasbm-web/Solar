import pandas as pd

from solar import auditoria
from solar.auditoria import ciclo, compensacao, fio_b, saldo


def faturas(**colunas) -> pd.DataFrame:
    n = len(next(iter(colunas.values())))
    base = dict(uc=["1"] * n, mes_ref=[f"2026-0{m + 1}" for m in range(n)], geradora=[False] * n, consumo_kwh=[500.0] * n,
                injetado_kwh=[0.0] * n, compensado_kwh=[400.0] * n, saldo_creditos_kwh=[0.0] * n, tarifa_kwh=[1.2] * n,
                fio_b_rs=[None] * n, emissao=[""] * n, proxima_leitura=[""] * n, multa_rs=[None] * n, juros_rs=[None] * n,
                rateio=[{}] * n)
    return pd.DataFrame({**base, **colunas})


def test_saldo_que_cai_mais_que_o_compensado_e_erro():
    df = faturas(compensado_kwh=[100.0, 100.0], saldo_creditos_kwh=[300.0, 50.0])
    achados = saldo.auditar(df)
    assert [a.gravidade for a in achados] == ["erro"] and achados[0].mes_ref == "2026-02"


def test_saldo_coerente_nao_gera_achado():
    df = faturas(compensado_kwh=[100.0, 100.0], saldo_creditos_kwh=[300.0, 350.0])
    assert saldo.auditar(df) == []


def test_recebido_abaixo_do_rateio_avisa_so_na_janela_completa():
    meses = ["2026-01", "2026-02", "2026-03", "2026-04"]
    gerad = faturas(uc=["G"] * 4, mes_ref=meses, geradora=[True] * 4, injetado_kwh=[1000.0] * 4)
    benef = faturas(uc=["1"] * 4, mes_ref=meses, compensado_kwh=[100.0] * 4, saldo_creditos_kwh=[0.0] * 4,
                    rateio=[{"G": 50.0}] * 4)
    achados = saldo.auditar(pd.concat([gerad, benef], ignore_index=True))
    assert len(achados) == 1 and achados[0].uc == "1" and "rateio" in achados[0].titulo.lower()


def test_credito_sobrando_com_consumo_cobrado_e_erro():
    df = faturas(consumo_kwh=[600.0], compensado_kwh=[300.0], saldo_creditos_kwh=[80.0])
    assert [a.titulo for a in compensacao.auditar(df)] == ["Crédito sobrando e consumo cobrado"]


def test_sem_saldo_sobrando_nao_reclama_da_compensacao():
    df = faturas(consumo_kwh=[600.0], compensado_kwh=[300.0], saldo_creditos_kwh=[0.0])
    assert compensacao.auditar(df) == []


def test_fio_b_com_salto_e_marcado_e_estavel_nao():
    estavel = faturas(compensado_kwh=[100.0] * 5, fio_b_rs=[10.0] * 5)
    assert fio_b.auditar(estavel) == []
    salto = faturas(compensado_kwh=[100.0] * 5, fio_b_rs=[10.0, 10.0, 10.0, 10.0, 30.0])
    assert [a.mes_ref for a in fio_b.auditar(salto)] == ["2026-05"]


def test_ciclo_medido_entre_emissoes_seguidas():
    df = faturas(emissao=["2026-01-10", "2026-02-09", "2026-03-31"])
    assert [a.mes_ref for a in ciclo.auditar(df)] == ["2026-03"]


def test_auditar_ordena_erros_antes_dos_avisos_e_ignora_df_vazio():
    assert auditoria.auditar(pd.DataFrame()) == []
    df = faturas(consumo_kwh=[600.0], compensado_kwh=[300.0], saldo_creditos_kwh=[80.0], multa_rs=[5.0])
    assert [a.gravidade for a in auditoria.auditar(df)] == ["erro", "aviso"]
