#!/usr/bin/env python3
"""CLI entry point for the canary project generator."""

from __future__ import annotations

import argparse

from .generator import build_project


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a realistic canary project scaffold.")
    parser.add_argument("--project-name", default="canary-project", help="Project directory name")
    parser.add_argument("--output-dir", default=".", help="Directory to write the generated project into")
    parser.add_argument("--mode", choices=["standard", "high-noise", "stealth"], default="standard", help="Project profile")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = build_project(args.project_name, args.output_dir, args.mode)
    print(f"Created canary project at: {project_dir}")
    print("Common scan targets include: /api/.env, /config/app.env, /public/index.php, /wp-config.php")
    return 0
