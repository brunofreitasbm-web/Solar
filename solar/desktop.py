"""Abre o Solar ROI como um aplicativo de janela única.

O Streamlit continua sendo o motor, mas nada disso aparece para quem usa: o lançador prepara
as pastas de dados, mostra uma tela de abertura imediata, sobe o servidor apenas em 127.0.0.1 e
troca para o app quando ele responde. Fechar a janela desliga o servidor e clicar de novo com o
app aberto só traz a janela de volta.
"""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template

log = logging.getLogger("solar.desktop")

# Sem proxy: em rede corporativa um proxy configurado faria o health check de 127.0.0.1 falhar.
_SEM_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))

PORTA_PREFERIDA = 8501
TENTATIVAS_DE_PORTA = 40
ESPERA_SERVIDOR_S = 120
ESPERA_OUTRA_INSTANCIA_S = 45
VIDA_MINIMA_JANELA_S = 5
TAMANHO_JANELA = (1360, 940)
ARQUIVO_LOG = "solar_app.log"
ARQUIVO_PORTA = "solar_porta.txt"
ARQUIVO_TRAVA = "solar.lock"
PASTA_NAVEGADOR = "navegador"


def _dirs() -> tuple[Path, Path]:
    """(pasta do executável — onde ficam os dados, pasta dos arquivos empacotados)."""
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
        return app_dir, Path(getattr(sys, "_MEIPASS", app_dir))
    raiz = Path(__file__).resolve().parent.parent
    return Path(os.environ.get("SOLAR_RAIZ_DADOS") or raiz), raiz


def preparar_ambiente() -> tuple[Path, Path]:
    """Cria as pastas de dados, copia banco e .env na primeira execução e fixa o tema."""
    app_dir, bundle_dir = _dirs()
    dados = app_dir / "data"
    for pasta in (dados, dados / "pdfs", dados / "rateio", app_dir / "backups"):
        pasta.mkdir(parents=True, exist_ok=True)
    _copiar_se_faltar(bundle_dir / "data" / "solar.db", dados / "solar.db")
    _copiar_se_faltar(bundle_dir / ".env", app_dir / ".env")
    # O Streamlit lê o tema de .streamlit/config.toml a partir da pasta atual.
    os.chdir(bundle_dir)
    return app_dir, bundle_dir


def _copiar_se_faltar(origem: Path, destino: Path) -> None:
    if origem.is_file() and not destino.exists():
        shutil.copy2(origem, destino)


def configurar_log(caminho: Path) -> None:
    """Sem janela de console, o log em arquivo é o único lugar onde os erros aparecem."""
    _rotacionar_log(caminho)
    arquivo = open(caminho, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = arquivo
    manipulador = logging.FileHandler(caminho, encoding="utf-8")
    manipulador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(manipulador)


def _rotacionar_log(caminho: Path) -> None:
    if not caminho.exists() or caminho.stat().st_size < 1_000_000:
        return
    anterior = caminho.with_name("solar_app.anterior.log")
    anterior.unlink(missing_ok=True)
    caminho.replace(anterior)


def url_app(porta: int) -> str:
    return f"http://127.0.0.1:{porta}"


def porta_disponivel(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", porta))
        except OSError:
            return False
    return True


def servidor_respondendo(porta: int, espera: float = 1.5) -> bool:
    try:
        with _SEM_PROXY.open(f"{url_app(porta)}/_stcore/health", timeout=espera) as resposta:
            return resposta.status == 200
    except OSError:
        return False


def aguardar_servidor(porta: int, segundos: float = ESPERA_SERVIDOR_S) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if servidor_respondendo(porta):
            return True
        time.sleep(0.4)
    return False


def ler_porta_salva(dados: Path) -> int | None:
    try:
        return int((dados / ARQUIVO_PORTA).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def salvar_porta(dados: Path, porta: int) -> None:
    try:
        (dados / ARQUIVO_PORTA).write_text(str(porta), encoding="utf-8")
    except OSError:
        log.warning("Não consegui guardar a porta atual", exc_info=True)


def app_aberto(dados: Path) -> int | None:
    """Porta de um servidor do Solar ROI que já está no ar (só a porta que o app registrou)."""
    porta = ler_porta_salva(dados)
    return porta if porta and servidor_respondendo(porta) else None


def escolher_porta(dados: Path, preferida: int = PORTA_PREFERIDA) -> int:
    """Reaproveita a porta que já era do app; senão pega a primeira livre da faixa."""
    salva = ler_porta_salva(dados)
    if salva and porta_disponivel(salva):
        return salva
    for porta in range(preferida, preferida + TENTATIVAS_DE_PORTA):
        if porta_disponivel(porta):
            return porta
    raise RuntimeError(f"Nenhuma porta livre entre {preferida} e {preferida + TENTATIVAS_DE_PORTA}.")


def travar_instancia(dados: Path):
    """Impede dois servidores quando o usuário clica duas vezes; o lock cai com o processo."""
    try:
        import msvcrt
    except ImportError:  # fora do Windows (testes) não há lock de arquivo
        return True
    arquivo = open(dados / ARQUIVO_TRAVA, "a+")
    try:
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        arquivo.close()
        return None
    return arquivo

def navegador_chromium() -> Path | None:
    """Edge ou Chrome instalado: abre o app em janela própria, sem abas nem barra de endereço."""
    pastas = (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA"))
    instalacoes = ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe")
    for base in pastas:
        if not base:
            continue
        for instalacao in instalacoes:
            caminho = Path(base) / instalacao
            if caminho.is_file():
                return caminho
    return None


def abrir_janela(url: str, perfil: Path) -> subprocess.Popen | None:
    navegador = navegador_chromium()
    if navegador is None:
        return None
    perfil.mkdir(parents=True, exist_ok=True)
    largura, altura = TAMANHO_JANELA
    return subprocess.Popen(
        [
            str(navegador),
            f"--app={url}",
            f"--user-data-dir={perfil}",
            f"--window-size={largura},{altura}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def abrir_ou_navegar(porta: int, perfil: Path) -> None:
    """Abre a janela do app; se não houver Edge/Chrome, cai no navegador padrão."""
    if abrir_janela(url_app(porta), perfil) is None:
        webbrowser.open(url_app(porta))


def acompanhar_janela(processo: subprocess.Popen, url: str) -> None:
    """Quando a janela fecha, o servidor fecha junto — o app não fica rodando escondido."""
    def _monitorar() -> None:
        inicio = time.monotonic()
        processo.wait()
        if time.monotonic() - inicio < VIDA_MINIMA_JANELA_S:
            log.warning("A janela fechou logo depois de abrir; abrindo no navegador padrão.")
            webbrowser.open(url)
            return
        log.info("Janela fechada: encerrando o servidor.")
        os._exit(0)

    threading.Thread(target=_monitorar, daemon=True).start()


class _HandlerAbertura(BaseHTTPRequestHandler):
    """Serve a tela de abertura até o app responder."""

    pagina = b""
    pronto = threading.Event()

    def do_GET(self) -> None:  # nome exigido por BaseHTTPRequestHandler
        if self.path.startswith("/pronto"):
            corpo, tipo = (b"sim" if self.pronto.is_set() else b"nao"), "text/plain; charset=utf-8"
        elif self.path in ("/", "/index.html"):
            corpo, tipo = self.pagina, "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args) -> None:
        """Silencia o log padrão do http.server: aqui nada disso interessa."""


def servir_abertura(porta_app: int, bundle_dir: Path, evento: threading.Event) -> int:
    """Página local que aparece na hora e troca pelo app assim que ele responde."""
    class Handler(_HandlerAbertura):
        pagina = _html_abertura(bundle_dir, porta_app).encode("utf-8")
        pronto = evento

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor.server_address[1]


def _html_abertura(bundle_dir: Path, porta: int) -> str:
    return _HTML_ABERTURA.safe_substitute(logo=_logo_inline(bundle_dir), url=url_app(porta))


def _logo_inline(bundle_dir: Path) -> str:
    try:
        svg = (bundle_dir / "assets" / "logo.svg").read_text(encoding="utf-8")
    except OSError:
        return '<span style="font-size:24px;font-weight:700">Solar ROI</span>'
    return "\n".join(linha for linha in svg.splitlines() if not linha.strip().startswith("<?xml"))


def avisar_erro(texto: str, titulo: str = "Solar ROI") -> None:
    """Caixa de diálogo do Windows: sem console, um erro silencioso pareceria 'não abriu'."""
    try:
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10)
    except (AttributeError, OSError):
        print(f"{titulo}: {texto}", flush=True)


def rodar_streamlit(app_script: Path, porta: int) -> None:
    import streamlit.web.cli as stcli

    endereco = "0.0.0.0" if os.environ.get("SOLAR_REDE") else "127.0.0.1"
    sys.argv = [
        "streamlit",
        "run",
        str(app_script),
        f"--server.port={porta}",
        f"--server.address={endereco}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]
    log.info("Subindo o Streamlit em %s (endereço %s).", url_app(porta), endereco)
    stcli.main()


def _marcar_pronto(porta: int, evento: threading.Event) -> None:
    if aguardar_servidor(porta):
        evento.set()
        log.info("Servidor pronto em %s.", url_app(porta))
    else:
        log.error("O servidor não respondeu em %s segundos.", ESPERA_SERVIDOR_S)


def _esperar_outra_instancia(dados: Path) -> int | None:
    limite = time.monotonic() + ESPERA_OUTRA_INSTANCIA_S
    while time.monotonic() < limite:
        porta = app_aberto(dados)
        if porta:
            return porta
        time.sleep(0.5)
    return None


def _mostrar_abertura(porta: int, bundle_dir: Path, perfil: Path, pronto: threading.Event) -> subprocess.Popen | None:
    porta_abertura = servir_abertura(porta, bundle_dir, pronto)
    janela = abrir_janela(url_app(porta_abertura), perfil)
    if janela is None:
        webbrowser.open(url_app(porta_abertura))
    return janela


def _iniciar() -> int:
    app_dir, bundle_dir = preparar_ambiente()
    dados = app_dir / "data"
    perfil = dados / PASTA_NAVEGADOR
    configurar_log(dados / ARQUIVO_LOG)

    aberto = app_aberto(dados)
    if aberto:
        log.info("O app já estava aberto na porta %s; abrindo a janela.", aberto)
        abrir_ou_navegar(aberto, perfil)
        return 0

    trava = travar_instancia(dados)  # fica aberta até o processo terminar
    if trava is None:
        log.info("Outra instância está subindo; aguardando ela responder.")
        porta = _esperar_outra_instancia(dados)
        if porta is None:
            avisar_erro("O Solar ROI está abrindo. Aguarde alguns segundos e tente de novo.")
            return 0
        abrir_ou_navegar(porta, perfil)
        return 0

    app_script = bundle_dir / "app.py"
    if not app_script.is_file():
        raise RuntimeError(f"Arquivo do app não encontrado em {app_script}.")

    porta = escolher_porta(dados)
    salvar_porta(dados, porta)
    pronto = threading.Event()
    janela = _mostrar_abertura(porta, bundle_dir, perfil, pronto)
    threading.Thread(target=_marcar_pronto, args=(porta, pronto), daemon=True).start()
    if janela is not None:
        acompanhar_janela(janela, url_app(porta))
    rodar_streamlit(app_script, porta)
    return 0


def main() -> int:
    try:
        return _iniciar()
    except Exception:
        log.exception("Falha ao abrir o Solar ROI")
        avisar_erro(
            "Não consegui abrir o Solar ROI.\n\n"
            "O que aconteceu ficou registrado em data\\solar_app.log, na pasta do aplicativo.\n"
            "Feche esta janela e abra de novo; se continuar, envie esse arquivo para quem cuida do sistema."
        )
        return 1


_HTML_ABERTURA = Template("""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar ROI</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; min-height: 100vh; display: flex; flex-direction: column; align-items: center;
         justify-content: center; gap: 20px; padding: 24px; text-align: center;
         background: #f8fafc; color: #0f172a;
         font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
  .marca svg { width: 168px; max-width: 60vw; height: auto; }
  p { margin: 0; font-size: 15px; color: #475569; }
  .barra { width: 220px; height: 4px; border-radius: 999px; background: #e2e8f0; overflow: hidden; }
  .barra span { display: block; width: 40%; height: 100%; border-radius: 999px; background: #0284c7;
                animation: correr 1.1s ease-in-out infinite; }
  @keyframes correr { from { transform: translateX(-110%); } to { transform: translateX(310%); } }
  #aviso { display: none; max-width: 420px; font-size: 13px; color: #b45309; }
  @media (prefers-color-scheme: dark) {
    body { background: #0b0f19; color: #f8fafc; }
    p { color: #94a3b8; }
    .barra { background: #1f2937; }
    #aviso { color: #fbbf24; }
  }
</style>
</head>
<body>
  <div class="marca">$logo</div>
  <p>Abrindo o seu painel…</p>
  <div class="barra"><span></span></div>
  <p id="aviso"></p>
<script>
  const alvo = "$url";
  const inicio = Date.now();
  async function verificar() {
    try {
      const resposta = await fetch("/pronto", {cache: "no-store"});
      if ((await resposta.text()).trim() === "sim") { location.replace(alvo); return; }
    } catch (erro) { /* o app ainda está subindo */ }
    if (Date.now() - inicio > 90000) {
      const aviso = document.getElementById("aviso");
      aviso.textContent = "Está demorando mais que o normal. Feche esta janela e abra o app de novo; "
        + "se continuar, veja o arquivo data\\\\solar_app.log na pasta do aplicativo.";
      aviso.style.display = "block";
    }
    setTimeout(verificar, 400);
  }
  verificar();
</script>
</body>
</html>
""")
