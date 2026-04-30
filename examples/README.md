# Examples (reference-only)

This folder consolidates historical examples from `exampleJV` and `exampleJV_enhanced`.

## Important

- Content here is **reference-only**.
- Runtime production code must live in `runtime/` (especially `runtime/modules/bots/`).
- Flutter hubs must use runtime services, not direct code under `examples/`.

## Included references

- `dorothy7.0-reference/` legacy standalone sample extracted for documentation and comparison.
- `enhanced/` placeholder for incoming collaboration examples before incremental runtime integration.

## Workflow

1. Review an example in `examples/`.
2. Port only validated improvements into `runtime/modules/*`.
3. Document the integration in `docs/CHANGELOG.md`.
