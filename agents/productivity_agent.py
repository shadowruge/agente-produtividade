from datetime import datetime
from zoneinfo import ZoneInfo

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

from config.settings import get_settings
from tools import ALL_TOOLS

SYSTEM_PROMPT = """Você é um assistente de produtividade pessoal. Responda sempre em português do Brasil, de forma curta e direta.
Data e hora atuais: {hoje}.

Você tem ferramentas para Google Calendar, Gmail e Notion (e, se configuradas, ferramentas adicionais via MCP). Regras:
- Use as ferramentas para buscar informações reais; nunca invente eventos, e-mails ou páginas.
- Para e-mails, você só lê e cria RASCUNHOS. Nunca diga que enviou um e-mail.
- Antes de criar um evento ou nota, confirme com o usuário se faltar título, data ou horário.
- Se uma ferramenta falhar, explique o erro em uma frase e diga o que o usuário pode fazer."""

MAX_HISTORICO = 20


class ProductivityAgent:
    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        settings = get_settings()
        self._tz = ZoneInfo(settings.timezone)
        ferramentas = tools if tools is not None else ALL_TOOLS

        llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
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
            agent=create_tool_calling_agent(llm, ferramentas, prompt),
            tools=ferramentas,
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
        ferramentas_usadas = [acao.tool for acao, _ in resultado.get("intermediate_steps", [])]
        return {"resposta": resposta, "ferramentas": ferramentas_usadas}

    def limpar(self, sessao: str) -> None:
        self._historicos.pop(sessao, None)


async def criar_agente() -> ProductivityAgent:
    """Fábrica assíncrona: carrega as ferramentas nativas + MCP e monta o agente.

    Use esta função sempre que houver um event loop disponível (ex: no
    startup do servidor web). O construtor `ProductivityAgent()` sozinho
    continua funcionando (modo --cli), só que sem as ferramentas MCP.
    """
    from tools import get_all_tools

    ferramentas = await get_all_tools()
    return ProductivityAgent(tools=ferramentas)
