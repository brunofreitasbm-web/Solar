from datetime import date, datetime, timezone

import pandas as pd
import pytest

from solar import backup, config, expansao
from solar.composicao import compor
from solar.datas import mes_ref, somar_meses
from solar.expansao import Demanda, simular_expansao
from solar.vencimentos import encargos_por_atraso, gerar_ics, proximos_vencimentos


# ---------- datas
def test_somar_meses_respeita_fim_de_mes():
    assert somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert somar_meses(date(2026, 11, 15), 3) == date(2027, 2, 15)
    assert mes_ref(date(2026, 9, 5)) == "2026-09"


# ---------- vencimentos
def _faturas():
    return pd.DataFrame([
        {"uc": "1", "mes_ref": "2026-09", "vencimento": "2026-09-17", "emissao": "2026-09-10", "proxima_leitura": "2026-10-09",
         "multa_rs": 4.0, "juros_rs": 1.0},
        {"uc": "1", "mes_ref": "2026-08", "vencimento": "2026-08-17", "emissao": "2026-08-10", "proxima_leitura": "2026-09-09",
         "multa_rs": None, "juros_rs": None},
    ])


def test_vencimento_previsto_pelo_ciclo_de_leitura():
    previsao = proximos_vencimentos(_faturas(), {"1": "Casa"}, date(2026, 10, 1))
    linha = previsao.iloc[0]
    # leitura 09/10 → emissão 10/10 → +7 dias do prazo da última fatura
    assert linha["vencimento_previsto"] == date(2026, 10, 17) and linha["dias"] == 16
    assert not linha["aguardando_fatura"] and linha["unidade"] == "Casa"


def test_fatura_atrasada_e_sinalizada():
    previsao = proximos_vencimentos(_faturas(), {}, date(2026, 10, 20))
    assert previsao.iloc[0]["aguardando_fatura"]


def test_historico_antigo_rola_para_o_ciclo_atual():
    previsao = proximos_vencimentos(_faturas(), {}, date(2027, 3, 1))
    assert previsao.iloc[0]["vencimento_previsto"] >= date(2027, 2, 1)


def test_ics_tem_evento_e_alarme_por_mes():
    previsao = proximos_vencimentos(_faturas(), {"1": "Casa"}, date(2026, 10, 1))
    ics = gerar_ics(previsao, meses=3, agora=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert ics.count("BEGIN:VEVENT") == 3 and ics.count("TRIGGER:-P3D") == 3
    assert "DTSTART;VALUE=DATE:20261017" in ics and "DTSTART;VALUE=DATE:20261217" in ics
    assert ics.startswith("BEGIN:VCALENDAR") and "\r\n" in ics


def test_encargos_por_atraso_somam_multa_e_juros():
    tabela = encargos_por_atraso(_faturas(), {"1": "Casa"})
    linha = tabela.iloc[0]
    assert linha["faturas"] == 2 and linha["com_encargo"] == 1
    assert linha["encargos_rs"] == 5.0 and linha["pct_faturas"] == 50.0


# ---------- composição
def _economia_df():
    return pd.DataFrame([{
        "uc": "1", "mes_ref": "2026-09", "total_rs": 232.47, "economia_rs": 284.45, "valor_compensado_rs": 416.87,
        "fio_b_rs": 76.72, "beneficio_rs": 55.70, "consumo_rs": 48.76, "bandeira_rs": 3.59, "cip_rs": 42.74,
        "multa_rs": 4.51, "juros_rs": 0.45, "outros_rs": 0.0,
    }])


def test_cascata_fecha_na_conta_real():
    c = compor(_economia_df())
    assert round(c.sem_usina - c.energia_compensada + c.fio_b + c.beneficio_scee + c.outros_ajustes, 2) == round(c.real, 2)
    assert round(c.sem_usina, 2) == round(232.47 + 284.45, 2)


def test_partes_da_conta_somam_o_total_pago():
    c = compor(_economia_df())
    assert round(sum(c.partes_da_conta.values()), 2) == round(c.real, 2)


def test_filtro_por_unidade_e_mes():
    df = pd.concat([_economia_df(), _economia_df().assign(uc="2", mes_ref="2026-08")])
    assert compor(df, uc="2").real == 232.47
    assert compor(df, meses=["2026-09"]).real == 232.47
    assert compor(df).real == 2 * 232.47


# ---------- expansão
def test_lacuna_so_aparece_quando_demanda_passa_a_geracao():
    d = Demanda(producao_kwh_mes=1000, demanda_kwh_mes=800, crescimento_kwh_mes_por_ano=100, meses_ate_faltar=None)
    assert d.lacuna_em(0, 0.0) == 0 and d.lacuna_em(12, 0.0) == 0
    assert round(d.lacuna_em(36, 0.0)) == 100
    assert d.sobra_kwh_mes == 200


def test_meses_ate_faltar_na_analise_de_demanda():
    meses = [f"2025-{m:02d}" for m in range(1, 13)]
    linhas = []
    for i, m in enumerate(meses):
        linhas.append({"uc": "A", "mes_ref": m, "consumo_kwh": 900 + 10 * i, "injetado_kwh": 0.0, "geradora": False})
        linhas.append({"uc": "G", "mes_ref": m, "consumo_kwh": 100, "injetado_kwh": 1000.0 if i >= 2 else 0.0, "geradora": True})
    d = expansao.analisar_demanda(pd.DataFrame(linhas), 0.0)
    assert d.producao_kwh_mes == pytest.approx(1000, rel=0.01)
    assert d.meses_ate_faltar is None or d.meses_ate_faltar > 0


def test_expansao_sem_demanda_a_cobrir_nao_gera_economia():
    r = simular_expansao(10, 3000, 120, 0.6, 0.06, 0.005, 0.13, kwh_uteis_mes=0.0)
    assert r.economia_mes_inicial == 0 and r.vpl < 0 and r.payback_meses is None


def test_expansao_com_demanda_se_paga_e_financiar_encarece():
    vista = simular_expansao(10, 3000, 120, 0.9, 0.06, 0.005, 0.10)
    financiada = simular_expansao(10, 3000, 120, 0.9, 0.06, 0.005, 0.10, juros_mensal=0.023, parcelas=48, entrada_pct=0.2)
    assert vista.payback_meses and vista.vpl > 0
    assert financiada.juros_total > 0 and financiada.parcela_mensal > 0
    assert financiada.vpl < vista.vpl


def test_expansao_limitada_pela_demanda_util():
    r = simular_expansao(10, 3000, 120, 1.0, 0.0, 0.0, 0.10, kwh_uteis_mes=400)
    assert r.kwh_mes == 400


# ---------- backup
def test_backup_gera_zip_com_o_banco_e_respeita_a_retencao(tmp_path, monkeypatch):
    import sqlite3
    banco = tmp_path / "solar.db"
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (42)")
    con.commit()
    con.close()
    monkeypatch.setattr(config, "CAMINHO_DB", banco)
    monkeypatch.setattr(config, "BACKUPS_MANTIDOS", 2)
    destino = tmp_path / "bk"
    for minuto in range(4):
        backup.fazer_backup(destino, agora=datetime(2026, 10, 1, 12, minuto))
    arquivos = backup.listar_backups(destino)
    assert len(arquivos) == 2 and arquivos[0].name == "solar_20261001_120300.zip"

    import zipfile
    with zipfile.ZipFile(arquivos[0]) as zf:
        zf.extract("solar.db", tmp_path / "extraido")
    assert sqlite3.connect(tmp_path / "extraido" / "solar.db").execute("SELECT x FROM t").fetchone() == (42,)


def test_backup_automatico_so_quando_passou_o_prazo(tmp_path, monkeypatch):
    import os, sqlite3
    banco = tmp_path / "solar.db"
    sqlite3.connect(banco).close()
    monkeypatch.setattr(config, "CAMINHO_DB", banco)
    primeiro = backup.backup_automatico_se_necessario(tmp_path / "bk", dias=7)
    assert primeiro is not None
    assert backup.backup_automatico_se_necessario(tmp_path / "bk", dias=7) is None
    antigo = datetime.now().timestamp() - 8 * 86400
    os.utime(primeiro, (antigo, antigo))
    assert backup.backup_automatico_se_necessario(tmp_path / "bk", dias=7) is not None


def test_restaurar_troca_o_banco_e_guarda_copia_de_seguranca(tmp_path, monkeypatch):
    import sqlite3
    banco = tmp_path / "solar.db"
    con = sqlite3.connect(banco); con.execute("CREATE TABLE t (x)"); con.execute("INSERT INTO t VALUES (1)"); con.commit(); con.close()
    monkeypatch.setattr(config, "CAMINHO_DB", banco)
    arquivo = backup.fazer_backup(tmp_path / "bk")
    con = sqlite3.connect(banco); con.execute("UPDATE t SET x = 99"); con.commit(); con.close()
    seguranca = backup.restaurar_backup(arquivo)
    assert sqlite3.connect(banco).execute("SELECT x FROM t").fetchone() == (1,)
    assert sqlite3.connect(seguranca).execute("SELECT x FROM t").fetchone() == (99,)
