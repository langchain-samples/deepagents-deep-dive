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
  - [Evaluations](#evaluations)
  - [Skills and AGENTS.md](#skills-and-agentsmd)
  - [Memory architecture](#memory-architecture)
  - [Sandboxes](#sandboxes)
  - [Interpreters and programmatic tool calling](#interpreters-and-programmatic-tool-calling)
  - [Async subagents](#async-subagents)
  - [Voice](#voice)
- [Repository layout](#repository-layout)

## Setup

### Prerequisites

- Python 3.13 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependency management
- `deepagents` >= 0.7 &mdash; task planning became opt-in in 0.7, and the notebooks are
  written against that behaviour

### Install

```bash
uv sync
uv run jupyter notebook
```

This starts the copy of Jupyter installed in the project's `.venv`, so the notebooks automatically
use the same environment as the project dependencies.

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
| `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`, `LANGSMITH_WORKSPACE_ID` | Tracing, evaluations, and the LangSmith sandbox backend |
| `TAVILY_API_KEY` | Web search in the async and voice notebooks |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Voice |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_REGION` | The S3 mount section of Sandboxes |
| `OPENAI_API_KEY` | The OpenAI half of the model comparison in Evaluations |

> **Note:** The AWS/S3 variables are only needed for the mount section of the Sandboxes notebook.
> Every other notebook runs without them.

## Notebooks

Suggested order — later notebooks assume the vocabulary of earlier ones.

| # | Notebook | Topic |
| --- | --- | --- |
| 1 | `deepagents-basics.ipynb` | Core anatomy of a deep agent |
| 2 | `deepagents-evals-v2.ipynb` | Offline evaluation with LangSmith |
| 3 | `deepagents-skills.ipynb` | Skills and `AGENTS.md` memory |
| 4 | `deepagents-memory-architecture.ipynb` | Routing memory by scope and owner |
| 5 | `deepagents-sandboxes.ipynb` | Executing real code safely |
| 6 | `deepagents-interpreters-ptc.ipynb` | Programmatic tool calling |
| 7 | `deepagents-async.ipynb` | Background subagents |
| 8 | `deepagents-voice.ipynb` | A realtime voice front end |

### Basics

`deepagents-basics.ipynb`

A deep agent is a regular agent plus subagents, a filesystem, and — since 0.7, only if you ask
for it — a TODO list. Opens on that opt-in: the same agent before and after
`middleware=[TodoListMiddleware()]`, then a plan that actually moves ☐ → ▶ → ☑. Goes on to task
delegation, dictionary vs. compiled subagents, and the backend family — default (thread-scoped
state), `StoreBackend`, `FilesystemBackend`, and `CompositeBackend` — closing on context isolation
and context-management techniques.

### Evaluations

`deepagents-evals-v2.ipynb`

A support-triage agent turns one convincing demo into a repeatable offline LangSmith experiment. A
supervisor delegates each ticket to a specialist that reads a fixed policy and writes
`/triage.json`; the supervisor reads that file back and reports a line for the on-call engineer.
Two agents, two artifacts — and that split is what the lesson turns on, because each one needs
a different kind of evaluator. `schema_valid` and `triage_accuracy` are ordinary code grading the
JSON; `summary_quality` is an LLM judge asking whether the prose still says what the file says.

The same dataset and evaluators then run twice, once on `claude-haiku-4-5-20251001` and once on
OpenAI's `gpt-5.4-mini`, with the judge pinned to one model so the two runs stay comparable. Four of
the six tickets are written so the surface phrasing points at the wrong answer — a safety
question that is not a security incident, a failed payment delivered as an angry bug report —
and each carries metadata marking it, so an experiment can be grouped by `trap` in the LangSmith UI.

> The comparison comes back flat: both models score alike. The notebook treats that as a result
> rather than a bug, which is the point — an experiment that finds no difference has still
> answered its question.

### Skills and AGENTS.md

`deepagents-skills.ipynb`

Two opposite ways to give an agent knowledge. **Skills** are folders loaded only when a task matches,
via three levels of progressive disclosure: frontmatter at startup, the `SKILL.md` body on
activation, and `references/` only when the body points at them. **`AGENTS.md`** is memory injected
into every prompt. Built around an on-call assistant that delegates alerts to a triage specialist,
and demonstrates that subagents inherit neither skills nor memory — plus a writable `notes.md` whose
correction survives across threads, processes, and agent objects.

### Memory architecture

`deepagents-memory-architecture.ipynb`

Where Skills covers *what* to give an agent, this covers *where it lives and who owns it*.
One agent, one filesystem, three memory types routed by `CompositeBackend` to different
backends: per-user preferences, an org-wide policy file the agent is blocked from editing,
and per-user skills — with anything unmatched falling through to thread-scoped state. Each
property is proved against the store rather than the model's say-so: Alice and Bob never
see each other's memory, a write to `/policies/` is refused by the harness even when the
prompt does not forbid it, and a preference mentioned in passing survives into a brand-new
thread.

> Note the routing gotcha it documents: `CompositeBackend` **strips** the route prefix
> before handing the key to the backend, so `/memories/preferences.md` is stored under
> `/preferences.md`. Seed the full path and reads miss silently.

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
narrates. Covers audio plumbing, the realtime loop, and server VAD with barge-in. This is the other
notebook that opts into `TodoListMiddleware`, for the reason the docs recommend it: the activity
panel is a progress UI streaming the coordinator's `todos` straight off agent state.

> **Note:** This notebook needs a working microphone and speaker, and installs `sounddevice`.

## Repository layout

```
├── deepagents-*.ipynb      # the deep-dive notebooks
├── async_agents/           # graph served to the async notebook
│   └── researcher.py
├── data/                   # dataset rows kept out of the notebooks
│   └── support_tickets.jsonl  # the evals dataset, one example per line
├── oncall_home/            # fixtures for the skills notebook
│   ├── AGENTS.md           #   always-loaded conventions
│   ├── memory/notes.md     #   writable learned preferences
│   └── skills/             #   per-agent skill sources
├── util/                   # notebook helpers (not part of the lesson)
│   ├── pretty.py           #   activity timelines, exchanges, file/tree/store display
│   ├── skills.py           #   skill and memory catalogs
│   ├── stats.py            #   token and tool-call stats
│   ├── charts.py           #   comparison bars
│   ├── voice.py            #   mic and speaker streams
│   └── triage_dataset.py   #   loads (and policy-checks) the evals dataset
├── images/                 # rendered notebook artifacts
└── langgraph.json          # graph config for `langgraph dev`
```

`util/` exists to keep the notebooks readable — the rendering helpers live there so each cell shows
the Deep Agents API and nothing else. `triage_dataset.py` is there for the same reason: it loads the
rows from `data/`, and checks on the way that every reference answer still follows from the policy
the agent is handed, so a dataset edit cannot quietly disagree with the policy.
