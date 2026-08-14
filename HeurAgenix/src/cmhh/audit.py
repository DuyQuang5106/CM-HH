from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AuditReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def audit_run(run_dir: str | Path) -> AuditReport:
    root = Path(run_dir)
    report = AuditReport()
    manifest_path = root / "manifest.json"
    checkpoint_path = root / "checkpoints/latest.json"
    events_path = root / "events.jsonl"
    for path in (manifest_path, checkpoint_path, events_path):
        if not path.exists():
            report.errors.append(f"Missing run artifact: {path.name}")
    if report.errors:
        return report

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for group in ("configs", "data_manifests"):
        for raw_path, expected in manifest.get(group, {}).items():
            path = Path(raw_path)
            if not path.exists():
                report.errors.append(f"Manifest input is missing: {path}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != expected:
                report.errors.append(f"Manifest input changed after run: {path}")
    for task_id, artifact in checkpoint.get("selected", {}).items():
        code_path = Path(artifact["code_path"])
        if not code_path.exists():
            report.errors.append(f"{task_id}: selected code is missing")
            continue
        digest = hashlib.sha256(code_path.read_bytes()).hexdigest()
        if digest != artifact["code_hash"]:
            report.errors.append(f"{task_id}: selected code hash changed after selection")

    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line]
    selected_at: dict[str, int] = {}
    for index, event in enumerate(events):
        task_id = event.get("task_id")
        if event["event"] == "candidate_selected":
            selected_at[task_id] = index
        elif event["event"] == "test_evaluation_started" and task_id not in selected_at:
            report.errors.append(f"{task_id}: test evaluation occurred before candidate selection")

    test_markers = ("/test/", "\\test\\")
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".json", ".jsonl"}:
            continue
        if "evaluations" in path.parts or path.name in {"checkpoint.json", "latest.json"}:
            continue
        try:
            content = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        is_generation_artifact = "candidates" in path.parts or "prompt" in str(path).lower()
        if any(marker in content for marker in test_markers) and is_generation_artifact:
            report.errors.append(f"Potential test path leakage in prompt artifact: {path}")
    return report
