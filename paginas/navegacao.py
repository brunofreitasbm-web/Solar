"""Mapa de páginas do app. Fica fora do app.py para que as páginas possam linkar umas às outras
(st.page_link só aceita páginas registradas no st.navigation da execução atual)."""

from importlib import import_module

import streamlit as st

from solar.faturas import pendentes as fila

CHAVE_PAGINAS = "_paginas_registradas"

# (grupo, módulo, título, ícone, url)
ROTAS = (
    ("Operações", "upload_pg", "Enviar faturas", ":material/upload_file:", "enviar-faturas"),
    ("Operações", "revisao_pg", "Revisar leitura", ":material/fact_check:", "revisar-leitura"),
    ("Operações", "rateio_pg", "Rateio de créditos", ":material/swap_horiz:", "rateio-creditos"),
    ("Visão Geral", "dashboard_pg", "Dashboard", ":material/dashboard:", "dashboard"),
    ("Visão Geral", "auditoria_pg", "Auditoria da fatura", ":material/rule:", "auditoria-fatura"),
    ("Visão Geral", "composicao_pg", "Composição da conta", ":material/pie_chart:", "composicao-conta"),
    ("Visão Geral", "faturas_pg", "Faturas", ":material/receipt_long:", "faturas"),
    ("Visão Geral", "unidades_pg", "Unidades", ":material/home:", "unidades"),
    ("Visão Geral", "vencimentos_pg", "Vencimentos", ":material/calendar_month:", "vencimentos"),
    ("Planejamento", "simulador_pg", "Simulador", ":material/calculate:", "simulador"),
    ("Planejamento", "nova_usina_pg", "Nova usina", ":material/solar_power:", "nova-usina"),
    ("Sistema", "configuracoes_pg", "Configurações", ":material/settings:", "configuracoes"),
)
PAGINA_INICIAL = "dashboard"


def _renderizador(modulo: str):
    # Import tardio: só a página aberta carrega suas dependências (plotly, reportlab...).
    def _render() -> None:
        import_module(f"paginas.{modulo}").render()
    _render.__name__ = f"_page_{modulo}"
    return _render


def _titulo(modulo: str, titulo: str) -> str:
    pendentes = fila.contar()
    return f"{titulo} ({pendentes})" if modulo == "revisao_pg" and pendentes else titulo


def construir() -> dict[str, list[st.Page]]:
    """Monta as páginas desta execução e guarda o registro para os links entre páginas."""
    grupos: dict[str, list[st.Page]] = {}
    registro: dict[str, st.Page] = {}
    for grupo, modulo, titulo, icone, url in ROTAS:
        pagina = st.Page(_renderizador(modulo), title=_titulo(modulo, titulo), icon=icone,
                         url_path=url, default=url == PAGINA_INICIAL)
        grupos.setdefault(grupo, []).append(pagina)
        registro[url] = pagina
    st.session_state[CHAVE_PAGINAS] = registro
    return grupos


def pagina(url: str) -> st.Page:
    return st.session_state[CHAVE_PAGINAS][url]
