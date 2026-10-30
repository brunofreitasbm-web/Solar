import os
import sys
import socket
import webbrowser
import threading
import time
import shutil
from pathlib import Path
import multiprocessing

def obter_porta_livre(porta_padrao: int = 8501) -> int:
    """Verifica se porta_padrao está livre; se ocupada, localiza uma disponível."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", porta_padrao)) != 0:
            return porta_padrao
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def inicializar_estrutura_pastas(app_dir: Path, bundle_dir: Path) -> None:
    """Cria as pastas locais de dados e backup se ainda não existirem."""
    pasta_data = app_dir / "data"
    pasta_data.mkdir(parents=True, exist_ok=True)
    (pasta_data / "pdfs").mkdir(parents=True, exist_ok=True)
    (pasta_data / "rateio").mkdir(parents=True, exist_ok=True)
    (app_dir / "backups").mkdir(parents=True, exist_ok=True)

    db_destino = pasta_data / "solar.db"
    if not db_destino.exists():
        db_origem = bundle_dir / "data" / "solar.db"
        if db_origem.exists():
            shutil.copy2(db_origem, db_destino)

def abrir_navegador_quando_disponivel(url: str, timeout: int = 25) -> None:
    """Aguarda o servidor Streamlit responder para abrir o navegador padrão."""
    def _aguardar():
        inicio = time.time()
        while time.time() - inicio < timeout:
            time.sleep(0.4)
            try:
                partes = url.replace("http://", "").split(":")
                host = partes[0]
                porta = int(partes[1])
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    if s.connect_ex((host, porta)) == 0:
                        webbrowser.open(url)
                        break
            except Exception:
                pass

    thread = threading.Thread(target=_aguardar, daemon=True)
    thread.start()

def main():
    multiprocessing.freeze_support()

    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        app_dir = Path(sys.executable).parent
    else:
        bundle_dir = Path(__file__).resolve().parent
        app_dir = Path(os.environ.get("SOLAR_RAIZ_DADOS", bundle_dir))

    # Garante estrutura de persistência local
    inicializar_estrutura_pastas(app_dir, bundle_dir)

    # Configura pasta de tema do streamlit
    streamlit_config = bundle_dir / ".streamlit"
    if streamlit_config.exists():
        os.environ["STREAMLIT_CONFIG_DIR"] = str(streamlit_config)

    app_script = str(bundle_dir / "app.py")
    porta = obter_porta_livre(8501)
    url = f"http://localhost:{porta}"

    # Dispara abertura automática do navegador
    abrir_navegador_quando_disponivel(url)

    # Importa CLI do streamlit após preparar variáveis de ambiente
    import streamlit.web.cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        app_script,
        f"--server.port={porta}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]

    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
