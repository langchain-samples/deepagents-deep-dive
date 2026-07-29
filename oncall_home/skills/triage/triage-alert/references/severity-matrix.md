# Severity matrix

## Rows

| Condition | Severity | Status page | Who is paged |
| --- | --- | --- | --- |
| Full outage, or API error rate above 10% | SEV1 | required within 15 min | both on-call engineers |
| API error rate 2–10%, or checkout or login broken | SEV2 | required within 60 min | primary on-call |
| API error rate below 2%, elevated latency, or a single tenant affected | SEV3 | not required | next business day |

## Override rules

These beat the rows above. Apply them first.

1. **Any risk of data loss or corruption is SEV1**, regardless of error rate.
2. Authentication or authorization failures are **never below SEV2**.
3. A single-tenant issue **caps at SEV3** — unless rule 1 applies.
4. If a symptom sits between two rows, **round up**.

## Target first response

- SEV1 — 5 minutes
- SEV2 — 30 minutes
- SEV3 — next business day
