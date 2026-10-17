from solar import config

# Créditos que chegam num ciclo e são lançados no seguinte: compara janelas de meses, não um mês só.
JANELA_CREDITOS_MESES = 3
TOLERANCIA_KWH = 5.0
TOLERANCIA_RECEBIDO = 0.15      # recebeu >15% menos que injetado × rateio

TOLERANCIA_FIO_B = 0.30         # Fio B por kWh >30% fora do padrão dos meses anteriores
MESES_BASE_FIO_B = 6
MINIMO_MESES_FIO_B = 3

CICLO_MIN_DIAS = 25
CICLO_MAX_DIAS = 35

MESES_ANALISADOS = 6            # só olha para trás este tanto; o resto é histórico antigo
DISPONIBILIDADE_KWH = config.DISPONIBILIDADE_KWH
