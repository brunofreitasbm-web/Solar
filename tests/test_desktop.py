import socket
import threading
import urllib.request

from solar import desktop


def test_porta_ocupada_nao_e_escolhida(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupada:
        ocupada.bind(("127.0.0.1", 0))
        ocupada.listen(1)
        porta = ocupada.getsockname()[1]
        assert desktop.porta_disponivel(porta) is False
        assert desktop.escolher_porta(tmp_path, preferida=porta) != porta


def test_porta_fechada_nao_responde_como_app(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as livre:
        livre.bind(("127.0.0.1", 0))
        porta = livre.getsockname()[1]
    assert desktop.servidor_respondendo(porta, espera=0.5) is False


def test_guarda_e_le_a_porta_usada(tmp_path):
    desktop.salvar_porta(tmp_path, 8599)
    assert desktop.ler_porta_salva(tmp_path) == 8599


def test_tela_de_abertura_avisa_quando_o_app_esta_pronto(tmp_path):
    pronto = threading.Event()
    porta = desktop.servir_abertura(8501, tmp_path, pronto)
    base = f"http://127.0.0.1:{porta}"

    pagina = urllib.request.urlopen(f"{base}/", timeout=5).read().decode("utf-8")
    assert "Abrindo o seu painel" in pagina
    assert "http://127.0.0.1:8501" in pagina
    assert urllib.request.urlopen(f"{base}/pronto", timeout=5).read() == b"nao"

    pronto.set()
    assert urllib.request.urlopen(f"{base}/pronto", timeout=5).read() == b"sim"
