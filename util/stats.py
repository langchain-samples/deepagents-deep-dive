from IPython.display import Markdown, display


def sum_tokens(result) -> dict:
    """Total the input/output tokens the model reported across a run (or a message slice)."""
    messages = result["messages"] if isinstance(result, dict) else result
    totals = {"input": 0, "output": 0}
    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        totals["input"] += usage.get("input_tokens", 0)
        totals["output"] += usage.get("output_tokens", 0)
    totals["total"] = totals["input"] + totals["output"]
    return totals


def count_tool_calls(result, name: str) -> int:
    """Count how many times the model called a given tool across a run (or a message slice)."""
    messages = result["messages"] if isinstance(result, dict) else result
    return sum(
        1
        for message in messages
        for call in (getattr(message, "tool_calls", None) or [])
        if call["name"] == name
    )


def show_run_stats(
    title: str, result, tool_counts: dict[str, int], elapsed: float | None = None
) -> dict:
    """Render a run's tool-call counts, token totals, and (optionally) wall-clock time as an
    HTML card, styled like the tables in deepagents-basics. Returns the token totals dict."""
    tokens = sum_tokens(result)
    rows = [(label, f"{count:,}") for label, count in tool_counts.items()]
    rows += [
        ("Input tokens", f"{tokens['input']:,}"),
        ("Output tokens", f"{tokens['output']:,}"),
        ("Total tokens", f"{tokens['total']:,}"),
    ]
    if elapsed is not None:
        rows.append(("Wall-clock time", f"{elapsed:.1f} s"))

    body = ""
    for label, value in rows:
        emphasize = label == "Total tokens"
        label_html = f"<b>{label}</b>" if emphasize else label
        value_html = f"<b>{value}</b>" if emphasize else value
        body += (
            "<tr>"
            f'<td style="border:1px solid #999; padding:10px; text-align:left;">{label_html}</td>'
            f'<td style="border:1px solid #999; padding:10px; text-align:right;">{value_html}</td>'
            "</tr>"
        )

    table = (
        '<table style="font-size:16px; border-collapse:collapse; width:100%;">'
        "<thead><tr>"
        f'<th style="border:1px solid #999; padding:10px; text-align:left;">{title}</th>'
        '<th style="border:1px solid #999; padding:10px; text-align:right;">Value</th>'
        f"</tr></thead><tbody>{body}</tbody></table>"
    )
    display(Markdown(table))
    return tokens


def show_comparison_table(rows, *, left_label="Direct", right_label="PTC", emphasize=()):
    """Render a two-run comparison as an HTML table (styled like the deepagents-basics tables)
    with a percent-reduction column.

    Each row is (name, left_value, right_value) or (name, left_value, right_value, fmt), where
    fmt formats a value for display (default: thousands-separated integer). Reduction is computed
    from the raw values. Pass row names in `emphasize` to bold those rows (e.g. the total)."""
    def reduction(before: float, after: float) -> str:
        return f"{(1 - after / before) * 100:.0f}%" if before else "—"

    headers = ["Metric", left_label, right_label, "Reduction"]
    aligns = ["left", "right", "right", "right"]
    head = "".join(
        f'<th style="border:1px solid #999; padding:10px; text-align:{align};">{label}</th>'
        for label, align in zip(headers, aligns)
    )

    body = ""
    for row in rows:
        name, left, right = row[0], row[1], row[2]
        fmt = row[3] if len(row) > 3 else (lambda v: f"{v:,}")
        values = [name, fmt(left), fmt(right), reduction(left, right)]
        if name in emphasize:
            values = [f"<b>{value}</b>" for value in values]
        body += "<tr>" + "".join(
            f'<td style="border:1px solid #999; padding:10px; text-align:{align};">{value}</td>'
            for value, align in zip(values, aligns)
        ) + "</tr>"

    table = (
        '<table style="font-size:16px; border-collapse:collapse; width:100%;">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )
    display(Markdown(table))
