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
  servidor recusa subir as rotas `/api/chat` e `/api/reset` (erro 500
  explicando o motivo).
- Com `API_AUTH_TOKEN` definido, essas rotas exigem o header
  `Authorization: Bearer <API_AUTH_TOKEN>`.
- Em desenvolvimento (`ENVIRONMENT=development`, padrão), sem o token,
  continua liberado — igual ao comportamento original, para não atrapalhar
  o uso local.
- `web/static/index.html` (a interface web) ainda não envia esse header;
  se for usá-la em produção, adicione o campo do token ali (ou coloque o
  serviço atrás de algo como Cloudflare Access / Tailscale, como o README
  já sugeria).

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
(veja `tests/conftest.py`).
