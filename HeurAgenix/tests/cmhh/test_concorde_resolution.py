from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cmhh.references.concorde import (
    ConcordeConfig,
    ConcordeNotFoundError,
    load_concorde_config,
    resolve_concorde_executable,
    validate_solver_command,
)


class ConcordeResolutionTests(unittest.TestCase):
    def test_explicit_path_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "fake_concorde.exe"
            fake_bin.write_text("fake binary", encoding="utf-8")

            resolved = resolve_concorde_executable(explicit_path=fake_bin)
            self.assertEqual(fake_bin.resolve(), resolved)

    def test_explicit_relative_path_resolution_with_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rel_bin = Path("bin/concorde.exe")
            (root / "bin").mkdir()
            (root / rel_bin).write_text("fake binary", encoding="utf-8")

            resolved = resolve_concorde_executable(explicit_path=str(rel_bin), repo_root=root)
            self.assertEqual((root / rel_bin).resolve(), resolved)

    def test_concorde_path_env_var_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "env_concorde.exe"
            fake_bin.write_text("fake binary", encoding="utf-8")

            with patch.dict(os.environ, {"CONCORDE_PATH": str(fake_bin)}):
                resolved = resolve_concorde_executable()
                self.assertEqual(fake_bin.resolve(), resolved)

    def test_system_path_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_bin = Path(temp_dir) / "concorde.exe"
            fake_bin.write_text("fake binary", encoding="utf-8")

            with patch.dict(os.environ, {"CONCORDE_PATH": ""}, clear=False), \
                 patch("shutil.which", return_value=str(fake_bin)):
                resolved = resolve_concorde_executable()
                self.assertEqual(fake_bin.resolve(), resolved)

    def test_local_tools_fallback_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_concorde = root / "tools" / "concorde" / "concorde.exe"
            local_concorde.parent.mkdir(parents=True)
            local_concorde.write_text("fake binary", encoding="utf-8")

            with patch.dict(os.environ, {"CONCORDE_PATH": ""}, clear=False), \
                 patch("shutil.which", return_value=None):
                resolved = resolve_concorde_executable(repo_root=root)
                self.assertEqual(local_concorde.resolve(), resolved)

    def test_missing_concorde_raises_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_root = Path(temp_dir)
            with patch.dict(os.environ, {"CONCORDE_PATH": ""}, clear=False), \
                 patch("shutil.which", return_value=None):
                with self.assertRaises(ConcordeNotFoundError) as ctx:
                    resolve_concorde_executable(repo_root=empty_root)

                error_message = str(ctx.exception)
                # Verify that error message contains actionable guidance
                self.assertIn("Concorde executable was not found", error_message)
                self.assertIn("Checked:", error_message)
                self.assertIn("CONCORDE_PATH", error_message)
                self.assertIn("concorde.yaml", error_message)
                self.assertIn("PowerShell", error_message)
                self.assertIn("PyVRP", error_message)
                self.assertIn("OR-Tools", error_message)

    def test_validate_solver_command_on_missing_raises_actionable_error(self) -> None:
        cfg = ConcordeConfig(
            command_prefix=("non_existent_concorde_binary.exe",),
            arguments=("-x",),
            max_workers=1,
            timeouts={"n20": 10.0},
        )
        with patch.dict(os.environ, {"CONCORDE_PATH": ""}, clear=False), \
             patch("shutil.which", return_value=None):
            with self.assertRaises(ConcordeNotFoundError):
                validate_solver_command(cfg, repo_root=Path("non_existent_dir"))


if __name__ == "__main__":
    unittest.main()
