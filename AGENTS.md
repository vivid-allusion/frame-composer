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
- MUST: Mirror input folder structure into the timestamped output directory (`relative_dir` metadata on `InputFile`)

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
- `src/engine_loader.py` — vendored byte-identical snapshot of studiolot's
  `pipeline/engine_loader.py` (**canonical home** — change there first, then
  re-vendor; verify with a three-way diff against MC)
- Uses `EngineLoadContext` dataclass (single param: `load_engine(ctx)`)
- Searches `search_paths` for `engine-<platform>/` directories
- Local clones take precedence over pip-installed packages (VEHICLE_CONTRACT §2b)
- Corrupted local engine falls back to pip-installed package (Stub 5 fix)
- After engine load, `copy_standby_profiles()` seeds `USER-FILES/02.STANDBY/` from the engine package

### Supported Platforms
`replicate`, `fal`, `openrouter`, `google`, `beeble`, `evolink` — new engines added by installing the corresponding package.

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
| `src/engine_loader.py` | Vendored snapshot of studiolot's `pipeline/engine_loader.py` (canonical) — `load_engine(ctx)` + `EngineLoadContext` + `copy_standby_profiles()` |
| `src/engine_helpers.py` | Engine discovery, installation, input construction (`build_inputs()` passes `relative_dir` metadata, `_relative_dir()`), loading, `print_engine_not_found()` (lists all platforms) |
| `src/engine_contract.py` | `EngineInputFile` protocol — shared contract for Engine.InputFile (requires `path`, `prompt`, `reference_urls`, `metadata`) |
| `src/processing/markdown_parser.py` | `parse_markdown()`, `extract_prompt_text()`, `extract_all_image_urls()`, `read_markdown_files()` — prompted + URL parsing + directory batch reader |
| `src/processing/first_run.py` | `handle_first_run()` — engine check, wizard launch, STANDBY seeding; extracted from `_run_standalone()` |
| `src/processing/profiles.py` | Profile loading (standalone + studiolot) via `_parse_profile_yaml()`, empty-STANDBY guidance |
| `src/processing/payload.py` | Generation payload: `compose_payload()` (recipe JSON schema v1, optional `error` field) + `error_info()` + `fit_payload()` + `compose_run_payloads()` (once-per-run composition) + `embed_payloads()` + `inject_payload()`/`read_payload()` |
| `src/processing/placeholders.py` | Vehicle-side error placeholders: `write_placeholders()` + `derive_size()` + `render_placeholder()` (Pillow) |
| `src/processing/payload_containers.py` | Pure byte transforms: XMP packet serializer, PNG iTXt / JPEG APP1 / WebP `XMP ` chunk envelopes + readers, `detect_format()` |
| `src/processing/context.py` | `PipelineContext` dataclass — shared orchestration state for payload/placeholder/log stages |
| `src/processing/results.py` | `is_success()` + `success_paths()` — single source of truth for the "ok + has path" result filter |
| `src/auth/__init__.py` | 4-tier API key resolution + interactive wizard (`get_api_key_interactive`, `_prompt_platform`, `_prompt_and_save_key`, `_offer_engine_install`) |
| `src/auth/env.py` | .env file loading |
| `src/exceptions.py` | Custom exception hierarchy including `PreflightExit` |
| `src/constants.py` | Shared constants (`__version__`, `TIMESTAMP_FORMAT`, `DEFAULT_PLATFORM`) |
| `src/datatypes.py` | `MarkdownFile` TypedDict — core data structure |
| `src/utils/path_resolver.py` | Input/output path resolution with USER-FILES defaults |
| `src/utils/logging.py` | loguru console configuration + complete-run capture: `_TerminalCleaner` (ANSI strip + CR collapse), `start_output_capture()`, `captured_output()`, `write_run_logs()` (header + payload + capture + summary per-file logs) |

---

## Configuration

- Profiles: YAML files in `USER-FILES/03.PROFILES/` (production) or `USER-FILES/02.STANDBY/` (engine-seeded backup)
- Profile format: `platform`, `parameters`, `prompt_prefix`, `prompt_suffix`, `pricing`, `paths`, `delay_between_requests`
- Standby profiles are engine-owned: `02.STANDBY/` is seeded by `copy_standby_profiles()` after engine install. Starts empty (`.gitkeep` only). Content is gitignored — only `.gitkeep` is tracked.
- API keys: env vars per platform (`REPLICATE_API_TOKEN`, `FAL_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, `BEEBLE_API_KEY`, `EVOLINK_API_KEY`)
- .env file: loaded from project root on startup
- Interactive wizard: `get_api_key_interactive()` available when `sys.stdin.isatty()` — platform selection + API key save to .env

---

## History

The chronological record (session history, known issues & technical debt,
external-repo handoffs) moved to [`docs/HISTORY.md`](docs/HISTORY.md) — it is
not loaded every turn. Read it on demand.
