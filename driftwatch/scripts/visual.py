"""
Driftwatch — Visual Budget Map

Terminal bar chart and HTML report generation for bootstrap file budget.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from references.constants import (
    BOOTSTRAP_MAX_CHARS_PER_FILE,
    BOOTSTRAP_TOTAL_MAX_CHARS,
)

# ANSI color codes
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BLINK_RED = "\033[5;31m"
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

BAR_WIDTH = 20
FILLED = "█"
EMPTY = "░"


def _color_for_percent(percent):
    """Return ANSI color code based on percentage."""
    if percent > 100:
        return _BLINK_RED
    elif percent > 80:
        return _RED
    elif percent > 60:
        return _YELLOW
    return _GREEN


def _bar(percent, width=BAR_WIDTH):
    """Render a bar like ████████░░░░░░░░░░░░"""
    filled = min(int(round(percent / 100 * width)), width)
    empty = width - filled
    return FILLED * filled + EMPTY * empty


def _strip_ansi(text):
    """Remove all ANSI escape codes from text."""
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)


def render_terminal(scan_result, use_color=None):
    """
    Render a terminal bar chart of bootstrap file budget consumption.

    Args:
        scan_result: Full scan result dict
        use_color: Force color on/off. None = auto-detect TTY.

    Returns:
        str with the rendered output
    """
    if use_color is None:
        use_color = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    truncation = scan_result.get("truncation", {})
    files = truncation.get("files", [])
    aggregate = truncation.get("aggregate", {})

    total_chars = aggregate.get("total_chars", 0)
    agg_limit = aggregate.get("aggregate_limit", BOOTSTRAP_TOTAL_MAX_CHARS)
    agg_percent = aggregate.get("percent_of_aggregate", 0)

    lines = []
    lines.append("")
    header = f"Bootstrap File Budget ({total_chars:,} / {agg_limit:,} chars = {agg_percent}%)"
    lines.append(f"{_BOLD}{header}{_RESET}" if use_color else header)
    lines.append("━" * len(header))
    lines.append("")

    # Find max filename length for alignment
    max_name = max((len(f.get("file", "")) for f in files), default=12)
    max_name = max(max_name, 9)  # "Aggregate" length

    for f in files:
        name = f.get("file", "?")
        chars = f.get("char_count", 0)
        limit = f.get("limit", BOOTSTRAP_MAX_CHARS_PER_FILE)
        percent = f.get("percent_of_limit", 0)

        color = _color_for_percent(percent) if use_color else ""
        reset = _RESET if use_color else ""

        bar = _bar(percent)
        stats = f"{chars:>6,} / {limit:>6,} ({percent:>5.1f}%)"
        line = f"{name:<{max_name}}  {color}{bar}{reset}  {stats}"
        lines.append(line)

    # Aggregate bar
    lines.append("")
    agg_color = _color_for_percent(agg_percent) if use_color else ""
    agg_reset = _RESET if use_color else ""
    agg_bar = _bar(agg_percent)
    agg_stats = f"{total_chars:>6,} / {agg_limit:>6,} ({agg_percent:>5.1f}%)"
    lines.append(f"{'Aggregate':<{max_name}}  {agg_color}{agg_bar}{agg_reset}  {agg_stats}")
    lines.append("")

    output = "\n".join(lines)
    if not use_color:
        output = _strip_ansi(output)
    return output


def render_html(scan_result, output_path):
    """
    Generate a self-contained HTML report with interactive budget visualization.

    Args:
        scan_result: Full scan result dict
        output_path: Path to write the HTML file
    """
    truncation = scan_result.get("truncation", {})
    files = truncation.get("files", [])
    aggregate = truncation.get("aggregate", {})
    simulation = scan_result.get("simulation", {})
    trends = scan_result.get("trends", {})
    compaction = scan_result.get("compaction", {})
    hygiene = scan_result.get("hygiene", {})

    # Inject scan data as JSON for JS to consume
    scan_json = json.dumps({
        "version": scan_result.get("driftwatch_version", ""),
        "timestamp": scan_result.get("scan_timestamp", ""),
        "workspace": scan_result.get("workspace", ""),
        "files": files,
        "aggregate": aggregate,
        "simulation": simulation,
        "trends": trends,
        "compaction": compaction,
        "hygiene": hygiene,
        "summary": scan_result.get("summary", {}),
    }, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Driftwatch Report</title>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --text-dim: #8b949e; --green: #3fb950;
    --yellow: #d29922; --red: #f85149; --blue: #58a6ff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
    background: var(--bg); color: var(--text);
    max-width: 900px; margin: 0 auto; padding: 24px;
  }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .meta {{ color: var(--text-dim); font-size: 0.85rem; margin-bottom: 24px; }}
  .summary {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
    margin-bottom: 24px;
  }}
  .stat {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px; text-align: center;
  }}
  .stat .value {{ font-size: 1.8rem; font-weight: 700; }}
  .stat .label {{ color: var(--text-dim); font-size: 0.8rem; margin-top: 4px; }}
  .stat.critical .value {{ color: var(--red); }}
  .stat.warning .value {{ color: var(--yellow); }}
  .stat.ok .value {{ color: var(--green); }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 20px; margin-bottom: 16px;
  }}
  .card h2 {{ font-size: 1.1rem; margin-bottom: 16px; }}
  .file-row {{
    display: grid; grid-template-columns: 140px 1fr 160px;
    align-items: center; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid var(--border); cursor: pointer;
  }}
  .file-row:last-child {{ border-bottom: none; }}
  .file-row:hover {{ background: rgba(255,255,255,0.03); }}
  .file-name {{ font-weight: 600; font-size: 0.9rem; }}
  .bar-container {{
    height: 20px; background: var(--border); border-radius: 4px;
    overflow: hidden; position: relative; min-width: 0; min-height: 20px;
  }}
  .bar-fill {{
    height: 100%; border-radius: 4px; transition: width 0.3s;
    position: relative;
  }}
  .bar-fill.green {{ background: #3fb950; background: linear-gradient(90deg, #238636, #3fb950); }}
  .bar-fill.yellow {{ background: #d29922; background: linear-gradient(90deg, #9e6a03, #d29922); }}
  .bar-fill.red {{ background: #f85149; background: linear-gradient(90deg, #da3633, #f85149); }}
  .file-stats {{ font-size: 0.85rem; color: var(--text-dim); text-align: right; }}
  .detail-panel {{
    display: none; background: rgba(0,0,0,0.2); padding: 12px 16px;
    border-radius: 4px; margin: 8px 0; font-size: 0.85rem;
  }}
  .detail-panel.active {{ display: block; }}
  .danger-zone {{ color: var(--red); }}
  .sparkline {{ display: inline-block; vertical-align: middle; }}
  .trend-tag {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 0.75rem; font-weight: 600;
  }}
  .trend-tag.stable {{ background: rgba(63,185,80,0.15); color: var(--green); }}
  .trend-tag.growing {{ background: rgba(210,153,34,0.15); color: var(--yellow); }}
  .trend-tag.accelerating {{ background: rgba(248,81,73,0.15); color: var(--red); }}
  .trend-tag.shrinking {{ background: rgba(88,166,255,0.15); color: var(--blue); }}
  .anchor-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 0; border-bottom: 1px solid var(--border);
  }}
  .anchor-row:last-child {{ border-bottom: none; }}
  .finding {{ padding: 6px 0; font-size: 0.85rem; }}
  .finding .severity {{ font-weight: 600; }}
  .finding .severity.critical {{ color: var(--red); }}
  .finding .severity.warning {{ color: var(--yellow); }}
  .finding .severity.info {{ color: var(--text-dim); }}
  footer {{ text-align: center; color: var(--text-dim); font-size: 0.8rem; margin-top: 32px; }}
  @media (max-width: 600px) {{
    .summary {{ grid-template-columns: repeat(2, 1fr); }}
    .file-row {{ grid-template-columns: 1fr; gap: 4px; }}
    .file-stats {{ text-align: left; }}
    body {{ padding: 12px; }}
  }}
</style>
</head>
<body>
<h1>🔍 Driftwatch Report</h1>
<div class="meta" id="meta"></div>
<div class="summary" id="summary"></div>
<div class="card" id="budget-card"><h2>Bootstrap File Budget</h2><div id="budget-bars"></div></div>
<div class="card" id="simulation-card" style="display:none"><h2>Truncation Simulation</h2><div id="simulation-content"></div></div>
<div class="card" id="trends-card" style="display:none"><h2>Growth Trends</h2><div id="trends-content"></div></div>
<div class="card" id="compaction-card"><h2>Compaction Anchors</h2><div id="compaction-content"></div></div>
<div class="card" id="hygiene-card"><h2>Workspace Hygiene</h2><div id="hygiene-content"></div></div>
<footer>Generated by Driftwatch &mdash; <a href="https://github.com/DanAndBub/driftwatch-skill" style="color:var(--blue)">github.com/DanAndBub/driftwatch-skill</a></footer>
<script>
const data = {scan_json};
// XSS escape helper — all user-controlled strings must go through this
function esc(s) {{ const d=document.createElement('div'); d.textContent=String(s); return d.innerHTML; }}
// Meta
document.getElementById('meta').innerHTML =
  `${{esc(data.workspace)}} &middot; ${{esc(data.timestamp)}} &middot; v${{esc(data.version)}}`;
// Summary
const s = data.summary || {{}};
document.getElementById('summary').innerHTML = [
  {{v: s.critical||0, l: 'Critical', c: (s.critical||0)>0?'critical':'ok'}},
  {{v: s.warning||0, l: 'Warning', c: (s.warning||0)>0?'warning':'ok'}},
  {{v: s.info||0, l: 'Info', c: 'ok'}},
  {{v: (data.aggregate||{{}}).percent_of_aggregate||0, l: '% Budget Used', c:
    ((data.aggregate||{{}}).percent_of_aggregate||0)>80?'critical':
    ((data.aggregate||{{}}).percent_of_aggregate||0)>60?'warning':'ok'}}
].map(x=>`<div class="stat ${{x.c}}"><div class="value">${{x.v}}</div><div class="label">${{x.l}}</div></div>`).join('');
// Budget bars
const files = data.files || [];
function barClass(p) {{ return p>100?'red':p>80?'red':p>60?'yellow':'green'; }}
document.getElementById('budget-bars').innerHTML = files.map((f,i) => {{
  const p = f.percent_of_limit||0;
  const sim = (data.simulation?.files||[]).find(s=>s.file===f.file);
  const trend = (data.trends?.files||[]).find(t=>t.file===f.file);
  let detail = '';
  if(sim && sim.simulation_needed) {{
    const dz = sim.danger_zone||{{}};
    const status = sim.status==='truncated_now'?'TRUNCATED NOW':'At Risk';
    detail += `<div class="danger-zone">⚠️ ${{esc(status)}}: ${{esc(sim.recommendation||'')}}</div>`;
  }}
  if(trend) {{
    const dtl = trend.days_to_limit;
    detail += `<div>Growth: ${{esc(trend.growth_rate_chars_per_day)}} chars/day` +
      (dtl!==null?` &middot; ${{esc(dtl)}} days to limit`:'') +
      ` <span class="trend-tag ${{esc(trend.trend)}}">${{esc(trend.trend)}}</span></div>`;
  }}
  return `<div class="file-row" onclick="this.nextElementSibling.classList.toggle('active')">
    <div class="file-name">${{esc(f.file)}}</div>
    <div class="bar-container"><div class="bar-fill ${{barClass(p)}}" style="width:${{Math.min(p,100)}}%"></div></div>
    <div class="file-stats">${{(f.char_count||0).toLocaleString()}} / ${{(f.limit||20000).toLocaleString()}} (${{p.toFixed(1)}}%)</div>
  </div><div class="detail-panel">${{detail||'No additional details'}}</div>`;
}}).join('') + `<div class="file-row" style="margin-top:12px;border-top:2px solid var(--border);padding-top:12px">
  <div class="file-name" style="font-weight:700">Aggregate</div>
  <div class="bar-container"><div class="bar-fill ${{barClass(data.aggregate?.percent_of_aggregate||0)}}" style="width:${{Math.min(data.aggregate?.percent_of_aggregate||0,100)}}%"></div></div>
  <div class="file-stats">${{(data.aggregate?.total_chars||0).toLocaleString()}} / ${{(data.aggregate?.aggregate_limit||150000).toLocaleString()}} (${{(data.aggregate?.percent_of_aggregate||0).toFixed(1)}}%)</div>
</div>`;
// Simulation
const simFiles = (data.simulation?.files||[]).filter(f=>f.simulation_needed);
if(simFiles.length) {{
  document.getElementById('simulation-card').style.display='block';
  document.getElementById('simulation-content').innerHTML = simFiles.map(f=>
    `<div class="finding"><span class="severity ${{f.status==='truncated_now'?'critical':'warning'}}">${{f.status==='truncated_now'?'TRUNCATED':'AT RISK'}}</span> ${{esc(f.file)}}: ${{esc(f.recommendation||'')}}</div>`
  ).join('');
}}
// Trends
if(data.trends?.files) {{
  document.getElementById('trends-card').style.display='block';
  document.getElementById('trends-content').innerHTML =
    `<div style="margin-bottom:8px;color:var(--text-dim)">Based on ${{data.trends.scans_analyzed}} scans over ${{data.trends.time_span_days}} days</div>` +
    data.trends.files.map(f=>
      `<div class="finding">${{esc(f.file)}}: ${{esc(f.growth_rate_chars_per_day)}} chars/day <span class="trend-tag ${{esc(f.trend)}}">${{esc(f.trend)}}</span>` +
      (f.days_to_limit!==null?` &middot; ${{esc(f.days_to_limit)}} days to limit`:'') + `</div>`
    ).join('');
}}
// Compaction
const anchors = data.compaction?.anchor_sections||[];
document.getElementById('compaction-content').innerHTML = anchors.map(a=>
  `<div class="anchor-row"><span>${{esc(a.heading)}} ${{a.found?'✓':'✗'}}</span><span>${{a.found?(a.char_count||0).toLocaleString()+' / '+(a.cap||3000).toLocaleString()+' chars':'Missing!'}}</span></div>`
).join('');
// Hygiene
const findings = data.hygiene?.findings||[];
document.getElementById('hygiene-content').innerHTML = findings.length?
  findings.map(f=>`<div class="finding"><span class="severity ${{esc(f.severity)}}">${{esc(f.severity)}}</span> ${{esc(f.message)}}</div>`).join('') :
  '<div style="color:var(--text-dim)">No hygiene issues found</div>';
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
