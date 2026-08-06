## Agent Behaviour Rules

### General Behavior

- MUST: Ask for clarification when requirements are ambiguous
- MUST: Verify all changes work before confirming completion
- SHOULD: Run tests before committing code
- SHOULD: Provide clear explanations for complex changes
- SHOULD NOT: Make assumptions about file locations or project structure

### Error Handling

- MUST: Report errors with full context to the user
- MUST: Continue processing other items when individual items fail
- SHOULD: Suggest solutions when errors occur
- SHOULD: Validate inputs before processing
- SHOULD NOT: Silently ignore errors or warnings

## USER-FILES Protection Rules

### ABSOLUTE FORBIDDEN - USER-FILES/04.INPUT/
- MUST NEVER: Create, delete, modify, move, or rename ANY files in USER-FILES/04.INPUT/
- CAN ONLY: Read files from USER-FILES/04.INPUT/

### General USER-FILES Rules
- MUST: Never create, delete, modify, move, or rename files in USER-FILES/ without explicit permission
- MUST: Ask before any operation in USER-FILES/
- SHOULD: Only read from USER-FILES/04.INPUT/ and write to USER-FILES/05.OUTPUT/
- SHOULD NOT: Implement any auto-cleanup or archiving features

## Project Structure Rules

- MUST: Read inputs only from USER-FILES/04.INPUT/
- MUST: Write outputs only to USER-FILES/05.OUTPUT/ with timestamps (YYMMDD_HHMMSS format)
- SHOULD: Preserve input directory structure in outputs

## Python Code Standards

- MUST: Use type hints for all function signatures
- MUST: Use pathlib.Path for file operations (not os.path)
- SHOULD: Keep functions under 50 lines
- SHOULD: Format with black and lint with ruff
- SHOULD: Add docstrings for all public functions

## Testing Standards

- MUST: Write tests for critical functionality
- SHOULD: Test happy paths and edge cases
- SHOULD: Mock external dependencies
- SHOULD: Keep tests fast and focused

## Configuration Management

- MUST: Use environment variables for sensitive data
- MUST: Validate configuration at startup
- SHOULD: Provide sensible defaults

## Dependency Management

- MUST: Pin exact versions in requirements.txt
- MUST: Use virtual environments
- SHOULD: Keep dependencies minimal

---

## Architecture: Engine Interface

### Core Concept
The Frame Composer (Vehicle) delegates all API/provider logic to Engine plugins.
"The Vehicle orchestrates. The Engine executes. The profile configures."

### Engine Loading
- `src/engine_loader.py` — canonical `load_engine()` implementation
- Uses `EngineLoadContext` dataclass (single param: `load_engine(ctx)`)
- Searches `search_paths` for `engine-<platform>/` directories
- Local clones take precedence over pip-installed packages (VEHICLE_CONTRACT §2b)
- Corrupted local engine falls back to pip-installed package (Stub 5 fix)
- After engine load, `copy_standby_profiles()` seeds `USER-FILES/02.STANDBY/` from the engine package

### Supported Platforms
`replicate`, `fal`, `openrouter`, `google` — new engines added by installing the corresponding package.

### Processing Flow

Standalone mode (TTY):
```
main() → _run_standalone()
  → handle_first_run()           # engine check → wizard → STANDBY seed
  → load_profile_standalone()    # profile from 03.PROFILES/ or 02.STANDBY/
  → _apply_cli_overrides()       # merge CLI flags into profile
  → get_api_key() / wizard       # 4-tier auth with TTY fallback
  → load_engine()                # real engine with chosen profile
  → read_markdown_files()        # parse .md inputs
  → _handle_preflight_checks()  # cost/dry-run early exit
  → _execute_pipeline()          # build_inputs → engine.run() → report
```

Studiolot mode:
```
main() → _run_studiolot()
  → load_profile_studiolot()
  → _apply_cli_overrides()
  → read_markdown_files()
  → _handle_preflight_checks()
  → get_api_key(platform)
  → _resolve_engine_for_studiolot()
  → _execute_pipeline()
```

### CLI Modes
1. **Standalone mode** (no `--profile`/`--input_dir`/`--output_dir`): reads profile from `USER-FILES/03.PROFILES/` (fallback `02.STANDBY/`), inputs from `USER-FILES/04.INPUT/`, outputs to `USER-FILES/05.OUTPUT/`
2. **Studiolot mode** (with `--profile --input_dir --output_dir`): explicit paths for all three, discovers Engine via `00_APPLICATIONS/ENGINES/` walking up from output_dir

---

## Source File Map (current)

| File | Purpose |
|------|---------|
| `run.py` | Bootstrap: venv management, dependency install, launches `src/main_simple.py` with TTY passthrough |
| `src/main_simple.py` | Entry point, CLI routing, both run modes, engine pre-check, interactive wizard fallback |
| `src/cli.py` | argparse definition (declarative `_ARGUMENTS` list) |
| `src/engine_loader.py` | Canonical `load_engine()` + `EngineLoadContext` dataclass + `copy_standby_profiles()` |
| `src/engine_helpers.py` | Engine discovery, installation, input construction, loading, `print_engine_not_found()` (lists all platforms) |
| `src/engine_contract.py` | `EngineInputFile` protocol — shared contract for Engine.InputFile |
| `src/processing/markdown_parser.py` | `parse_markdown()`, `extract_prompt_text()`, `extract_all_image_urls()`, `read_markdown_files()` — prompted + URL parsing + directory batch reader |
| `src/processing/first_run.py` | `handle_first_run()` — engine check, wizard launch, STANDBY seeding; extracted from `_run_standalone()` |
| `src/processing/profiles.py` | Profile loading (standalone + studiolot) via `_parse_profile_yaml()`, empty-STANDBY guidance |
| `src/auth/__init__.py` | 4-tier API key resolution + interactive wizard (`get_api_key_interactive`, `_prompt_platform`, `_prompt_and_save_key`, `_offer_engine_install`) |
| `src/auth/env.py` | .env file loading |
| `src/exceptions.py` | Custom exception hierarchy including `PreflightExit` |
| `src/constants.py` | Shared constants (`__version__`, `TIMESTAMP_FORMAT`, `DEFAULT_PLATFORM`) |
| `src/types.py` | `Bullet` TypedDict — core data structure |
| `src/utils/path_resolver.py` | Input/output path resolution with USER-FILES defaults |
| `src/utils/logging.py` | loguru configuration — 3-tier level (WARNING/INFO/DEBUG), `CONSOLE_FORMAT`/`FILE_FORMAT` constants |

---

## Configuration

- Profiles: YAML files in `USER-FILES/03.PROFILES/` (production) or `USER-FILES/02.STANDBY/` (engine-seeded backup)
- Profile format: `platform`, `parameters`, `prompt_prefix`, `prompt_suffix`, `pricing`, `paths`, `delay_between_requests`
- Standby profiles are engine-owned: `02.STANDBY/` is seeded by `copy_standby_profiles()` after engine install. Starts empty (`.gitkeep` only).
- API keys: env vars per platform (`REPLICATE_API_TOKEN`, `FAL_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`)
- .env file: loaded from project root on startup
- Interactive wizard: `get_api_key_interactive()` available when `sys.stdin.isatty()` — platform selection + API key save to .env

## Session History

### 2026-08-06 — Session 6: Clean Per-Image Progress Output (6/6 completed)
- Spec: `USER-FILES/07.TEMP/new_feature.md` + `USER-FILES/07.TEMP/questions.md` (3 questions, 0 resolved — feature took precedence)
- **Goal:** Remove fake Rich progress bar, replace with engine-driven `on_progress` callback output + loguru for Vehicle messages
- **T1 — Remove Rich Progress bar:** `_execute_pipeline()` at `src/main_simple.py:81-87` — dead `rich.progress.Progress` block replaced with plain `engine.run(inputs)`. 12 lines → 3 lines.
- **T2 — loguru results:** `_report_results()` at `src/main_simple.py:70-78` — `rich.console.Console` replaced with `logger.info` (summary) + `logger.error` (per-file failures). Error lines always visible; summary requires `--verbose`.
- **T3 — `--verbose` flag:** `setup_logging()` at `src/utils/logging.py:20` now accepts `verbose` param. 3-tier level: `DEBUG` (debug) > `INFO` (verbose) > `WARNING` (default). Added `--verbose` to `_ARGUMENTS` in `src/cli.py`. Wired through `main()` at `src/main_simple.py:113`.
- **T4 — Plain stderr progress:** `_emit_progress()` at `src/engine_helpers.py:110-113` — Rich `Console(stderr=True).print("[bold blue]...")` → `sys.stderr.write` + `flush`. Engine messages bypass loguru level filter, always visible.
- **Cleanup — Drop Rich:** Removed `rich>=13.0.0` from `requirements.txt`. Zero Rich references remain in Python source.
- **T5 — File logging:** Verified `add_file_logging(output_dir)` already called at `src/processing/first_run.py:46` during every standalone run. No changes needed.
- 4 files modified, `main_simple.py`: 251 → 234 lines. All pass `ast.parse()`, all under 250L.
- **Manifesto note:** §12 previously stated "Rich for progress displays." This session removed Rich entirely — engine-driven `on_progress` callbacks provide per-image progress, loguru handles all Vehicle output. The §12 guideline is superseded by this approach for this project.
- Per manifesto §15, no tests written or run.

### 2026-08-05 — Session 5: TODO-Driven Review Pass (4/4 completed)
- Spec: `USER-FILES/07.TEMP/new_feature.md` + `USER-FILES/07.TEMP/questions.md` (9 questions resolved)
- Confirmed all 8 Session 4 stubs were already implemented; this was a review pass closing remaining gaps
- **BACKEND/PARSING (1pt):** Fixed stale `parse_markdown()` docstring — "no image URLs found" removed (guard was removed in Session 4 but docstring wasn't updated)
- **BACKEND/ERRORS (1pt):** `print_engine_not_found()` now iterates `SUPPORTED_PLATFORMS` and prints clone/pip/env-var instructions for all four engines, not just one
- **BACKEND/AUTH (2pt):** Added `_offer_engine_install()` to `get_api_key_interactive()` wizard — checks `importlib.util.find_spec(f"engine_{platform}")`, offers to clone/install via `auto_install_engine()` if missing; exits with manual instructions on decline or failure
- **ARCHITECTURE (3pt):** Created `src/processing/first_run.py` with `handle_first_run()` — extracted engine-check + TTY detection + wizard + STANDBY-seed block from `_run_standalone()`. Also moved `_read_markdown_files()` → `read_markdown_files()` into `markdown_parser.py`. `main_simple.py`: 308 → 250 lines
- 4 files modified, 1 new file (`first_run.py`), all pass `ast.parse()`, all within file-size limits
- Per manifesto §15, no tests written or run

### 2026-08-04 — Session 4: Standalone Fix Batch (8/8 stubs)
- Spec: `USER-FILES/07.TEMP/new_feature.md`
- **Block A — Foundation (3):** Stub 8 TTY fix (`stdin=None` in run.py subprocess), Stub 2 text-to-image (removed ValueError guard for empty urls), Stub 6 unified auth error messages
- **Block B — Engine Loader (2):** Stub 4 signature drift (dataclass stays canonical), Stub 5 pip fallback (try/except around exec_module)
- **Block C — First-Run UX (2):** Stub 1 interactive wizard (`get_api_key_interactive`, `_prompt_platform`, `_prompt_and_save_key` wired into `_run_standalone`), Stub 7 engine pre-check (fires before API key, prevents sequential cascade)
- **Block D — Engine-Owned Profiles (2):** Stub 3 moved 10 STANDBY YAMLs out + `copy_standby_profiles()` in engine_loader + wired into `load_engine_or_install()`, empty-STANDBY `ConfigurationError` with engine install guidance
- 7 files modified, 0 new files, all pass `ast.parse()`, all under 250L
- Unanswered Q1-Q4 resolved by Manifesto defaults: FC-only scope, dataclass canonical, `stdin=None` TTY fix, hard-error for empty STANDBY
- External repo changes (engine-replicate profiles, studiolot/MC engine_loader sync) documented in handoff section below

### 2026-08-04 — Session 3: Full Refactor Sweep (22/22 tasks)
- Applied all items from `USER-FILES/07.TEMP/260804_134720_refactor_report.md`
- **High (2):** `EngineLoadContext` dataclass (6 params → 1), SRP split — `main_simple.py` 365→232 lines with `profiles.py` + `engine_helpers.py` + `types.py` extraction
- **Medium (8):** `DEFAULT_PLATFORM` constant, declarative CLI `_ARGUMENTS` list, shared `_execute_pipeline()`, `PreflightExit` exception, `run.py` bootstrap split (`_find_valid_venv`/`_create_or_repair_venv`/`_upgrade_pip`/`_install_requirements`), `_parse_profile_yaml()` DRY, `EngineInputFile` protocol + `validate_input_file()`
- **Low (12):** `--no-progress` dead flag removed, `__version__` constant, `Bullet` TypedDict, `PASS_STORE_PREFIX`, import ordering in logging.py, `CONSOLE_FORMAT`/`FILE_FORMAT` constants, `parse_bullet()` combined parser, `Optional[str]→str|None`, `from __future__` removed (3.10+ min), `pyproject.toml`, `conftest.py`
- 6 new files, 11 modified, 18/20 tests pass (2 pre-existing failures), all 21 .py files pass `ast.parse()`

### 2026-08-04 — Session 2: Refactor Report Execution (16/16 tasks)
- Applied all items from `USER-FILES/07.TEMP/260804_000000_refactor_report.md`
- **High (3):** Silent error swallowing → `logger.warning`, missing CLI overrides in studiolot mode → fixed, `_build_inputs` dynamic import → try/except
- **Medium (5):** `_call_load_engine()` extracted to DRY `_load_engine_or_install`, `_resolve_engine_for_studiolot()` extracted (28→SRP split), `_handle_preflight_checks()` extracted from `_run_standalone`, dead `config` param removed from path_resolver, `ENGINE_INSTALL_MESSAGE` parameterised
- **Low (8):** Return types `-> int` added, `SUPPORTED_PLATFORMS` consolidated in auth, `MAX_WALK_DEPTH` → default param, emoji → plain text in run.py, `_GENAI` suffix, `_handle_subprocess_error()` extracted in run.py, Replicate default removed from `get_api_token_from_env()`
- Tests updated: `test_path_resolver.py` signatures and `_GENAI` assertion
- 5 source files modified, 1 test file updated, all pass `ast.parse()`

### 2026-08-04 — Session 1: Systematic Refactor (31/33 tasks)
- Source: 1,173 → 964 lines (-17.7%)
- Tests: 0 → 153 lines (4 test files: markdown_parser, engine_loader, auth, path_resolver)
- Deleted: `src/processing/discovery.py` (154L dead), 5 dead deps, 5 dead constants
- Auth: parameterized by platform (replicate/fal/openrouter/google)
- main_simple.py: extracted `_report_results()`, `_load_engine_or_install()`, `_apply_cli_overrides()`
- path_resolver: single-profile API, dead branches removed, suffix constant
- Exceptions: RecoverableAPIError/FatalAPIError removed, pass statements removed
- Package init files created, __pycache__ cleaned, AGENTS.md rewritten
- 2 deferred: EngineLoadContext dataclass + split load_engine() (needs Engine plugin compat review)

---

## Known Issues & Technical Debt

### New (2026-08-06 — Session 6)
- `_emit_progress()` writes directly to `sys.stderr` bypassing loguru — engine progress messages won't appear in file logs. The log file will only contain Vehicle-level messages (errors, summary). This may be intentional (engine output is per-run ephemera).
- Feature spec's T5 indicated standalone had no file logging — investigation showed `add_file_logging()` was already called in `first_run.py:46`. No bug, but spec/implementation mismatch noted.
- 3 questions in `USER-FILES/07.TEMP/questions.md` remain unanswered. Implementation proceeded from code examples in the spec rather than waiting for resolution.

### Remaining (2026-08-04)
- `_build_inputs()` still dynamically imports `engine_{platform}` — `EngineInputFile` protocol validates the constructor signature at import time, but the per-platform dynamic import remains inherently fragile at module-load time (no way to statically verify all engines)
- `_resolve_engine_for_studiolot()` uses `load_engine()` directly while standalone mode uses `load_engine_or_install()` — slight asymmetry; both could use engine_helpers
- 2 pre-existing test failures: `test_missing_key_raises` (real `.env` bypasses env mock) and `test_custom_path_from_profile` (needs `/tmp/test_input` to exist on disk)
- `PreflightExit` is now caught in `main()` but studiolot mode calls `_handle_preflight_checks()` without a dedicated try/except — relies on the outer `main()` handler; works but is implicit
- `USER-FILES/02.STANDBY/` is empty after profile migration — needs `engine-replicate` repo to add `profiles/standby/` before FC standalone mode can seed profiles via `copy_standby_profiles()`

### Resolved (Session 4)
- Stub 8: TTY broken in subprocess → `stdin=None` fix
- Stub 2: Text-to-image blocked by ValueError → guard removed
- Stub 6: Conflicting auth error messages → unified
- Stub 4: engine_loader signature drift → dataclass is canonical
- Stub 5: Corrupted local engine crashes → try/except → pip fallback
- Stub 1: No interactive wizard → `get_api_key_interactive()` implemented + wired
- Stub 7: Sequential cascade (API key then engine) → engine pre-check before API key
- Stub 3: Profiles in Vehicle → moved to engine-owned, `copy_standby_profiles()` added
- Empty STANDBY: cryptic error → install-engine guidance

### External Repo Handoff (Session 4)
- **engine-replicate**: Create `engine_replicate/profiles/standby/` with the 10 deleted YAMLs. Update `__init__.py` and `pyproject.toml` package-data.
- **studiolot**: Create/update `pipeline/engine_loader.py` to match FC's `EngineLoadContext` dataclass signature + Stub 5 try/except fallback.
- **motion-conductor**: Sync `src/engine_loader.py` to match FC's `EngineLoadContext` dataclass signature + Stub 5 try/except fallback.

### Resolved (Session 3)
- `load_engine()` 6-param → `EngineLoadContext` dataclass (1 param)
- `main_simple.py` SRP split: 365→232 lines, extracted to `profiles.py`, `engine_helpers.py`, `types.py`
- `DEFAULT_PLATFORM` constant — single source of truth for `"replicate"` default
- `"replicate"` hardcoded at 4 sites → all reference `DEFAULT_PLATFORM`
- Declarative CLI `_ARGUMENTS` list — new flags are 1 dict literal
- Shared `_execute_pipeline()` — eliminates 12-line duplicate in both run modes
- `_handle_preflight_checks()` sentinel `int|None` → `PreflightExit` exception
- `_call_load_engine()` thin wrapper → replaced with `_make_engine_ctx()`
- `_parse_profile_yaml()` extracted — single change-point for profile parsing
- `EngineInputFile` protocol + `validate_input_file()` in `engine_contract.py`
- `run.py` bootstrap split: `_find_valid_venv()`, `_create_or_repair_venv()`, `_upgrade_pip()`, `_install_requirements()`
- `--no-progress` dead flag removed from CLI
- `__version__` constant in `constants.py`, referenced by banner
- `Bullet` TypedDict — typed contract for bullet data (path, prompt, reference_urls)
- `PASS_STORE_PREFIX` constant in auth module
- Import order fixed in `logging.py` (stdlib → third-party)
- `CONSOLE_FORMAT` / `FILE_FORMAT` module-level constants
- `parse_bullet()` — single-pass markdown parser (prompt + URLs in one split)
- `Optional[str] → str|None` in `path_resolver.py`
- `from __future__ import annotations` removed from all files (3.10+ min)
- `pyproject.toml` — ruff, black, pytest, project metadata
- `conftest.py` — pytest path configuration

### Resolved (Session 2)
- run.py emoji → plain text: `[REPAIR]`, `[INSTALL]`, `[OK]`, `[ERROR]`, `[WARN]`
- `_run_studiolot()` now applies CLI overrides via `_apply_cli_overrides(profile, args)` at line 289
- Output suffix `_IMG-TO-IMG` → `_GENAI` in path_resolver.py
- `_read_bullets()`: silent `pass` → `logger.warning` for prompt/URL extraction failures
- `_load_engine_or_install()`: duplicate `load_engine()` call → extracted `_call_load_engine()` helper
- `resolve_input_path()` / `resolve_output_base_path()`: dead `config` parameter removed
- `MAX_WALK_DEPTH` constant → default parameter in `_find_project_engines_dir()`
- `SUPPORTED_PLATFORMS` duplicated in two files → consolidated in `auth/__init__.py`, derived from `_PLATFORM_KEY_MAP`
- `get_api_token_from_env()`: Replicate-specific default removed
- `run.py`: duplicate subprocess error handling → `_handle_subprocess_error()` helper
- All entry functions (`main`, `_run_studiolot`, `_run_standalone`) now have `-> int` return type annotations

### Resolved (Session 1)
- Engine interface migration: all provider SDKs loaded via `load_engine()` instead of direct import
- Dead code purge: ~186 lines removed (discovery.py, dead imports, dead constants, dead exceptions)
- Profile dict mutation: replaced with `_apply_cli_overrides()` returning a copy
- Duplicate results-reporting: extracted to `_report_results()`
- Auto-install retry: extracted to `_load_engine_or_install()`
- Auth hardcoded for Replicate: parameterized by platform
- Log filename: `replicate_wrapper` → `frame_composer`
- Missing `__init__.py` files: created for all packages
- Stale `__pycache__`: cleaned
