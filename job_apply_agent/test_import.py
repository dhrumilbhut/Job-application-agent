import importlib
import sys

try:
    importlib.import_module('job_apply_agent.app.main')
    print('IMPORT_OK')
    sys.exit(0)
except Exception as e:
    print('IMPORT_FAIL:', repr(e))
    sys.exit(1)
