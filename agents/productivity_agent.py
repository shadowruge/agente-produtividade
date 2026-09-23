import os
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama

from tools import ALL_TOOLS

SYSTEM_PROMPT = """Você é um assistente de produtividade pessoal. Responda sempre em português do Brasil, de forma curta e direta.
Data e hora atuais: {hoje}.

Você tem ferramentas para Google Calendar, Gmail e Notion. Regras:
- Use as ferramentas para buscar informações reais; nunca invente eventos, e-mails ou páginas.
- Para e-mails, você só lê e cria RASCUNHOS. Nunca diga que enviou um e-mail.
- Antes de criar um evento ou nota, confirme com o usuário se faltar título, data ou horário.
- Se uma ferramenta falhar, explique o erro em uma frase e diga o que o usuário pode fazer."""

MAX_HISTORICO = 20


class ProductivityAgent:
    def __init__(self) -> None:
        self._tz = ZoneInfo(os.getenv("TIMEZONE", "America/Sao_Paulo"))
        llm = ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.2:latest"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder("historico"),
                ("human", "{entrada}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        self._executor = AgentExecutor(
            agent=create_tool_calling_agent(llm, ALL_TOOLS, prompt),
            tools=ALL_TOOLS,
            max_iterations=6,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )
        self._historicos: dict[str, list] = {}

    def perguntar(self, sessao: str, mensagem: str) -> dict:
        historico = self._historicos.setdefault(sessao, [])
        resultado = self._executor.invoke(
            {
                "entrada": mensagem,
                "historico": historico,
                "hoje": datetime.now(self._tz).strftime("%A, %d/%m/%Y %H:%M"),
            }
        )
        resposta = resultado["output"]
        historico.extend([HumanMessage(mensagem), AIMessage(resposta)])
        del historico[:-MAX_HISTORICO]
        ferramentas = [acao.tool for acao, _ in resultado.get("intermediate_steps", [])]
        return {"resposta": resposta, "ferramentas": ferramentas}

    def limpar(self, sessao: str) -> None:
        self._historicos.pop(sessao, None)
