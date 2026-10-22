"""Testes unitários para o módulo solar.ia."""

from unittest.mock import MagicMock

import pytest

from solar import db
from solar.ia import cliente, ferramentas
from solar.tarifa import aneel


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_DB", tmp_path / "solar.db")
    tarifa_mock = MagicMock()
    tarifa_mock.tusd_kwh = 0.35
    tarifa_mock.com_tributos.return_value = 0.95
    monkeypatch.setattr(aneel, "tarifa_de_hoje", lambda: tarifa_mock)
    monkeypatch.setattr(cliente, "obter_chave_configurada", lambda: ("", ""))


def test_obter_resumo_sistema():
    resumo = ferramentas.obter_resumo_sistema()
    assert isinstance(resumo, dict)
    assert "status" in resumo


def test_analisar_expansao_demanda():
    exp = ferramentas.analisar_expansao_demanda()
    assert isinstance(exp, dict)
    assert "status" in exp


def test_analisar_decisao_quitacao():
    quit = ferramentas.analisar_decisao_quitacao()
    assert isinstance(quit, dict)
    assert "status" in quit


def test_gerar_relatorio_executivo_markdown():
    relatorio = ferramentas.gerar_relatorio_executivo_markdown()
    assert isinstance(relatorio, str)
    assert len(relatorio) > 20


def test_salvar_e_obter_chave_deepseek(monkeypatch):
    monkeypatch.undo()
    cliente.salvar_chave("deepseek", "sk-teste-123")
    prov, chave = cliente.obter_chave_configurada()
    assert prov == "deepseek"
    assert "sk-teste-123" in chave
