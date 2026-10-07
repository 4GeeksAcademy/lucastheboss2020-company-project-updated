import builtins
import json
import subprocess
import sys
from pathlib import Path

from scripts.analyze_incidents import export_to_csv

SCRIPT = "scripts/analyze_incidents.py"


def run_analyzer(*args, cwd=None):
    return subprocess.run(
        [sys.executable, SCRIPT, *map(str, args)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_analyzer_missing_argument_exits_nonzero_with_safe_json():
    result = run_analyzer()

    assert result.returncode == 2
    assert "No CSV file path provided." in result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {"error": "No CSV file path provided."}
    assert "Traceback" not in result.stderr


def test_analyzer_missing_file_exits_nonzero_without_echoing_path(tmp_path):
    missing_path = tmp_path / "private-folder" / "customer-data.csv"

    result = run_analyzer(missing_path)

    assert result.returncode == 1
    assert "CSV file was not found." in result.stderr
    assert str(tmp_path) not in result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {"error": "CSV file was not found."}
    assert "Traceback" not in result.stderr


def test_analyzer_invalid_utf8_is_a_controlled_failure(tmp_path):
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_bytes(b"\xff\xfe")

    result = run_analyzer(csv_path)

    assert result.returncode == 1
    assert "UTF-8" in result.stderr
    assert "Traceback" not in result.stderr


def test_export_write_failure_returns_false_and_sanitized_stderr(monkeypatch, capsys):
    def fail_open(*args, **kwargs):
        raise PermissionError("private directory details")

    monkeypatch.setattr(builtins, "open", fail_open)

    assert export_to_csv({}, "private-results.csv") is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Could not export analysis results to CSV." in captured.err
    assert "private directory details" not in captured.err


def test_pandas_clean_missing_input_exits_nonzero_without_traceback(tmp_path):
    script = Path(__file__).resolve().parents[2] / "skills" / "data-analysis" / "scripts" / "pandas_clean.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert result.stderr.strip()
    assert "Traceback" not in result.stderr


def test_fixture_generator_write_failure_exits_nonzero_without_traceback(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "generate_fixture.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Could not write the incident fixture CSV." in result.stderr
    assert "Traceback" not in result.stderr


def test_seed_missing_input_exits_nonzero_without_echoing_path(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "seed_incidents.py"
    missing_path = tmp_path / "private-folder" / "customers.csv"
    result = subprocess.run(
        [sys.executable, str(script), str(missing_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Incident seed CSV was not found." in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
