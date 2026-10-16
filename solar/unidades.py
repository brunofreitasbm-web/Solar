from dataclasses import asdict, dataclass

from solar.db import conexao


@dataclass
class Unidade:
    uc: str
    apelido: str = ""
    endereco: str = ""
    geradora: bool = False
    kwp: float | None = None
    lat: float | None = None
    lon: float | None = None
    data_pedido_conexao: str | None = None

    @property
    def nome(self) -> str:
        return self.apelido or f"UC {self.uc}"


def listar() -> list[Unidade]:
    with conexao() as con:
        linhas = con.execute("SELECT * FROM unidades ORDER BY geradora DESC, apelido, uc").fetchall()
    return [Unidade(**{**dict(l), "geradora": bool(l["geradora"])}) for l in linhas]


def salvar(unidade: Unidade) -> None:
    dados = asdict(unidade)
    dados["geradora"] = int(unidade.geradora)
    colunas = ", ".join(dados)
    marcadores = ", ".join(f":{c}" for c in dados)
    with conexao() as con:
        con.execute(f"INSERT OR REPLACE INTO unidades ({colunas}) VALUES ({marcadores})", dados)


def garantir(uc: str, endereco: str = "", geradora_sugerida: bool = False) -> None:
    """Cria a UC na primeira fatura lida; nunca sobrescreve o que o usuário já marcou."""
    with conexao() as con:
        con.execute(
            "INSERT OR IGNORE INTO unidades (uc, endereco, geradora) VALUES (?, ?, ?)",
            (uc, endereco, int(geradora_sugerida)),
        )


def excluir(uc: str) -> None:
    with conexao() as con:
        con.execute("DELETE FROM faturas WHERE uc = ?", (uc,))
        con.execute("DELETE FROM unidades WHERE uc = ?", (uc,))
