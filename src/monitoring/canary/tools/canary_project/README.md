# Canary Project Module

This module creates a realistic, passive canary deployment for defensive scan telemetry.

## Usage

```bash
python3 -m tools.canary_project --project-name demo-site --output-dir /tmp --mode standard
```

## Modes

- `standard` – realistic default layout with common scan targets
- `high-noise` – additional noisy files and logs
- `stealth` – more minimal but still scan-attractive layout

## Design

The generated project is intentionally passive. It logs request metadata automatically without active exfiltration or interaction from the scanner.
