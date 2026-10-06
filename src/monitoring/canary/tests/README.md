# Canary tests

Run `python3 installer/verify.py` from the repository root for the complete isolated suite.

| Directory | Coverage |
| --- | --- |
| `lifecycle/` | Service configuration rollback and installed command workflow |
| `tracker/` | C parser, event name, and JSONL output units |
| `tools/` | Mailer and project generator |

Focused commands from the repository root:

```bash
bash src/monitoring/canary/tests/tracker/c_unit_test.sh
bash src/monitoring/canary/tests/lifecycle/integration_test.sh
PYTHONPATH=src/monitoring/canary python3 -m unittest discover -s src/monitoring/canary/tests/lifecycle -p '*Test*.py'
PYTHONPATH=src/monitoring/canary python3 -m unittest discover -s src/monitoring/canary/tests/tools -p '*Test*.py'
```
