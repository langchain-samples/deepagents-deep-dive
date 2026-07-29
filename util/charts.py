from IPython.display import HTML, display

# Categorical slots 1 (blue) and 2 (aqua) from the validated data-viz palette,
# with light/dark steps. Adjacent CVD ΔE 73.6; every bar is directly value-labeled
# (the relief rule), so the sub-3:1 aqua is safe.
_CSS = """
<style>
.ptc-cmp { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  --s1:#2a78d6; --s2:#1baf7a; --text:#0b0b0b; --muted:#52514e;
  --track:#e1e0d9; --good:#006300; --bad:#c0392b; --border:rgba(11,11,11,0.10);
  border:1px solid var(--border); border-radius:8px; padding:16px 18px; margin:8px 0; }
@media (prefers-color-scheme: dark) {
  .ptc-cmp { --s1:#3987e5; --s2:#199e70; --text:#ffffff; --muted:#c3c2b7;
    --track:#2c2c2a; --good:#0ca30c; --bad:#e66767; --border:rgba(255,255,255,0.10); } }
.ptc-cmp .cmp-title { font-size:15px; font-weight:600; color:var(--text); margin-bottom:2px; }
.ptc-cmp .cmp-legend { display:flex; gap:16px; margin:6px 0 14px; font-size:13px; color:var(--muted); }
.ptc-cmp .cmp-legend span { display:inline-flex; align-items:center; gap:6px; }
.ptc-cmp .cmp-chip { width:11px; height:11px; border-radius:3px; }
.ptc-cmp .cmp-metric { font-size:13px; color:var(--muted); margin:12px 0 5px;
  display:flex; justify-content:space-between; align-items:baseline; }
.ptc-cmp .cmp-badge { font-size:12px; font-weight:600; }
.ptc-cmp .cmp-track { display:grid; grid-template-columns:1fr 92px; align-items:center;
  gap:10px; margin:4px 0; }
.ptc-cmp .cmp-barbg { background:var(--track); border-radius:4px; }
.ptc-cmp .cmp-fill { height:16px; border-radius:4px; }
.ptc-cmp .cmp-num { font-size:13px; color:var(--text); text-align:right;
  font-variant-numeric:tabular-nums; }
</style>
"""


def show_comparison_bars(rows, *, left_label="Direct", right_label="PTC", title=None):
    """Render a grouped horizontal bar chart comparing two series across metrics.

    Each row is (name, left_value, right_value) or (name, left_value, right_value, fmt),
    where fmt formats a value for its label (default: thousands-separated integer). Bars
    are scaled per-row to that row's larger value, so metrics with different units
    (tokens vs seconds) can share the figure without a misleading common axis.
    """
    parts = ['<div class="ptc-cmp">']
    if title:
        parts.append(f'<div class="cmp-title">{title}</div>')
    parts.append(
        '<div class="cmp-legend">'
        f'<span><span class="cmp-chip" style="background:var(--s1)"></span>{left_label}</span>'
        f'<span><span class="cmp-chip" style="background:var(--s2)"></span>{right_label}</span>'
        "</div>"
    )

    for row in rows:
        name, left, right = row[0], row[1], row[2]
        fmt = row[3] if len(row) > 3 else (lambda v: f"{v:,}")
        top = max(left, right) or 1

        badge = ""
        if left:
            pct = (1 - right / left) * 100
            if pct >= 0:
                badge = f'<span class="cmp-badge" style="color:var(--good)">▼ {pct:.0f}%</span>'
            else:
                badge = f'<span class="cmp-badge" style="color:var(--bad)">▲ {abs(pct):.0f}%</span>'

        parts.append(f'<div class="cmp-metric"><span>{name}</span>{badge}</div>')
        for value, color in ((left, "var(--s1)"), (right, "var(--s2)")):
            width = value / top * 100
            parts.append(
                '<div class="cmp-track">'
                f'<div class="cmp-barbg"><div class="cmp-fill" style="width:{width:.1f}%; background:{color}"></div></div>'
                f'<span class="cmp-num">{fmt(value)}</span>'
                "</div>"
            )

    parts.append("</div>")
    display(HTML(_CSS + "".join(parts)))
