"""Central de alertas: reúne em um só lugar tudo que pede atenção."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from solar import anomalias, auditoria, creditos, pagamentos, saude, vencimentos
from solar.loggers import repositorio as loggers, strings

DIAS_DE_AVISO_VENCIMENTO = 7


@dataclass
class Alerta:
    gravidade: str  # "erro" | "aviso"
    texto: str
    pagina: str     # url da página em navegacao.ROTAS
    rotulo: str


def _unidades(nomes: dict[str, str], ucs) -> str:
    return ", ".join(nomes.get(uc, uc) for uc in ucs)


def reunir(df: pd.DataFrame, nomes: dict[str, str], performance_ratio: float, em_revisao: int = 0,
           hoje: date | None = None) -> list[Alerta]:
    hoje = hoje or date.today()
    alertas: list[Alerta] = []
    if em_revisao:
        alertas.append(Alerta("aviso", f"{em_revisao} fatura(s) esperando revisão.", "revisar-leitura", "Revisar agora"))
    if df.empty:
        return alertas

    abertas = pagamentos.a_pagar(df, nomes, hoje)
    vencidas = abertas[abertas["vencida"]]
    if not vencidas.empty:
        alertas.append(Alerta("erro", f"Fatura vencida e sem pagamento registrado: {', '.join(vencidas['unidade'])}.",
                              "vencimentos", "Ver vencimentos"))
    a_vencer = abertas[~abertas["vencida"] & (abertas["dias"] <= DIAS_DE_AVISO_VENCIMENTO)]
    if not a_vencer.empty:
        alertas.append(Alerta("aviso", f"Vence em até {DIAS_DE_AVISO_VENCIMENTO} dias: {', '.join(a_vencer['unidade'])}.",
                              "vencimentos", "Ver vencimentos"))

    previsoes = vencimentos.proximos_vencimentos(df, nomes, hoje)
    aguardando = previsoes[previsoes["aguardando_fatura"].astype(bool)]
    if not aguardando.empty:
        alertas.append(Alerta("aviso", f"Fatura ainda não carregada: {', '.join(aguardando['unidade'])}.",
                              "enviar-faturas", "Enviar faturas"))

    geradoras = df[df["geradora"]]
    quedas = saude.quedas_persistentes(saude.avaliar(geradoras, performance_ratio)) if not geradoras.empty else []
    if quedas:
        alertas.append(Alerta("erro", f"Geração abaixo do normal há {saude.MESES_PARA_QUEDA_PERSISTENTE} meses em "
                                      f"{_unidades(nomes, quedas)}: verifique sujeira, sombra ou inversor.", "dashboard", "Ver geração"))

    fora = anomalias.consumo_fora_do_padrao(df)
    if not fora.empty:
        alertas.append(Alerta("aviso", f"Consumo fora do padrão no último mês: {_unidades(nomes, fora['uc'])}.",
                              "dashboard", "Ver consumo"))

    divergencias = [a for a in auditoria.auditar(df) if a.gravidade == "erro"]
    if divergencias:
        alertas.append(Alerta("erro", f"{len(divergencias)} divergência(s) grave(s) nas faturas: compensação ou créditos "
                                      "não batem.", "auditoria-fatura", "Ver auditoria"))

    expirando = creditos.creditos_a_expirar(df, hoje=hoje)
    if not expirando.empty:
        alertas.append(Alerta("aviso", f"Créditos perto de expirar em {_unidades(nomes, expirando['uc'].unique())}.",
                              "rateio-creditos", "Ajustar rateio"))
    return alertas


def de_loggers() -> list[Alerta]:
    """Strings sem tensão nos inversores monitorados."""
    resultado: list[Alerta] = []
    for logger in loggers.listar_loggers():
        leitura = loggers.ultima_leitura(logger["sn"])
        falhas = strings.strings_em_falha(logger["sn"], leitura) if leitura else []
        if falhas:
            numeros = ", ".join(str(i + 1) for i in falhas)
            resultado.append(Alerta("erro", f"{logger['nome']}: string {numeros} sem tensão com o inversor gerando.",
                                    "geracao-loggers", "Ver loggers"))
    return resultado
