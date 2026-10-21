import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    RAIZ = Path(sys.executable).resolve().parent
else:
    RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
PASTA_PDFS = PASTA_DADOS / "pdfs"
CAMINHO_DB = PASTA_DADOS / "solar.db"

load_dotenv(RAIZ / ".env")

DISTRIBUIDORA_ANEEL = "EQUATORIAL PA"
ANEEL_URL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
ANEEL_RECURSO_TARIFAS = "fcf2906c-7c32-4b9b-a637-054e7a5234f4"

BCB_SERIE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
BCB_SERIE_CDI_MENSAL = 4391
BCB_SERIE_IPCA_MENSAL = 433

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"

MODELO_IA = "claude-opus-5-5"
TEM_CHAVE_IA = bool(os.getenv("ANTHROPIC_API_KEY"))

# Padrões editáveis na tela Configurações
PADRAO_ICMS = 0.19
PADRAO_PIS_COFINS = 0.05
PADRAO_DEGRADACAO_ANUAL = 0.005
PADRAO_REAJUSTE_TARIFA_ANUAL = 0.06
PADRAO_PERFORMANCE_RATIO = 0.78
VIDA_UTIL_ANOS = 25

# Lei 14.300/2022: % do Fio B pago sobre energia compensada (pedidos após 07/01/2023)
DATA_CORTE_LEI_14300 = "2023-01-07"
FIO_B_PERCENTUAL_POR_ANO = {2023: 0.15, 2024: 0.30, 2025: 0.45, 2026: 0.60, 2027: 0.75, 2028: 0.90}
FIO_B_APOS_2028 = 1.0

VALIDADE_CREDITOS_MESES = 60
LIMIAR_ALERTA_GERACAO = 0.80

# Custo de disponibilidade (kWh/mês) cobrado mesmo com toda a energia compensada: 30 monofásico,
# 50 bifásico, 100 trifásico. As unidades deste projeto são trifásicas.
DISPONIBILIDADE_KWH = 100

PASTA_BACKUP = RAIZ / "backups"
BACKUPS_MANTIDOS = 12
DIAS_ENTRE_BACKUPS_AUTOMATICOS = 7

# Fio A e encargos que usinas novas (GD III) não compensam, além do Fio B
DESCONTO_USINA_NOVA = 0.10

# Sincronização Google Drive e Notificações Google Agenda
PASTA_GOOGLE_DRIVE = Path(r"C:\Users\bruno\Documents\Faturas de Energia Equatorial")
EMAIL_ISABELA = "isabella.vgoncalves@gmail.com"
