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
    """Detecta com precisão se o navegador está em uma sessão autenticada da Equatorial."""
    try:
        url = page.url.lower()
        # Se ainda está no Keycloak SSO, Google OAuth ou no redirect transitório, não está pronto
        if "auth.equatorialenergia.com.br" in url or "accounts.google.com" in url or "/ca/redirect" in url:
            return False

        # Se voltou para a agência virtual
        if "agenciavirtual.equatorialenergia.com.br" in url:
            # Checa se o botão de login ('Entrar') ainda está visível na tela
            btn_login = page.locator(".btn-login, button:has-text('Entrar')")
            if btn_login.count() > 0:
                for i in range(min(btn_login.count(), 2)):
                    if btn_login.nth(i).is_visible():
                        return False
            # Se não há botão de login visível, ou se já está em SegundaVia ou Home logada
            return True
    except Exception:
        pass
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
                        "Feche as janelas abertas do Chrome e tente novamente."
                    ) from e


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
            page = context.new_page()
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
                if page.is_closed():
                    break
                if esta_autenticado_na_pagina(page):
                    logado = True
                    _avisar("Login reconhecido com sucesso! Memorizando sessão...")
                    page.wait_for_timeout(3000)
                    break
                time.sleep(1)

            _salvar_status_sessao(logado)
            if logado:
                return True, "Sessão conectada e salva com sucesso!"
            if page.is_closed():
                return False, "Janela finalizada antes da conclusão do login."
            return False, "Tempo limite para login esgotado (180s)."
        finally:
            try:
                context.close()
            except Exception:
                pass
            _limpar_processos_residuais()


def _recusar_se_bloqueado(page) -> None:
    """Detecta bloqueio por firewall anti-robô (Imperva/Incapsula)."""
    html = page.content()
    if "_Incapsula_Resource" in html and len(html) < 5000:
        raise RuntimeError(
            "O site da Equatorial bloqueou o navegador invisível (firewall anti-robô). "
            "Execute com a janela visível para que o login e downloads prossigam."
        )


def verificar_autenticado() -> bool:
    """Checa se a sessão salva ainda é válida no portal da Equatorial."""
    if not tem_sessao_salva():
        return False
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            context = _obter_contexto(p, headless=True)
            try:
                page = context.new_page()
                page.goto(URL_SEGUNDA_VIA, timeout=20000)
                page.wait_for_timeout(3000)
                valido = esta_autenticado_na_pagina(page)
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
            page = context.new_page()

            _avisar("Acessando área de faturas da Equatorial...")
            page.goto(URL_SEGUNDA_VIA, timeout=45000)
            page.wait_for_timeout(4000)
            _recusar_se_bloqueado(page)

            # Verifica se precisa de login
            if not esta_autenticado_na_pagina(page):
                if headless:
                    raise RuntimeError(
                        "A sessão da Equatorial expirou ou requer login. "
                        "Marque a opção 'Abrir janela visível do navegador' para se autenticar."
                    )

                _avisar("Por favor, conclua seu login na janela aberta. O download começará automaticamente em seguida...")
                inicio_login = time.time()
                logado = False
                while time.time() - inicio_login < 180:
                    if page.is_closed():
                        break
                    if esta_autenticado_na_pagina(page):
                        logado = True
                        _salvar_status_sessao(True)
                        _avisar("Login confirmado! Prosseguindo para o download das contas...")
                        page.wait_for_timeout(3000)
                        break
                    time.sleep(1)

                if not logado:
                    if page.is_closed():
                        raise RuntimeError("A janela do navegador foi fechada antes da confirmação do login na Equatorial.")
                    raise RuntimeError("Tempo limite para login na Equatorial esgotado (180s).")

            # Garante que está na tela de Segunda Via
            if "segundavia" not in page.url.lower():
                _avisar("Carregando tela de 2ª via e faturas...")
                page.goto(URL_SEGUNDA_VIA, timeout=45000)
                page.wait_for_timeout(5000)

            _avisar("Procurando faturas disponíveis para download...")
            # Procura botões ou links de PDF / Baixar / 2ª via
            locators_fatura = page.locator(
                "button:has-text('Baixar'), a:has-text('Baixar'), "
                "button:has-text('PDF'), a:has-text('PDF'), "
                "button:has-text('2ª Via'), a:has-text('2ª Via'), "
                "[title*='fatura'], [title*='Fatura'], "
                "[aria-label*='Baixar'], [aria-label*='fatura']"
            )
            total_encontrados = locators_fatura.count()
            _avisar(f"Localizados {total_encontrados} elemento(s) de download na página.")

            falhas = 0
            for i in range(min(total_encontrados, LIMITE_DOWNLOADS)):
                try:
                    el = locators_fatura.nth(i)
                    if not el.is_visible():
                        continue

                    with page.expect_download(timeout=12000) as download_info:
                        el.click()
                    download = download_info.value
                    nome_arquivo = download.suggested_filename or f"fatura_equatorial_{int(time.time())}_{i}.pdf"
                    caminho_final = PASTA_DOWNLOADS / nome_arquivo
                    download.save_as(str(caminho_final))
                    arquivos_baixados.append(caminho_final)
                    _avisar(f"Baixado: {nome_arquivo}")

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
                # Tenta localizar links no menu alternativo
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
