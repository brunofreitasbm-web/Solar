import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from solar import config
from solar.faturas.extracao import ResultadoExtracao, extrair
from solar.faturas.importacao import salvar_se_completa

PASTA_PERFIL = config.PASTA_DADOS / "perfil_equatorial"
PASTA_DOWNLOADS = config.PASTA_PDFS / "equatorial"
ARQUIVO_SESSAO = PASTA_PERFIL / "sessao.json"
URL_AGENCIA = "https://agenciavirtual.equatorialenergia.com.br/Login/"
URL_SSO = "https://auth.equatorialenergia.com.br/"


def _salvar_status_sessao(autenticado: bool) -> None:
    """Registra em disco o estado do último login realizado com sucesso."""
    try:
        PASTA_PERFIL.mkdir(parents=True, exist_ok=True)
        ARQUIVO_SESSAO.write_text(
            json.dumps({"autenticado": autenticado, "atualizado_em": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def tem_sessao_salva() -> bool:
    """Verifica de forma rápida e segura se há um registro de login salvo na máquina."""
    if not ARQUIVO_SESSAO.exists():
        return False
    try:
        dados = json.loads(ARQUIVO_SESSAO.read_text(encoding="utf-8"))
        return bool(dados.get("autenticado"))
    except Exception:
        return False


def _limpar_processos_residuais():
    """Encerra processos órfãos do Chrome/Chromium/Edge que possam estar retendo a pasta de perfil local."""
    if os.name == "nt":
        try:
            ps_code = (
                "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe' or Name = 'msedge.exe'\" | "
                "Where-Object { $_.CommandLine -like '*perfil_equatorial*' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_code],
                capture_output=True,
                timeout=5,
                check=False,
            )
            time.sleep(0.5)
        except Exception:
            pass

    # Remove arquivos de trava residuais se o processo foi encerrado
    for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
        p_lock = PASTA_PERFIL / lock
        if p_lock.exists():
            try:
                p_lock.unlink(missing_ok=True)
            except Exception:
                pass


def _obter_contexto(p, headless: bool = False):
    """Cria ou recupera o contexto de navegador com perfil persistente para manter a sessão."""
    PASTA_PERFIL.mkdir(parents=True, exist_ok=True)
    PASTA_DOWNLOADS.mkdir(parents=True, exist_ok=True)
    _limpar_processos_residuais()

    argumentos = [
        "--disable-blink-features=AutomationControlled",
        "--start-maximized",
        "--disable-background-mode",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
    ]

    for tentativa in range(2):
        try:
            return p.chromium.launch_persistent_context(
                user_data_dir=str(PASTA_PERFIL),
                channel="chrome",
                headless=headless,
                accept_downloads=True,
                args=argumentos,
                no_viewport=True,
            )
        except Exception as e:
            _limpar_processos_residuais()
            time.sleep(1)
            if tentativa == 1:
                # Se persistir o erro no Chrome do sistema, tenta o Chromium embutido do Playwright como fallback
                try:
                    return p.chromium.launch_persistent_context(
                        user_data_dir=str(PASTA_PERFIL),
                        headless=headless,
                        accept_downloads=True,
                        args=argumentos,
                        no_viewport=True,
                    )
                except Exception:
                    raise RuntimeError(
                        "O Chrome foi encerrado inesperadamente ou já existe uma janela da Equatorial em execução. "
                        "Feche as janelas abertas do Chrome ou processos em segundo plano e tente novamente."
                    ) from e


def abrir_sessao_login() -> str:
    """Abre o navegador Chrome para o usuário se identificar na Equatorial.
    A sessão (cookies e tokens) fica gravada na pasta de perfil local para automações futuras."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _obter_contexto(p, headless=False)
        try:
            page = context.new_page()
            page.goto(URL_AGENCIA, timeout=45000)

            # Se já estiver na tela inicial, tenta clicar no botão Entrar para adiantar
            try:
                btn_entrar = page.locator("button:has-text('Entrar'), a:has-text('Entrar'), [role='button']:has-text('Entrar'), text='Entrar'").first
                if btn_entrar.is_visible(timeout=3000):
                    btn_entrar.click()
            except Exception:
                pass

            # Aguarda até o usuário navegar para uma tela pós-login ou fechar
            # Monitora a URL por até 180 segundos
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

            _salvar_status_sessao(logado)
            return "Sessão iniciada e salva com sucesso!" if logado else "Janela finalizada. Faça o login para memorizar a sessão."
        finally:
            try:
                context.close()
            except Exception:
                pass
            _limpar_processos_residuais()


def verificar_autenticado() -> bool:
    """Checa de forma rápida se a sessão atual ainda está válida."""
    if not tem_sessao_salva():
        return False
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            context = _obter_contexto(p, headless=True)
            try:
                page = context.new_page()
                page.goto(URL_AGENCIA, timeout=20000)
                page.wait_for_timeout(3000)
                url_atual = page.url.lower()
                valido = "agenciavirtual" in url_atual and "login" not in url_atual and "auth" not in url_atual
                _salvar_status_sessao(valido)
                return valido
            finally:
                try:
                    context.close()
                except Exception:
                    pass
                _limpar_processos_residuais()
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
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _obter_contexto(p, headless=headless)
        try:
            page = context.new_page()

            _avisar("Acessando Agência Virtual Equatorial…")
            page.goto(URL_AGENCIA, timeout=45000)
            page.wait_for_timeout(4000)

            # Se não estiver logado, clica no login
            if "auth.equatorialenergia" in page.url or "login" in page.url.lower():
                try:
                    btn_entrar = page.locator("button:has-text('Entrar'), a:has-text('Entrar'), [role='button']:has-text('Entrar'), text='Entrar'").first
                    if btn_entrar.is_visible(timeout=2000):
                        btn_entrar.click()
                        page.wait_for_timeout(3000)
                except Exception:
                    pass

                # Se ainda estiver na tela de login ou auth
                if "auth.equatorialenergia" in page.url or "login" in page.url.lower():
                    if headless:
                        raise RuntimeError(
                            "A sessão da Equatorial expirou ou ainda não foi configurada neste computador. "
                            "Marque a opção 'Abrir janela visível do navegador' ou clique em 'Conectar na Equatorial' para se autenticar."
                        )

                    _avisar("Aguardando login no navegador… Conclua a identificação na janela aberta.")
                    inicio_login = time.time()
                    logado = False
                    while time.time() - inicio_login < 90:
                        if page.is_closed():
                            break
                        try:
                            url_atual = page.url.lower()
                            if "agenciavirtual" in url_atual and "login" not in url_atual and "auth" not in url_atual:
                                logado = True
                                _salvar_status_sessao(True)
                                break
                        except Exception:
                            pass
                        time.sleep(1)

                    if not logado:
                        if page.is_closed():
                            raise RuntimeError("A janela do navegador foi fechada antes da confirmação do login na Equatorial.")
                        raise RuntimeError(
                            "Tempo limite para login na Equatorial esgotado (90s). "
                            "Conclua a digitação das suas credenciais na janela aberta e tente novamente."
                        )

            _avisar("Localizando contas e faturas…")
            # Abre menu ou área de faturas
            try:
                menu_contas = page.locator("text='Contas e consumo', text='Contas de luz', text='Segunda via', text='2ª Via', text='Faturas'").first
                if menu_contas.is_visible(timeout=3000):
                    menu_contas.click()
            except Exception:
                pass

            page.wait_for_timeout(4000)

            # Procura botões ou links de PDF / Baixar / 2ª via
            locators_fatura = page.locator("button:has-text('Baixar'), a:has-text('Baixar'), button:has-text('PDF'), a:has-text('PDF'), [title*='fatura'], [title*='Fatura'], [aria-label*='Baixar'], [aria-label*='fatura']")
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

                    # Coloca automaticamente no Google Drive
                    try:
                        config.PASTA_GOOGLE_DRIVE.mkdir(parents=True, exist_ok=True)
                        caminho_drive = config.PASTA_GOOGLE_DRIVE / nome_arquivo
                        shutil.copy2(caminho_final, caminho_drive)
                        _avisar(f"Copiado para o Google Drive: {nome_arquivo}")
                    except Exception as e_drive:
                        _avisar(f"Aviso Google Drive: {e_drive}")
                except Exception:
                    continue
        finally:
            try:
                context.close()
            except Exception:
                pass
            _limpar_processos_residuais()

    return arquivos_baixados


def sincronizar_com_google_drive(arquivos: list[Path] | None = None) -> int:
    """Copia as faturas especificadas (ou todas as da pasta de downloads) para o Google Drive."""
    config.PASTA_GOOGLE_DRIVE.mkdir(parents=True, exist_ok=True)
    lista = arquivos or list(PASTA_DOWNLOADS.glob("*.pdf"))
    copiados = 0
    for arq in lista:
        try:
            destino = config.PASTA_GOOGLE_DRIVE / arq.name
            shutil.copy2(arq, destino)
            copiados += 1
        except Exception:
            continue
    return copiados


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
