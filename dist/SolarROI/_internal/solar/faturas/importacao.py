from pathlib import Path

from solar.faturas import repositorio
from solar.faturas.extracao import ResultadoExtracao, extrair


def salvar_se_completa(resultado: ResultadoExtracao) -> bool:
    """Salva direto quando a leitura veio completa e sem aviso; senão deixa para revisão."""
    if resultado.fatura.campos_faltando or resultado.aviso:
        return False
    repositorio.salvar(resultado.fatura)
    return True


def importar_pasta(pasta: Path) -> tuple[int, list[ResultadoExtracao]]:
    """Lê todos os PDFs da pasta (e subpastas). Devolve quantas foram salvas e as pendentes
    de revisão. Arquivos com o mesmo mês/UC se substituem — vale a última leitura."""
    salvas, pendentes = 0, []
    for pdf in sorted(pasta.rglob("*.pdf")):
        resultado = extrair(str(pdf.relative_to(pasta)), pdf.read_bytes())
        if salvar_se_completa(resultado):
            salvas += 1
        else:
            pendentes.append(resultado)
    return salvas, pendentes
