import pandas as pd
import pytest

from app.analyzer import ReportInputError, analyze


def _df(rows, columns=("server", "status", "cpu", "ram", "disk")):
    return pd.DataFrame(rows, columns=columns)


def test_analyze_matches_the_worked_example_from_the_spec():
    # Server01's CPU (92%) and Server03's disk (91%) both clear the
    # critical threshold in their own right, same as Server04 being down -
    # each server is scored independently on the worst thing wrong with it.
    df = _df(
        [
            ["Server01", "up", 92, 40, 55],
            ["Server02", "up", 35, 50, 60],
            ["Server03", "up", 20, 30, 91],
            ["Server04", "down", None, None, None],
        ]
    )

    report = analyze(df)

    assert report["summary"] == {"total_servers": 4, "healthy": 1, "warning": 0, "critical": 3}
    assert report["critical_issues"] == [
        "Server01 CPU usage is 92%",
        "Server03 disk usage is 91%",
        "Server04 is unreachable",
    ]
    assert "Check Server04 connectivity" in report["recommendations"]
    assert "Investigate Server01 CPU usage" in report["recommendations"]
    assert "Clean or extend Server03 storage" in report["recommendations"]


def test_warning_band_below_critical_threshold_is_not_critical():
    df = _df([["Server01", "up", 75, 50, 50]])

    report = analyze(df)

    assert report["summary"] == {"total_servers": 1, "healthy": 0, "warning": 1, "critical": 0}
    assert report["servers"][0]["severity"] == "warning"
    assert "elevated" in report["warning_issues"][0]


def test_missing_metric_columns_default_to_healthy_on_that_metric():
    df = pd.DataFrame([["Server01", "up"]], columns=["server", "status"])

    report = analyze(df)

    assert report["summary"]["healthy"] == 1
    assert report["servers"][0]["cpu"] is None


def test_missing_status_column_defaults_to_up():
    df = pd.DataFrame([["Server01", 10]], columns=["server", "cpu"])

    report = analyze(df)

    assert report["servers"][0]["status"] == "up"


def test_column_aliases_are_matched_case_insensitively():
    df = pd.DataFrame([["Server01", "UP", 10, 20, 30]], columns=["Hostname", "State", "CPU_Percent", "Memory", "Storage"])

    report = analyze(df)

    assert report["servers"][0] == {
        "name": "Server01",
        "status": "up",
        "cpu": 10.0,
        "ram": 20.0,
        "disk": 30.0,
        "severity": "healthy",
    }


def test_no_server_column_raises_report_input_error():
    df = pd.DataFrame([[92]], columns=["cpu"])

    with pytest.raises(ReportInputError, match="server/hostname column"):
        analyze(df)


def test_empty_dataframe_raises_report_input_error():
    with pytest.raises(ReportInputError, match="no rows"):
        analyze(pd.DataFrame(columns=["server"]))
