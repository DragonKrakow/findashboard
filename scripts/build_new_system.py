#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


def build() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    old_system = repo_root / "FinDashboard_Pro.html"
    if not old_system.exists():
        raise FileNotFoundError(f"Old system file not found: {old_system}")

    backup_dir = repo_root / "backup" / "old-system"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / "FinDashboard_Pro.backup.html"
    shutil.copy2(old_system, backup_file)

    dist_dir = repo_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(repo_root / "index.html", dist_dir / "index.html")
    shutil.copy2(repo_root / "FinDashboard_Pro.html", dist_dir / "FinDashboard_Pro.html")
    shutil.copytree(repo_root / "data", dist_dir / "data")

    print(f"Backup created: {backup_file}")
    print(f"New system build created: {dist_dir}")


if __name__ == "__main__":
    build()
