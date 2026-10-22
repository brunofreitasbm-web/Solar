"""Página do Consultor Inteligente de Tomada de Decisão e Expansão."""

import streamlit as st

from paginas import painel_dados, ui
from solar.ia import cliente, ferramentas


def render() -> None:
    st.header("Consultor IA")
    st.caption("Inteligência Artificial para apoio a decisões financeiras, viabilidade de expansão e auditoria regulatória.")

    painel = painel_dados.carregar()
    if painel is None or painel.df.empty:
        ui.sem_faturas()
        return

    provedor, chave = cliente.obter_chave_configurada()

    # Barra de status e configuração rápida de chaves
    with st.container(border=True):
        col_status, col_btn = st.columns([3, 1])
        with col_status:
            if provedor:
                st.markdown(
                    f":green[●] **API Conectada:** `{provedor.upper()}` (Análise em tempo real habilitada)"
                )
            else:
                st.markdown(
                    ":orange[●] **Modo Analítico Local Ativo:** Operando com os motores matemáticos locais. Configure uma chave para habilitar conversação livre."
                )
        with col_btn:
            configurar = st.toggle("Configurar API", value=False)

        if configurar:
            st.divider()
            st.markdown("##### Chaves de API para IA")
            st.caption("Você pode usar o **DeepSeek**, **Google Gemini** ou **Anthropic Claude**.")

            tipo_api = st.radio("Escolha o Provedor:", ["DeepSeek (Recomendado)", "Google Gemini", "Claude (Anthropic)"], horizontal=True)
            if "DeepSeek" in tipo_api:
                nome_prov = "deepseek"
            elif "Gemini" in tipo_api:
                nome_prov = "gemini"
            else:
                nome_prov = "anthropic"

            chave_input = st.text_input(
                f"Chave de API {tipo_api}:",
                type="password",
                placeholder="Cole sua chave de API aqui",
                help="A chave fica armazenada no banco de dados local do seu computador.",
            )

            if st.button("Salvar Chave", type="primary"):
                if chave_input.strip():
                    cliente.salvar_chave(nome_prov, chave_input.strip())
                    st.success(f"Chave da API {tipo_api} salva com sucesso!")
                    st.rerun()
                else:
                    st.error("Informe uma chave válida.")

    st.markdown("### Ações Rápidas de Decisão")
    col1, col2, col3, col4 = st.columns(4)

    pergunta_acionada = None

    with col1:
        if st.button("📊 Diagnóstico Completo", use_container_width=True):
            pergunta_acionada = "Gerar diagnóstico executivo completo do sistema solar"
    with col2:
        if st.button("📈 Análise de Expansão", use_container_width=True):
            pergunta_acionada = "Avaliar expansão das usinas: quando a demanda vai superar a geração e qual o tamanho ideal de ampliação?"
    with col3:
        if st.button("🏦 Decisão de Quitação", use_container_width=True):
            pergunta_acionada = "Compensa quitar o financiamento antecipadamente ou manter o dinheiro aplicado no CDI?"
    with col4:
        if st.button("⚠️ Auditar Anomalias", use_container_width=True):
            pergunta_acionada = "Verificar se há anomalias, multas ou perdas de geração nas faturas recentes"

    # Histórico de Chat
    if "mensagens_ia" not in st.session_state:
        st.session_state.mensagens_ia = []
        # Mensagem inicial de boas-vindas com resumo inicial
        st.session_state.mensagens_ia.append({
            "role": "assistant",
            "content": (
                "Olá! Sou seu **Consultor de Inteligência Artificial Solar**.\n\n"
                "Estou conectado aos seus dados de faturas, contratos e modelos de projeção da Equatorial Pará. "
                "Posso responder dúvidas sobre **ampliação de usinas**, **quitação de parcelas**, **otimização de rateio** "
                "e **auditoria de cobranças**.\n\n"
                "Selecione uma ação rápida acima ou faça uma pergunta específica abaixo."
            ),
        })

    # Renderiza mensagens anteriores
    for msg in st.session_state.mensagens_ia:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Processamento de perguntas (via botão rápido ou campo de chat)
    pergunta_input = st.chat_input("Pergunte sobre expansão, financiamento, faturas ou rateio...")
    pergunta = pergunta_acionada or pergunta_input

    if pergunta:
        st.session_state.mensagens_ia.append({"role": "user", "content": pergunta})
        with st.chat_message("user"):
            st.markdown(pergunta)

        with st.chat_message("assistant"):
            resposta_gen = cliente.responder_pergunta(pergunta, st.session_state.mensagens_ia)
            resposta_completa = st.write_stream(resposta_gen)

        st.session_state.mensagens_ia.append({"role": "assistant", "content": resposta_completa})

    # Botão para limpar histórico
    if len(st.session_state.mensagens_ia) > 1:
        st.caption("")
        if st.button("Limpar conversa", type="secondary"):
            st.session_state.mensagens_ia = []
            st.rerun()
