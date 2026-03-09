#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from context_db import is_excluded, load_config


MARKER_START = "<!-- vibekit:agent-notes:start -->"
MARKER_END = "<!-- vibekit:agent-notes:end -->"

AGENT_PATHS: dict[str, Path] = {
    "codex": Path("AGENTS.md"),
    "claude": Path("CLAUDE.md"),
    "copilot": Path(".github/copilot-instructions.md"),
    "cursor": Path(".cursor/rules/vibekit.md"),
    "gemini": Path("GEMINI.md"),
}

MISSING_FILE_HEADERS: dict[str, str] = {
    "AGENTS.md": "# Agent Notes\n",
    "CLAUDE.md": "# Project Instructions\n",
    ".github/copilot-instructions.md": "# Copilot Instructions\n",
    ".cursor/rules/vibekit.md": "# Cursor Rules\n",
    "GEMINI.md": "# Gemini Instructions\n",
}


def _notes_block() -> str:
    body = (
        "## Startup\n"
        "- At the start of each new task, read: `.vibe/context/LATEST_CONTEXT.md`\n"
        "- For substantial coding, debugging, or refactoring work, also read: `.vibe/AGENT_CHECKLIST.md`\n"
        "- If repo context looks stale or missing, run: `python3 scripts/vibe.py doctor --full`\n"
        "- (Recommended once after install) Run: `python3 scripts/vibe.py configure --apply`\n\n"
        "## Workflow policy\n"
        "- Use `.vibe/AGENT_CHECKLIST.md` as the primary vibe-kit workflow reference.\n"
        "- Prefer vibe-kit-guided discovery before broad manual searching.\n"
        "- When moving to a different area of the repo, re-read `.vibe/context/LATEST_CONTEXT.md`.\n"
        "- Before finalizing substantial work, refresh context with `python3 scripts/vibe.py doctor --full` so `.vibe/context/LATEST_CONTEXT.md` stays current.\n"
        "- If agent instruction files changed, validate wiring with `python3 scripts/vibe.py agents doctor --fail`.\n\n"
        "## Environment\n"
        "- Use `venv/bin/python` for Python commands in this repo.\n"
        "- Use `venv/bin/python -m pip` or `venv/bin/pip` for package installs.\n"
        "- Use `venv/bin/pytest` for tests.\n"
        "- Do not install Python packages globally.\n\n"
        "## Repo rules\n"
        "- Avoid repo-wide formatting and unrelated cleanup refactors.\n"
        "- Treat placeholders/tokens as runtime contracts (e.g. `<...>`, `{0}`, `%s`).\n"
        "- Prefer small, testable edits; keep behavior stable.\n"
    )
    return f"{MARKER_START}\n{body}{MARKER_END}\n"


def _upsert_notes(content: str) -> tuple[str, bool]:
    block = _notes_block()
    start = content.find(MARKER_START)
    end = content.find(MARKER_END)
    if start != -1 and end != -1 and end > start:
        end += len(MARKER_END)
        updated = content[:start].rstrip("\n")
        if updated:
            updated += "\n\n"
        updated += block
        tail = content[end:].lstrip("\n")
        if tail:
            updated += "\n" + tail
        return updated, updated != content

    updated = content.rstrip("\n")
    if updated:
        updated += "\n\n"
    updated += block
    return updated, updated != content


def _resolve_targets(root: Path, exclude_dirs: list[str], agent: str) -> list[Path]:
    requested = agent.strip().lower()
    keys = list(AGENT_PATHS.keys()) if requested == "all" else [requested]
    targets: list[Path] = []
    for key in keys:
        rel = AGENT_PATHS.get(key)
        if rel is None:
            raise SystemExit(f"unknown --agent: {agent} (expected: codex|claude|copilot|cursor|gemini|all)")
        if is_excluded(rel, exclude_dirs):
            continue
        targets.append(root / rel)
    return targets


def _default_header(path: Path) -> str:
    return MISSING_FILE_HEADERS.get(path.as_posix(), "# Agent Instructions\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Upsert vibe-kit Agent Notes block into scaffolded agent instruction files.")
    ap.add_argument("--agent", default="all", help="Target file set: codex|claude|copilot|cursor|gemini|all.")
    ap.add_argument("--create-missing", action="store_true", help="Create missing target files with a minimal heading.")
    ap.add_argument("--dry-run", action="store_true", help="Print planned updates without writing files.")
    ap.add_argument("--fail-if-changed", action="store_true", help="Exit 1 when any file would be updated.")
    args = ap.parse_args(argv)

    cfg = load_config()
    targets = _resolve_targets(cfg.root, cfg.exclude_dirs, args.agent)
    if not targets:
        print("[agents-sync] WARN: no target files selected")
        return 0

    changed = 0
    for path in targets:
        rel = path.relative_to(cfg.root).as_posix()
        if path.exists():
            original = path.read_text(encoding="utf-8", errors="ignore")
        elif args.create_missing:
            original = _default_header(path.relative_to(cfg.root))
        else:
            print(f"[agents-sync] SKIP: {rel} (missing; use --create-missing)")
            continue

        updated, is_changed = _upsert_notes(original)
        if not is_changed:
            print(f"[agents-sync] OK: {rel}")
            continue

        changed += 1
        if args.dry_run:
            print(f"[agents-sync] WOULD-UPDATE: {rel}")
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
        print(f"[agents-sync] UPDATED: {rel}")

    if changed and args.fail_if_changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
