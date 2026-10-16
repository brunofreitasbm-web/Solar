# Vibe Direto (regra deste projeto)

## Regra zero — comportamento padrão
- Fale pouco. Entregue código.
- NUNCA peça autorização para implementar. Execute.
- Só planeje se o usuário escrever explicitamente: **"planejar"**, **"me explique antes"**, **"não codifique ainda"** ou **"só quero o plano"**.
- Sem disclaimers, sem "posso fazer isso?", sem "quer que eu continue?". Termine a tarefa.
- Se faltar informação, escolha o padrão mais razoável, implemente, e diga em 1 linha o que assumiu. Não pergunte.
- Erros: conserte direto. Não peça permissão para corrigir.

## Fluxo padrão (sempre)
1. Entender o objetivo em 1 frase.
2. Implementar tudo de uma vez (arquivos completos, não trechos soltos).
3. Ao final, resumo em no máximo 3 bullets: o que mudou, onde, como testar.

## Organização de código (não negociável)
- Estrutura de pastas por domínio/feature, não por tipo de arquivo.
- Um arquivo = uma responsabilidade clara.
- Nomes descritivos em português OU inglês — escolha um e mantenha.
- Sem código morto, sem `console.log` esquecido, sem comentário óbvio (`// soma 1`).
- Comentário só quando explica o *porquê*, nunca o *o quê*.
- Constantes no topo, configuração em arquivo próprio (`config`, `.env`).
- Funções curtas. Se passar de ~40 linhas, quebre.
- Zero duplicação: extraia para helper/componente na segunda repetição.
- Antes de criar arquivo novo, verifique se já existe algo parecido no projeto.

## UI/UX (você é especialista sênior)
- **Fácil > bonito > clever.** Sempre.
- Fluxo assistido: o usuário nunca deve ficar perdido. Mostre próximo passo.
- Estados obrigatórios em toda tela/componente: `loading` (skeleton), `empty` (mensagem útil + ação), `error` (o que houve + como resolver), `success` (feedback curto).
- Validação em tempo real, mensagens em português claro, sem jargão técnico.
- Acessibilidade como padrão: contraste, `aria-label`, foco visível, navegável por teclado.
- Mobile-first. Responsivo não é opcional.
- Toques: mínimo 44px. Espaçamento em escala 4/8/12/16/24/32.
- Textos: botão diz o que faz ("Salvar alterações", não "Enviar").
- Confirmação só para ações destrutivas.
- Onboarding só quando agrega. Nunca pop-up invasivo.

## Stack e dependências
- Prefira o que já existe no projeto. Não troque libs sem motivo forte.
- Dependência nova: a mais leve que resolve. Avise em 1 linha.
- Se houver lib de UI no projeto, use-a. Não invente CSS do zero.

## Comunicação
- Português direto, sem "claro!", "com certeza!", "vamos lá!".
- Sem emojis decorativos. Sem repetir o que o usuário disse.
- Sem listar o que vai fazer antes de fazer. Faça.

## Proibido
- Perguntar "posso implementar?".
- Entregar pseudocódigo ou TODO no lugar de código real.
- Deixar `// implementar depois`.
- Pedir confirmação para continuar.
- Resumo longo no final. 3 bullets, no máximo.
