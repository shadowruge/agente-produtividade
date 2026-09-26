# Agente de Produtividade

Assistente pessoal que roda um modelo de IA local (via [Ollama](https://ollama.com)) e consulta/organiza **Google Calendar**, **Gmail** e **Notion** através de uma interface de chat web. Não depende de nenhuma API paga de IA — o modelo roda na sua máquina.

- 📅 Consulta e cria eventos no Google Calendar
- 📧 Lê e-mails e cria **rascunhos** no Gmail (nunca envia sozinho)
- 📝 Busca e cria notas em um banco de dados do Notion
- 💬 Interface web de chat, com histórico por sessão
- ⚙️ Tela de configuração para chaves de API, ferramentas e skills — sem precisar mexer no `.env`

---

## Sumário

1. [Pré-requisitos](#1-pré-requisitos)
2. [Instalar o Python](#2-instalar-o-python)
3. [Baixar e preparar o projeto](#3-baixar-e-preparar-o-projeto)
4. [Instalar e configurar o Ollama](#4-instalar-e-configurar-o-ollama)
5. [Configurar o Google (Calendar e Gmail)](#5-configurar-o-google-calendar-e-gmail)
6. [Configurar o Notion](#6-configurar-o-notion)
7. [Configurando pela tela web](#7-configurando-pela-tela-web)
8. [Arquivo `.env` completo](#8-arquivo-env-completo)
9. [Rodando o agente](#9-rodando-o-agente)
10. [Usando o chat](#10-usando-o-chat)
11. [Ferramentas e skills](#11-ferramentas-e-skills)
12. [Acesso de outros computadores na rede](#12-acesso-de-outros-computadores-na-rede)
13. [Estrutura do projeto](#13-estrutura-do-projeto)
14. [Notas de versão](#14-notas-de-versão)
15. [Solução de problemas](#15-solução-de-problemas)
16. [Rodando os testes e as verificações](#16-rodando-os-testes-e-as-verificações)

---

## 1. Pré-requisitos

- Um computador Linux ou Windows com pelo menos 8 GB de RAM (o modelo de IA local consome memória).
- Uma conta Google (Gmail/Calendar).
- Uma conta Notion (gratuita já serve).
- Conexão com a internet (para autorizar Google/Notion e baixar dependências; depois de configurado, o modelo de IA roda offline).

---

## 2. Instalar o Python

O projeto precisa do **Python 3.11 ou superior**.

### Linux (Debian/Ubuntu e derivados)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 --version
```

Deve mostrar `Python 3.11.x` ou mais recente. Se a versão do repositório da sua distribuição for mais antiga, use o [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) (Ubuntu) ou instale via [pyenv](https://github.com/pyenv/pyenv).

### Windows

1. Baixe o instalador em [python.org/downloads](https://www.python.org/downloads/) (versão 3.11 ou superior).
2. Ao abrir o instalador, **marque a caixa "Add python.exe to PATH"** na primeira tela — esse é o passo que mais gera problema quando esquecido.
3. Clique em **Install Now**.
4. Abra o **PowerShell** (ou Prompt de Comando) e confirme:
   ```powershell
   python --version
   ```
   Se aparecer "python não é reconhecido", reinicie o terminal; se persistir, reinstale marcando a opção do PATH.

> Nos comandos deste README, `python3` é usado para Linux e `python` para Windows. Ajuste conforme o seu sistema.

---

## 3. Baixar e preparar o projeto

Extraia o projeto em uma pasta de sua preferência e entre nela pelo terminal.

### Linux

```bash
cd agente-produtividade
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
cd agente-produtividade
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Se o PowerShell bloquear a ativação do venv com um erro de "política de execução", rode uma vez:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

Em todos os comandos abaixo, o venv precisa estar ativado (o terminal mostra `(.venv)` no início da linha). Sempre que abrir um terminal novo, ative de novo com o comando `source .venv/bin/activate` (Linux) ou `.venv\Scripts\Activate.ps1` (Windows).

---

## 4. Instalar e configurar o Ollama

O Ollama roda o modelo de IA localmente.

1. Baixe em [ollama.com/download](https://ollama.com/download) (tem versão para Linux, Windows e Mac).
2. Instale seguindo o instalador padrão da sua plataforma.
3. Baixe o modelo usado pelo projeto:
   ```bash
   ollama pull qwen2.5:7b
   ```
4. No Linux, o Ollama geralmente já roda como serviço em segundo plano. Para checar:
   ```bash
   ollama list
   ```
   Se der erro de conexão, inicie manualmente com `ollama serve` em outro terminal.

No Windows, o Ollama roda como aplicativo com ícone na bandeja do sistema — basta ele estar aberto.

---

## 5. Configurar o Google (Calendar e Gmail)

### 5.1. Criar o projeto e ativar as APIs

1. Acesse [console.cloud.google.com](https://console.cloud.google.com) e crie um novo projeto (ex.: `agente-produtividade`).
2. Vá em **APIs e serviços → Biblioteca** e ative:
   - **Google Calendar API**
   - **Gmail API**

### 5.2. Configurar a tela de consentimento

1. Vá em **Google Auth Platform** (ou "Tela de consentimento OAuth", em consoles mais antigos).
2. Tipo de usuário: **Externo**.
3. Preencha nome do app, e-mail de suporte etc.
4. Em **Público-alvo → Usuários de teste**, adicione o seu próprio e-mail do Google (a conta que você vai usar no agente).

### 5.3. Criar as credenciais OAuth

1. Vá em **Credenciais → Criar credenciais → ID do cliente OAuth**.
2. Tipo de aplicativo: **App para computador (Desktop)**.
3. Baixe o JSON gerado.
4. Renomeie o arquivo para `credentials.json` e coloque na **raiz do projeto** (ao lado do `main.py`).

### 5.4. Autorizar o agente

Com o venv ativado:

```bash
python main.py --auth
```

O navegador vai abrir. Como o app está em modo de teste, o Google mostra um aviso de "app não verificado" — isso é esperado, pois o app é seu; clique em **Avançado → Acessar (não seguro)** e conceda as permissões.

Isso gera um arquivo `token.json` na raiz do projeto — não é preciso rodar `--auth` de novo, a menos que o token expire (apps em teste expiram em ~7 dias; nesse caso apague o `token.json` e rode `--auth` outra vez).

---

## 6. Configurar o Notion

### 6.1. Criar a integração

1. Acesse [notion.so/my-integrations](https://www.notion.so/my-integrations) e clique em **Nova integração**.
2. Escolha o workspace correto (se você tiver mais de um) e dê um nome.
3. Copie o **segredo da integração** — vai ser o `NOTION_TOKEN`.

### 6.2. Criar o banco de dados

1. No Notion, crie uma página com uma **Tabela** (banco de dados).
2. Anote o nome da coluna de título (aparece como `Nome`, `Name` ou `Título`, dependendo do idioma do seu workspace) — isso vai para `NOTION_TITLE_PROP`.

### 6.3. Compartilhar o banco com a integração

No banco de dados, clique em **⋯** (canto superior direito) → **Conexões** → selecione a integração criada. Sem esse passo, a API retorna erro mesmo com token e ID corretos.

### 6.4. Pegar o ID do banco

Abra o banco no navegador. A URL tem este formato:

```
https://www.notion.so/meu-workspace/1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d?v=...
```

O ID é o trecho de 32 caracteres logo antes do `?v=` — é isso que vai em `NOTION_DATABASE_ID`.

---

## 7. Configurando pela tela web

Em vez de editar o `.env` na mão, você pode configurar tudo pela interface:

```bash
python main.py
```

e abrir **`http://127.0.0.1:8000/config`** (ou clicar em *Configuração* na barra lateral do chat).

A tela tem quatro partes:

| Seção | O que você configura |
|---|---|
| **Modelo de IA** | Modelo do Ollama, URL e fuso horário |
| **Google** | Nomes dos arquivos `credentials.json` e `token.json` |
| **Notion** | Token do Notion, ID do banco e nome da coluna de título |
| **Segurança** | Token de acesso à API e origens do CORS |
| **Ferramentas** | Liga e desliga cada ferramenta (agenda, Gmail, Notion) |
| **Skills** | Instruções extras injetadas no system prompt do agente |

### Onde as chaves ficam salvas

Num arquivo chamado **`.config.local.json`**, na raiz do projeto. Ele:

- **fica fora do git** (já está no `.gitignore`);
- é criado com **permissão `0600`** — só o seu usuário lê;
- é escrito de forma **atômica**, então nunca fica pela metade se o servidor cair no meio da gravação.

Para guardar as chaves na nuvem (Render), use o painel do Render: *Environment → Secret Files*. Nesse caso a tela não altera o valor — variáveis de ambiente têm prioridade, por desenho (ver a tabela de precedência abaixo).

### A tela nunca mostra uma chave de novo

Os campos de segredo (Notion token e token de acesso) são **write-only**: depois de salvos, aparecem em branco com a marca "Salvo neste arquivo". Não existe forma de ler o valor pela interface, nem pela API — `/api/config` responde apenas se o campo está configurado ou não.

Isso é proposital. Se a API devolvesse o valor, qualquer pessoa com acesso ao servidor leria suas chaves. Se você esquecer um valor, é só digitar o novo por cima.

> ⚠️ A tela de configuração é o ponto mais sensível do sistema: é ela que grava as chaves. Por isso ela exige o mesmo token de acesso do chat, e em produção (`ENVIRONMENT=production`) **recusa funcionar sem token** em vez de ficar aberta. Se a tela aparecer vazia, preencha o token de acesso lá em cima.

### Precedência dos valores

Quando o mesmo campo está definido em mais de um lugar, vale esta ordem (da mais forte para a mais fraca):

1. **Variáveis de ambiente** — é assim que o Render injeta as chaves em produção.
2. **`.config.local.json`** — o que você salvou na tela.
3. **`.env`** — o arquivo de texto, se existir.
4. **Padrões do código**.

Ou seja: a tela preenche o que o `.env` não define, mas **nunca sobrescreve uma variável de ambiente real**. Se você salvar um valor na tela e ele não mudar, quase sempre é porque existe uma variável de ambiente com o mesmo nome — a tela marca esses campos com a etiqueta "vem do ambiente".

Um detalhe importante: um campo em branco significa "não definido". Por isso `API_AUTH_TOKEN=` (vazio) no `.env` é o mesmo que não ter a variável — ele não bloqueia o chat local.

---

## 8. Arquivo `.env` completo

O `.env` é **opcional**. Se você configurar tudo pela tela, não precisa dele. Use se preferir manter as chaves em arquivo de texto, ou para fixar valores que a tela não deve alterar.

```bash
cp .env.example .env      # Linux
copy .env.example .env    # Windows
```

Os campos de segredo (`NOTION_TOKEN`, `API_AUTH_TOKEN`) podem ficar vazios — a tela preenche. O `.env.example` já vem com tudo comentado, então copie e edite só o que quiser:

```env
# Ollama
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://localhost:11434

# Fuso horário usado na agenda
TIMEZONE=America/Sao_Paulo

# Google (arquivos ficam na raiz do projeto)
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json

# Notion
NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d
NOTION_TITLE_PROP=Título
```

O valor de `NOTION_TITLE_PROP` deve ser **exatamente** o nome da coluna de título do seu banco (sensível a maiúsculas/minúsculas e acentos).

---

## 9. Rodando o agente

### Interface web (padrão)

```bash
python main.py
```

Abra `http://127.0.0.1:8000` no navegador. A barra lateral mostra o status das três conexões (Ollama, Google, Notion) com um ponto verde ou vermelho.

### Chat no terminal

```bash
python main.py --cli
```

### Apenas autorizar o Google (sem abrir o chat)

```bash
python main.py --auth
```

---

## 10. Usando o chat

Exemplos de mensagens para testar cada integração:

| Mensagem | O que acontece |
|---|---|
| `O que tenho na agenda essa semana?` | Lista eventos do Google Calendar |
| `Marque uma reunião amanhã às 15h com o título Teste` | Cria um evento e retorna o link |
| `Resuma meus e-mails não lidos` | Lista remetente/assunto dos e-mails |
| `Crie um rascunho para alguem@exemplo.com com assunto Teste e corpo Isso é um teste` | Cria um rascunho no Gmail (não envia) |
| `Anote no Notion: teste do agente` | Cria uma página no banco configurado |
| `Busque no Notion por teste` | Procura páginas pelo título |

O botão **Nova conversa** limpa o histórico da sessão atual.

### Sobre as sessões

Cada aba do navegador tem uma **sessão**, e o id dela é emitido e assinado pelo servidor (não é um `UUID` inventado no cliente). Isso tem duas consequências práticas:

- Um id de sessão **não é adivinhável**. Sem assinatura, qualquer cliente que descobrisse o id de outra pessoa leria o histórico dela — que é onde fica o que o agente descobriu da sua agenda e dos seus e-mails.
- Trocar o **token de acesso** invalida as sessões já abertas. Se você revogar o token, as conversas antigas param de responder, mesmo com o id em mãos.

O histórico é **só em memória**: fica no servidor enquanto ele roda e some quando ele reinicia. Não é guardado em disco em lugar nenhum.

> Isto **não** é autenticação multiusuário. Com um único token compartilhado, todos que o conhecem continuam sendo o mesmo usuário. Para isolar usuários de verdade seria preciso login com contas — o que muda a natureza do projeto, hoje feito para uma pessoa só.

> Se você definiu um token de acesso, cole-o em **Configuração** uma vez. O chat e a tela de configuração compartilham o mesmo token, guardado no `sessionStorage` do navegador — não é preciso digitar de novo a cada acesso.

---

## 11. Ferramentas e skills

As duas coisas se ajustam na tela de configuração (`/config`).

### Ferramentas

Cada ferramenta pode ser ligada e desligada. Desmarque, por exemplo, **Criar evento** se você quer que o agente só *consulte* a agenda e nunca escreva nela. O filtro vale também para as ferramentas vindas de servidores MCP.

Ferramentas disponíveis:

| Ferramenta | O que faz |
|---|---|
| `listar_eventos` | Lista eventos da agenda |
| `criar_evento` | Cria eventos |
| `listar_emails` | Lista e-mails |
| `ler_email` | Lê o conteúdo de um e-mail |
| `criar_rascunho` | Cria rascunhos (nunca envia) |
| `buscar_notion` | Busca páginas no Notion |
| `criar_nota` | Cria notas no banco do Notion |

> ⚠️ **Desligar ferramentas é o controle mais forte que você tem.** O prompt do agente diz para confirmar antes de criar algo, mas um modelo pequeno rodando local pode não seguir a instrução à risca. Se você quer garantia, não dê a ferramenta a ele.

### Skills

Skills são instruções extras injetadas no system prompt do agente — a forma de adaptar o comportamento dele sem mexer no código. Cada skill tem um nome e um texto.

Exemplos que funcionam bem:

| Nome | Instrução |
|---|---|
| Agenda | Antes de criar qualquer evento, mostre dia, hora e título e espere eu confirmar. |
| E-mails | Nunca resuma mais de 5 e-mails por vez. Sempre comece pelo remetente. |
| Agenda | Ao listar eventos, agrupe por dia e diga quantos dias livres há. |
| Idioma | Se eu escrever em inglês, responda em inglês. |
| Notion | Prefira títulos curtos, no máximo 6 palavras. |

Para remover uma skill, apague o texto dela e salve — a skill com instrução vazia é descartada.

---

## 12. Acesso de outros computadores na rede

Por padrão, o servidor só aceita conexões da própria máquina (`127.0.0.1`). Para acessar de outro computador **na mesma rede local**:

1. Descubra o IP da máquina que roda o agente:
   ```bash
   hostname -I        # Linux
   ipconfig            # Windows (veja "Endereço IPv4")
   ```
2. Suba o servidor escutando em todos os IPs:
   ```bash
   python main.py --host 0.0.0.0
   ```
3. Nos outros dispositivos da mesma rede, acesse `http://SEU_IP:8000`.

> ⚠️ **Atenção:** por padrão o servidor não tem senha, e **qualquer dispositivo que acessar esse endereço consegue ler seus e-mails, mexer na agenda, criar notas no Notion e alterar a configuração do agente** (inclusive as chaves). Use apenas em redes de confiança (ex.: Wi-Fi doméstico).

> Para uso em rede compartilhada ou na internet, **defina um token de acesso** em Configuração → *Segurança* (rode `openssl rand -hex 32`). Ele é guardado no navegador de cada dispositivo, então cada um precisa colar o token uma vez. Para acesso pela internet, prefira uma VPN como o [Tailscale](https://tailscale.com).

---

## 13. Estrutura do projeto

```
agente-produtividade/
│
├── config/
│   ├── settings.py         # Configuração central (Settings) e precedência de valores
│   ├── secrets_store.py    # Leitura/gravação do .config.local.json (tela de config)
│   ├── google_auth.py      # Autenticação OAuth do Google
│   ├── notion_config.py    # Cliente e configuração do Notion
│   └── mcp_config.py       # Carregamento opcional de ferramentas MCP
│
├── tools/
│   ├── google_calendar.py  # Ferramentas de agenda (listar/criar eventos)
│   ├── gmail.py            # Ferramentas de e-mail (ler, listar, criar rascunho)
│   └── notion_tools.py     # Ferramentas do Notion (buscar, criar nota)
│
├── agents/
│   └── productivity_agent.py  # Monta o agente (LLM + ferramentas + skills + histórico)
│
├── web/
│   ├── server.py           # API FastAPI (chat, status, reset, config)
│   └── static/
│       ├── index.html      # Interface de chat
│       └── config.html     # Tela de configuração
│
├── config/
│   ├── settings.py         # Configuração central (Settings) e precedência de valores
│   ├── secrets_store.py    # Leitura/gravação do .config.local.json (tela de config)
│   ├── sessoes.py          # Ids de sessão assinados (impede ler a conversa de outro)
│   ├── google_auth.py      # Autenticação OAuth do Google
│   ├── notion_config.py    # Cliente e configuração do Notion
│   └── mcp_config.py       # Carregamento opcional de ferramentas MCP
│
├── tools/
│   ├── google_calendar.py  # Ferramentas de agenda (listar/criar eventos)
│   ├── gmail.py            # Ferramentas de e-mail (ler, listar, criar rascunho)
│   └── notion_tools.py     # Ferramentas do Notion (buscar, criar nota)
│
├── agents/
│   └── productivity_agent.py  # Monta o agente (LLM + ferramentas + skills + histórico)
│
├── web/
│   ├── server.py           # API FastAPI (chat, status, reset, sessão, config)
│   └── static/
│       ├── index.html      # Interface de chat
│       └── config.html     # Tela de configuração
│
├── tests/                  # 121 testes (não precisam de Ollama, Google ou Notion)
│
├── .github/workflows/      # CI: lint, formatação, tipos, testes
├── pyproject.toml          # Config do ruff e do mypy
├── .env                    # Config opcional em texto (não versionar)
├── .env.example            # Modelo do .env
├── .config.local.json      # Config da tela (não versionar, permissão 0600)
├── requirements.txt
└── main.py                 # Ponto de entrada (web, --cli, --auth)
```

---

## 14. Notas de versão

### LangChain 1.x

O projeto usa a API `create_agent` do LangChain 1.x. A API anterior
(`AgentExecutor` + `create_tool_calling_agent`) foi removida no 1.0, e o
antigo teto `langchain<1.0` no `requirements.txt` deixou de ser necessário.

O que mudou de verdade, além dos nomes:

- **A data no prompt.** Em 0.x o prompt era um template com `{hoje}`
  preenchido a cada chamada. Em 1.x o `system_prompt` é uma string fixa
  na construção do agente — uma data escrita ali ficaria congelada até o
  próximo reinício. A solução é um middleware `dynamic_prompt`, que é
  reavaliado a cada turno (`montar_system_prompt`).
- **O limite de iterações.** `max_iterations=6` virou
  `ModelCallLimitMiddleware(run_limit=6)`. A diferença que importa: o
  `AgentExecutor` parava devolvendo uma resposta parcial, enquanto o
  LangGraph estoura uma exceção. O middleware devolve o comportamento
  gracioso — o usuário vê "Model call limits exceeded" em vez de um 500.
- **As ferramentas usadas.** Não existe mais `intermediate_steps`; o nome
  da ferramenta é lido de `tool_calls` nas mensagens devolvidas.
- **`handle_parsing_errors`** não tem equivalente. No 1.x o tratamento de
  tool call malformada é interno ao agente.
- **`langchain-community` saiu das dependências.** Nenhuma linha do
  projeto o importava, e ele traz uma árvore de dependências grande que
  só pesa no `pip install`.

Se for atualizar de uma versão futura, o ponto de atenção é
`create_agent`: ele é construído sobre o LangGraph, então mudanças de
middleware afetam este arquivo.

### Sessões assinadas

O id de sessão é `<nonce>.<assinatura HMAC>`, emitido por
`GET /api/sessao` e assinado com o `api_auth_token` (ou, em
desenvolvimento, um segredo aleatório do processo). Sem isso, um cliente
que copiasse o id de outro leria o histórico daquela conversa.

Dois detalhes que parecem exagerados e não são:

- **HMAC simples, sem PBKDF2.** Os nonces têm 192 bits de entropia, então
  adivinhá-los exigiria 2^192 tentativas. Um KDF caro aqui só serviria
  para dar a um cliente um vetor de negação de serviço (cada validação
  gastaria dezenas de ms de CPU, disparáveis à vontade).
- **Trocar o token invalida as sessões abertas.** É o que faz revogar o
  token realmente cortar o acesso a conversas que já existiam.

---

## 15. Solução de problemas

**A tela de configuração pede token mas eu não defini nenhum**
Acontece quando existe `API_AUTH_TOKEN=` (vazio) no `.env` **e** há um token salvo no `.config.local.json`. Apague a linha do `.env` — campo em branco significa "não definido". Para destravar, apague o arquivo `.config.local.json` e suba o servidor de novo.

**Salvei um valor na tela mas ele não mudou**
Existe uma variável de ambiente com o mesmo nome, e ela tem prioridade por desenho (é assim que o Render injeta as chaves). A tela marca esses campos com a etiqueta "vem do ambiente". Remova a variável do `.env` ou do painel do Render para o valor da tela valer.

**Esqueci o token de acesso**
Os segredos são write-only por decisão de segurança — não dá para recuperá-los pela tela. Se o token da API for o esquecido, apague o `.config.local.json` e suba o servidor (o chat volta a ficar aberto, que é o padrão em desenvolvimento). Para o Notion, gere um novo em [notion.so/my-integrations](https://www.notion.so/my-integrations).

**`401` ao usar a API direto (curl, script)**
As rotas `/api/chat`, `/api/reset`, `/api/config`, `/api/sessao` e `/api/status` exigem o header `Authorization: Bearer <token>`. O `/health` é a única que não exige (o Render precisa dele).

Lembre que `/api/chat` e `/api/reset` também exigem uma **sessão válida**, emitida pelo servidor:

```bash
# 1. pegue o token de acesso (se você definiu um)
TOKEN="seu-token"

# 2. peça um id de sessão
SESSAO=$(curl -s http://127.0.0.1:8000/api/sessao \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; print(json.load(sys.stdin)['sessao'])")

# 3. converse
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"sessao\":\"$SESSAO\",\"mensagem\":\"oi\"}"
```

Um id inventado (`"sessao": "s1"`) é recusado com 401 — é o que impede que um cliente leia a conversa de outro.

**`429` — muitas mensagens seguidas**
Limite de 20 mensagens por minuto por IP, para uma enxurrada de pedidos não travar o chat. É só esperar um pouco.

**"Model call limits exceeded" na resposta**
O agente passou de 6 chamadas ao modelo numa mesma mensagem — normalmente um laço em que ele insiste numa ferramenta que falha. O sistema de proteção funcionou; vale verificar se alguma configuração (Notion, agenda) está com erro, porque é aí que costuma estar a causa. Se for um caso legítimo de muitas etapas, aumente `MAX_ITERACOES` em `agents/productivity_agent.py`.

**A conversa sumiu**
O histórico é só em memória. Ele some quando o servidor reinicia e quando você troca o token de acesso. Não há backup por desenho: é dado do seu e-mail e agenda, guardado em um arquivo em texto puro seria um risco maior.

**`FileNotFoundError: Arquivo credentials.json não encontrado`**
O arquivo baixado do Google Cloud não está na raiz do projeto, ou tem outro nome. Confira o passo [5.3](#53-criar-as-credenciais-oauth).

**Erro 403 (access_denied) ao autorizar no navegador**
Seu e-mail não está na lista de usuários de teste do app. Veja o passo [5.2](#52-configurar-a-tela-de-consentimento).

**`RefreshError: invalid_grant`**
O token expirou (apps em modo de teste duram ~7 dias). Apague `token.json` e rode `python main.py --auth` de novo.

**`notion_client.errors.APIResponseError: API token is invalid`**
O `NOTION_TOKEN` está errado, incompleto ou foi copiado de outra integração. Gere um novo em [notion.so/my-integrations](https://www.notion.so/my-integrations) → sua integração → **Segredos** → **Show**, e cole sem aspas nem espaços no `.env`.

**`KeyError: 'properties'` ao consultar o banco do Notion**
Já corrigido no projeto: o cliente do Notion é criado fixando `notion_version="2022-06-28"` em `config/notion_config.py`, para manter o formato de resposta esperado pelo restante do código.

**Notion diz `object_not_found`**
O banco de dados não foi compartilhado com a integração. Veja o passo [6.3](#63-compartilhar-o-banco-com-a-integração).

**Ponto do Ollama fica vermelho na interface**
O Ollama não está rodando. Rode `ollama serve` (Linux) ou abra o aplicativo do Ollama (Windows), e confirme que o modelo foi baixado com `ollama list`.

**A interface web não abre / "não consigo alcançar o servidor"**
Confirme que o `python main.py` está rodando e sem erros no terminal, e que você está acessando o endereço e a porta corretos (`http://127.0.0.1:8000` por padrão).

---

## 16. Rodando os testes e as verificações

```bash
pip install -r requirements-dev.txt
```

| Comando | O que faz |
|---|---|
| `pytest` | Roda a suíte |
| `ruff check .` | Procura erros de estilo e problemas comuns |
| `ruff format .` | Aplica o padrão de formatação |
| `mypy .` | Confere as anotações de tipo |

São **121 testes** e nenhum precisa de Ollama, Google ou Notion: as integrações são mockadas. A cobertura inclui a tela de configuração, a precedência de valores, as sessões assinadas, o limite de requisições, o filtro de ferramentas, as skills, a sincronização do histórico e o ciclo de tools do agente.

Os testes rodam isolados da sua máquina: o `.env` e o `.config.local.json` reais são ignorados (`tests/conftest.py` redireciona a configuração para uma pasta temporária), então rodar a suíte nunca mostra nem altera as suas chaves.

Tudo isso roda sozinho no **GitHub Actions** a cada push em `main` e em cada pull request (`.github/workflows/ci.yml`). Um workflow que falha bloqueia o merge — inclusive se alguém versionar um arquivo de segredo por engano, que é uma checagem explícita do CI.

### Sobre o lint

A configuração está no `pyproject.toml`, em `ruff format` e em `mypy`. Duas escolhas que valem explicação:

- **As linhas longas dentro de strings não são reformatadas.** O `SYSTEM_PROMPT` e as descrições das `@tool` vão literalmente para o modelo; quebrá-las mudaria o comportamento do agente. Por isso o `E501` (linha longa) está desligado.
- **O `mypy` é estrito no código de produção e permissivo nos testes.** Nos testes, anotar os dublês não agrega nada; exigir anotações só na produção evita ruído sem perder a proteção.
