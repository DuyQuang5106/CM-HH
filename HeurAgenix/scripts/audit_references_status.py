from pathlib import Path
import json
import yaml

repo = Path(".")
reg_path = repo / "cmhh/configs/tasks/task_registry.yaml"
with open(reg_path, "r", encoding="utf-8") as f:
    reg = yaml.safe_load(f)

tasks = reg.get("tasks", [])
print(f"Total registered tasks: {len(tasks)}\n")
print(f"{'Task ID':<25} {'Problem':<10} {'Validation':<12} {'Test':<12} {'Status'}")
print("-" * 75)

full_count = 0
partial_count = 0
empty_count = 0

for t in tasks:
    tid = t["task_id"]
    prob = t["problem"]
    ref_path = repo / t["reference"]["path"]
    
    val_cnt, test_cnt = 0, 0
    if ref_path.exists():
        try:
            data = json.loads(ref_path.read_text(encoding="utf-8"))
            records = data.get("records", [])
            val_cnt = sum(1 for r in records if "validation" in r.get("instance_id", ""))
            test_cnt = sum(1 for r in records if "test" in r.get("instance_id", ""))
        except Exception:
            pass
            
    if val_cnt >= 10 and test_cnt >= 30:
        status = "FULL (Ready)"
        full_count += 1
    elif val_cnt > 0 or test_cnt > 0:
        status = f"PARTIAL ({val_cnt+test_cnt}/40)"
        partial_count += 1
    else:
        status = "EMPTY (0/40)"
        empty_count += 1
        
    print(f"{tid:<25} {prob:<10} {val_cnt:>2}/10        {test_cnt:>2}/30        {status}")

print("-" * 75)
print(f"Summary: {full_count} Full, {partial_count} Partial, {empty_count} Empty (Total: {len(tasks)})")
