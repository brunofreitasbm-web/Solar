import re
from typing import Iterator

URL_SEGUNDA_VIA = "https://agenciavirtual.equatorialenergia.com.br/SegundaVia/"
SELETOR_UNIDADE = ".item-imovel"
SELETOR_CONTA = ".conta-segundavia"
SELETOR_BAIXAR = "button.btn-download-segundavia"
TEXTO_MAIS_IMOVEIS = "Mostrar mais imóveis"
ESPERA_LISTA_MS = 25000
ESPERA_PDF_MS = 20000

_RE_VALOR = re.compile(r"R\$\s*([\d.]+,\d{2})")
_RE_MES = re.compile(r"([A-Za-zçÇãÃ]+)\s+(\d{4})")


def _abrir_lista_de_unidades(page) -> int:
    page.goto(URL_SEGUNDA_VIA, timeout=45000)
    page.wait_for_selector(SELETOR_UNIDADE, timeout=ESPERA_LISTA_MS)
    while True:
        mais = page.get_by_text(TEXTO_MAIS_IMOVEIS, exact=True)
        if mais.count() == 0 or not mais.first.is_visible():
            break
        antes = page.locator(SELETOR_UNIDADE).count()
        mais.first.click()
        page.wait_for_timeout(1500)
        if page.locator(SELETOR_UNIDADE).count() == antes:
            break
    return page.locator(SELETOR_UNIDADE).count()


def contar_unidades(page) -> int:
    return _abrir_lista_de_unidades(page)


def abrir_unidade(page, indice: int) -> tuple[str, bool]:
    """Entra na unidade e espera as contas carregarem. Retorna (identificação da unidade, tem contas)."""
    _abrir_lista_de_unidades(page)
    cartao = page.locator(SELETOR_UNIDADE).nth(indice)
    texto = " ".join(cartao.inner_text().split())
    cartao.click()
    try:
        page.wait_for_selector(SELETOR_CONTA, timeout=ESPERA_LISTA_MS)
    except Exception:
        return texto, False
    return texto, True


def identificar_conta(unidade: str, texto_conta: str) -> str:
    """Chave estável da conta (unidade + mês + valor), sem o status que muda de Vencida para Paga."""
    valor = _RE_VALOR.search(texto_conta)
    mes = _RE_MES.search(texto_conta)
    return "|".join([unidade, mes.group(0) if mes else "", valor.group(1) if valor else ""])


def contas_da_unidade(page) -> Iterator[tuple[str, object]]:
    """Gera (texto da conta, botão de baixar) para cada conta listada."""
    contas = page.locator(SELETOR_CONTA)
    for i in range(contas.count()):
        conta = contas.nth(i)
        botao = conta.locator(SELETOR_BAIXAR)
        if botao.count():
            yield " ".join(conta.inner_text().split()), botao.first
