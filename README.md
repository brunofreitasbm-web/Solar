# Solar ROI

App local (Streamlit) para ler as contas de energia da Equatorial Pará, calcular a economia
real das usinas, o ROI e o efeito do financiamento, e apoiar decisões (quitar, ampliar, ratear).

## Rodando

```
.venv\Scripts\activate   # ou: python -m venv .venv && pip install -r requirements.txt
streamlit run app.py
```

Os dados ficam só no seu PC: `data/solar.db` e `data/pdfs/` (fora do git). Opcional:
`ANTHROPIC_API_KEY` no `.env` ativa a leitura por IA para faturas que o parser não entende.

## Páginas

| Página | Para quê |
|---|---|
| Enviar faturas | Arraste PDFs ou aponte uma pasta (lê subpastas; salva direto o que veio completo). |
| Revisar leitura | Confirma/corrige só as faturas com campo faltando. |
| Unidades | Quais são geradoras, kWp, coordenadas, data do pedido de conexão. |
| Dashboard | Economia, ROI, payback e equilíbrio previstos (com Fio B escalonado), financiamento, créditos. |
| Composição da conta | Da conta sem usina até a conta real; quanto é Fio B, benefício, iluminação pública. |
| Rateio de créditos | Percentuais sugeridos por usina para zerar consumo descoberto e crédito parado. |
| Simulador | Quitação antecipada (juros × CDI) e ampliação da usina (VPL, TIR, payback). |
| Vencimentos | Próximos vencimentos, lembretes `.ics` para o calendário e custo dos atrasos. |
| Configurações | Investimento, financiamento, tributos, backup e tarifa ANEEL do dia. |

## Como a economia é calculada

Economia = valor da energia compensada pela tarifa cheia − (Fio B + benefício tarifário SCEE
que a fatura ainda cobra). A linha "Benefício Tarifário Líquido" sozinha **não** é a economia.
Iluminação pública, multa, bandeira e custo de disponibilidade existem com ou sem usina.

A projeção calibra tarifa, Fio B (60% hoje, 100% em 2029), sazonalidade (medida por usina e
ancorada na irradiação NASA) e degradação nas próprias faturas.

## Testes

```
.venv\Scripts\python -m pytest
```
