# Deploy em produção (Render.com)

Este documento cobre o que mudou para preparar o projeto para produção:
configuração centralizada (`config/settings.py`), suporte a ferramentas MCP
externas (`config/mcp_config.py`), autenticação da API web, e os arquivos de
deploy (`render.yaml`, `Procfile`).

## 0. Aviso importante: o Ollama não roda no Render

O agente usa `ChatOllama`, que precisa de um servidor Ollama rodando e
acessível pela rede (`OLLAMA_BASE_URL`). **O Render não tem Ollama
embutido** — os planos padrão (web service) não têm GPU e não instalam o
Ollama para você. Antes de colocar em produção, escolha uma opção:

1. **Ollama em outra máquina/serviço que você controla**, acessível pela
   internet (ex: uma VPS sua, ou outro serviço com GPU), com a porta da API
   do Ollama exposta e, idealmente, atrás de autenticação/rede privada.
   Aponte `OLLAMA_BASE_URL` para essa URL.
2. **Trocar o LLM** por um provedor hospedado (ex: OpenAI, Anthropic,
   Groq, Together) — isso exige trocar `ChatOllama` por outro `ChatModel`
   do LangChain em `agents/productivity_agent.py`. Não fizemos essa troca
   aqui porque muda a arquitetura (modelo local → API paga) e não foi
   pedido, mas o código já está isolado nesse ponto único caso você queira
   fazer essa mudança depois.

Sem uma dessas duas opções, o serviço sobe no Render, mas todo `/api/chat`
vai falhar ao tentar falar com o Ollama.

## 1. Autenticação da API

O projeto original não tinha senha (documentado no README como aceitável só
em rede doméstica). Isso não é seguro com uma URL pública do Render.
Agora:

- Se `ENVIRONMENT=production` e `API_AUTH_TOKEN` não estiver definido, o
  servidor recusa as rotas `/api/chat`, `/api/reset`, `/api/config` e
  `/api/status` (erro 500 explicando o motivo).
- Com `API_AUTH_TOKEN` definido, essas rotas exigem o header
  `Authorization: Bearer <API_AUTH_TOKEN>`. A comparação é feita com
  `secrets.compare_digest`, sem vazar tempo.
- Em desenvolvimento (`ENVIRONMENT=development`, padrão), sem o token,
  continua liberado — igual ao comportamento original, para não atrapalhar
  o uso local.
- `/health` é a **única** rota sem autenticação: o Render precisa dela para
  decidir se o serviço está vivo.
- O token pode ser definido por variável de ambiente (recomendado em
  produção) **ou** pela tela `/config` — mas a tela em produção exige o
  token, então em produção defina por variável de ambiente.

### A interface web já envia o token

A tela de chat e a de configuração guardam o token no `sessionStorage` do
navegador e o enviam em todas as chamadas. Em produção, o primeiro acesso
pede o token no campo no topo da tela `/config`; o chat usa o mesmo valor.
Nada mais precisa ser feito no deploy.

### Sessões em produção

O id de sessão é assinado com o `API_AUTH_TOKEN`. Duas consequências
práticas:

- trocar o token (por exemplo, se suspeitar de vazamento) **invalida
  todas as conversas abertas**. Se o Render tiver reiniciado, as sessões
  antigas também deixam de valer, porque o segredo temporário do
  processo mudou. Não é um problema: o histórico é só em memória e já
  teria sido perdido de qualquer forma.
- chamar a API direto exige pedir uma sessão primeiro. Veja o exemplo no
  README, seção 15.

## 1.1 Tela de configuração em produção

A tela `/config` grava as chaves em `.config.local.json`, na raiz do
projeto. Em produção isso **não substitui** os Secret Files do Render:

- variáveis de ambiente têm prioridade sobre o arquivo, por desenho;
- o Render não tem disco persistente, então o arquivo se perde a cada
  deploy.

Ou seja: **em produção, continue usando o painel do Render** (Secret Files
para `credentials.json`/`token.json`, e variáveis de ambiente para os
tokens). A tela é para uso local. A tela mostra exatamente essa
situação, marcando os campos com a etiqueta "vem do ambiente".

Vale o mesmo aviso de segurança do README: essa tela grava chaves de API,
por isso exige o token de acesso e falha fechada em produção.

## 2. Autenticação Google (`credentials.json` / `token.json`)

O fluxo `InstalledAppFlow.run_local_server()` abre um navegador — isso não
funciona num servidor headless como o Render. Por isso, a autorização
**continua sendo feita localmente**:

1. Rode `python main.py --auth` na sua máquina, normalmente.
2. Isso gera `token.json` local.
3. No painel do Render, vá em **Environment → Secret Files** e suba
   `credentials.json` e `token.json` nesses mesmos nomes (na raiz do
   working dir do serviço). O código já lê pelos caminhos configuráveis
   `GOOGLE_CREDENTIALS_FILE` / `GOOGLE_TOKEN_FILE`.
4. Como o token é de um app em modo de teste, ele expira em ~7 dias por
   padrão do Google — quando expirar, repita local e resuba o
   `token.json`. Para produção de verdade, mova o app para fora do modo de
   teste ("in production") na tela de consentimento OAuth do Google Cloud.

Nunca commite `credentials.json` nem `token.json` no git (já estão no
`.gitignore`).

## 3. Variáveis de ambiente no Render

Veja `render.yaml` — ele já declara todas. Resumo do que preencher no
painel (as marcadas `sync: false` no blueprint):

| Variável | Onde conseguir |
|---|---|
| `OLLAMA_BASE_URL` | URL do seu Ollama acessível pela internet (ver seção 0) |
| `NOTION_TOKEN` | notion.so/my-integrations |
| `NOTION_DATABASE_ID` | ID do banco no Notion |
| `MCP_SERVERS` | opcional, ver seção 4 |

`API_AUTH_TOKEN` é gerado automaticamente pelo Render na primeira vez
(`generateValue: true`); copie o valor gerado no painel para usar nas
chamadas.

## 4. Ferramentas MCP externas (opcional)

`config/mcp_config.py` carrega ferramentas de servidores MCP configurados
em `MCP_SERVERS` (JSON), usando `langchain-mcp-adapters`. Exemplo:

```env
MCP_SERVERS={"clima":{"transport":"streamable_http","url":"https://exemplo.com/mcp"}}
```

Se a variável estiver vazia (padrão), nada muda: o agente roda só com as
ferramentas nativas (Google/Gmail/Notion). Se um servidor MCP configurado
estiver fora do ar, o agente sobe normalmente e loga um aviso — ele não
trava a inicialização.

## 5. Subindo

### Opção A — Blueprint (`render.yaml`)

No painel do Render: **New → Blueprint**, aponte para o repositório. O
Render lê `render.yaml` e cria o serviço com as variáveis já listadas
(faltando você preencher as `sync: false`).

### Opção B — Web Service manual

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn web.server:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- Configure as variáveis de ambiente da tabela acima manualmente.

## 6. Rodando os testes antes de subir

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes não dependem de Ollama, Google ou Notion reais — tudo é mockado
(veja `tests/conftest.py`), inclusive a tela de configuração e o
`.config.local.json`, que é redirecionado para uma pasta temporária.

## 7. Checklist de segurança

O que este deploy faz por você, e o que fica com você:

- [x] Escopos OAuth mínimos: `gmail.readonly` e `gmail.compose` — o
      agente **não tem** permissão de enviar e-mail, mesmo que o modelo
      tente.
- [x] Segredos fora do git (`.gitignore` cobre `.env`, `token.json`,
      `credentials.json` e `.config.local.json`). O CI falha se algum
      deles for versionado por engano.
- [x] `.config.local.json` com permissão `0600` e gravação atômica.
- [x] Segredos write-only pela API: nenhum endpoint devolve o valor.
- [x] Comparação de token em tempo constante.
- [x] Ids de sessão assinados pelo servidor — um cliente não consegue
      ler a conversa de outro, e trocar o token invalida as sessões
      abertas.
- [x] Rate limit no chat (20 msg/min por IP).
- [x] Tela de configuração falha fechada em produção.
- [x] Conteúdo de e-mail/Notion tratado como dado, não como instrução
      (ver `SYSTEM_PROMPT`), contra prompt injection.
- [x] CI com lint, formatação, tipos e testes, bloqueando o merge.
- [ ] **Você:** o app do Google em modo de teste expira em ~7 dias. Mova
      para "in production" na tela de consentimento, senão o `token.json`
      precisa ser reenviado semanalmente.
- [ ] **Você:** o Ollama acessível pela internet **não tem autenticação**.
      Placing-o atrás de uma VPN ou proxy com senha é responsabilidade sua.
