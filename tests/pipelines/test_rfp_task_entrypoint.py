"""Regression for installed console workers, which omit the checkout from sys.path."""

import os
from pathlib import Path
import subprocess
import sys


def test_task_loads_pipeline_without_checkout_on_python_path(tmp_path):
    root = str(Path(__file__).resolve().parents[2])
    code = """
import sys
from pathlib import Path
assert not any(Path(p or '.').resolve() == Path(sys.argv[1]) for p in sys.path)
from services.database import engine
from services.rfp_intake.models import create_tables
from services.rfp_intake.tasks import run_rfp_intake
create_tables(engine)
result = run_rfp_intake.run('missing-entrypoint-regression-ticket')
assert result['status'] == 'not_claimed'
print('CONSOLE_IMPORT_OK')
"""
    env = dict(os.environ, DATABASE_URL="sqlite://", PYTHONPATH="")
    result = subprocess.run(
        [sys.executable, "-c", code, root],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "CONSOLE_IMPORT_OK" in result.stdout
