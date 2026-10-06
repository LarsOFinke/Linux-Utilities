# Installer tests

Run the whole isolated suite with `python3 installer/verify.py` from the repository root. The verifier discovers tests in these directories:

| Directory | Coverage |
| --- | --- |
| `catalog/` | Manifest and catalog validation |
| `lifecycle/` | Setup, component ownership, update, registry routing, transactions, concurrency, and recovery |
| `portable/` | Canonical helper bundled into temporary SSH archives |
| `remote/` | SSH deployment and remote state records |
| `ui/` | Interactive and scripted selector behavior |

Run an individual Python test with `python3 installer/tests/<directory>/<file>.py`; run the shell setup test with `bash installer/tests/lifecycle/setup_test.sh`. Tests use temporary homes and install roots.

`lifecycle/registry_routing_test.py` also exercises each module's direct entry link to the shared `installer/module_entry.sh` router.
