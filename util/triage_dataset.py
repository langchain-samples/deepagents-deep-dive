"""The support-triage evaluation dataset.

One ticket per example, which is the shape LangSmith examples usually take: ``inputs`` is a
single ticket, ``outputs`` is the single answer the triage policy requires for it. The
reference is a lookup table, not an expected response -- it fixes the classification and says
nothing about how the agent should word anything.

The rows live in ``data/support_tickets.jsonl`` so the dataset can be edited without touching
Python. Each row also carries metadata marking whether it is one of the four tickets whose
surface phrasing points at the wrong answer, which rides along into LangSmith and lets you
group an experiment by ``trap`` in the UI.
"""

import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "support_tickets.jsonl"

LABELS = ("billing", "how-to", "bug", "security")
PRIORITIES = ("P1", "P2", "P3")

_REQUIRED_PRIORITY = {"security": "P1", "billing": "P2", "how-to": "P3"}


def load_examples(path: Path = DATASET_PATH) -> list[dict]:
    """Read the dataset, checking every answer against the policy's priority rules on the way.

    The dataset is only meaningful if the references agree with the policy the agent is handed,
    so a row that drifts out of line fails here rather than showing up as a mysterious score.
    """
    examples = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for example in examples:
        answer = example["outputs"]
        assert answer["label"] in LABELS, example
        assert answer["priority"] in PRIORITIES, example
        want = _REQUIRED_PRIORITY.get(answer["label"])
        # a bug is P1 or P2 depending on whether the customer describes a workaround
        assert answer["priority"] == want if want else answer["priority"] in ("P1", "P2"), example
    return examples


TRIAGE_EXAMPLES = load_examples()
