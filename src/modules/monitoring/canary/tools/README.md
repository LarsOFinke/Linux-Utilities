# Tools

This directory contains project utilities and self-contained modules.

## Modules

- `canary_project` – generates a passive, realistic canary deployment for reconnaissance logging and scan telemetry.
- `canary-mailer` – bundled Python mailer used by the fs-tracker action pipeline.

## Module execution

```bash
python3 -m tools.canary_project --project-name demo-site --output-dir /tmp --mode standard
```

## Legacy convenience wrappers

Some repository scripts remain as thin wrappers around the module entry points for compatibility with existing shell-based workflows.
