from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cmhh.logging import EventRecord, EventWriter
from cmhh.memory_diagnostics import build_memory_diagnostics


class AuditDiagnosticsTests(unittest.TestCase):
    def test_event_record_serialization_schema_v1(self) -> None:
        record = EventRecord(
            event="candidate_selected",
            task_id="tsp_20",
            run_id="run_001",
            payload={"heuristic_id": "h_1", "score": -10.5},
            schema_version=1,
        )
        serialized = record.to_dict()
        self.assertEqual(1, serialized["schema_version"])
        self.assertEqual("candidate_selected", serialized["event"])
        self.assertEqual("tsp_20", serialized["task_id"])
        self.assertEqual("h_1", serialized["heuristic_id"])

        deserialized = EventRecord.from_dict(serialized)
        self.assertEqual(record.event, deserialized.event)
        self.assertEqual(record.task_id, deserialized.task_id)

    def test_event_writer_persists_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "events.jsonl"
            writer = EventWriter(path)
            writer.write_event(EventRecord(event="task_started", task_id="tsp_20"))
            writer.write_event(EventRecord(event="task_completed", task_id="tsp_20"))

            lines = path.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(2, len(lines))
            first = json.loads(lines[0])
            self.assertEqual("task_started", first["event"])
            self.assertEqual(1, first["schema_version"])

    def test_build_memory_diagnostics_includes_eviction_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            events_path = run_dir / "events.jsonl"
            writer = EventWriter(events_path)

            writer.write_event(EventRecord(
                event="memory_written",
                task_id="tsp_20",
                payload={"memory_id": "mem_1", "validation_score": -10.0},
            ))
            writer.write_event(EventRecord(
                event="memory_retrieved",
                task_id="tsp_50",
                payload={"memory_ids": ["mem_1"], "source_tasks": ["tsp_20"], "duplicate_key_rate": 0.0},
            ))
            writer.write_event(EventRecord(
                event="memory_evicted",
                task_id="tsp_100",
                payload={"memory_id": "mem_1"},
            ))

            diagnostics = build_memory_diagnostics(run_dir, task_ids=["tsp_20", "tsp_50", "tsp_100"])

            self.assertEqual(1, diagnostics["schema_version"])
            self.assertEqual(1, diagnostics["retrieval_events"])
            self.assertEqual(1, diagnostics["memory_units_written"])
            self.assertEqual(1, diagnostics["memory_units_retrieved"])
            self.assertEqual(1, len(diagnostics["eviction_lineage"]))
            self.assertEqual("mem_1", diagnostics["eviction_lineage"][0]["memory_id"])
            self.assertEqual("tsp_100", diagnostics["eviction_lineage"][0]["task_id"])


if __name__ == "__main__":
    unittest.main()
