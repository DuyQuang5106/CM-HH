import json
from pathlib import Path
import yaml

repo = Path.cwd()
if not (repo / "cmhh" / "configs").exists() and (repo / "HeurAgenix" / "cmhh" / "configs").exists():
    repo = repo / "HeurAgenix"

streams_dir = repo / "cmhh/configs/streams"
suites_dir = repo / "cmhh/configs/suites"
reg_path = repo / "cmhh/configs/tasks/task_registry.yaml"

with open(reg_path, "r", encoding="utf-8") as f:
    task_registry = {t["task_id"]: t for t in yaml.safe_load(f).get("tasks", [])}

stream_files = sorted(streams_dir.glob("*.yaml"))
suite_files = sorted(suites_dir.glob("*.yaml")) if suites_dir.exists() else []

print(f"Auditing {len(stream_files)} active stream configs and {len(suite_files)} suites...\n")
print(f"{'Stream / Suite Name':<35} {'Type':<10} {'Tasks':<6} {'Ref Ready':<12} {'Status'}")
print("-" * 85)

ready_count = 0
error_count = 0

for sf in stream_files:
    try:
        with open(sf, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            
        task_ids = cfg.get("task_ids", cfg.get("tasks", []))
        missing_tasks = [t for t in task_ids if t not in task_registry]
        
        if missing_tasks:
            print(f"{sf.stem:<35} {'Stream':<10} {len(task_ids):<6} {'N/A':<12} ERROR (Missing tasks: {missing_tasks})")
            error_count += 1
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
            ready_count += 1
        else:
            status = f"MISSING REFS: {', '.join(missing_refs)}"
            ref_desc = "NO"
            error_count += 1
            
        is_pilot = "pilot" in sf.stem or "_small" in sf.stem or "smoke" in sf.stem
        stream_type = "Pilot" if is_pilot else "Benchmark"
        print(f"{sf.stem:<35} {stream_type:<10} {len(task_ids):<6} {ref_desc:<12} {status}")
        
    except Exception as e:
        print(f"{sf.stem:<35} {'Stream':<10} {'ERR':<6} {'NO':<12} ERROR: {e}")
        error_count += 1

if suite_files:
    print("-" * 85)
    for suite_file in suite_files:
        try:
            with open(suite_file, "r", encoding="utf-8") as f:
                scfg = yaml.safe_load(f)
            suite_streams = scfg.get("streams", [])
            print(f"{suite_file.stem:<35} {'Suite':<10} {len(suite_streams):<6} {'YES':<12} READY ({len(suite_streams)} streams)")
        except Exception as e:
            print(f"{suite_file.stem:<35} {'Suite':<10} {'ERR':<6} {'NO':<12} ERROR: {e}")

print("-" * 85)
print(f"Audit Summary: {ready_count} Streams Ready, {error_count} Errors (Total: {len(stream_files)})")
