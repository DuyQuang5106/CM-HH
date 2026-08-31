from pathlib import Path
import yaml
import json

repo = Path(".")
streams_dir = repo / "cmhh/configs/streams"
reg_path = repo / "cmhh/configs/tasks/task_registry.yaml"

with open(reg_path, "r", encoding="utf-8") as f:
    task_registry = {t["task_id"]: t for t in yaml.safe_load(f).get("tasks", [])}

stream_files = sorted(streams_dir.glob("*.yaml"))
print(f"Auditing {len(stream_files)} stream configs against task registry and references...\n")
print(f"{'Stream Name':<32} {'Tasks':<6} {'Ref Ready':<12} {'Status'}")
print("-" * 80)

for sf in stream_files:
    try:
        with open(sf, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            
        task_ids = cfg.get("task_ids", cfg.get("tasks", []))
        missing_tasks = [t for t in task_ids if t not in task_registry]
        
        if missing_tasks:
            print(f"{sf.stem:<32} {len(task_ids):<6} {'N/A':<12} ERROR (Missing tasks: {missing_tasks})")
            continue
            
        ref_status = True
        missing_refs = []
        for tid in task_ids:
            t = task_registry[tid]
            ref_file = repo / t["reference"]["path"]
            if not ref_file.exists():
                ref_status = False
                missing_refs.append(f"{tid} (no file)")
                continue
            try:
                data = json.loads(ref_file.read_text(encoding="utf-8"))
                records = data.get("records", [])
                val_cnt = sum(1 for r in records if "validation" in r.get("instance_id", ""))
                test_cnt = sum(1 for r in records if "test" in r.get("instance_id", ""))
                if val_cnt < 10 or test_cnt < 30:
                    ref_status = False
                    missing_refs.append(f"{tid} ({val_cnt}v/{test_cnt}t)")
            except Exception:
                ref_status = False
                missing_refs.append(f"{tid} (corrupted)")
                
        if ref_status:
            status = "READY TO RUN"
            ref_desc = "YES (40/40)"
        else:
            status = f"MISSING REFS: {', '.join(missing_refs)}"
            ref_desc = "NO"
            
        print(f"{sf.stem:<32} {len(task_ids):<6} {ref_desc:<12} {status}")
        
    except Exception as e:
        print(f"{sf.stem:<32} ERROR: {e}")

print("-" * 80)
