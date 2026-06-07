"""Weekly machine-progress PDF report for ROTOCON.

Reads the "Europe Machine Overview" board via `monday_rotocon`, renders an
engineering-style PDF (portfolio KPIs + per-machine table + exceptions), and
POSTs it to an n8n webhook that emails it as an attachment and logs a row to
Postgres. Read-only: never mutates monday state.

Run locally:

    uv run python scripts/weekly_machine_report.py [--dry-run]

`--dry-run` writes the PDF to `reports/` and skips the n8n POST.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html import escape
from pathlib import Path
from typing import TypedDict

import httpx

from monday_rotocon import Item, MondayAPIError, MondayClient

# ------------------------------ constants --------------------------------------

BOARD_ID = "5086438002"            # Europe Machine Overview
CURRENT_GROUP_ID = "topics"        # "Current Machines" group

COL_PHASE = "status"
COL_PHASE_PCT = "numeric_mm3xhrbf"
COL_SUBTASK_PCT = "numeric_mm3xgyyw"
COL_OVERALL = "numeric_mm3x30na"
COL_PROJECT_STATUS = "color_mm06k0h1"
COL_PROCUREMENT = "color_mm06wr1p"
COL_MACHINE_TYPE = "text_mkxvf3xh"
COL_CLIENT = "text_mkxvxap2"
COL_COUNTRY = "country_mkxvqhys"
COL_RESPONSIBLE = "person"
COL_TIMELINE = "timerange_mkxw4hgt"
COL_CALC_DELIVER = "formula_mkxw3x4k"
COL_FAT = "date_mky7mk4f"
COL_SAT = "date_mky785fe"

DISCREPANCY_THRESHOLD = 40.0
DELIVERY_HORIZON_DAYS = 30
DELIVERY_OVERALL_FLOOR = 70.0

# ------------------------------ env --------------------------------------------


@dataclass(frozen=True)
class RequiredEnv:
    monday_token: str
    webhook_url: str
    webhook_token: str
    recipient: str


def load_env() -> RequiredEnv:
    """Read required env vars. Exits with code 1 if any are missing."""
    required = {
        "MONDAY_API_TOKEN": "monday_token",
        "N8N_WEBHOOK_URL": "webhook_url",
        "N8N_WEBHOOK_TOKEN": "webhook_token",
        "REPORT_RECIPIENT": "recipient",
    }
    values: dict[str, str] = {}
    missing: list[str] = []
    for env_name, attr_name in required.items():
        v = os.environ.get(env_name, "").strip()
        if not v:
            missing.append(env_name)
        else:
            values[attr_name] = v
    if missing:
        print(f"Missing required env: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(1)
    return RequiredEnv(**values)


# ------------------------------ column helpers ---------------------------------


def col_text(item: Item, column_id: str) -> str | None:
    """Return the `text` of a column value by id, or None if absent/empty."""
    for cv in item.column_values:
        if cv.column_id == column_id:
            text = (cv.text or "").strip()
            return text or None
    return None


def col_number(item: Item, column_id: str) -> float | None:
    """Return a column's numeric text parsed to float, or None if absent/blank."""
    raw = col_text(item, column_id)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@dataclass(frozen=True)
class MachineRow:
    machine_no: str
    machine_type: str | None
    client: str | None
    country: str | None
    responsible: str | None
    phase: str | None
    project_status: str | None
    procurement: str | None
    phase_pct: float | None
    subtask_pct: float | None
    overall: float | None
    deliver_text: str | None
    fat_date: str | None
    sat_date: str | None

    @classmethod
    def from_item(cls, item: Item) -> MachineRow:
        return cls(
            machine_no=item.name,
            machine_type=col_text(item, COL_MACHINE_TYPE),
            client=col_text(item, COL_CLIENT),
            country=col_text(item, COL_COUNTRY),
            responsible=col_text(item, COL_RESPONSIBLE),
            phase=col_text(item, COL_PHASE),
            project_status=col_text(item, COL_PROJECT_STATUS),
            procurement=col_text(item, COL_PROCUREMENT),
            phase_pct=col_number(item, COL_PHASE_PCT),
            subtask_pct=col_number(item, COL_SUBTASK_PCT),
            overall=col_number(item, COL_OVERALL),
            deliver_text=col_text(item, COL_CALC_DELIVER),
            fat_date=col_text(item, COL_FAT),
            sat_date=col_text(item, COL_SAT),
        )


def fetch_current_machines(client: MondayClient) -> list[MachineRow]:
    """Fetch all items on the board, keep only the Current Machines group."""
    rows: list[MachineRow] = []
    for item in client.items_for_board(board_id=BOARD_ID):
        if item.group is not None and item.group.id == CURRENT_GROUP_ID:
            rows.append(MachineRow.from_item(item))
    return rows


def parse_deliver_date(text: str | None) -> date | None:
    """Parse monday's Calc Deliver Date formula text (e.g. '15-Aug-2026')."""
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


@dataclass(frozen=True)
class PortfolioSummary:
    total: int
    avg_overall: float | None
    critical_count: int
    late_count: int
    discrepancy_count: int
    delivery_30d_count: int
    week: int
    generated_at: datetime
    by_phase: dict[str, int] = field(default_factory=dict)


def _is_discrepant(row: MachineRow) -> bool:
    if row.phase_pct is None or row.subtask_pct is None:
        return False
    return (row.phase_pct - row.subtask_pct) >= DISCREPANCY_THRESHOLD


def _delivers_within_horizon(row: MachineRow, *, today: date) -> bool:
    d = parse_deliver_date(row.deliver_text)
    if d is None:
        return False
    delta = (d - today).days
    return 0 <= delta <= DELIVERY_HORIZON_DAYS


def compute_summary(rows: list[MachineRow], *, generated_at: datetime) -> PortfolioSummary:
    today = generated_at.date()
    overalls = [r.overall for r in rows if r.overall is not None]
    by_phase: dict[str, int] = {}
    for r in rows:
        key = r.phase or "(none)"
        by_phase[key] = by_phase.get(key, 0) + 1
    return PortfolioSummary(
        total=len(rows),
        avg_overall=round(sum(overalls) / len(overalls), 1) if overalls else None,
        critical_count=sum(1 for r in rows if r.project_status == "critical"),
        late_count=sum(1 for r in rows if r.project_status == "late delivery"),
        discrepancy_count=sum(1 for r in rows if _is_discrepant(r)),
        delivery_30d_count=sum(1 for r in rows if _delivers_within_horizon(r, today=today)),
        week=generated_at.isocalendar().week,
        generated_at=generated_at,
        by_phase=by_phase,
    )


@dataclass(frozen=True)
class ExceptionRow:
    machine_no: str
    client: str | None
    phase: str | None
    overall: float | None
    why: str
    urgency: int   # lower sorts first


def build_exceptions(
    rows: list[MachineRow], *, generated_at: datetime
) -> list[ExceptionRow]:
    """Flag machines needing attention, sorted by urgency (critical first)."""
    today = generated_at.date()
    out: list[ExceptionRow] = []
    for r in rows:
        reasons: list[str] = []
        urgency = 9
        if r.project_status == "critical":
            reasons.append("Project status critical")
            urgency = min(urgency, 0)
        if r.project_status == "late delivery":
            reasons.append("Late delivery")
            urgency = min(urgency, 1)
        if _is_discrepant(r):
            gap = int((r.phase_pct or 0) - (r.subtask_pct or 0))
            reasons.append(f"Phase ahead of subtasks (gap {gap})")
            urgency = min(urgency, 2)
        if _delivers_within_horizon(r, today=today) and (r.overall or 0) < DELIVERY_OVERALL_FLOOR:
            reasons.append(f"Delivers <={DELIVERY_HORIZON_DAYS}d, overall {int(r.overall or 0)}%")
            urgency = min(urgency, 3)
        if reasons:
            out.append(
                ExceptionRow(
                    machine_no=r.machine_no,
                    client=r.client,
                    phase=r.phase,
                    overall=r.overall,
                    why="; ".join(reasons),
                    urgency=urgency,
                )
            )
    out.sort(key=lambda e: (e.urgency, e.machine_no))
    return out


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{int(round(value))}%"


def _fmt(value: str | None) -> str:
    return escape(value) if value else "—"


def _progress_bar(value: float | None) -> str:
    pct = 0 if value is None else max(0, min(100, int(round(value))))
    return (
        "<div class='track'>"
        f"<div class='fill' style='width:{pct}%'></div>"
        f"<span class='barlabel'>{_fmt_pct(value)}</span>"
        "</div>"
    )


_REPORT_CSS = """
@page {
  size: A4;
  margin: 16mm 12mm 18mm 12mm;
  @top-left { content: "ROTOCON · Machine Progress"; font-size: 8pt; color: #888; }
  @top-right { content: "KW" string(kw); font-size: 8pt; color: #888; }
  @bottom-right { content: "Page " counter(page) " / " counter(pages); font-size: 8pt; color: #888; }
  @bottom-left { content: string(genstamp); font-size: 8pt; color: #888; }
}
* { box-sizing: border-box; }
body { font-family: "Helvetica Neue", Arial, sans-serif; color: #111; font-size: 9pt; }
h1 { font-size: 16pt; margin: 0 0 2mm 0; }
h2 { font-size: 11pt; margin: 6mm 0 2mm 0; border-bottom: 1.5pt solid #0073EA; padding-bottom: 1mm; }
.meta { color: #555; font-size: 8pt; string-set: kw "REPLACED_KW"; }
.kpis { display: flex; gap: 4mm; margin: 4mm 0; }
.kpi { flex: 1; border: 0.5pt solid #ccc; border-top: 2.5pt solid #0073EA; padding: 2mm 3mm; }
.kpi .num { font-size: 15pt; font-weight: bold; font-family: "Courier New", monospace; }
.kpi .lbl { font-size: 7.5pt; color: #666; text-transform: uppercase; letter-spacing: 0.3pt; }
table { width: 100%; border-collapse: collapse; font-size: 8pt; }
th { background: #f2f4f7; text-align: left; padding: 1.5mm 2mm; border-bottom: 1pt solid #ccc; }
td { padding: 1.5mm 2mm; border-bottom: 0.5pt solid #e6e6e6; vertical-align: middle; }
td.mono, th.mono { font-family: "Courier New", monospace; text-align: right; }
.badge { display: inline-block; padding: 0.3mm 1.6mm; border-radius: 2pt; color: #fff; font-size: 7pt; }
.b-critical { background: #df2f4a; } .b-late { background: #ff6d3b; }
.b-ok { background: #037f4c; } .b-hold { background: #c4c4c4; color:#222; }
.b-proc { background: #ff007f; }
.track { position: relative; height: 9pt; background: #eee; border-radius: 2pt; width: 80pt; }
.fill { position: absolute; left:0; top:0; bottom:0; background: #0073EA; border-radius: 2pt; }
.barlabel { position: absolute; right: 2pt; top: 0.5pt; font-size: 6.5pt; font-family: "Courier New", monospace; }
.empty { color: #037f4c; font-style: italic; padding: 2mm 0; }
"""

_BADGE_CLASS = {
    "critical": "b-critical",
    "late delivery": "b-late",
    "ok": "b-ok",
    "on hold": "b-hold",
    "open procurement": "b-proc",
}


def _status_badge(status: str | None) -> str:
    if not status:
        return "—"
    cls = _BADGE_CLASS.get(status, "b-hold")
    return f"<span class='badge {cls}'>{escape(status)}</span>"


def render_report_html(
    summary: PortfolioSummary,
    exceptions: list[ExceptionRow],
    machines: list[MachineRow],
) -> str:
    stamp = summary.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    css = _REPORT_CSS.replace("REPLACED_KW", str(summary.week))

    if exceptions:
        exc_rows = "".join(
            f"<tr><td class='mono'>{escape(e.machine_no)}</td>"
            f"<td>{_fmt(e.client)}</td><td>{_fmt(e.phase)}</td>"
            f"<td class='mono'>{_fmt_pct(e.overall)}</td>"
            f"<td>{escape(e.why)}</td></tr>"
            for e in exceptions
        )
        exc_block = (
            "<table><thead><tr><th class='mono'>Machine</th><th>Client</th>"
            "<th>Phase</th><th class='mono'>Overall</th><th>Why</th></tr></thead>"
            f"<tbody>{exc_rows}</tbody></table>"
        )
    else:
        exc_block = "<p class='empty'>No exceptions this week ✅</p>"

    machine_rows = "".join(
        f"<tr><td class='mono'>{escape(m.machine_no)}</td>"
        f"<td>{_fmt(m.client)}</td><td>{_fmt(m.machine_type)}</td>"
        f"<td>{_fmt(m.responsible)}</td><td>{_fmt(m.phase)}</td>"
        f"<td>{_status_badge(m.project_status)}</td>"
        f"<td>{_progress_bar(m.overall)}</td></tr>"
        for m in sorted(machines, key=lambda r: (r.overall is None, -(r.overall or 0)))
    )

    return f"""\
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><style>{css}
.meta {{ string-set: kw "{summary.week}", genstamp "{stamp}"; }}
</style></head>
<body>
  <h1>Machine Progress Report</h1>
  <div class="meta">Rotocon · Europe Machine Overview · KW{summary.week} · generated {stamp} · board {BOARD_ID}</div>

  <div class="kpis">
    <div class="kpi"><div class="num">{summary.total}</div><div class="lbl">Total machines</div></div>
    <div class="kpi"><div class="num">{_fmt_pct(summary.avg_overall)}</div><div class="lbl">Avg overall</div></div>
    <div class="kpi"><div class="num">{summary.critical_count}</div><div class="lbl">Critical</div></div>
    <div class="kpi"><div class="num">{summary.late_count}</div><div class="lbl">Late delivery</div></div>
  </div>

  <h2>Needs attention</h2>
  {exc_block}

  <h2>Full portfolio (sorted by overall progress)</h2>
  <table>
    <thead><tr><th class='mono'>Machine</th><th>Client</th><th>Type</th>
      <th>Responsible</th><th>Phase</th><th>Status</th><th>Overall</th></tr></thead>
    <tbody>{machine_rows}</tbody>
  </table>
</body>
</html>
"""


def render_pdf(html: str) -> bytes:
    """Render an HTML string to PDF bytes via WeasyPrint.

    WeasyPrint is imported lazily so the rest of the module (and the unit
    test suite) loads without its system libraries installed.
    """
    from weasyprint import HTML  # noqa: PLC0415  (intentional lazy import)

    pdf = HTML(string=html).write_pdf()
    if pdf is None:  # pragma: no cover - write_pdf() returns bytes when no target
        raise RuntimeError("WeasyPrint returned no PDF bytes")
    return pdf


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly machine PDF report")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + render + save PDF locally; do not POST to n8n.",
    )
    args = parser.parse_args()
    _ = load_env()
    # Orchestration is wired up in Task 11.
    _ = args
    raise SystemExit(0)


if __name__ == "__main__":
    raise SystemExit(main())
