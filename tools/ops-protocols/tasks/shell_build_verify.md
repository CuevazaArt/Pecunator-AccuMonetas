# Task: Verificación de Desktop Shell (Flutter)

## Objective
Ensure that the Flutter frontend of the desktop shell compiles correctly,
has no static analysis regressions, and stays in sync with the
FastAPI backend schemas.

## Contexto del Proyecto
- **Ubicación:** `desktop_shell/`
- **Framework:** Flutter (Windows desktop)
- **Backend schemas:** `runtime/api/schemas.py` (Pydantic models)
- **Previous analysis:** `desktop_shell/analyze_out.txt`
- **Config:** `desktop_shell/pubspec.yaml`

## Execution Steps

### Step 1 — Static Analysis
```bash
cd desktop_shell && flutter analyze
```
Capture full output. Classify issues as:
- 🔴 **Errors** — Prevent compilation
- ⚠️ **Warnings** — Possible problems
- 💡 **Info/Hints** — Improvement suggestions

### Step 2 — Compare with Previous Analysis
Read `desktop_shell/analyze_out.txt` (previous analysis).
Detect:
- **New** issues that did not exist before → Regressions
- **Resolved** issues that no longer appear → Progress
- **Persistent** issues → Pending technical debt

### Step 3 — Verify Compilation
```bash
cd desktop_shell && flutter build windows --debug
```
If it fails:
- Capture exact error
- Identify whether it is a dependency, code, or configuration error
- Propose fix

### Step 4 — Schema Sync
Compare the frontend data models (Dart files in `lib/`)
with backend schemas in `runtime/api/schemas.py`:

- Do field names and types match?
- Are there new backend fields that the frontend does not know about?
- Are there deprecated backend fields that the frontend still uses?

Generate discrepancy table:
| Schema Backend | Modelo Frontend | Estado | Discrepancia |
|---------------|----------------|--------|-------------|
| BotStatus     | BotStatusModel | ✅/⚠️  | [detalle]    |
| ...           | ...            | ...    | ...         |

### Step 5 — Dependencies
Review `pubspec.yaml` and `pubspec.lock`:
- Are there packages with very old versions?
- Are there deprecation warnings in dependencies?

### Step 6 — Update Record
Save the new `flutter analyze` output to `desktop_shell/analyze_out.txt`
for the next comparison.

## Expected Output
Report with:
1. Compilation status: ✅ BUILD OK / 🔴 BUILD FAILED
2. Static analysis: X errors, Y warnings, Z hints
3. Delta vs previous analysis: +N new, -M resolved
4. Schema sync table
5. List of dependencies to update (if applicable)

## Success Criteria
- [ ] `flutter analyze` executed
- [ ] Comparison with previous analysis performed
- [ ] Debug build attempted
- [ ] Schema sync verified
- [ ] `analyze_out.txt` updated
