# CM-HH Documentation Map

This directory contains the canonical research and implementation documents for
CM-HH. Documents are grouped by purpose so the project has one clear source of
truth for each kind of decision.

## Source of Truth

Use `source_of_truth/` for documents that define the meaning of the research and
the required implementation contracts.

- `source_of_truth/CMHH_Research_Specification.md`
  - Research thesis, task-stream semantics, RQs/hypotheses, evaluation metrics,
    statistical protocol, and interpretation rules.
  - This document wins when a change would affect the meaning of a research
    claim or metric.
- `source_of_truth/CMHH_Archivist_Retriever_Design_Specification.md`
  - Research-level architecture for memory, Archivist, Retriever, storage vs
    retrieval-induced forgetting, and managed memory behavior.
- `source_of_truth/CMHH_Implementation_Ready_Specification.md`
  - Engineering contracts, schemas, runner lifecycle, integrity tests,
    acceptance gates, audit requirements, and definition of done.

## Planning

Use `planning/` for the live roadmap.

- `planning/Implementation_plan.md`
  - Current execution roadmap.
  - Maps the research and implementation-ready specifications into build
    phases, gates, and immediate next actions.
  - This replaces the older `HeurAgenix/Implementation_plan.md`.

## Logs

Use `logs/` for chronological implementation history.

- `logs/Implementation_Log.md`
  - Historical record of what changed, what was verified, and what remained
    blocked at each implementation increment.
  - This replaces the older `HeurAgenix/Implement_docs.md`.

## Archive

Use `archive/` for old notes that are useful context but not current authority.

- `archive/CM-HH original onboarding note.md`
  - Early onboarding/research idea note.
  - Useful for background, but superseded by the source-of-truth specs.
- `archive/Implementation_plan_legacy.md`
  - Previous implementation plan retained for traceability.
  - Superseded by `planning/Implementation_plan.md`.

## Assets

Use `assets/` for images and other non-text documentation assets.

- `assets/cmhh-overview.png`

## Reading Order

For research review:

1. `source_of_truth/CMHH_Research_Specification.md`
2. `source_of_truth/CMHH_Archivist_Retriever_Design_Specification.md`
3. `source_of_truth/CMHH_Implementation_Ready_Specification.md`
4. `planning/Implementation_plan.md`

For implementation work:

1. `planning/Implementation_plan.md`
2. `source_of_truth/CMHH_Implementation_Ready_Specification.md`
3. `logs/Implementation_Log.md`

For historical context:

1. `archive/CM-HH original onboarding note.md`
2. `archive/Implementation_plan_legacy.md`
