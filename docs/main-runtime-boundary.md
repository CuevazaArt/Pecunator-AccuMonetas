# `main` vs `runtime` Boundary

Updated: 2026-04-29

## Why both exist

- `main.py` (repo root) is a **bootstrap entrypoint** for operators and scripts (`python main.py`).
- `runtime/` is the **engine package** that owns real behavior: API, Binance connector, bot hubs, persistence, and domain modules.

This split is conventional in scalable Python projects: a thin executable wrapper + an importable package.

## Critical evaluation

### What was weak

- Ambiguity between "startup script logic" and "engine domain logic" can cause tight coupling and harder testing.
- Operational scripts and examples were previously mixed with product paths, which blurred ownership.

### What is now stronger

- Root `main.py` stays minimal and stable.
- `runtime/main.py` concentrates engine lifecycle and server startup.
- Domain modules live under `runtime/modules/` with API as a façade (`runtime/api/`), which limits cross-layer coupling.
- Script responsibilities are explicit (`scripts/ui`, `scripts/engine`, `scripts/data`).
- Legacy examples are isolated under `examples/` (reference-only, non-functional).

## Scaling convention

1. Keep root `main.py` thin: no business logic, no connector setup details.
2. Keep orchestration in `runtime/main.py` and composition in `runtime/api/app.py`.
3. Keep bot strategies under `runtime/modules/bots/*`; avoid direct UI coupling.
4. Keep shared infrastructure in `runtime/core/*` and connectors in `runtime/connectors/*`.
5. Treat `examples/` as read-only references; never import them from runtime.

## Practical command surface

- Operator bootstrap: `python main.py`
- Package bootstrap: `python -m runtime`
- Engine scripts: `scripts/engine/*`
- UI scripts: `scripts/ui/*`

## Next recommended step

- When compatibility bridges are no longer needed, gradually retire direct imports from `runtime/bot/*` in favor of `runtime/modules/bots/*` only.
