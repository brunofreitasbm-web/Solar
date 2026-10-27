import json
import os
import shutil
import sqlite3
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
URL_SEGUNDA_VIA = "https://agenciavirtual.equatorialenergia.com.br/SegundaVia/"
URL_SSO = "https://auth.equatorialenergia.com.br/"
LIMITE_DOWNLOADS = 20


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
    """Verifica de forma rápida se há um registro de login salvo na máquina."""
    if not ARQUIVO_SESSAO.exists():
        return False
    try:
        dados = json.loads(ARQUIVO_SESSAO.read_text(encoding="utf-8"))
        return bool(dados.get("autenticado"))
    except Exception:
        return False


def esta_autenticado_na_pagina(page) -> bool:
    """Detecta com precisão se a página do navegador está em uma sessão autenticada da Equatorial."""
    if not page or page.is_closed():
        return False
    try:
        url = page.url.lower()
        # Se ainda está no Keycloak SSO, Google OAuth, Apple ou no redirect transitório, ainda não concluiu
        if (
            "auth.equatorialenergia.com.br" in url
            or "accounts.google.com" in url
            or "appleid.apple.com" in url
            or "/ca/redirect" in url
            or url == "about:blank"
        ):
            return False

        # 1. Checagem direta de tokens no localStorage do navegador (Cognito / OutSystems)
        try:
            tem_token = page.evaluate("""() => {
                try {
                    const keys = Object.keys(localStorage);
                    const hasCognito = keys.some(k => k.includes('CognitoIdentityServiceProvider') && k.endsWith('.refreshToken'));
                    const hasSession = Boolean(localStorage.getItem('$OS_Users$CA$ClientVars$UserId')) ||
                                       Boolean(localStorage.getItem('$OS_Users$$ClientVars$$SESSION_USER_ID')) ||
                                       Boolean(localStorage.getItem('$OS_Users$Home$ClientVars$CodigoSessao'));
                    return hasCognito || hasSession;
                } catch(e) {
                    return false;
                }
            }""")
            if tem_token:
                return True
        except Exception:
            pass

        # 2. Se está no domínio da agência virtual
        if "agenciavirtual.equatorialenergia.com.br" in url or "equatorialenergia.com.br" in url:
            # Se a página tem campos de login ativos (#username ou #kc-login), ainda não logou
            if page.locator("input#username, input[name='username'], #kc-login").count() > 0:
                return False

            # Se possui elementos de sessão ativa (Olá, Sair, Segunda Via, Unidade Consumidora, Contratos)
            indicadores = page.locator("text='Olá', text='Sair', text='Minha Conta', text='Meus Contratos', text='Unidade Consumidora', text='Conta Contrato', text='Segunda via', [title*='Sair']")
            for i in range(min(indicadores.count(), 4)):
                if indicadores.nth(i).is_visible():
                    return True

            # Se já está na rota de SegundaVia ou Home sem formulário de login visível
            if "segundavia" in url or "home" in url:
                return True
    except Exception:
        pass
    return False


def obter_pagina_ativa(context):
    """Retorna a página relevante mais recente do contexto."""
    if not context or not context.pages:
        return None
    for p in reversed(context.pages):
        if not p.is_closed():
            u = p.url.lower()
            if "agenciavirtual.equatorialenergia.com.br" in u or "auth.equatorialenergia.com.br" in u:
                return p
    for p in reversed(context.pages):
        if not p.is_closed():
            return p
    return None


def esta_autenticado_no_contexto(context) -> bool:
    """Varre todas as abas abertas no contexto para detectar autenticação."""
    if not context or not context.pages:
        return False
    for p in context.pages:
        if esta_autenticado_na_pagina(p):
            return True
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


USER_AGENT_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


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

    contexto = None
    for tentativa in range(2):
        try:
            contexto = p.chromium.launch_persistent_context(
                user_data_dir=str(PASTA_PERFIL),
                channel="chrome",
                headless=headless,
                accept_downloads=True,
                user_agent=USER_AGENT_PADRAO,
                args=argumentos,
                no_viewport=True,
            )
            break
        except Exception as e:
            _limpar_processos_residuais()
            time.sleep(1)
            if tentativa == 1:
                try:
                    contexto = p.chromium.launch_persistent_context(
                        user_data_dir=str(PASTA_PERFIL),
                        headless=headless,
                        accept_downloads=True,
                        user_agent=USER_AGENT_PADRAO,
                        args=argumentos,
                        no_viewport=True,
                    )
                    break
                except Exception:
                    raise RuntimeError(
                        "O Chrome foi encerrado inesperadamente ou já existe uma janela da Equatorial em execução. "
                        "Feche as janelas abertas do Chrome e tente novamente."
                    ) from e

    if contexto:
        try:
            contexto.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception:
            pass
    return contexto




def abrir_sessao_login(callback_progresso: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """Abre o navegador Chrome para o usuário se identificar na Equatorial.
    Monitora ativamente a tela e salva a sessão assim que o login for detectado."""
    from playwright.sync_api import sync_playwright

    def _avisar(msg: str):
        if callback_progresso:
            callback_progresso(msg)

    _avisar("Iniciando navegador com perfil seguro...")
    with sync_playwright() as p:
        context = _obter_contexto(p, headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            _avisar("Acessando portal da Equatorial...")
            page.goto(URL_SEGUNDA_VIA, timeout=45000)
            page.wait_for_timeout(3000)

            # Se ainda estiver na tela inicial, clica no botão Entrar
            try:
                btn_entrar = page.locator(".btn-login, button:has-text('Entrar'), a:has-text('Entrar')").first
                if btn_entrar.is_visible(timeout=2000):
                    btn_entrar.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            _avisar("Aguardando seu login na janela aberta (via Google ou CPF/senha)...")
            inicio = time.time()
            logado = False
            while time.time() - inicio < 180:
                paginas_vivas = [pg for pg in context.pages if not pg.is_closed()]
                if not paginas_vivas:
                    break
                for pg in paginas_vivas:
                    if esta_autenticado_na_pagina(pg):
                        logado = True
                        break
                if logado:
                    _avisar("Login reconhecido com sucesso! Memorizando sessão...")
                    time.sleep(2)
                    break
                time.sleep(1)

            _salvar_status_sessao(logado)
            if logado:
                return True, "Sessão conectada e salva com sucesso!"
            paginas_vivas = [pg for pg in context.pages if not pg.is_closed()]
            if not paginas_vivas:
                return False, "Janela finalizada antes da conclusão do login."
            return False, "Tempo limite para login esgotado (180s)."
        finally:
            try:
                context.close()
            except Exception:
                pass
            _limpar_processos_residuais()


def _tratar_bloqueio_antirobo(page, headless: bool = False, callback_progresso: Callable[[str], None] | None = None) -> None:
    """Detecta e aguarda resolução do bloqueio anti-robô (Imperva/Incapsula)."""
    try:
        html = page.content()
    except Exception:
        return

    if "_Incapsula_Resource" in html and len(html) < 5000:
        # Se bloqueou em rota interna, recarrega a raiz oficial para obter cookies de permissão
        try:
            if "segundavia" in page.url.lower():
                page.goto(URL_AGENCIA, timeout=30000)
                page.wait_for_timeout(3000)
                if "_Incapsula_Resource" not in page.content():
                    return
        except Exception:
            pass

        if headless:
            raise RuntimeError(
                "O site da Equatorial bloqueou o navegador invisível (firewall anti-robô). "
                "Execute com a opção 'Abrir janela visível do navegador' marcada para resolver."
            )

        if callback_progresso:
            callback_progresso("Verificação de segurança da Equatorial em andamento. Aguardando...")

        inicio = time.time()
        while time.time() - inicio < 45:
            if page.is_closed():
                raise RuntimeError("A janela do navegador foi fechada durante a verificação de segurança.")
            page.wait_for_timeout(2000)
            try:
                html_atual = page.content()
                if "_Incapsula_Resource" not in html_atual or len(html_atual) >= 5000:
                    return
            except Exception:
                pass

        # Tentativa final pela URL de entrada da agência
        try:
            page.goto(URL_AGENCIA, timeout=30000)
            page.wait_for_timeout(3000)
            if "_Incapsula_Resource" not in page.content():
                return
        except Exception:
            pass
        raise RuntimeError("Tempo limite esgotado para verificação de segurança anti-robô da Equatorial (45s).")


def verificar_autenticado() -> bool:
    """Checa se a sessão salva ainda é válida no portal da Equatorial."""
    return tem_sessao_salva()


def baixar_faturas_equatorial(
    callback_progresso: Callable[[str], None] | None = None,
    headless: bool = False,
) -> list[Path]:
    """Fluxo unificado: se precisar de login, aguarda na mesma janela e já baixa as faturas."""
    def _avisar(msg: str):
        if callback_progresso:
            callback_progresso(msg)

    PASTA_DOWNLOADS.mkdir(parents=True, exist_ok=True)
    arquivos_baixados: list[Path] = []

    _avisar("Iniciando navegador...")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _obter_contexto(p, headless=headless)
        try:
            page = context.pages[0] if context.pages else context.new_page()

            _avisar("Acessando portal da Equatorial...")
            page.goto(URL_AGENCIA, timeout=45000)
            page.wait_for_timeout(3000)
            _tratar_bloqueio_antirobo(page, headless=headless, callback_progresso=_avisar)

            # Verifica se precisa de login varrendo as abas
            if not esta_autenticado_no_contexto(context):
                if headless:
                    raise RuntimeError(
                        "A sessão da Equatorial expirou ou requer login. "
                        "Marque a opção 'Abrir janela visível do navegador' para se autenticar."
                    )

                _avisar("Por favor, conclua seu login na janela aberta. O download começará automaticamente em seguida...")
                inicio_login = time.time()
                logado = False
                while time.time() - inicio_login < 180:
                    paginas_vivas = [pg for pg in context.pages if not pg.is_closed()]
                    if not paginas_vivas:
                        break
                    for pg in paginas_vivas:
                        if esta_autenticado_na_pagina(pg):
                            logado = True
                            page = pg
                            _salvar_status_sessao(True)
                            _avisar("Login confirmado! Prosseguindo para o download das contas...")
                            time.sleep(2)
                            break
                    if logado:
                        break
                    time.sleep(1)

                if not logado:
                    paginas_vivas = [pg for pg in context.pages if not pg.is_closed()]
                    if not paginas_vivas:
                        raise RuntimeError("A janela do navegador foi fechada antes da confirmação do login na Equatorial.")
                    raise RuntimeError("Tempo limite para login na Equatorial esgotado (180s).")

            # Agora que está autenticado e com cookies de permissão, acessa Segunda Via
            page = obter_pagina_ativa(context) or page
            _avisar("Acessando tela de 2ª via e faturas...")
            page.goto(URL_SEGUNDA_VIA, timeout=45000)
            page.wait_for_timeout(3000)
            _tratar_bloqueio_antirobo(page, headless=headless, callback_progresso=_avisar)

            # Garante que está na tela de Segunda Via na página ativa
            page = obter_pagina_ativa(context) or page
            if "segundavia" not in page.url.lower():
                _avisar("Carregando tela de 2ª via e faturas...")
                page.goto(URL_SEGUNDA_VIA, timeout=45000)
                page.wait_for_timeout(4000)


            # Se houver lista de unidades consumidoras / contratos, avisa ou seleciona
            cards_contrato = page.locator(".card-contrato, [data-testid*='contrato'], button:has-text('Acessar'), button:has-text('Selecionar')")
            if cards_contrato.count() > 0 and cards_contrato.first.is_visible():
                _avisar("Acessando unidade consumidora...")
                try:
                    cards_contrato.first.click(timeout=3000)
                    page.wait_for_timeout(3000)
                except Exception:
                    pass

            _avisar("Procurando faturas disponíveis para download...")
            locators_fatura = page.locator(
                "button:has-text('Baixar'), a:has-text('Baixar'), "
                "button:has-text('PDF'), a:has-text('PDF'), "
                "button:has-text('2ª Via'), a:has-text('2ª Via'), "
                "button:has-text('Visualizar'), a:has-text('Visualizar'), "
                "[title*='fatura'], [title*='Fatura'], "
                "[aria-label*='Baixar'], [aria-label*='fatura'], [aria-label*='PDF'], "
                ".btn-download, .download-fatura"
            )
            total_encontrados = locators_fatura.count()
            _avisar(f"Localizados {total_encontrados} elemento(s) de download na página.")

            falhas = 0
            for i in range(min(total_encontrados, LIMITE_DOWNLOADS)):
                try:
                    el = locators_fatura.nth(i)
                    if not el.is_visible():
                        continue

                    download_concluido = False
                    # 1. Tentativa de download direto
                    try:
                        with page.expect_download(timeout=6000) as download_info:
                            el.click(timeout=3000)
                        download = download_info.value
                        nome_arquivo = download.suggested_filename or f"fatura_equatorial_{int(time.time())}_{i}.pdf"
                        caminho_final = PASTA_DOWNLOADS / nome_arquivo
                        download.save_as(str(caminho_final))
                        arquivos_baixados.append(caminho_final)
                        _avisar(f"Baixado: {nome_arquivo}")
                        download_concluido = True
                    except Exception:
                        pass

                    # 2. Se abriu modal com botão de Baixar PDF
                    if not download_concluido:
                        btn_modal = page.locator("button:has-text('Baixar PDF'), a:has-text('Baixar PDF'), button:has-text('Download'), a:has-text('Download')").first
                        if btn_modal.is_visible(timeout=2000):
                            try:
                                with page.expect_download(timeout=8000) as download_info:
                                    btn_modal.click(timeout=3000)
                                download = download_info.value
                                nome_arquivo = download.suggested_filename or f"fatura_equatorial_{int(time.time())}_{i}.pdf"
                                caminho_final = PASTA_DOWNLOADS / nome_arquivo
                                download.save_as(str(caminho_final))
                                arquivos_baixados.append(caminho_final)
                                _avisar(f"Baixado: {nome_arquivo}")
                                download_concluido = True
                            except Exception:
                                pass
                            try:
                                page.locator("button:has-text('Fechar'), .close, [aria-label='Close']").first.click(timeout=1000)
                            except Exception:
                                pass

                    if not download_concluido:
                        falhas += 1
                    else:
                        # Copia para o Google Drive local se configurado
                        try:
                            config.PASTA_GOOGLE_DRIVE.mkdir(parents=True, exist_ok=True)
                            caminho_drive = config.PASTA_GOOGLE_DRIVE / nome_arquivo
                            shutil.copy2(caminho_final, caminho_drive)
                            _avisar(f"Sincronizado com Google Drive: {nome_arquivo}")
                        except Exception as e_drive:
                            _avisar(f"Aviso Google Drive: {e_drive}")
                except Exception:
                    falhas += 1

            if not arquivos_baixados and total_encontrados == 0:
                _avisar("Verificando histórico de faturas...")
                page.wait_for_timeout(2000)

            if falhas and arquivos_baixados:
                _avisar(f"{falhas} elemento(s) não geraram download direto.")
        finally:
            try:
                context.close()
            except Exception:
                pass
            _limpar_processos_residuais()

    return arquivos_baixados


def obter_arquivos_drive() -> tuple[list[Path], list[Path]]:
    """Compara as faturas na pasta do Google Drive com as já cadastradas no banco de dados.
    Retorna (todas_as_faturas_drive, faturas_novas_para_importar)."""
    pasta = config.PASTA_GOOGLE_DRIVE
    if not pasta.exists():
        return [], []

    todos_pdfs = sorted(pasta.rglob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not todos_pdfs:
        return [], []

    # Busca nomes de arquivos já importados no banco
    arquivos_no_db: set[str] = set()
    try:
        with sqlite3.connect(config.CAMINHO_DB) as con:
            for row in con.execute("SELECT arquivo FROM faturas WHERE arquivo != ''").fetchall():
                if row[0]:
                    arquivos_no_db.add(Path(row[0]).name)
    except Exception:
        pass

    novos_pdfs = [p for p in todos_pdfs if p.name not in arquivos_no_db]
    return todos_pdfs, novos_pdfs


def sincronizar_com_google_drive(arquivos: list[Path] | None = None) -> int:
    """Copia faturas baixadas para a pasta do Google Drive."""
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
    """Extrai os dados dos PDFs e salva no banco de dados automaticamente."""
    salvas = 0
    pendentes: list[ResultadoExtracao] = []
    for arq in arquivos:
        resultado = extrair(arq.name, arq.read_bytes())
        if salvar_se_completa(resultado):
            salvas += 1
        else:
            pendentes.append(resultado)
    return salvas, pendentes


def baixar_e_importar(callback_progresso: Callable[[str], None] | None = None) -> tuple[int, list[ResultadoExtracao]]:
    """Rotina completa: baixa, lê, salva e avisa."""
    arquivos = baixar_faturas_equatorial(callback_progresso, headless=False)
    return processar_faturas_baixadas(arquivos)


if __name__ == "__main__":
    salvas_, pendentes_ = baixar_e_importar(print)
    print(f"{salvas_} fatura(s) salva(s); {len(pendentes_)} para revisão no app.")
