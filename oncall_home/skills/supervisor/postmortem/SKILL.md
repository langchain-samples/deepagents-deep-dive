---
name: postmortem
description: >-
  Write the postmortem document for a resolved incident. Use when asked for a
  postmortem, an incident report, or a write-up after an incident is closed.
---

# postmortem

## Overview

The org-wide postmortem format. One document per incident, written after it closes.

## Instructions

Produce the document with these sections, in order:

1. `## Summary` — two sentences: what broke, who was affected.
2. `## Timeline` — one line per event, earliest first.
3. `## Root cause` — the technical cause.
4. `## Action items` — what we will change.

## Edge cases

- Missing timeline detail → list the gap explicitly rather than inferring times.
