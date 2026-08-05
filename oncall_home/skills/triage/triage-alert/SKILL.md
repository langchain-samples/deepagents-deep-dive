---
name: triage-alert
description: >-
  Triage a production alert or pager notification: assign a severity, state the
  blast radius, and give the first actions. Use when handed an alert, a pager
  message, an error-rate or latency spike, or asked "how bad is this?".
---

# triage-alert
## Overview
Turns a raw alert into a severity, a blast radius, and the first three things to do.

## Instructions
1. **Read `references/severity-matrix.md` first.** Severity is decided by the
   matrix, never by feel. The matrix also carries override rules that beat the
   error-rate rows outright — you cannot get severity right without reading them.
2. State the **blast radius**: what share of traffic or which customers are
   affected. If the alert doesn't say, write `unknown`.
3. Assign the severity and **quote the matrix row or rule you matched**.
4. Give the **first three actions**, most reversible first.
5. State whether a status-page update is required, per the matrix.

## Output format
```
Severity: SEV<n> — matched: <the row or rule you applied>
Blast radius: <share of traffic or customers, or "unknown">
Status page: <required within N min | not required>
First actions:
  1. <most reversible>
  2. ...
  3. ...
```

## Edge cases
- Symptom sits between two rows → round up, never down.
- Several symptoms at once → triage the worst one, and note the others.
- No error rate given → say so and triage on the remaining evidence.
