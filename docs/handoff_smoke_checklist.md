# CM-HH Handoff Smoke Checklist

Use this checklist to perform integration validation before launching long-running experiment suites.

---

## 1. Verify Environment & Reference Solvers

```powershell
# 1. Check dependency and solver health
uv run python scripts/check_reference_solvers.py

# 2. Validate configuration loading
uv run cmhh validate-config --experiment cmhh/configs/experiments/h1_isolated.yaml --stream cmhh/configs/streams/pilot/s1_tsp_scale.yaml
```

**Expected:**
- PyVRP, OR-Tools CP-SAT, and Concorde pass health checks.
- Configuration validation exits with code 0.

---

## 2. Pre-Flight Pilot Suite Audit

Run the pre-flight validator to inspect all streams, conditions, paired manifests, and reference parity without calling LLM APIs:

```powershell
uv run cmhh validate-pilot-suite
```

**Expected output:**
```text
Pilot Suite Validation
────────────────────────────
Streams                  4/4 PASS
Conditions               5/5 PASS
Seeds                    3/3 PASS

S2 CVRP pairing           PASS
S2 capacity ordering      PASS
S2 reference coverage     PASS

S3/S4 TSP-A parity        PASS
S3/S4 TSP-B parity        PASS
TSP-A != TSP-B            PASS

Cross-domain exec guard   PASS
Target contracts          PASS

Manifest parity           PASS
Reference parity          PASS

READY FOR EXPERIMENT
```

---

## 3. Quick Smoke Run (Optional Pre-Flight)

```powershell
uv run cmhh run-suite --suite cmhh/configs/suites/pilot_4streams.yaml --mode quick-smoke --seeds 1
```

A successful smoke verifies:
- `metrics.json` and run manifests are generated.
- Audit run passes with zero tracebacks.
- Observability logs contain properly redacted credentials.
