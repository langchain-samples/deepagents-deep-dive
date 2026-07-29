"""Inspect what the skills and memory middleware actually put in the system prompt.

Progressive disclosure is invisible from the outside: the agent just answers. These
helpers make the two teachable layers visible — the level-1 metadata injected at
startup, and the AGENTS.md text injected verbatim — so a workshop can show the
prompt the agent was really given.

They reach into `SkillsMiddleware` / `MemoryMiddleware` internals to render the
same strings the middleware builds, rather than re-implementing the formatting and
risking drift from the real behavior.
"""

from IPython.display import Markdown, display

from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.skills import SkillsMiddleware, _list_skills

from util.pretty import _highlight


def load_skill_metadata(backend, sources) -> list[dict]:
    """Level-1 metadata for every skill across `sources`, merged the way the
    middleware merges it: later sources win on a name collision."""
    merged: dict[str, dict] = {}
    for source in sources:
        path = source[0] if isinstance(source, tuple) else source
        for skill in _list_skills(backend, path):
            merged[skill["name"]] = skill
    return list(merged.values())


def show_skills(backend, sources) -> None:
    """Render the skills section of the system prompt: the source list plus the
    name/description of each discovered skill, with the path that won."""
    middleware = SkillsMiddleware(backend=backend, sources=sources)
    skills = load_skill_metadata(backend, sources)
    body = (
        f"{middleware._format_skills_locations()}\n\n"
        f"**Available Skills:**\n\n{middleware._format_skills_list(skills)}"
    )
    display(Markdown(f"# Progressive Disclosure: Level 1 (injected at startup)\n\n{body}"))


def show_memory(backend, sources) -> None:
    """Render the memory block the way MemoryMiddleware assembles it, with HTML
    comments stripped exactly as the middleware strips them."""
    middleware = MemoryMiddleware(backend=backend, sources=list(sources))
    contents = {}
    for path, response in zip(sources, backend.download_files(list(sources)), strict=True):
        if response.error is None and response.content is not None:
            contents[path] = response.content.decode("utf-8")
    block = middleware._format_agent_memory(contents, "{agent_memory}")
    display(Markdown(f"# AGENTS.md: injected every turn\n\n{_highlight(block, 'markdown', 'xcode')}"))
