from dataclasses import dataclass

from solar.config import PASTA_PDFS, TEM_CHAVE_IA
from solar.faturas import parser_equatorial, parser_ia
from solar.faturas.modelo import CAMPOS_OBRIGATORIOS, Fatura


@dataclass
class ResultadoExtracao:
    fatura: Fatura
    aviso: str = ""


def _arquivar(nome: str, pdf: bytes) -> str:
    PASTA_PDFS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_PDFS / nome
    destino.write_bytes(pdf)
    return str(destino.name)


def _faltando(fatura: Fatura) -> list[str]:
    return [c for c in CAMPOS_OBRIGATORIOS if not getattr(fatura, c)]


def extrair(nome_arquivo: str, pdf: bytes) -> ResultadoExtracao:
    try:
        fatura = parser_equatorial.interpretar(parser_equatorial.extrair_texto(pdf))
    except Exception:  # PDF corrompido ou escaneado sem texto: segue para a IA
        fatura = Fatura(campos_faltando=list(CAMPOS_OBRIGATORIOS))
    aviso = ""

    if fatura.campos_faltando:
        if TEM_CHAVE_IA:
            try:
                fatura = parser_ia.interpretar(pdf)
                fatura.campos_faltando = _faltando(fatura)
            except parser_ia.FalhaLeituraIA as erro:
                aviso = str(erro)
        else:
            aviso = "Alguns campos não foram lidos. Preencha-os abaixo ou configure a IA no arquivo .env."

    fatura.arquivo = _arquivar(nome_arquivo, pdf)
    return ResultadoExtracao(fatura, aviso)
