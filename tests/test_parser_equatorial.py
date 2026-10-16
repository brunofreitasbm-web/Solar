from solar.faturas.parser_equatorial import interpretar, normalizar, numero_br

FATURA_REAL = """
2ª Via
GRUPO DE TENSÃO: B SUBGRUPO: B1 TIPO DE FORNECIMENTO: TRIFÁSICO
BRUNO PINTO FREITAS 13/05/2025 12/06/2025 30 15/07/2025
CPF: ***.352.68*-**
PR DO ATALAIA , 5 , CONDOMINIO CASA DE SAL
CEP: 68721-000 - SALINOPOLIS - SALINOPOLIS - PA NOTA FISCAL Nº 129948443
Consulte pela Chave de Acesso em:
2.312.367.013-40 https://dfe-portal.svrs.rs.gov.br/NFE/Consulta
Protocolo de autorização: 3152500017172071 -
06/2025 26/06/2025 R$ 170,24 12/06/2025 às 15:04:22
Períodos: Band. Tarif.: Amarela : 14/05 - 31/05 Vermelha : 01/06 - 12/06
ICMS 146,55 19,0000 27,84
Consumo (kWh) 95,06 1,255312 0,938450 7,46 22,67 119,33 PIS 120,34 1,3751 1,66
Consumo Compensado (kWh) 26,93 0,940587 0,703500 1,58 4,81 25,33 COFINS 120,34 6,3379 7,63
Energia Ativa Injetada (kWh) 26,93 0,940587 0,703500 -1,58 -4,81 -25,33
Parc. Inj. s/ Desc. - GD2 (kWh) 26,93 0,230598 0,175335 0,39 1,10 6,21
Benefício Tarifário Bruto SCEE 1,19 3,33 18,74
Benefício Tarifário Líquido SCEE -14,22
58108183 Consumo ATIVO TOTAL 209 331 1,00 122 kWh
58108183 Energia Injetada ATIVO TOTAL 4.964 8.080 1,00 3.116 kWh
Nome do Cliente: C.C: Unidade de Leitura: Competência: Vencimento: Valor cobrado (R$):
BRUNO PINTO FREITAS 3032332055 SP08B004 06/2025 170,24
FATURA ARRECADADA - NÃO RECEBER
"""


def test_numero_br():
    assert numero_br("1.234,56") == 1234.56


def test_normalizar_remove_acentos():
    assert normalizar("Energia Injetada") == "ENERGIA INJETADA"


def test_interpreta_fatura_real():
    fatura = interpretar(FATURA_REAL)
    assert fatura.uc == "2312367013" + "40"
    assert fatura.mes_ref == "2025-06"
    assert fatura.total_rs == 170.24
    assert fatura.consumo_kwh == 122
    assert fatura.injetado_kwh == 3116
    assert fatura.compensado_kwh == 26.93
    assert fatura.credito_rs == 14.22
    assert round(fatura.tarifa_kwh, 4) == round(119.33 / 95.06, 4)
    assert fatura.bandeira == "Amarela/Vermelha"
    assert not fatura.campos_faltando


def test_fatura_sem_geracao_nao_acusa_injetado():
    texto = FATURA_REAL.replace("58108183 Energia Injetada ATIVO TOTAL 4.964 8.080 1,00 3.116 kWh", "")
    fatura = interpretar(texto)
    assert fatura.injetado_kwh == 0.0
