import asyncio
import html as html_lib
import time
from functools import lru_cache
from pathlib import Path

import ipywidgets as widgets
from IPython.display import Markdown, display
from pygments import highlight
from pygments.filter import Filter
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.styles import get_style_by_name
from pygments.token import Generic, String
from pygments.util import ClassNotFound

_CODE_STYLE = "xcode"

_LANG_BY_SUFFIX = {
    ".py": "python",
    ".md": "markdown",
    ".sh": "bash",
    ".json": "json",
    ".js": "javascript",
    ".ts": "typescript",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
    ".csv": "",
}


def _lang_for(file_path: str) -> str:
    """Guess a Markdown fence language from a file path's extension."""
    return _LANG_BY_SUFFIX.get(Path(str(file_path)).suffix.lower(), "")


# Forced with !important so an IDE's injected theme CSS (JetBrains/VS Code often
# use !important to background code blocks) can't override the card and leave the
# syntax colors clashing. Fixed light card => readable under any editor theme.
_CARD_CSS = (
    "background:#ffffff !important; color:#1a1a1a !important; "
    "border:1px solid #d0d7de; border-radius:6px; "
    "padding:12px 14px; margin:8px 0; overflow-x:auto;"
)
_PRE_CSS = (
    "background:transparent !important; color:#1a1a1a !important; "
    "margin:0; line-height:1.45;"
)


class _FencedBlockFilter(Filter):
    """Retag a multi-line ``` block so it can be styled apart from inline code.

    The Markdown lexer emits `String.Backtick` for an inline `span` and for a whole
    fenced block alike, and most styles paint strings red - which turned a SKILL.md's
    "Output format" block into a wall of red prose, one span per line. Only the
    multi-line case is a block, so send it to its own token.
    """

    def filter(self, lexer, stream):  # noqa: A003 - Pygments' hook name
        for ttype, value in stream:
            if ttype is String.Backtick and "\n" in value:
                ttype = Generic.Output
            yield ttype, value


@lru_cache(maxsize=None)
def _markdown_style(name: str):
    """`name` with code rendered for reading: fenced blocks in plain ink, inline
    code tinted just enough to stay distinct from prose."""
    base = get_style_by_name(name)
    return type(
        f"{name}_markdown",
        (base,),
        {"styles": {**base.styles, Generic.Output: "#24292f", String.Backtick: "#0550ae"}},
    )


def _highlight(code: str, lang: str, style: str) -> str:
    """Syntax-highlight code to a self-contained HTML card (inline styles, no
    external CSS) that renders identically in JupyterLab, VS Code, JetBrains,
    nbviewer, and export, regardless of the surrounding editor theme."""
    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code)
    except ClassNotFound:
        lexer = get_lexer_by_name("text")
    if lexer.name.lower() == "markdown":
        # get_lexer_by_name hands back a fresh instance, so this filter is not global
        lexer.add_filter(_FencedBlockFilter())
        style = _markdown_style(style)
    formatter = HtmlFormatter(
        style=style, noclasses=True, cssstyles=_CARD_CSS, prestyles=_PRE_CSS
    )
    return highlight(code, lexer, formatter)


def _render_tool_use(block, *, fence_code: bool, code_style: str = _CODE_STYLE) -> str:
    """Render a tool_use block. When fence_code, show file content / shell
    commands as syntax-highlighted HTML blocks instead of a single inline blob."""
    name = block.get("name")
    args = block.get("input")
    if fence_code and isinstance(args, dict):
        if "file_path" in args and "content" in args:
            lang = _lang_for(args["file_path"])
            return f"🔧 **{name}**(`{args['file_path']}`)\n\n{_highlight(args['content'], lang, code_style)}"
        if "command" in args:
            return f"🔧 **{name}**\n\n{_highlight(args['command'], 'bash', code_style)}"
    return f"🔧 **{name}**(`{args}`)"


def render_content(content) -> str:
    """Flatten LangChain message content (str or list of blocks) to markdown."""
    if isinstance(content, str):
        return content

    parts = []
    for block in content:
        block_type = block.get("type")
        if block_type == "thinking":
            thought = block.get("thinking", "").strip()
            if thought:
                parts.append(f"> 🧠 *{thought}*")
        elif block_type == "text":
            parts.append(block.get("text", ""))
        elif block_type == "tool_use":
            parts.append(_render_tool_use(block, fence_code=False))
    return "\n\n".join(parts)


def render_content_with_code(content, code_style: str = _CODE_STYLE) -> str:
    """Like render_content, but renders file content and shell commands from
    tool calls as syntax-highlighted code blocks (e.g. a write_file's Python
    script). code_style is any Pygments style name (`pygmentize -L styles`)."""
    if isinstance(content, str):
        return content

    parts = []
    for block in content:
        block_type = block.get("type")
        if block_type == "thinking":
            thought = block.get("thinking", "").strip()
            if thought:
                parts.append(f"> 🧠 *{thought}*")
        elif block_type == "text":
            parts.append(block.get("text", ""))
        elif block_type == "tool_use":
            parts.append(_render_tool_use(block, fence_code=True, code_style=code_style))
    return "\n\n".join(parts)


def pretty_print(result) -> None:
    for message in result["messages"]:
        role = message.type.capitalize()
        body = render_content(message.content)
        if body.strip():
            display(Markdown(f"### {role}\n\n{body}"))


def pretty_print_with_code(result, code_style: str = _CODE_STYLE) -> None:
    """pretty_print, but with syntax-highlighted code blocks for the file
    content and shell commands the agent writes (nicer for coding agents).

    code_style is any Pygments style name, e.g. "friendly" (light) or "monokai"
    (dark). Run `pygmentize -L styles` to list available styles.
    """
    for message in result["messages"]:
        role = message.type.capitalize()
        body = render_content_with_code(message.content, code_style=code_style)
        if body.strip():
            display(Markdown(f"### {role}\n\n{body}"))


def print_exchange(result) -> None:
    """Print just the first human message and the final AI response."""
    messages = result["messages"]
    first_human = next((m for m in messages if m.type == "human"), None)
    last_ai = next((m for m in reversed(messages) if m.type == "ai"), None)

    for label, message in (("Human", first_human), ("Ai", last_ai)):
        if message is None:
            continue
        body = render_content(message.content)
        if body.strip():
            display(Markdown(f"### {label}\n\n{body}"))


def print_last_exchange(result) -> None:
    """Print the most recent human turn and the final AI response.

    Use this when several turns share one thread (e.g. an ongoing async-subagent
    session): print_exchange always shows the *first* human message, whereas here
    we want the human message from the current turn.
    """
    messages = result["messages"]
    last_human = next((m for m in reversed(messages) if m.type == "human"), None)
    last_ai = next((m for m in reversed(messages) if m.type == "ai"), None)

    for label, message in (("Human", last_human), ("Ai", last_ai)):
        if message is None:
            continue
        body = render_content(message.content)
        if body.strip():
            display(Markdown(f"### {label}\n\n{body}"))


def _truncate(text: str, max_len: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_len else text[:max_len] + "…"


def _summarize_args(args: dict, max_len: int) -> str:
    if "file_path" in args:
        summary = f"`{args['file_path']}`"
        if "content" in args:
            summary += f", content=“{_truncate(str(args['content']), max_len)}”"
        return summary
    return _truncate(str(args), max_len)


def print_activity(
    agent, user_input, config=None, show_results=True, max_len=80, title="Activity timeline"
) -> None:
    """Stream a deep-agent run and render a supervisor-vs-subagent action timeline.

    A subagent's tool calls (e.g. write_file) run inside an isolated subgraph and
    never appear in the supervisor's returned messages. Streaming with
    subgraphs=True is the only way to observe the subagent actually doing the work.
    """
    if isinstance(user_input, str):
        user_input = {"messages": [{"role": "user", "content": user_input}]}

    lines = [f"### {title}", ""]
    subagent_names: dict[str, str] = {}
    pending_subagent = None

    def label(ns) -> str:
        if not ns:
            return "🧑‍✈️ **supervisor**"
        ns_id = ns[-1]
        if ns_id not in subagent_names:
            subagent_names[ns_id] = pending_subagent or "subagent"
        return f"🤖 **{subagent_names[ns_id]}**"

    for ns, update in agent.stream(
        user_input, config=config, stream_mode="updates", subgraphs=True
    ):
        indent = "    " * len(ns)
        for payload in (update or {}).values():
            messages = payload.get("messages", []) if isinstance(payload, dict) else []
            for message in messages:
                for tool_call in getattr(message, "tool_calls", None) or []:
                    name = tool_call["name"]
                    if name == "task":
                        pending_subagent = tool_call["args"].get("subagent_type", "subagent")
                        lines.append(f"{indent}- {label(ns)} → 📨 delegates via **task** to `{pending_subagent}`")
                    else:
                        args = _summarize_args(tool_call["args"], max_len)
                        lines.append(f"{indent}- {label(ns)} → 🔧 **{name}**({args})")
                if show_results and message.__class__.__name__ == "ToolMessage":
                    result = _truncate(str(message.content), max_len)
                    lines.append(f"{indent}- {label(ns)} ← 📥 `{message.name}` → {result}")
    display(Markdown("\n".join(lines)))


_TODO_MARKERS = {"pending": "☐", "in_progress": "▶", "completed": "☑"}


def print_todos(result) -> None:
    """Render the agent's todo list as a human-readable checklist."""
    todos = result.get("todos", [])
    if not todos:
        display(Markdown("*No todos.*"))
        return

    lines = ["### Todo list", ""]
    for todo in todos:
        status = todo["status"]
        marker = _TODO_MARKERS.get(status, "•")
        content = todo["content"]
        if status == "completed":
            content = f"~~{content}~~"
        label = status.replace("_", " ")
        lines.append(f"- {marker} {content} — *{label}*")
    display(Markdown("\n".join(lines)))


_STATUS_COLOR = {"pending": "#8a8a8a", "in_progress": "#1f6feb", "completed": "#2b8a3e"}

# Sizes are tuned for projecting the voice demo to a room — bump these if the audience
# is far back. Everything else scales from _PANEL_FONT.
_PANEL_FONT = 24        # base text; todo rows use this, searches a touch smaller
_PANEL_HEAD_FONT = 32   # the "Researching …" header line

# Fixed light card (like _CARD_CSS): stays readable under any editor/notebook theme.
_PANEL_CSS = (
    "background:#ffffff;color:#1a1a1a;border:2px solid #d0d7de;border-radius:10px;"
    "padding:18px 22px;margin:10px 0;font-family:-apple-system,Segoe UI,sans-serif;"
    f"font-size:{_PANEL_FONT}px;line-height:1.55;font-weight:600;"
)


class LiveActivityPanel:
    """A single widget that shows, in place, what a deep agent is doing *right now*.

    Built for live demos: while a blocking research call runs, the audience sees the
    coordinator's todo plan, delegation to a subagent, that subagent's own plan, and
    every web search stream in — plus a ticking elapsed timer so there is always
    motion even between tool calls. Drive it from a streamed run: call `start(topic)`
    before the run, feed it events (`plan` / `delegate` / `search`) as they arrive,
    and call `finish(report)` when done.
    """

    def __init__(self):
        self._widget = widgets.HTML(value="")
        display(self._widget)
        self._ticker: asyncio.Task | None = None
        self._reset("")

    def _reset(self, topic: str) -> None:
        self._topic = topic
        self._start = time.monotonic()
        self._done = False
        self._report = ""
        self._plans: dict[str, list] = {}            # scope label -> todos (insertion order)
        self._searches: list[tuple[str, str]] = []   # (scope label, query)

    # --- lifecycle ---------------------------------------------------------
    def start(self, topic: str) -> None:
        """Begin a run: reset state and start the elapsed-time heartbeat."""
        if self._ticker is not None:
            self._ticker.cancel()
        self._reset(topic)
        self._render()
        self._ticker = asyncio.create_task(self._tick())

    def finish(self, report: str = "") -> None:
        """End a run: stop the heartbeat and freeze the panel in its done state.

        Idempotent, so a defensive call during session cleanup can't clobber a run
        that already finished normally (and reported its char count)."""
        if self._done:
            return
        self._report = report
        self._done = True
        if self._ticker is not None:
            self._ticker.cancel()
            self._ticker = None
        self._render()

    async def _tick(self) -> None:
        try:
            while not self._done:
                self._render()
                await asyncio.sleep(1)  # keep the elapsed timer moving between events
        except asyncio.CancelledError:
            pass

    # --- event sink (fed by the streamed run) ------------------------------
    def plan(self, scope: str, todos: list) -> None:
        """Record the latest todo list for a scope ("coordinator" or a subagent name)."""
        self._plans[scope] = todos
        self._render()

    def delegate(self, subagent: str) -> None:
        """Record that the coordinator handed work to a subagent."""
        self._plans.setdefault(subagent, [])
        self._render()

    def search(self, scope: str, query: str) -> None:
        """Record a web search issued within a scope."""
        self._searches.append((scope, query))
        self._render()

    # --- rendering ---------------------------------------------------------
    def _render(self) -> None:
        self._widget.value = self._build_html()

    def _scope_block(self, scope: str, todos: list) -> str:
        esc = html_lib.escape
        label_text = "🧑‍✈️ coordinator" if scope == "coordinator" else f"📨 delegated → 🤖 {esc(scope)}"
        label = f"<div style='font-size:{_PANEL_FONT + 2}px;font-weight:800;margin:10px 0 4px;'>{label_text}</div>"
        rows = []
        for todo in todos:
            status = todo.get("status", "pending")
            marker = _TODO_MARKERS.get(status, "•")
            content = esc(todo.get("content", ""))
            if status == "completed":
                content = f"<span style='opacity:.55;text-decoration:line-through;'>{content}</span>"
            color = _STATUS_COLOR.get(status, "#1a1a1a")
            rows.append(f"<div style='margin:5px 0 5px 30px;color:{color};'>{marker} {content}</div>")
        if rows:
            plan_html = "".join(rows)
        elif self._done:
            # Finished: no todos were ever recorded for this actor, so say nothing
            # rather than leave a progress word standing over a completed run.
            plan_html = ""
        else:
            # Live, but nothing to show yet. Only the coordinator is asked to plan;
            # a subagent that just searches never writes todos, so calling its state
            # "planning" would be a permanent lie.
            waiting = "planning…" if scope == "coordinator" else "working…"
            plan_html = f"<div style='margin-left:30px;color:#8a8a8a;'>{waiting}</div>"

        queries = [q for s, q in self._searches if s == scope]
        search_html = ""
        if queries:
            # Newest first so the latest query is always visible without scrolling.
            items = "".join(
                f"<div style='margin:3px 0 3px 30px;color:#555;font-size:{_PANEL_FONT - 3}px;'>🔧 {esc(q)}</div>"
                for q in reversed(queries)
            )
            search_html = (
                f"<div style='margin:6px 0 2px 30px;font-weight:800;'>searches ({len(queries)})</div>"
                f"<div style='max-height:260px;overflow:auto;'>{items}</div>"
            )
        return f"<div style='margin:10px 0;'>{label}{plan_html}{search_html}</div>"

    def _build_html(self) -> str:
        if not self._topic:
            return ""
        esc = html_lib.escape
        elapsed = int(time.monotonic() - self._start)
        if self._done:
            header = f"✅ Researched · {esc(self._topic)} <span style='color:#2b8a3e;'>done in {elapsed}s</span>"
        else:
            header = f"🔎 Researching · {esc(self._topic)} <span style='color:#1f6feb;'>⏳ {elapsed}s</span>"
        blocks = [f"<div style='font-size:{_PANEL_HEAD_FONT}px;font-weight:800;margin-bottom:12px;'>{header}</div>"]
        blocks += [self._scope_block(scope, todos) for scope, todos in self._plans.items()]
        if self._done and self._report:
            blocks.append(
                f"<div style='margin-top:12px;font-weight:800;color:#2b8a3e;'>🗣️ narrating ({len(self._report)} chars)…</div>"
            )
        return f"<div style='{_PANEL_CSS}'>" + "".join(blocks) + "</div>"


def _plain_text(content) -> str:
    """Concatenate only the text blocks of a message — no markdown, no thinking.

    render_content() is for display: it wraps thinking in a blockquote and renders
    tool calls. A report headed for a text-to-speech layer must carry neither.
    """
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content or ""


_NO_FINDINGS = "I couldn't find anything useful on that."

# Deep agents ship planning and filesystem tools of their own. The panel's activity
# lane is for the *research* work, so the built-ins are filtered out of it rather
# than the caller's search tool being hardcoded here by name.
_BUILTIN_TOOLS = frozenset(
    {"write_todos", "task", "ls", "read_file", "write_file", "edit_file", "glob", "grep"}
)


async def stream_report(agent, topic: str, panel: LiveActivityPanel | None = None) -> str:
    """Stream a deep-agent run into a LiveActivityPanel and return its final report.

    The async sibling of print_activity: the same astream(subgraphs=True) trick, but
    the events drive a panel live instead of a timeline printed after the fact, and
    the coordinator's last AI message comes back as plain text for a caller to speak.
    Events with an empty namespace `ns` are the coordinator's; a non-empty `ns` is a
    subagent's own subgraph — that is how each step is attributed to an actor.

    Owns the panel's lifecycle, including on cancellation, so a session torn down
    mid-research still stops the panel's heartbeat.
    """
    if panel is not None:
        panel.start(topic)

    report = ""
    current_subagent = None
    try:
        async for ns, update in agent.astream(
            {"messages": [{"role": "user", "content": topic}]},
            stream_mode="updates",
            subgraphs=True,
        ):
            scope = "coordinator" if not ns else (current_subagent or "subagent")
            for payload in (update or {}).values():
                messages = payload.get("messages", []) if isinstance(payload, dict) else []
                for message in messages:
                    for call in getattr(message, "tool_calls", None) or []:
                        name, args = call["name"], (call["args"] or {})
                        if name == "task":
                            current_subagent = args.get("subagent_type", "subagent")
                        if panel is None:
                            continue
                        if name == "write_todos":
                            panel.plan(scope, args.get("todos", []))
                        elif name == "task":
                            panel.delegate(current_subagent)
                        elif name not in _BUILTIN_TOOLS:
                            panel.search(scope, args.get("query") or _summarize_args(args, 80))
                    # The coordinator's own AI text is the spoken report; a subagent's
                    # findings are an intermediate result the coordinator rewrites.
                    if not ns and message.__class__.__name__ == "AIMessage":
                        text = _plain_text(message.content)
                        if text.strip():
                            report = text
        report = report or _NO_FINDINGS
    finally:
        if panel is not None:
            panel.finish(report)
    return report


def show_file(path, code_style: str = _CODE_STYLE, limit: int | None = None) -> None:
    """Render a file from disk as a syntax-highlighted card, headed by its path.

    Used to put the *actual* contents of a SKILL.md or AGENTS.md on screen next to
    the agent run that consumes it, so the audience reads the same bytes the agent does.
    """
    path = Path(path)
    text = path.read_text()
    if limit is not None:
        lines = text.splitlines()
        if len(lines) > limit:
            text = "\n".join(lines[:limit]) + f"\n… ({len(lines) - limit} more lines)"
    display(Markdown(f"**`{path}`**\n\n{_highlight(text, _lang_for(path.name), code_style)}"))


_TREE_SKIP = {"__pycache__", ".DS_Store", ".ipynb_checkpoints"}


def show_tree(root) -> None:
    """Render a directory as an indented tree — the layout of a skills library."""
    root = Path(root)
    display(Markdown(f"```\n{root.name}/\n{_tree_lines(root, '')}```"))


def _tree_lines(directory: Path, prefix: str) -> str:
    entries = sorted(
        (p for p in directory.iterdir() if p.name not in _TREE_SKIP),
        key=lambda p: (p.is_file(), p.name),
    )
    lines = []
    for i, entry in enumerate(entries):
        last = i == len(entries) - 1
        connector = "└── " if last else "├── "
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{prefix}{connector}{entry.name}{suffix}\n")
        if entry.is_dir():
            lines.append(_tree_lines(entry, prefix + ("    " if last else "│   ")))
    return "".join(lines)


def show_eval_code(result, code_style: str = _CODE_STYLE) -> None:
    """Render the JavaScript from every interpreter `eval` tool call in a run (or a message
    slice) as syntax-highlighted code cards. code_style is any Pygments style name."""
    messages = result["messages"] if isinstance(result, dict) else result
    blocks = []
    for message in messages:
        for call in (getattr(message, "tool_calls", None) or []):
            if call["name"] == "eval":
                code = (call["args"] or {}).get("code", "")
                blocks.append(_highlight(code, "javascript", code_style))
    display(Markdown("\n\n".join(blocks) or "*No eval calls.*"))
