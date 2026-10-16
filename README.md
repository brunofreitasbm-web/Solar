# Solar ROI

App local (Streamlit) para ler as contas de energia da Equatorial Pará, calcular a
economia mensal de cada unidade consumidora e o ROI das usinas, com créditos, alertas de
geração e comparação com CDI/IPCA.

## Rodando

```
.venv/Scripts/activate  # ou: python -m venv .venv && pip install -r requirements.txt
streamlit run app.py
```

Dados ficam só no seu PC, em `data/solar.db` e `data/pdfs/` (fora do git).

## Fluxo

1. **Enviar faturas** — arraste os PDFs. O parser por regras lê os campos; se faltar algo
   e `ANTHROPIC_API_KEY` estiver configurada (veja `.env.example`), a IA tenta completar.
2. **Revisar leitura** — confirme ou corrija os campos e marque quais unidades são
   geradoras.
3. **Unidades** — endereço, potência (kWp), coordenadas e data do pedido de conexão
   (define a regra do Fio B pela Lei 14.300).
4. **Dashboard** — economia mensal, ROI, payback, TIR, comparação com CDI/IPCA, saldo e
   validade de créditos, alerta de baixa geração (NASA POWER).
5. **Configurações** — investimento total, tributos, e a tarifa vigente da ANEEL (Dados
   Abertos), atualizável a qualquer momento.
