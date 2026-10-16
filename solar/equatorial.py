import os
import time
from pathlib import Path
from typing import Callable

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from solar import config
from solar.faturas.extracao import ResultadoExtracao, extrair
from solar.faturas.importacao import salvar_se_completa

PASTA_PERFIL = config.PASTA_DADOS / "perfil_equatorial"
PASTA_DOWNLOADS = config.PASTA_PDFS / "equatorial"
URL_AGENCIA = "https://agenciavirtual.equatorialenergia.com.br/Login/"
URL_SSO = "https://auth.equatorialenergia.com.br/"


def _obter_contexto(p, headless: bool = False):
    """Cria ou recupera o contexto de navegador com perfil persistente para manter a sessão."""
    PASTA_PERFIL.mkdir(parents=True, exist_ok=True)
    PASTA_DOWNLOADS.mkdir(parents=True, exist_ok=True)
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PASTA_PERFIL),
        channel="chrome",
        headless=headless,
        accept_downloads=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
        no_viewport=True,
    )


def abrir_sessao_login() -> str:
    """Abre o navegador Chrome para o usuário se identificar na Equatorial.
    A sessão (cookies e tokens) fica gravada na pasta de perfil local para automações futuras."""
    with sync_playwright() as p:
        context = _obter_contexto(p, headless=False)
        page = context.new_page()
        page.goto(URL_AGENCIA, timeout=45000)

        # Se já estiver na tela inicial, tenta clicar no botão Entrar para adiantar
        try:
            btn_entrar = page.locator("button:has-text('Entrar')").first
            if btn_entrar.is_visible(timeout=3000):
                btn_entrar.click()
        except Exception:
            pass

        # Aguarda até o usuário navegar para uma tela pós-login ou fechar
        # Monitora a URL por até 120 segundos
        inicio = time.time()
        logado = False
        while time.time() - inicio < 180:
            if not page.is_closed():
                url_atual = page.url.lower()
                # Quando sai da URL de auth e volta para a agência logada
                if "agenciavirtual" in url_atual and "login" not in url_atual and "auth" not in url_atual:
                    logado = True
                    break
            else:
                break
            time.sleep(1)

        context.close()
        return "Sessão iniciada e salva com sucesso." if logado else "Janela finalizada. Faça o login para memorizar a sessão."


def verificar_autenticado() -> bool:
    """Checa de forma rápida se a sessão atual ainda está válida."""
    if not PASTA_PERFIL.exists():
        return False
    try:
        with sync_playwright() as p:
            context = _obter_contexto(p, headless=True)
            page = context.new_page()
            page.goto(URL_AGENCIA, timeout=20000)
            page.wait_for_timeout(3000)
            url_atual = page.url.lower()
            logado = "agenciavirtual" in url_atual and "login" not in url_atual and "auth" not in url_atual
            context.close()
            return logado
    except Exception:
        return False


def baixar_faturas_equatorial(
    callback_progresso: Callable[[str], None] | None = None,
    headless: bool = False,
) -> list[Path]:
    """Navega na Agência Virtual, localiza as contas e baixa os PDFs disponíveis."""
    def _avisar(msg: str):
        if callback_progresso:
            callback_progresso(msg)

    PASTA_DOWNLOADS.mkdir(parents=True, exist_ok=True)
    arquivos_baixados: list[Path] = []

    _avisar("Iniciando navegador com perfil do usuário…")
    with sync_playwright() as p:
        context = _obter_contexto(p, headless=headless)
        page = context.new_page()

        _avisar("Acessando Agência Virtual Equatorial…")
        page.goto(URL_AGENCIA, timeout=45000)
        page.wait_for_timeout(4000)

        # Se não estiver logado, clica no login
        if "auth.equatorialenergia" in page.url or "login" in page.url.lower():
            try:
                btn_entrar = page.locator("button:has-text('Entrar')").first
                if btn_entrar.is_visible(timeout=2000):
                    btn_entrar.click()
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            if "auth.equatorialenergia" in page.url:
                _avisar("Aguardando login no navegador…")
                # Espera até 90 segundos caso o usuário precise confirmar credencial
                page.wait_for_url(lambda u: "agenciavirtual" in u and "login" not in u and "auth" not in u, timeout=90000)

        _avisar("Localizando contas e faturas…")
        # Abre menu ou área de faturas
        try:
            # Tenta clicar no menu Contas ou Segunda Via
            menu_contas = page.locator("text='Contas de luz'").first
            if menu_contas.is_visible(timeout=3000):
                menu_contas.click()
        except Exception:
            pass

        page.wait_for_timeout(4000)

        # Procura botões ou links de PDF / Baixar / 2ª via
        locators_fatura = page.locator("button:has-text('Baixar'), a:has-text('Baixar'), button:has-text('PDF'), a:has-text('PDF'), [title*='fatura'], [title*='Fatura']")
        total_encontrados = locators_fatura.count()
        _avisar(f"Encontrados {total_encontrados} elemento(s) de download.")

        for i in range(min(total_encontrados, 15)):
            try:
                el = locators_fatura.nth(i)
                if not el.is_visible():
                    continue

                with page.expect_download(timeout=10000) as download_info:
                    el.click()
                download = download_info.value
                nome_arquivo = download.suggested_filename or f"fatura_equatorial_{int(time.time())}_{i}.pdf"
                caminho_final = PASTA_DOWNLOADS / nome_arquivo
                download.save_as(str(caminho_final))
                arquivos_baixados.append(caminho_final)
                _avisar(f"Baixado: {nome_arquivo}")
            except Exception:
                continue

        context.close()

    return arquivos_baixados


def processar_faturas_baixadas(arquivos: list[Path]) -> tuple[int, list[ResultadoExtracao]]:
    """Extrai os dados dos PDFs baixados e salva no banco de dados automaticamente."""
    salvas = 0
    pendentes: list[ResultadoExtracao] = []
    for arq in arquivos:
        resultado = extrair(arq.name, arq.read_bytes())
        if salvar_se_completa(resultado):
            salvas += 1
        else:
            pendentes.append(resultado)
    return salvas, pendentes
