"""Turns a raw server-metrics table into a structured infrastructure report.

Expected input (CSV or XLSX), one row per server, column names matched
case-insensitively with a few common aliases:

    server, status, cpu, ram, disk
    Server01, up, 92, 40, 55
    Server02, up, 35, 50, 60
    Server03, up, 20, 30, 91
    Server04, down, , ,

`status` and the metric columns are all optional per row - a row missing a
metric just isn't scored on it, and a missing `status` column defaults every
row to "up" (severity then comes entirely from the metric thresholds).
"""
import io
from dataclasses import dataclass, field

import pandas as pd

CPU_WARNING, CPU_CRITICAL = 70, 85
RAM_WARNING, RAM_CRITICAL = 75, 90
DISK_WARNING, DISK_CRITICAL = 80, 90

# First matching alias wins; order doesn't matter within a group since
# column names are normalized (lowercased/stripped) before lookup.
COLUMN_ALIASES = {
    "server": ["server", "hostname", "host", "name"],
    "status": ["status", "state"],
    "cpu": ["cpu", "cpu_percent", "cpu%", "cpu_usage"],
    "ram": ["ram", "ram_percent", "ram%", "memory", "memory_percent", "mem"],
    "disk": ["disk", "disk_percent", "disk%", "storage"],
}

DOWN_VALUES = {"down", "offline", "unreachable", "dead", "no"}


class ReportInputError(ValueError):
    pass


@dataclass
class ServerRecord:
    name: str
    status: str
    cpu: float | None
    ram: float | None
    disk: float | None
    severity: str  # "healthy" | "warning" | "critical"
    issues: list[str] = field(default_factory=list)


def load_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    lower = filename.lower()
    try:
        if lower.endswith((".xlsx", ".xls")):
            return pd.read_excel(io.BytesIO(file_bytes))
        return pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ReportInputError(f"Couldn't parse {filename} as a spreadsheet: {exc}") from exc


def _resolve_columns(df: pd.DataFrame) -> dict[str, str | None]:
    normalized = {str(c).strip().lower(): c for c in df.columns}
    resolved: dict[str, str | None] = {}
    for field_name, aliases in COLUMN_ALIASES.items():
        resolved[field_name] = next((normalized[a] for a in aliases if a in normalized), None)
    if resolved["server"] is None:
        raise ReportInputError(
            "No server/hostname column found - expected one of: " + ", ".join(COLUMN_ALIASES["server"])
        )
    return resolved


def _to_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_metric(value: float | None, warning: float, critical: float) -> str:
    if value is None:
        return "healthy"
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "healthy"


_SEVERITY_RANK = {"healthy": 0, "warning": 1, "critical": 2}


def _worse(a: str, b: str) -> str:
    return a if _SEVERITY_RANK[a] >= _SEVERITY_RANK[b] else b


def _build_record(row: pd.Series, columns: dict[str, str | None]) -> ServerRecord:
    name = str(row[columns["server"]]).strip()
    raw_status = row[columns["status"]] if columns["status"] else "up"
    is_down = str(raw_status).strip().lower() in DOWN_VALUES
    status = "down" if is_down else "up"

    cpu = _to_float(row[columns["cpu"]]) if columns["cpu"] else None
    ram = _to_float(row[columns["ram"]]) if columns["ram"] else None
    disk = _to_float(row[columns["disk"]]) if columns["disk"] else None

    issues: list[str] = []
    severity = "critical" if is_down else "healthy"
    if is_down:
        issues.append(f"{name} is unreachable")

    for label, value, warning, critical in (
        ("CPU", cpu, CPU_WARNING, CPU_CRITICAL),
        ("RAM", ram, RAM_WARNING, RAM_CRITICAL),
        ("disk", disk, DISK_WARNING, DISK_CRITICAL),
    ):
        metric_severity = _score_metric(value, warning, critical)
        severity = _worse(severity, metric_severity)
        if metric_severity == "critical":
            issues.append(f"{name} {label} usage is {value:.0f}%")
        elif metric_severity == "warning":
            issues.append(f"{name} {label} usage is elevated at {value:.0f}%")

    return ServerRecord(name=name, status=status, cpu=cpu, ram=ram, disk=disk, severity=severity, issues=issues)


def _recommend(record: ServerRecord) -> list[str]:
    recs = []
    if record.status == "down":
        recs.append(f"Check {record.name} connectivity")
    if record.cpu is not None and record.cpu >= CPU_WARNING:
        recs.append(f"Investigate {record.name} CPU usage" if record.cpu >= CPU_CRITICAL else f"Monitor {record.name} CPU usage")
    if record.ram is not None and record.ram >= RAM_WARNING:
        recs.append(
            f"Investigate {record.name} memory usage for leaks" if record.ram >= RAM_CRITICAL else f"Monitor {record.name} memory usage"
        )
    if record.disk is not None and record.disk >= DISK_WARNING:
        recs.append(f"Clean or extend {record.name} storage" if record.disk >= DISK_CRITICAL else f"Plan storage cleanup for {record.name}")
    return recs


def analyze(df: pd.DataFrame) -> dict:
    if df.empty:
        raise ReportInputError("The uploaded file has no rows.")

    columns = _resolve_columns(df)
    records = [_build_record(row, columns) for _, row in df.iterrows()]

    counts = {"healthy": 0, "warning": 0, "critical": 0}
    for r in records:
        counts[r.severity] += 1

    critical_issues = [issue for r in records if r.severity == "critical" for issue in r.issues]
    warning_issues = [issue for r in records if r.severity == "warning" for issue in r.issues]

    recommendations: list[str] = []
    for r in sorted(records, key=lambda r: _SEVERITY_RANK[r.severity], reverse=True):
        for rec in _recommend(r):
            if rec not in recommendations:
                recommendations.append(rec)

    return {
        "summary": {
            "total_servers": len(records),
            "healthy": counts["healthy"],
            "warning": counts["warning"],
            "critical": counts["critical"],
        },
        "servers": [
            {
                "name": r.name,
                "status": r.status,
                "cpu": r.cpu,
                "ram": r.ram,
                "disk": r.disk,
                "severity": r.severity,
            }
            for r in records
        ],
        "critical_issues": critical_issues,
        "warning_issues": warning_issues,
        "recommendations": recommendations,
    }
