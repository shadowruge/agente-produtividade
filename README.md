# Agente de Produtividade

Assistente pessoal que roda um modelo de IA local (via [Ollama](https://ollama.com)) e consulta/organiza **Google Calendar**, **Gmail** e **Notion** através de uma interface de chat web. Não depende de nenhuma API paga de IA — o modelo roda na sua máquina.

- 📅 Consulta e cria eventos no Google Calendar
- 📧 Lê e-mails e cria **rascunhos** no Gmail (nunca envia sozinho)
- 📝 Busca e cria notas em um banco de dados do Notion
- 💬 Interface web de chat, com histórico por sessão

---

## Sumário

1. [Pré-requisitos](#1-pré-requisitos)
2. [Instalar o Python](#2-instalar-o-python)
3. [Baixar e preparar o projeto](#3-baixar-e-preparar-o-projeto)
4. [Instalar e configurar o Ollama](#4-instalar-e-configurar-o-ollama)
5. [Configurar o Google (Calendar e Gmail)](#5-configurar-o-google-calendar-e-gmail)
6. [Configurar o Notion](#6-configurar-o-notion)
7. [Arquivo `.env` completo](#7-arquivo-env-completo)
8. [Rodando o agente](#8-rodando-o-agente)
9. [Usando o chat](#9-usando-o-chat)
10. [Acesso de outros computadores na rede](#10-acesso-de-outros-computadores-na-rede)
11. [Estrutura do projeto](#11-estrutura-do-projeto)
12. [Solução de problemas](#12-solução-de-problemas)

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

## 7. Arquivo `.env` completo

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env      # Linux
copy .env.example .env    # Windows
```

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

## 8. Rodando o agente

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

## 9. Usando o chat

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

---

## 10. Acesso de outros computadores na rede

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

> ⚠️ **Atenção:** o servidor não tem senha. Qualquer dispositivo que acessar esse endereço consegue ler seus e-mails, mexer na sua agenda e criar notas no Notion. Use isso apenas em redes de confiança (ex.: Wi-Fi doméstico). Para acesso pela internet (fora da rede local), não exponha a porta diretamente — prefira uma VPN como o [Tailscale](https://tailscale.com), e considere adicionar autenticação antes.

---

## 11. Estrutura do projeto

```
agente-produtividade/
│
├── config/
│   ├── google_auth.py      # Autenticação OAuth do Google
│   └── notion_config.py    # Cliente e configuração do Notion
│
├── tools/
│   ├── google_calendar.py  # Ferramentas de agenda (listar/criar eventos)
│   ├── gmail.py            # Ferramentas de e-mail (ler, listar, criar rascunho)
│   └── notion_tools.py     # Ferramentas do Notion (buscar, criar nota)
│
├── agents/
│   └── productivity_agent.py  # Monta o agente (LLM + ferramentas + histórico)
│
├── web/
│   ├── server.py           # API FastAPI (chat, status, reset)
│   └── static/index.html   # Interface web de chat
│
├── .env                     # Suas configurações (não versionar)
├── .env.example             # Modelo do .env
├── requirements.txt
└── main.py                  # Ponto de entrada (web, --cli, --auth)
```

---

## 12. Solução de problemas

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
