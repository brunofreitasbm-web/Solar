import pytest

from solar import ampliacao, db, unidades
from solar.ampliacao import Premissas, UsinaPlanejada


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "solar.db")


def premissas(**ajustes) -> Premissas:
    base = dict(rendimento_kwh_kwp_mes=100.0, valor_direto_kwh=1.0, valor_credito_kwh=0.5, lacuna_outras_unidades_kwh=0.0,
                custo_por_kwp_estimado=3_000.0, reajuste_anual=0.0, degradacao_anual=0.0, desconto_anual=0.1)
    return Premissas(**{**base, **ajustes})


def clinica(**campos) -> UsinaPlanejada:
    return UsinaPlanejada(nome="Clínica", paineis=20, potencia_painel_w=660, potencia_inversor_kw=10, **campos)


def test_potencia_e_relacao_com_o_inversor():
    u = clinica()
    assert u.kwp == pytest.approx(13.2)
    assert u.relacao_cc_ca == pytest.approx(1.32)


def test_energia_na_hora_vale_tarifa_cheia_e_credito_vale_o_liquido():
    # 1.320 kWh/mês; consumo de 1.000 kWh, 40% na hora (400) e 100 kWh de disponibilidade
    r = ampliacao.projetar(clinica(consumo_kwh_mes=1000, simultaneidade=0.4), premissas())
    assert r.geracao_kwh_mes == pytest.approx(1320)
    assert r.direto_kwh == pytest.approx(400)
    assert r.creditos_unidade_kwh == pytest.approx(500)   # 1000 - 400 - 100
    assert r.sobra_kwh == pytest.approx(420)
    assert r.economia_mes == pytest.approx(400 * 1.0 + 500 * 0.5)


def test_sem_consumo_informado_nao_ha_economia():
    r = ampliacao.projetar(clinica(), premissas())
    assert r.economia_mes == 0 and r.sobra_kwh == pytest.approx(1320)


def test_custo_estimado_e_custo_informado():
    assert ampliacao.projetar(clinica(consumo_kwh_mes=1000), premissas()).custo_total == pytest.approx(13.2 * 3000)
    informado = ampliacao.projetar(clinica(consumo_kwh_mes=1000, custo_total=30_000), premissas())
    assert informado.custo_total == 30_000 and not informado.custo_estimado


def test_financiamento_recupera_a_parcela_informada():
    u = clinica(consumo_kwh_mes=1500, custo_total=30_000, valor_financiado=24_000, parcela_mensal=700, qtd_parcelas=48)
    r = ampliacao.projetar(u, premissas())
    assert r.expansao.parcela_mensal == pytest.approx(700, rel=1e-6)
    assert r.financiamento_juros_mensal == pytest.approx(0.01467, abs=1e-4)


def test_salvar_com_uc_cria_unidade_geradora_com_kwp():
    usina_id = ampliacao.salvar(clinica(uc="3.456.789.012-34", endereco="Rua A"))
    u = ampliacao.listar()[0]
    assert u.id == usina_id and u.uc == "345678901234"
    unidade = next(x for x in unidades.listar() if x.uc == "345678901234")
    assert unidade.geradora and unidade.kwp == pytest.approx(13.2) and unidade.apelido == "Clínica"


def test_salvar_de_novo_atualiza_em_vez_de_duplicar():
    usina_id = ampliacao.salvar(clinica())
    ampliacao.salvar(UsinaPlanejada(id=usina_id, nome="Clínica", paineis=22, potencia_painel_w=660))
    assert len(ampliacao.listar()) == 1 and ampliacao.listar()[0].paineis == 22
