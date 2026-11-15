import hashlib
import json
import sqlite3
from pathlib import Path

from solar import config


def hash_conteudo(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def nomes_no_banco() -> set[str]:
    try:
        with sqlite3.connect(config.CAMINHO_DB) as con:
            linhas = con.execute("SELECT arquivo FROM faturas WHERE arquivo != ''").fetchall()
    except sqlite3.Error:
        return set()
    return {Path(linha[0]).name for linha in linhas if linha[0]}


class FaturasConhecidas:
    """Tudo o que o app já tem: PDFs nas pastas informadas e faturas gravadas no banco.

    Compara por conteúdo (hash) e por nome, porque o portal pode reusar o nome do arquivo
    entre meses ou entregar o mesmo PDF com outro nome.
    """

    def __init__(self, pastas: list[Path], arquivo_contas: Path | None = None):
        self._arquivo_contas = arquivo_contas
        self._contas: set[str] = self._ler_contas()
        self._hashes: set[str] = set()
        self._nomes: set[str] = nomes_no_banco()
        for pasta in pastas:
            if not pasta.exists():
                continue
            for pdf in pasta.rglob("*.pdf"):
                self._nomes.add(pdf.name)
                self._hashes.add(hash_conteudo(pdf.read_bytes()))

    def ja_existe(self, conteudo: bytes) -> bool:
        return hash_conteudo(conteudo) in self._hashes

    def registrar(self, nome: str, conteudo: bytes) -> None:
        self._nomes.add(nome)
        self._hashes.add(hash_conteudo(conteudo))

    def nome_livre(self, nome: str) -> str:
        """Evita sobrescrever um PDF diferente que tenha o mesmo nome."""
        if nome not in self._nomes:
            return nome
        base = Path(nome)
        contador = 2
        while f"{base.stem}_{contador}{base.suffix}" in self._nomes:
            contador += 1
        return f"{base.stem}_{contador}{base.suffix}"

    def _ler_contas(self) -> set[str]:
        if not self._arquivo_contas or not self._arquivo_contas.exists():
            return set()
        try:
            return set(json.loads(self._arquivo_contas.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return set()

    def conta_ja_baixada(self, chave: str) -> bool:
        return chave in self._contas

    def marcar_conta(self, chave: str) -> None:
        """Lembra a conta do portal para não clicar nela de novo nas próximas execuções."""
        self._contas.add(chave)
        if self._arquivo_contas:
            self._arquivo_contas.parent.mkdir(parents=True, exist_ok=True)
            self._arquivo_contas.write_text(json.dumps(sorted(self._contas), ensure_ascii=False, indent=1), encoding="utf-8")
