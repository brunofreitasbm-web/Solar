import pytest

from solar import db, telegram
from solar.faturas import importacao
from solar.faturas.modelo import Fatura

PIX = "00020126580014br.gov.bcb.pix0136abc<&>5204000053039865802BR"


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "solar.db")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)


@pytest.fixture
def enviados(monkeypatch):
    lista = []
    monkeypatch.setattr(telegram, "_chamar", lambda token, metodo, dados: lista.append(dados) or {"ok": True})
    return lista


def _fatura(**extra) -> Fatura:
    return Fatura(uc="3033711769", mes_ref="2026-09", total_rs=1232.5, vencimento="2026-10-17",
                  pix_copia_cola=PIX, codigo_barras="83640000001-1 23250138000-3", **extra)


def test_mensagem_traz_unidade_valor_pix_e_codigo_de_barras():
    texto = telegram.montar_mensagem(_fatura(), "Casa da Praia", "Rua A, 101")
    assert "Casa da Praia" in texto and "UC 3033711769" in texto and "Rua A, 101" in texto
    assert "R$ 1.232,50" in texto and "17/10/2026" in texto and "09/2026" in texto
    assert "<code>00020126580014br.gov.bcb.pix0136abc&lt;&amp;&gt;5204000053039865802BR</code>" in texto
    assert "<code>83640000001-1 23250138000-3</code>" in texto


def test_mensagem_sem_pix_nem_barras_avisa_onde_buscar():
    texto = telegram.montar_mensagem(Fatura(uc="1", mes_ref="2026-09", total_rs=10.0), "UC 1")
    assert "Agência Virtual" in texto and "<code>" not in texto


def test_desativado_nao_envia(banco, enviados):
    telegram.salvar(telegram.ConfigTelegram("tok", "123", ativo=False))
    assert telegram.notificar_fatura(_fatura()) is False and enviados == []


def test_importar_fatura_envia_uma_vez_por_uc_e_mes(banco, enviados):
    telegram.salvar(telegram.ConfigTelegram("tok", "123", ativo=True))
    importacao.registrar(_fatura())
    importacao.registrar(_fatura())
    assert len(enviados) == 1 and enviados[0]["chat_id"] == "123"
    importacao.registrar(Fatura(uc="3033711769", mes_ref="2026-10", total_rs=50.0))
    assert len(enviados) == 2


def test_falha_no_telegram_nao_impede_a_importacao(banco, monkeypatch):
    def quebra(*_):
        raise telegram.FalhaTelegram("sem rede")
    monkeypatch.setattr(telegram, "_chamar", quebra)
    telegram.salvar(telegram.ConfigTelegram("tok", "123", ativo=True))
    importacao.registrar(_fatura())
    from solar.faturas import repositorio
    assert len(repositorio.tabela()) == 1
    assert telegram.notificar_fatura(_fatura()) is False  # não ficou marcada como enviada


def test_descobrir_chat_id_usa_a_ultima_conversa(monkeypatch):
    monkeypatch.setattr(telegram, "_chamar", lambda *_: {"result": [{"message": {"chat": {"id": 1}}}, {"message": {"chat": {"id": 999}}}]})
    assert telegram.descobrir_chat_id("tok") == "999"
