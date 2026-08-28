import os
import tempfile

# Settings() is instantiated once at import time (app.config), so the env
# vars redirecting the DB/reports dir to throwaway locations have to be set
# before any test module imports app.* - conftest.py is collected first.
_tmp_dir = tempfile.mkdtemp(prefix="it_report_tests_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_dir}/test.db")
os.environ.setdefault("REPORTS_DIR", f"{_tmp_dir}/reports")
