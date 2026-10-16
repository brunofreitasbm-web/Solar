"""Geração do formulário oficial em PDF da Equatorial Pará para rateio de créditos de energia.

Preenche o modelo oficial 'Lista de Rateio para as Unidades Consumidoras Participantes
do Sistema de Compensação' (Autoconsumo Remoto, Geração Compartilhada e EMUC).
"""

from datetime import datetime
from pathlib import Path
from reportlab.lib import colors
from reportlab.pdfgen import canvas

PAGE_W = 612.0
PAGE_H = 792.0

# Cadastro unificado de informações cadastrais da Equatorial
DADOS_UNIDADES = {
    # Usinas Geradoras
    "231236701340": {
        "apelido": "Salinas",
        "conta_contrato": "3032332055",
        "classe": "Residencial",
        "endereco": "Pr. do Atalaia, 5, Condomínio Casa de Sal, Salinópolis - PA, CEP 68721-000",
        "municipio": "Salinópolis-PA",
    },
    "458420701358": {
        "apelido": "Salvaterra",
        "conta_contrato": "3033711769",
        "classe": "Residencial",
        "endereco": "Tv. Terceira, S/N, Joanes, Salvaterra - PA, CEP 68860-000",
        "municipio": "Salvaterra-PA",
    },
    # Unidades Beneficiárias
    "415013401359": {
        "apelido": "Marambaia",
        "conta_contrato": "3024187216",
        "classe": "Residencial",
        "endereco": "R. Rodolfo Chermont, 02, Al. D13, Cj. Mendara, Loja 02, Marambaia, Belém - PA",
        "municipio": "Belém-PA",
    },
    "106426901380": {
        "apelido": "Icoaraci",
        "conta_contrato": "3032480739",
        "classe": "Comercial",
        "endereco": "Av. Dr. Lopo de Castro, 251, Cruzeiro, Icoaraci, Belém - PA",
        "municipio": "Belém-PA",
    },
    "267344001348": {
        "apelido": "101",
        "conta_contrato": "3031789744",
        "classe": "Residencial",
        "endereco": "R. Boaventura da Silva, 1035, Apt. 101, Edf. Belize, Umarizal, Belém - PA",
        "municipio": "Belém-PA",
    },
    "258717601383": {
        "apelido": "701",
        "conta_contrato": "3031845245",
        "classe": "Residencial",
        "endereco": "R. Boaventura da Silva, 1035, Apt. 701, Ed. Belize, Umarizal, Belém - PA",
        "municipio": "Belém-PA",
    },
    "425281101305": {
        "apelido": "Conteiner",
        "conta_contrato": "3036237855",
        "classe": "Residencial",
        "endereco": "Rod. Mário Covas, S/N, Contêiner Cacau Show, Coqueiro, Ananindeua - PA",
        "municipio": "Ananindeua-PA",
    },
}

# Mapa reverso de apelido para UC
UC_POR_APELIDO = {info["apelido"].lower(): uc for uc, info in DADOS_UNIDADES.items()}
UC_POR_APELIDO.update({
    "mariocovas": "425281101305",
    "mario covas": "425281101305",
    "cacau show": "425281101305",
    "belize 101": "267344001348",
    "belize 701": "258717601383",
})


def _pt_y(top: float) -> float:
    return PAGE_H - top


def desenhar_pdf_rateio(
    caminho_saida: Path | str,
    conta_contrato_geradora: str,
    local_solicitacao: str,
    data_solicitacao: str,
    itens_rateio: list[dict],
    enquadramento: str = "Autoconsumo Remoto",
) -> Path:
    """Gera o arquivo PDF oficial no layout idêntico ao modelo da Equatorial Pará."""
    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(caminho_saida), pagesize=(PAGE_W, PAGE_H))

    # Coordenadas horizontais (X)
    x_left = 83.2
    x_col1 = 110.2  # Ordem
    x_col2 = 155.0  # % kWh
    x_col3 = 215.8  # Conta Contrato
    x_col4 = 353.5  # Classe de Consumo
    x_right = 557.8 # Endereço

    # Coordenadas verticais (Y de cima para baixo)
    y_header_top = 43.1
    y_row1_top = 66.7
    y_row2_top = 76.6
    y_row3_top = 86.5
    y_sep1_top = 96.4
    y_table_hdr_top = 113.3
    y_rows_start_top = 123.2
    y_table_bottom = 732.7

    row_height = (y_table_bottom - y_rows_start_top) / 53.0

    # 1. Fundos cinza de cabeçalhos
    c.setFillColor(colors.HexColor("#F2F2F2"))
    # Linha de títulos da tabela
    c.rect(x_left, _pt_y(y_rows_start_top), x_right - x_left, y_rows_start_top - y_table_hdr_top, fill=True, stroke=False)
    # Rótulos do cabeçalho
    c.rect(x_left, _pt_y(y_row2_top), x_col3 - x_left, y_row2_top - y_row1_top, fill=True, stroke=False)
    c.rect(313.1, _pt_y(y_row2_top), 376.6 - 313.1, y_row2_top - y_row1_top, fill=True, stroke=False)
    c.rect(x_left, _pt_y(y_row3_top), 166.9 - x_left, y_row3_top - y_row2_top, fill=True, stroke=False)
    c.rect(414.4, _pt_y(y_row3_top), 475.8 - 414.4, y_row3_top - y_row2_top, fill=True, stroke=False)
    c.rect(x_left, _pt_y(y_sep1_top), x_col3 - x_left, y_sep1_top - y_row3_top, fill=True, stroke=False)

    # 2. Bordas e linhas
    c.setStrokeColor(colors.HexColor("#000000"))
    c.setLineWidth(0.5)

    # Borda do bloco superior
    c.rect(x_left, _pt_y(y_sep1_top), x_right - x_left, y_sep1_top - y_header_top, fill=False, stroke=True)
    for y_top in [y_row1_top, y_row2_top, y_row3_top]:
        c.line(x_left, _pt_y(y_top), x_right, _pt_y(y_top))

    c.line(x_col3, _pt_y(y_row1_top), x_col3, _pt_y(y_row2_top))
    c.line(313.1, _pt_y(y_row1_top), 313.1, _pt_y(y_row2_top))
    c.line(376.6, _pt_y(y_row1_top), 376.6, _pt_y(y_row2_top))

    c.line(166.9, _pt_y(y_row2_top), 166.9, _pt_y(y_row3_top))
    c.line(414.4, _pt_y(y_row2_top), 414.4, _pt_y(y_row3_top))
    c.line(475.8, _pt_y(y_row2_top), 475.8, _pt_y(y_row3_top))

    c.line(x_col3, _pt_y(y_row3_top), x_col3, _pt_y(y_sep1_top))
    c.line(313.1, _pt_y(y_row3_top), 313.1, _pt_y(y_sep1_top))

    # Borda da tabela de 53 linhas
    c.rect(x_left, _pt_y(y_table_bottom), x_right - x_left, y_table_bottom - y_table_hdr_top, fill=False, stroke=True)
    c.line(x_left, _pt_y(y_rows_start_top), x_right, _pt_y(y_rows_start_top))

    for i in range(1, 54):
        y_line = y_rows_start_top + (i * row_height)
        c.line(x_left, _pt_y(y_line), x_right, _pt_y(y_line))

    for x_col in [x_col1, x_col2, x_col3, x_col4]:
        c.line(x_col, _pt_y(y_table_hdr_top), x_col, _pt_y(y_table_bottom))

    # 3. Textos do Cabeçalho
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.0)
    c.drawCentredString(PAGE_W / 2.0, _pt_y(y_header_top + 10.0), "LISTA DE RATEIO PARA AS UNIDADES CONSUMIDORAS PARTICIPANTES DO SISTEMA DE COMPENSAÇÃO")
    c.setFont("Helvetica", 7.0)
    c.drawCentredString(PAGE_W / 2.0, _pt_y(y_header_top + 19.0), "(Autoconsumo Remoto, Geração Compartilhada e EMUC)")

    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(x_left + 4.0, _pt_y(y_row1_top + 6.8), "Conta Contrato da UC geradora")
    c.setFont("Helvetica", 8.0)
    c.drawCentredString((x_col3 + 313.1) / 2.0, _pt_y(y_row1_top + 7.2), str(conta_contrato_geradora))

    c.setFont("Helvetica-Bold", 6.8)
    c.drawCentredString((313.1 + 376.6) / 2.0, _pt_y(y_row1_top + 6.8), "Enquadramento")
    c.setFont("Helvetica", 7.5)
    c.drawCentredString((376.6 + x_right) / 2.0, _pt_y(y_row1_top + 7.0), enquadramento)

    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(x_left + 4.0, _pt_y(y_row2_top + 6.8), "Local da solicitação")
    c.setFont("Helvetica", 7.5)
    c.drawCentredString((166.9 + 414.4) / 2.0, _pt_y(y_row2_top + 7.0), local_solicitacao)

    c.setFont("Helvetica-Bold", 6.8)
    c.drawCentredString((414.4 + 475.8) / 2.0, _pt_y(y_row2_top + 6.8), "Data solicitação")
    c.setFont("Helvetica", 7.5)
    c.drawCentredString((475.8 + x_right) / 2.0, _pt_y(y_row2_top + 7.0), data_solicitacao)

    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(x_left + 4.0, _pt_y(y_row3_top + 6.8), "Forma de alocação dos créditos")
    c.setFont("Helvetica", 7.5)
    c.drawCentredString((x_col3 + 313.1) / 2.0, _pt_y(y_row3_top + 7.0), "Percentual do Excedente")
    c.setFont("Helvetica-Oblique", 6.5)
    c.drawString(320.0, _pt_y(y_row3_top + 6.8), "Preencher as porcentagens")

    # 4. Títulos das Colunas
    c.setFont("Helvetica-Bold", 6.8)
    c.drawCentredString((x_left + x_col1) / 2.0, _pt_y(y_table_hdr_top + 7.0), "Ordem")
    c.drawCentredString((x_col1 + x_col2) / 2.0, _pt_y(y_table_hdr_top + 7.0), "% kWh")
    c.drawCentredString((x_col2 + x_col3) / 2.0, _pt_y(y_table_hdr_top + 7.0), "Conta Contrato")
    c.drawCentredString((x_col3 + x_col4) / 2.0, _pt_y(y_table_hdr_top + 7.0), "Classe de Consumo")
    c.drawCentredString((x_col4 + x_right) / 2.0, _pt_y(y_table_hdr_top + 7.0), "Endereço")

    # 5. Linhas de Dados (1 a 53)
    itens_dict = {i + 1: item for i, item in enumerate(itens_rateio)}
    for num in range(1, 54):
        y_top = y_rows_start_top + ((num - 1) * row_height)
        y_text = _pt_y(y_top + (row_height * 0.72))

        # Ordem (sempre 1 a 53)
        c.setFont("Helvetica", 6.8)
        c.drawCentredString((x_left + x_col1) / 2.0, y_text, str(num))

        if num in itens_dict:
            item = itens_dict[num]
            pct = item.get("pct", 0.0)
            cc = item.get("conta_contrato", "")
            classe = item.get("classe", "Residencial")
            end = item.get("endereco", "")

            # % kWh
            c.setFont("Helvetica-Bold", 8.0)
            c.drawCentredString((x_col1 + x_col2) / 2.0, y_text, f"{pct:.2f}".replace(".", ","))

            # Conta Contrato
            c.setFont("Helvetica", 8.0)
            c.drawCentredString((x_col2 + x_col3) / 2.0, y_text, str(cc))

            # Classe de Consumo
            c.setFont("Helvetica", 7.5)
            c.drawCentredString((x_col3 + x_col4) / 2.0, y_text, classe)

            # Endereço
            c.setFont("Helvetica", 6.8 if len(end) <= 52 else 5.8)
            c.drawString(x_col4 + 4.0, y_text, end)

    c.save()
    return caminho_saida


def montar_itens_rateio(
    distribuicao_pct: dict[str, float],
    filtro_zerados: bool = True,
) -> list[dict]:
    """Converte um dicionário de {uc_ou_apelido: percentual} em itens com dados cadastrais."""
    itens = []
    # Ordena por maior percentual primeiro
    ordenados = sorted(distribuicao_pct.items(), key=lambda x: x[1], reverse=True)

    for chave, pct in ordenados:
        if filtro_zerados and pct <= 0.001:
            continue

        # Identifica a UC
        uc_limpa = str(chave).replace(".", "").replace("-", "").strip()
        info = DADOS_UNIDADES.get(uc_limpa)
        if not info:
            uc_mapeada = UC_POR_APELIDO.get(str(chave).lower().strip())
            if uc_mapeada:
                info = DADOS_UNIDADES.get(uc_mapeada)

        if info:
            itens.append({
                "apelido": info["apelido"],
                "pct": pct,
                "conta_contrato": info["conta_contrato"],
                "classe": info["classe"],
                "endereco": info["endereco"],
            })
        else:
            # Fallback caso não esteja no cadastro
            itens.append({
                "apelido": str(chave),
                "pct": pct,
                "conta_contrato": str(chave),
                "classe": "Residencial",
                "endereco": "Pará",
            })

    return itens


def gerar_listas_usinas(
    pasta_saida: Path | str,
    rateio_pct: dict[str, float] | None = None,
    data_solicitacao: str | None = None,
) -> dict[str, Path]:
    """Gera 1 PDF para cada usina geradora cadastrada (Salinas e Salvaterra)."""
    pasta = Path(pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    if data_solicitacao is None:
        data_solicitacao = datetime.now().strftime("%d/%m/%Y")

    # Percentuais padrão sugeridos pelo app se nenhum for passado
    if rateio_pct is None:
        # Rateio sugerido padrão (otimização de demanda e saldo)
        rateio_pct = {
            "Marambaia": 32.99,
            "Icoaraci": 28.57,
            "101": 21.16,
            "701": 15.80,
            "Salinas": 1.48,
        }

    itens = montar_itens_rateio(rateio_pct)
    arquivos_gerados = {}

    # 1. Salinas
    salinas_info = DADOS_UNIDADES["231236701340"]
    caminho_salinas = pasta / "Lista_de_Rateio_Salinas.pdf"
    desenhar_pdf_rateio(
        caminho_saida=caminho_salinas,
        conta_contrato_geradora=salinas_info["conta_contrato"],
        local_solicitacao=salinas_info["municipio"],
        data_solicitacao=data_solicitacao,
        itens_rateio=itens,
        enquadramento="Autoconsumo Remoto",
    )
    arquivos_gerados["Salinas"] = caminho_salinas

    # 2. Salvaterra
    salvaterra_info = DADOS_UNIDADES["458420701358"]
    caminho_salvaterra = pasta / "Lista_de_Rateio_Salvaterra.pdf"
    desenhar_pdf_rateio(
        caminho_saida=caminho_salvaterra,
        conta_contrato_geradora=salvaterra_info["conta_contrato"],
        local_solicitacao=salvaterra_info["municipio"],
        data_solicitacao=data_solicitacao,
        itens_rateio=itens,
        enquadramento="Autoconsumo Remoto",
    )
    arquivos_gerados["Salvaterra"] = caminho_salvaterra

    return arquivos_gerados
