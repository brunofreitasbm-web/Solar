from solar.faturas.parser_equatorial import interpretar, normalizar, numero_br


def test_numero_br():
    assert numero_br("1.234,56") == 1234.56


def test_normalizar_remove_acentos():
    assert normalizar("Energia Injetada") == "ENERGIA INJETADA"


def test_interpreta_fatura_simples():
    texto = """
    UNIDADE CONSUMIDORA: 12345678
    REFERENTE A: JUN/2026
    CONSUMO KWH 350 0,98 343,00
    ENERGIA INJETADA NO MES 420 KWH
    ENERGIA COMPENSADA TUSD KWH -350 0,69 -241,50
    ENERGIA COMPENSADA TE KWH -350 0,29 -101,50
    SALDO ATUAL DE CREDITOS 70 KWH
    BANDEIRA VERDE
    TOTAL A PAGAR 45,67
    """
    fatura = interpretar(texto)
    assert fatura.uc == "12345678"
    assert fatura.mes_ref == "2026-06"
    assert fatura.consumo_kwh == 350
    assert fatura.injetado_kwh == 420
    assert fatura.compensado_kwh == 350
    assert fatura.credito_rs == 343.0
    assert fatura.saldo_creditos_kwh == 70
    assert fatura.total_rs == 45.67
    assert fatura.bandeira == "Verde"
    assert not fatura.campos_faltando
