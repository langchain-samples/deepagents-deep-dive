"""A travel-research subagent, served over the Agent Protocol by `langgraph dev`.

This is an ordinary compiled deep agent. What makes it an *async* subagent is
purely how the supervisor reaches it: over HTTP via the LangGraph SDK, as a
background run it can start, poll, update, and cancel — never blocking.

Do not compile with a checkpointer here: the LangGraph server injects its own
persistence for every served graph.
"""

from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient
from deepagents import create_deep_agent

load_dotenv(override=True)


@tool
def search(query: str) -> str:
    """Search the internet for information.

    Args:
        query (str): search query
    """
    results = TavilyClient().search(query)
    return results.get("results", [])


research_system_prompt = """You are a travel research assistant.
Use the search tool to investigate the destination or travel question.
Return a concise briefing with clear headings and inline citations.
Limit yourself to 3 search calls."""

graph = create_deep_agent(
    model="claude-haiku-4-5-20251001",
    system_prompt=research_system_prompt,
    tools=[search],
)
