"""Create a secret-free source release archive."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import zipfile
from pathlib import Path

EXCLUDED_PARTS = {".git", ".claude", "node_modules", ".next", ".venv", "venv", "__pycache__", "runtime", "test-results", "playwright-report"}
EXCLUDED_NAMES = {".env", ".env.local", ".env.production", "NUL"}
SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{25,}"),
    re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s@/]+@", re.I),
]
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml", ".md", ".txt", ".toml", ".ini", ".ps1", ".sh"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    files: list[Path] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_dir() or any(part in EXCLUDED_PARTS for part in rel.parts) or path.name in EXCLUDED_NAMES:
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.suffix in {".pem", ".key", ".p12", ".pfx"}:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                raise SystemExit(f"Potential secret detected in {rel}")
        files.append(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(root))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256.txt").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"Created {output}\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
