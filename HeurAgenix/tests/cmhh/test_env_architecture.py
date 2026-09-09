from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from cmhh.env import (
    MissingEnvironmentVariableError,
    expand_env_vars,
    find_repo_root,
    find_root_env_file,
    load_environment,
    sanitize_config,
)
from cmhh.references.concorde import ConcordeNotFoundError, resolve_concorde_executable


class EnvironmentArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_environ = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._orig_environ)

    def test_repo_root_discovery_and_anchoring(self) -> None:
        root = find_repo_root()
        self.assertTrue((root / "pyproject.toml").is_file() or (root / ".git").is_dir())
        
        # Verify boundary anchoring does not escape into parent directories
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            sub_path = temp_path / "subdir" / "nested"
            sub_path.mkdir(parents=True)
            # Create a pyproject.toml marker inside temp_path
            (temp_path / "pyproject.toml").write_text("[project]\nname='test'", encoding="utf-8")
            
            discovered = find_repo_root(start_path=sub_path)
            self.assertEqual(temp_path.resolve(), discovered.resolve())
            
            # Subdir .env lookup inside bounded root
            (temp_path / ".env").write_text("TEST_VAR=123\n", encoding="utf-8")
            env_file = find_root_env_file(repo_root=temp_path)
            self.assertIsNotNone(env_file)
            self.assertEqual((temp_path / ".env").resolve(), env_file.resolve())

    def test_load_environment_precedence_and_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "# Comment line\n"
                "ENV_TEST_KEY=from_file\n"
                "QUOTED_KEY=\"hello world\"\n"
                "WINDOWS_PATH=C:\\tools\\bin\n"
                "OVERRIDE_TARGET=from_file\n",
                encoding="utf-8",
            )
            
            # Process environment precedence
            os.environ["OVERRIDE_TARGET"] = "from_process"
            loaded = load_environment(env_file=env_file, override=False)
            self.assertTrue(loaded)
            
            self.assertEqual("from_file", os.environ.get("ENV_TEST_KEY"))
            self.assertEqual("hello world", os.environ.get("QUOTED_KEY"))
            self.assertEqual("C:\\tools\\bin", os.environ.get("WINDOWS_PATH"))
            self.assertEqual("from_process", os.environ.get("OVERRIDE_TARGET"))

    def test_expand_env_vars_success_and_defaults(self) -> None:
        os.environ["MY_SECRET"] = "super_secret_key"
        
        raw_config = {
            "api_key": "${MY_SECRET}",
            "fallback": "${UNSET_VAR:-default_val}",
            "nested": {
                "list": ["item1", "${MY_SECRET}"],
                "literal": "$100 cost",
            },
        }
        
        resolved = expand_env_vars(raw_config, strict=True)
        self.assertEqual("super_secret_key", resolved["api_key"])
        self.assertEqual("default_val", resolved["fallback"])
        self.assertEqual(["item1", "super_secret_key"], resolved["nested"]["list"])
        self.assertEqual("$100 cost", resolved["nested"]["literal"])

    def test_expand_env_vars_fail_fast_on_missing_required(self) -> None:
        raw_config = {
            "provider": "nvidia",
            "api_key": "${MISSING_NVIDIA_KEY}",
        }
        
        with self.assertRaises(MissingEnvironmentVariableError) as ctx:
            expand_env_vars(
                raw_config,
                strict=True,
                source_context="test_config.json",
            )
        
        err_msg = str(ctx.exception)
        self.assertIn("MISSING_NVIDIA_KEY", err_msg)
        self.assertIn("test_config.json", err_msg)
        self.assertIn("api_key", err_msg)

    def test_no_implicit_environment_override_of_experiment_config(self) -> None:
        # Setting TEMPERATURE in os.environ must NOT implicitly override config
        os.environ["TEMPERATURE"] = "0.0"
        os.environ["SEED"] = "999"
        
        config = {
            "temperature": 1.0,
            "seed": 42,
            "explicit_api": "${TEST_API:-fallback_key}",
        }
        
        resolved = expand_env_vars(config, strict=True)
        self.assertEqual(1.0, resolved["temperature"])
        self.assertEqual(42, resolved["seed"])
        self.assertEqual("fallback_key", resolved["explicit_api"])

    def test_sanitization_does_not_mutate_runtime_config(self) -> None:
        real_key = "nvapi-actual-secret-key-12345"
        runtime_config = {
            "name": "nvidia-model",
            "api_key": real_key,
            "headers": {
                "Authorization": f"Bearer {real_key}",
            },
            "parameters": {
                "temperature": 0.7,
                "token": "token_abc",
            },
        }
        
        sanitized = sanitize_config(runtime_config, mask="<redacted>")
        
        # Invariant 2 & 3: Runtime config remains intact with real secrets
        self.assertEqual(real_key, runtime_config["api_key"])
        self.assertEqual(f"Bearer {real_key}", runtime_config["headers"]["Authorization"])
        self.assertEqual("token_abc", runtime_config["parameters"]["token"])
        
        # Sanitized config masks all sensitive fields
        self.assertEqual("<redacted>", sanitized["api_key"])
        self.assertEqual("<redacted>", sanitized["headers"]["Authorization"])
        self.assertEqual("<redacted>", sanitized["parameters"]["token"])
        self.assertEqual(0.7, sanitized["parameters"]["temperature"])

    def test_concorde_solver_resolution_hierarchy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_bin = Path(temp_dir) / "fake_concorde.exe"
            temp_bin.write_text("binary", encoding="utf-8")
            
            # 1. Explicit path takes highest precedence
            resolved = resolve_concorde_executable(explicit_path=temp_bin)
            self.assertEqual(temp_bin.resolve(), resolved.resolve())
            
            # 2. CONCORDE_EXECUTABLE environment variable
            os.environ["CONCORDE_EXECUTABLE"] = str(temp_bin)
            resolved_env = resolve_concorde_executable(explicit_path=None)
            self.assertEqual(temp_bin.resolve(), resolved_env.resolve())
            
            # 3. Non-existent path with no local tools raises actionable ConcordeNotFoundError
            os.environ["CONCORDE_EXECUTABLE"] = str(Path(temp_dir) / "non_existent.exe")
            with self.assertRaises(ConcordeNotFoundError):
                resolve_concorde_executable(explicit_path=None, repo_root=temp_dir)
