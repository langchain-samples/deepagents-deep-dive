"""Load and validate the six incident-evaluation examples."""

import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "incidents.jsonl"

CAUSES = {
    "bad_deploy",
    "upstream_failure",
    "exposed_secret",
    "false_positive",
    "capacity",
    "batch_job",
}
IMPACTS = {
    "customer_failure",
    "confirmed_exposure",
    "customer_degradation",
    "internal_only",
    "no_impact",
}
SEVERITY_BY_IMPACT = {
    "customer_failure": "SEV1",
    "confirmed_exposure": "SEV1",
    "customer_degradation": "SEV2",
    "internal_only": "SEV3",
    "no_impact": "SEV3",
}
ACTION_BY_CAUSE = {
    "bad_deploy": "rollback",
    "upstream_failure": "failover",
    "exposed_secret": "rotate_credential",
    "false_positive": "close_alert",
    "capacity": "scale_out",
    "batch_job": "throttle_job",
}


def load_cases(path: Path = DATASET_PATH) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids = [case["inputs"]["id"] for case in cases]
    if len(cases) != 6 or len(ids) != len(set(ids)):
        raise ValueError("The incident suite must contain six unique examples.")

    for case in cases:
        expected = case["outputs"]
        fixtures = case["fixtures"]
        available_evidence = set(fixtures["telemetry"]) | set(fixtures["changes"])
        if expected["cause"] not in CAUSES or expected["impact"] not in IMPACTS:
            raise ValueError(f"Unknown reference value in {case['inputs']['id']}.")
        if expected["severity"] != SEVERITY_BY_IMPACT[expected["impact"]]:
            raise ValueError(f"Severity conflicts with impact in {case['inputs']['id']}.")
        if expected["action"] != ACTION_BY_CAUSE[expected["cause"]]:
            raise ValueError(f"Action conflicts with cause in {case['inputs']['id']}.")
        if set(expected["evidence"]) != available_evidence:
            raise ValueError(f"Reference evidence is incomplete in {case['inputs']['id']}.")
    return cases


INCIDENT_CASES = load_cases()
INCIDENT_FIXTURES = {case["inputs"]["id"]: case["fixtures"] for case in INCIDENT_CASES}
INCIDENT_EXAMPLES = [
    {key: case[key] for key in ("inputs", "outputs", "metadata")} for case in INCIDENT_CASES
]
