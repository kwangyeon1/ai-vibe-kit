from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / ".vibe" / "brain"))
import agents_sync  # noqa: E402


@dataclass
class _DummyCfg:
    root: Path
    exclude_dirs: list[str] = field(default_factory=list)


class TestAgentsSync(unittest.TestCase):
    def test_updates_existing_gemini_file_with_notes_block(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gemini = root / "GEMINI.md"
            gemini.write_text("# Gemini Instructions\n\n- Keep changes small.\n", encoding="utf-8")

            with patch.object(agents_sync, "load_config", return_value=_DummyCfg(root=root)):
                rc = agents_sync.main(["--agent", "gemini"])

            self.assertEqual(rc, 0)
            content = gemini.read_text(encoding="utf-8")
            self.assertIn("vibekit:agent-notes:start", content)
            self.assertIn(".vibe/AGENT_CHECKLIST.md", content)
            self.assertIn("python3 scripts/vibe.py agents doctor --fail", content)

    def test_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents_file = root / "AGENTS.md"
            agents_file.write_text("# Agent Notes\n", encoding="utf-8")

            with patch.object(agents_sync, "load_config", return_value=_DummyCfg(root=root)):
                rc1 = agents_sync.main(["--agent", "codex"])
                first = agents_file.read_text(encoding="utf-8")
                rc2 = agents_sync.main(["--agent", "codex"])
                second = agents_file.read_text(encoding="utf-8")

            self.assertEqual(rc1, 0)
            self.assertEqual(rc2, 0)
            self.assertEqual(first, second)
            self.assertEqual(second.count("vibekit:agent-notes:start"), 1)

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents_file = root / "AGENTS.md"
            original = "# Agent Notes\n"
            agents_file.write_text(original, encoding="utf-8")

            with patch.object(agents_sync, "load_config", return_value=_DummyCfg(root=root)):
                rc = agents_sync.main(["--agent", "codex", "--dry-run"])

            self.assertEqual(rc, 0)
            self.assertEqual(agents_file.read_text(encoding="utf-8"), original)

    def test_create_missing_writes_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            claude = root / "CLAUDE.md"
            self.assertFalse(claude.exists())

            with patch.object(agents_sync, "load_config", return_value=_DummyCfg(root=root)):
                rc = agents_sync.main(["--agent", "claude", "--create-missing"])

            self.assertEqual(rc, 0)
            self.assertTrue(claude.exists())
            content = claude.read_text(encoding="utf-8")
            self.assertIn("# Project Instructions", content)
            self.assertIn("vibekit:agent-notes:start", content)


if __name__ == "__main__":
    unittest.main()
