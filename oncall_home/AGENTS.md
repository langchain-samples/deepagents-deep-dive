# Acme on-call conventions

<!-- Curated by the team. The agent reads this every session and does not edit it.
     Things it learns go in /memory/notes.md instead. -->

## The service

Acme is a small SaaS team running one API and one web app. Two engineers are on
call at a time: primary and secondary.

## How we write incidents

- Timestamps in UTC, ISO 8601: `2026-07-27T14:32Z`. Never local time, never "2:32pm".
- Severity is always `SEV1` / `SEV2` / `SEV3`. Never "critical", "high", or "P1".
- Lead with impact, then cause, then action.

## Non-negotiables

- Never invent customer-impact numbers. If you don't have them, write `unknown`.
- Never name an individual as the cause of an incident. Name the change, not the person.
- Customer-facing messages are drafted for review, never sent.

## Where things live

- Runbooks: `/skills/supervisor/` (yours) and `/skills/triage/` (the triage specialist's).
- Learned preferences: `/memory/notes.md`. When we correct you, append it there
  with `edit_file` so it survives into later sessions.
- **This file is ours, not yours. Never call `edit_file` on `/AGENTS.md`** — not to
  record a correction, and not to keep anything here consistent with a new rule. If a
  correction makes something above look out of date, say so in `/memory/notes.md` and
  we will update this file ourselves.
