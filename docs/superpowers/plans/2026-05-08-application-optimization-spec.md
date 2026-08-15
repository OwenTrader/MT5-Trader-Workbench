# Application Optimization Spec

## Goal

Produce a prioritized optimization plan for the MT5 Trader Workbench application.

## Scope

- Read the existing Electron, React, and FastAPI codebase.
- Identify the highest-value reliability, maintainability, and product-completeness improvements.
- Sort the work by importance.
- Prefer DRY, YAGNI, TDD, and small safe changes.

## Constraints

- Use the repository's real scripts and structure.
- Do not invent lint or typecheck commands that do not exist.
- Python tests currently require explicit import-path handling in this repository.
- Frontend UI work should preserve existing shadcn-based patterns.
