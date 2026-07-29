# Deep Agents Deep Dive

A hands-on tour of [Deep Agents](https://github.com/langchain-ai/deepagents) built as a series of
runnable Jupyter notebooks. Each notebook is self-contained and most close with a recap, so you can
work straight through or jump to the topic you care about.

## Table of Contents

- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Install](#install)
  - [Environment variables](#environment-variables)
- [Notebooks](#notebooks)
  - [Basics](#basics)
  - [Skills and AGENTS.md](#skills-and-agentsmd)
  - [Sandboxes](#sandboxes)
  - [Interpreters and programmatic tool calling](#interpreters-and-programmatic-tool-calling)
  - [Async subagents](#async-subagents)
  - [Voice](#voice)
- [Repository layout](#repository-layout)

## Setup

### Prerequisites

- Python 3.13 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependency management

### Install

```bash
uv sync
```

Then point your notebook kernel at the project's `.venv`.

### Environment variables

Copy `.env.example` to `.env` and fill in the keys you need:

```bash
cp .env.example .env
```

Every notebook calls `load_dotenv(override=True)`, so `.env` wins over anything already exported in
your shell — edit it mid-session and the change takes effect on the next run.

| Variable | Needed by |
| --- | --- |
| `ANTHROPIC_API_KEY` | All notebooks |
| `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`, `LANGSMITH_WORKSPACE_ID` | Tracing, and the LangSmith sandbox backend |
| `TAVILY_API_KEY` | Web search in the async and voice notebooks |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Voice |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_REGION` | The S3 mount section of Sandboxes |
| `OPENAI_API_KEY` | Optional, for swapping models |

> **Note:** The AWS/S3 variables are only needed for the mount section of the Sandboxes notebook.
> Every other notebook runs without them.

## Notebooks

Suggested order — later notebooks assume the vocabulary of earlier ones.

| # | Notebook | Topic |
| --- | --- | --- |
| 1 | `deepagents-basics.ipynb` | Core anatomy of a deep agent |
| 2 | `deepagents-skills.ipynb` | Skills and `AGENTS.md` memory |
| 3 | `deepagents-sandboxes.ipynb` | Executing real code safely |
| 4 | `deepagents-interpreters-ptc.ipynb` | Programmatic tool calling |
| 5 | `deepagents-async.ipynb` | Background subagents |
| 6 | `deepagents-voice.ipynb` | A realtime voice front end |

### Basics

`deepagents-basics.ipynb`

A deep agent is a regular agent plus a TODO list, subagents, and a filesystem. Covers the built-in
planning tool, task delegation, dictionary vs. compiled subagents, and the backend family —
default (thread-scoped state), `StoreBackend`, `FilesystemBackend`, and `CompositeBackend` — closing
on context isolation and context-management techniques.

### Skills and AGENTS.md

`deepagents-skills.ipynb`

Two opposite ways to give an agent knowledge. **Skills** are folders loaded only when a task matches,
via three levels of progressive disclosure: frontmatter at startup, the `SKILL.md` body on
activation, and `references/` only when the body points at them. **`AGENTS.md`** is memory injected
into every prompt. Built around an on-call assistant that delegates alerts to a triage specialist,
and demonstrates that subagents inherit neither skills nor memory — plus a writable `notes.md` whose
correction survives across threads, processes, and agent objects.

### Sandboxes

`deepagents-sandboxes.ipynb`

A sandbox backend gives the agent a real Linux box — filesystem, shell, package installs — behind a
boundary that protects the host, and adds the `execute` tool. A data-analysis agent cleans a
deliberately messy CSV and renders a chart by *actually running code*. The second half mounts an S3
bucket into the sandbox with `mount_config`, using a read-only input prefix and a writable output
prefix, and shows the write-back path: an ordinary shell redirect inside the box lands an object in
S3 with no `put_object` call.

### Interpreters and programmatic tool calling

`deepagents-interpreters-ptc.ipynb`

The same task solved twice — once with direct tool calling, once with programmatic tool calling —
then compared side by side on token count and tool-call volume, with the code the agent wrote shown
in full.

### Async subagents

`deepagents-async.ipynb`

Subagents that run in the background on an Agent Protocol server. Launching returns a task id
immediately so the supervisor stays responsive; five tools manage the lifecycle. Uses the graph in
`async_agents/researcher.py`, served via `langgraph.json`:

```bash
uv run langgraph dev
```

### Voice

`deepagents-voice.ipynb`

A realtime voice layer over a deep agent, driven straight from the `google-genai` Live API with no
web stack. The deep agent is exposed as a single `deep_research` tool that the voice model calls and
narrates. Covers audio plumbing, the realtime loop, and server VAD with barge-in.

> **Note:** This notebook needs a working microphone and speaker, and installs `sounddevice`.

## Repository layout

```
├── deepagents-*.ipynb      # the deep-dive notebooks
├── async_agents/           # graph served to the async notebook
│   └── researcher.py
├── oncall_home/            # fixtures for the skills notebook
│   ├── AGENTS.md           #   always-loaded conventions
│   ├── memory/notes.md     #   writable learned preferences
│   └── skills/             #   per-agent skill sources
├── util/                   # notebook helpers (not part of the lesson)
│   ├── pretty.py           #   activity timelines, exchanges, file/tree display
│   ├── skills.py           #   skill and memory catalogs
│   ├── stats.py            #   token and tool-call stats
│   ├── charts.py           #   comparison bars
│   └── voice.py            #   mic and speaker streams
├── images/                 # rendered notebook artifacts
└── langgraph.json          # graph config for `langgraph dev`
```

`util/` exists to keep the notebooks readable — the rendering helpers live there so each cell shows
the Deep Agents API and nothing else.
