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
- Standby profiles are engine-owned: `02.STANDBY/` is seeded by `copy_standby_profiles()` after engine install. Starts empty (`.gitkeep` only).
- API keys: env vars per platform (`REPLICATE_API_TOKEN`, `FAL_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`)
- .env file: loaded from project root on startup
- Interactive wizard: `get_api_key_interactive()` available when `sys.stdin.isatty()` — platform selection + API key save to .env

## Session History

### 2026-09-05 — Session 14: Systematic refactor from TODO backlog (32/32)
- Spec: `USER-FILES/07.TEMP/260905_111816_refactor_report.md` (refactor analysis) → structured TODO.md (32 tasks: 3 High, 15 Med, 14 Low with IDs, effort points, pairings).
- **T01/PipelineContext:** New `src/processing/context.py` — `PipelineContext` dataclass collapses the 6-9 param signatures of `compose_payload`, `compose_run_payloads`, `write_placeholders`, `write_run_logs`, `_execute_pipeline`. `_execute_pipeline` 9 params/88L → 1 param/~25L; progress display extracted to `_run_with_progress()` (documents the `_on_progress` swap as the de-facto Vehicle↔Engine progress contract — T04/T22).
- **T08:** `write_placeholders` cc16/8 params → `_should_write_placeholders` + `_success_paths` + `_write_error_placeholder` (cc ~5 each).
- **T17/T18:** `engine_loader.py` (canonical) — `load_engine` 67L/cc11 → 15L; new `find_engine_dir()` (raises, lists searched paths) + `find_first_engine_dir()`; internal `_load_engine_package()` + `_exec_from_dir()`. Error message contract unchanged. Re-vendor into motion-conductor + studiolot.
- **T19:** `first_run.py` — `_detect_engine_platform()` reuses `find_first_engine_dir`; `load_engine_or_install` now takes ctx (T21, `_seed_standby_profiles` extracted).
- **T02/T03:** `_prepare_profile()` (CLI overrides + platform precedence; fixes standalone ignoring `--platform`), `_load_engine_with_ctx()`, `_make_pipeline_context()` shared by both run modes.
- **T09/T16 + T15/T20:** shared `index_md_files()` (markdown_parser) + canonical `relative_posix()` (path_resolver) with unified `None`-fallback semantics; `_relative_dir`/`_relative_input_file` delegate.
- **T10:** `setup_logging` restored to 3-tier DEBUG > INFO(`--verbose`) > WARNING(default) — `--verbose` was dead.
- **T12:** fallback log name uses `TIMESTAMP_FORMAT`. **T23:** `_print_manual_install()` extraction. **T26:** all `src.X` absolute imports → relative.
- **T27:** `validate_image_urls` — bounded ThreadPoolExecutor (8 workers, order preserved). **T28 no-op:** `sorted(key=)` already precomputes keys once per element.
- **T32:** cli `_ARGUMENTS` TypedDict spec. **Dead code removed:** `list_standby`/`activate_profile` (profiles.py), `ValidationError` (exceptions), `project_name` return (path_resolver), TYPE_CHECKING `Callable` (markdown_parser).
- **T06:** missing active profile now exits 1 (was 0); guidance via stderr (T07/T29 policy documented in logging.py docstring).
- **Test repairs:** 4 pre-existing failures fixed (stale `_GENAI` assertion, `/tmp/test_input` fixture, auth error-match now "No API key found", removed no-URLs ValueError guard). Tests updated to ctx-based signatures.
- **Verification:** 62/62 tests pass; ruff (E,F,W,I,UP) clean repo-wide; black clean repo-wide (venv recreated in-project; black/ruff/pytest now installed there); compileall OK; `--help` smoke OK. New venv at `venv/` (gitignored).

### 2026-09-05 — Session 15: Cleanup report execution (8/8)
- Spec: `USER-FILES/07.TEMP/260905_145111_cleanup_report.md` (systematic cleanup analysis) → structured TODO.md (8 code tasks + 4 INFO items), all executed.
- **Dead code removed:** `find_vehicle_engines_dir()` (engine_helpers.py — zero callers), `venv_new` repair probes in run.py `_find_valid_venv`/`_create_or_repair_venv` (Session 12 artifact; only `venv/` is ever created).
- **Dependencies:** `replicate` removed from requirements.txt — verified `GAI_ENGINES/engine-replicate/requirements.txt` self-declares `replicate>=1.0`, so the Engine installs its own SDK. pyproject `dependencies` aligned with requirements.txt (added `rich` + `pillow`); requirements.txt remains the canonical bootstrap list.
- **Duplicate consolidation:** new `src/processing/results.py` — `is_success()` + `success_paths()` replace the 3× duplicated `status == "ok" and path` filter (`_generated_paths` in main_simple.py, `_success_paths` in placeholders.py, inline count in logging.py `_build_header`).
- **Docs:** README.md fully rewritten (311 → ~150 lines) to the real Engine/Vehicle architecture — removed references to deleted modules, `--no-progress`, 1Password/auth.yaml, `requests`/`natsort`, `_IMG-TO-IMG` suffix, payload `.md` files. AGENTS.md Source File Map `src/types.py | Bullet` → `src/datatypes.py | MarkdownFile` (historical Session 3 notes left untouched). run.py import order fixed (ruff --fix).
- **Verification:** 62/62 tests, ruff clean, black clean, compileall OK. No USER-FILES changes (INFO items reviewed, left untouched per protection rules).
- Note: Session 14 + 15 changes are still UNCOMMITTED in the working tree (`src/processing/context.py` + `src/processing/results.py` are untracked).

### 2026-08-31 — Session 13: Readable, LLM-friendly per-file run logs
- Spec: `USER-FILES/07.TEMP/new_feature.md` + `questions.md` (3 questions, all answered option 1: pytest tests govern over manifesto §15, one payload per log, terminal-faithful capture accepts progress-frame loss). Problem: Session 9's rich live display floods the Session 7 capture with ~21K in-place redraws (`\r` + `\x1b[2K`) — each `.log` was a 2.2 MB "character salad" written 203×.
- **T1 — Capture:** `src/utils/logging.py` — new `_TerminalCleaner` state machine (feeds char-by-chat, survives sequences split across write boundaries): strips all CSI (`\x1b[...final 0x40-0x7E`, incl. SGR/cursor/erase) + OSC (BEL or ST terminated); on `\r` discards the current line buffer, on `\n` finalises; `captured_output()` flushes a partial trailing line. Replaces the old SGR-only `_ANSI_ESCAPE` regex. `_TeeStream` now feeds the cleaner; the raw passthrough to the real terminal is untouched (byte-identical).
- **T2 — Payload:** `src/processing/payload.py` — new `compose_run_payloads()` composes every payload ONCE per run, keyed by `str(output path)`: success results → `json.dumps(..., indent=2, ensure_ascii=False)`; error results → `compose_payload(..., error=error_info(...))` + `fit_payload()` (byte-identical to what the placeholder embeds). `embed_payloads(results, payloads)` now takes precomposed text; `inject_payload()`'s `payload` param is optional (raises if both payload/text missing).
- **T3 — Wiring:** `src/main_simple.py` — `_execute_pipeline()` composes payloads right after `engine.run()`, passes them to `write_placeholders(payloads=...)` (new optional param; composes internally when omitted — placeholder tests unchanged), `write_run_logs(...)`, and `embed_payloads(...)`. Gains `run_mode` + `cli_args` params (both run modes pass them). `profiles.py` now annotates `profile["profile_path"]` so the header can cite the file.
- **T4 — Log writer:** `write_run_logs(generated_paths, output_dir, run_info, payloads, results, md_files)` — per-file logs hold, in order: run header (version, UTC start, run mode, platform, engine, profile path + endpoint/parameters/media_type/pricing, input/output roots, CLI args, counts), the named file's own payload (one per log per Q2), the cleaned console capture, and a per-input summary (status, output, error message/code/provider-id). Fallback log (`frame_composer_<ts>.log` when nothing generated) = header + capture + summary, no payload section. Logs are always written even with `--no-save-payloads` (flag gates image embedding only). Never contains API keys.
- **Design decisions:** terminal-faithful collapse means every intermediate progress frame vanishes (Q3 accepted); the final frame survives (terminal shows it). `Path.read_text()` must NOT be used on raw captured bytes in tests — universal-newlines mode converts `\r`→`\n` before the cleaner runs.
- **Verification:** `tests/test_logging.py` — 21 tests: cleaner (SGR/cursor/erase/OSC-BEL/OSC-ST, CSI split across feeds, CR collapse incl. across feeds, partial-line flush, rich-session simulation, stray-escape, plain passthrough), tee (raw bytes byte-identical to target, cleaned capture), stub-engine pipeline through `_execute_pipeline` (section order, payload section byte-identical to embedded payload, error payload in placeholder log, summary coverage, all-fail fallback, no API keys, logs with `--no-save-payloads`), real-log replay (2,232,770 bytes → 4,702 chars, 0 ESC, 23 lines, tens of KB). Full suite: 58 passed, 4 pre-existing failures unchanged. black + ruff clean.
- Line counts: `logging.py` 228, `payload.py` 194, `main_simple.py` 338 (orchestration cohesion), `test_logging.py` ~340.

### 2026-08-31 — Session 12: Vehicle-side error placeholder images
- Spec: `USER-FILES/07.TEMP/new_feature.md` + `questions.md` (8 questions; Q3/Q4 revised by author: placeholders only after ≥1 success — all-fail runs fail fast with logs; error text at decent size, crop overflow, full details in .log). Feature goal: botched individual jobs must not leave gaps in the output serial the user places on a video-editor timeline.
- **T1 — Dependency:** `requirements.txt` + `Pillow==12.3.0` (pinned). Also repaired the moved venv (recreated in place — old pyvenv.cfg pointed at `/home/admin/Downloads/frame-composer/venv`).
- **T2 — Engine contract:** `ENGINES/engine-replicate` — `OutputFile` gains `expected_path: Path | None`. `engine.py` precomputes the destination name BEFORE the API call (`{ts}-{stem}-{idx}{ext}`, ext from profile `output_format`/media default via new `_default_extension()`) and attaches it to all three error paths. Vehicle-side naming would have broken filename-sort serial (later timestamp groups placeholders at the end).
- **T3 — Payload:** `src/processing/payload.py` — `compose_payload()` accepts optional `error` dict; `error_info()` regex-extracts `E\d{3}` code + provider id (`p/<id>` / `prediction_id:`); `fit_payload()` halves `error.message` until the serialized JSON fits `MAX_JPEG_PAYLOAD` (keeps valid JSON); `inject_payload()` accepts pre-serialized `text`.
- **T4 — New module `src/processing/placeholders.py`:** `write_placeholders()` (orchestrates: skip when no successes / video media_type / legacy engine / unknown size; mkdirs, renders, embeds, logs-and-continues), `derive_size()` (aspect_ratio×resolution map: 16:9/21:9/1:1/9:16 × 1K/2K, fallback to first successful image dims via Pillow header), `render_placeholder()` (red 200,0,0 bg, black text, fixed font = width//60 min 12, textwrap, crop overflow).
- **T5/T6 — Wiring:** `_execute_pipeline()` calls `write_placeholders()` after `engine.run()` and passes placeholder paths to `write_run_logs()`; `_report_results(results, placeholders)` prints "Complete: N generated, M placeholders written, K errors" and still exits 1 when any generation failed.
- **Engine lint fixes:** `Callable` runtime import (same TYPE_CHECKING bug family as Session 7), SDK check via `importlib.import_module` (behavior-preserving: `None in sys.modules` raises ImportError).
- **Stale engine test fixes:** `bullet_path`→`source_path`, endpoint regex, ProgressEvent `.message` API, missing `urlretrieve` mock, `reference_param: start_image`, duration/fps moved to profile `parameters` (engine forwards params, not metadata). Engine suite now 39/39 green.
- **Verification:** Vehicle `tests/test_placeholders.py` — 16 tests (mixed run + payload round-trip, all-fail writes nothing, legacy engine skip, video skip, relative_dir mirror, save_payloads=False, JPEG truncation of 50KB error, derive_size mapping/fallback/None, render red/black + JPEG suffix + overflow crop, error_info). Stub-engine end-to-end through `_execute_pipeline`: mixed run → 2 generated + 1 placeholder + per-file `.log`, serial intact; all-fail run → 0 placeholders, fallback log, exit 1. Vehicle suite: 4 pre-existing failures unchanged (auth .env, /tmp/test_input, stale no_urls, stale _GENAI). black + ruff clean; ast.parse ok. No real API calls made (author's request — Replicate tokens).
- Line counts: `main_simple.py` 306 (soft-limit overrun justified: single cohesive orchestration, new logic extracted), `placeholders.py` 132, `payload.py` 166, engine.py 280 (single cohesive class).

### 2026-08-31 — Session 11: Natural sort for input markdown files
- Spec: user report — aborted run's generations started at `100_rw_ACM` instead of `1_rw` (natsort order).
- Diagnosis: `read_markdown_files()` used plain `sorted()` (lexicographic). `"100_rw_ACM" < "10_rw_IH_JP_JS"` and `"10x..." < "1_rw"` because digits sort below `_` — so `100_rw_ACM.md` is first in sorted order, and the Engine faithfully numbers outputs by `enumerate(inputs)`.
- **Fix:** `src/processing/markdown_parser.py` — added `_natural_sort_key()` (stdlib `re.split` digit chunks) and `sorted(..., key=_natural_sort_key)`. No new dependency.
- **Test:** `tests/test_markdown_parser.py` — `TestReadMarkdownFiles.test_natural_sort_order` (1/2/10/100 → natural order). Passes.
- Note: pytest now needed to verify locally (installed ad-hoc into venv; not in requirements.txt). 4 pre-existing test failures observed (2 documented + 2 stale: `test_no_urls_raises`, `test_creates_timestamped_dir` expecting `_GENAI` suffix).

### 2026-08-24 — Session 10: Embedded generation payload (image metadata)
- Spec: `USER-FILES/07.TEMP/new_feature.md` + `questions.md` (3 questions resolved: no tests per manifesto §15, parsed fields only, WebP append-only without VP8X flag).
- Goal: marry each generated image to its recipe — the payload JSON is embedded INSIDE the file (survives copies/B2 upload). Inspectable with exiftool/ImageMagick. Extraction into a bullet is deferred.
- **T1 — `payload_containers.py`:** new module, pure byte transforms, stdlib only. One XMP packet (`dc:description`, XML-escaped) wrapped by three envelopes: PNG `iTXt` (keyword `XML:com.adobe.xmp`, inserted before IEND, CRC'd), JPEG XMP `APP1` (right after SOI; idempotent strip of a previous segment), WebP `XMP ` RIFF chunk (RIFF size bumped; VP8X flag intentionally NOT set — exiftool/reader see it, browsers won't). `detect_format()` by magic bytes. No GIF/mp4 support.
- **T2 — `payload.py`:** `compose_payload()` — schema v1 (`schema`, `generated_at`, `vehicle`, `engine`, `endpoint`, `parameters`, `prompt` {raw, wrapped}, `prefix`, `suffix`, `reference_urls`, `input_file` relative to input root, `media_type`, `output_file`; never key material). `inject_payload()` — atomic rewrite (temp + `os.replace`), JPEG payload guard >60KB. `read_payload()` — reverses detection + XMP extraction. `embed_payloads()` — pairs results↔md_files by `source_path`, logs and continues on failure.
- **T3 — Wiring:** `_execute_pipeline()` gained `profile` + `save_payloads: bool = True`; both run modes pass `args.save_payloads`. Embedding runs after `write_run_logs()`.
- **Bug fix:** `_apply_cli_overrides()` no longer injects `save_payloads: False` into the API request params — the flag is gate-only now.
- **Verification (per §15):** 24-check script (round-trip per format incl. unicode, idempotency, PNG CRC walk, JPEG SOI/APP1, WebP RIFF size, ffprobe decodability, stub-engine `_execute_pipeline` end-to-end, no-save path) + ImageMagick `Profile-xmp` confirmation + CLI `--dry-run` smoke. All passed. A real API generation remains for the author to eyeball.
- 2 new files + `main_simple.py` modified (273 → 292).

### 2026-08-24 — Session 9: Animated live progress display
- Spec: user report — "stdout during run doesn't show an animation, more like just spitting out frames of the progress bar"
- Diagnosis (reproduced in a PTY): `_execute_pipeline()` printed one console line per engine event (~4 lines × N items) via `bar.console.print()`, and the default Progress bar only advanced per completed item — the live region worked, but the output read as hundreds of scrolled "frames" with a mostly-static bar.
- **Change:** `src/main_simple.py` — Progress now uses `SpinnerColumn` + `TextColumn(description)` + `BarColumn` + `TaskProgressColumn` + `TimeElapsedColumn`; `on_progress` sets `task.description` to the current engine message (rendered in place) instead of printing a line per event.
- Verified in a PTY: single live line, rotating spinner, ~33 in-place redraws, zero message spam; piped/non-TTY mode prints only the final state. Full messages still land in per-file `.log` via the tee capture.
- Correction: Session 6's claim that rich was dropped from requirements was inaccurate — `rich>=13.0.0` is in `requirements.txt` and is now actively used for the live display.

### 2026-08-24 — Session 8: Mirror input folder structure in outputs
- Spec: direct author request — "I want the folder structure of the input folder to be mirrored into the results of the output folder"
- **T1 — `_relative_dir()`:** `src/engine_helpers.py` — new helper returns a file's parent dir relative to the input root as a posix string (`""` for root-level files; `""` fallback when `input_root` is `None` or the path is outside it).
- **T2 — Input construction:** `src/engine_helpers.py` — `build_inputs()` gained an `input_root: Path | None` param and passes `metadata={"relative_dir": ...}` to every `InputFile`.
- **T3 — Wiring:** `src/main_simple.py` — `_execute_pipeline()` gained an `input_root` param, threaded from both run modes (`input_dir` in studiolot, `input_path` in standalone).
- **T4 — Contract updated:** `src/engine_contract.py` — `EngineInputFile` protocol + `validate_input_file()` now require `metadata`. Engines lacking it fail fast with a descriptive ImportError.
- **Engine-side:** feature was already supported — `engine_replicate/engine.py` reads `item.metadata.get("relative_dir")` and writes into `output_dir/<rel_dir>`. Per-file `.log` files mirror automatically (`write_run_logs()` writes beside each generated file).
- **Test:** `tests/test_engine_loader.py` — `TestRelativeDir` (4 cases: no root, root dir, nested dir, outside root).
- 4 source files + 1 test file modified.

### 2026-08-15 — Session 7: Complete per-file run logs (2/2 + 2 bug fixes)
- Spec: direct author request — "log files should be much more verbose, show the complete stdout, named [same name as generated file].log"
- **T1 — Complete output capture:** `src/utils/logging.py` — `start_output_capture()` tees stdout/stderr through `_TeeStream` (ANSI-stripped into a StringIO) and is called first thing in `main()`, before `setup_logging()` binds loguru. `write_run_logs(generated_paths, output_dir)` writes one log per generated file named `<generated-file-stem>.log` (e.g. `test-0-260815_151642.png` → `test-0-260815_151642.log`), falling back to `frame_composer_{time}.log` when nothing was generated. `add_file_logging()` + `FILE_FORMAT` deleted — superseded by full-run capture.
- **T2 — Wiring:** `main_simple.py` — `_execute_pipeline()` gained an `output_dir` param and calls `write_run_logs()` after `_report_results()`; both run modes pass `output_dir`.
- **Bug fix (pre-existing):** `src/engine_loader.py` — `Any`/`Callable` were TYPE_CHECKING-only imports used in runtime annotations; NameError on Python < 3.14 (lazy annotations). Moved to runtime import. MC's vendored copy has the same bug — sync later.
- **Bug fix (new code):** `_TeeStream.encoding` must be a property — rich Console does `getattr(file, "encoding", None).lower()`, which crashes on a method.
- Verified end-to-end against a real project (studiolot-mode run): per-file `.log` written beside the PNG with complete ANSI-clean output. Fallback path tested separately.
- 3 files modified, all pass `ast.parse()`, all under 250L. Per manifesto §15, no tests written.

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

### New (2026-09-05 — Session 15)
- Session 14 + 15 changes are UNCOMMITTED; `src/processing/context.py` and `src/processing/results.py` are untracked (`git add` both on next commit).
- `requirements.txt` uses `>=` pins (dotenv/loguru/yaml/rich) against the AGENTS.md "pin exact versions" rule — pre-existing gap, not addressed in cleanup; pin when dependencies next change.
- `pyproject.toml` dependencies are unpinned (`rich`, `pillow` added in Session 15) while requirements.txt pins `Pillow==12.3.0` — requirements.txt is canonical for venv bootstrap; keep the two aligned by package SET, accept version-spec divergence.
- `src/processing/results.py` helpers (`is_success`/`success_paths`) have no dedicated unit tests — covered indirectly by test_logging/test_placeholders (62 green). Add direct tests if they grow beyond the one-liner filter.
- `USER-FILES/01.CONFIG/config.yaml` is legacy and unread by any code path — it WILL look like config bloat to future cleanup scans; deliberately kept (USER-FILES protection). Do not re-flag.

### New (2026-09-05 — Session 14)
- `engine_loader.py` was split (`find_engine_dir()`, `find_first_engine_dir()`, `_load_engine_package()`, `_exec_from_dir()`) and `load_engine_or_install()` now takes an `EngineLoadContext`. motion-conductor + studiolot still vendor the old monolithic snapshot — re-vendor before they diverge further.
- `_run_standalone` is ~58 lines (SHOULD <50) — accepted: single cohesive orchestration; further splits would scatter state.
- `_write_error_placeholder` takes 5 params (ctx, result, by_source, payloads, size) — fold `by_source` into a per-run lookup if it grows further.
- `_on_progress` swap remains an engine-private API touch, now documented in `_run_with_progress()` as the de-facto Vehicle↔Engine progress contract. A public hook requires engine-repo changes (out of Vehicle scope).

### New (2026-08-31 — Session 13)
- ~~Repo-wide `black --check src/` is not clean~~ Resolved in Session 14 — black + ruff now clean repo-wide (black/ruff/pytest installed in the in-project venv).
- `tests/test_logging.py::TestRealLogReplay` depends on the external reference log at `/home/admin/Nextcloud-QO1/...` — guarded with `skipif` so the suite stays green when the path is absent.
- Log naming: `<generated-file-stem>.log` = `Path.with_suffix(".log")` (e.g. `0-a.png` → `0-a.log`). Tests must not expect `0-a.png.log`.

### New (2026-08-31 — Session 12)
- ~~`USER-FILES/04.INPUT/.gitkeep` shows as deleted~~ Resolved — no longer shows in the working tree.
- "Failure notification" for all-fail runs = loud stderr errors + exit 1 + fallback `frame_composer_<ts>.log` (no desktop notification). Matches revised Q3 as implemented; revisit only if the author wants OS-level alerts.

### New (2026-08-24 — Session 9)
- Payload extraction (embedded payload → regenerable bullet `.md`) is deferred — no CLI/UX built on `read_payload()` yet.
- GIF/mp4 outputs get no payload (`inject_payload` raises on unsupported format → logged, original kept). FC is image-only and png/jpg/webp cover the real cases; mp4 is MC's domain.
- JPEG XMP `APP1` has a 2-byte length field — payloads over ~60KB are rejected with an error. Prompts run ~1-5KB, so this is theoretical.
- WebP without `VP8X` (simple lossy files): the `XMP ` chunk is appended without a flag, so browsers won't surface it — exiftool/ImageMagick/`read_payload()` do. Deliberate per Q3.

### New (2026-08-15 — Session 7)
- Resolved: `_emit_progress()` previously bypassed loguru file sinks — the full-run capture now records engine progress, loguru output, prints, and rich progress in the per-file run logs.
- `motion-conductor` has the same TYPE_CHECKING-only annotation import bug in its vendored `engine_loader.py` and still uses the old minimal file-log pattern — sync both when MC is next worked on.
- Multiple generated files each get a complete-run `.log` copy (identical content). Intentional — one log per generated file per the naming contract.

### New (2026-08-06 — Session 6)
- Feature spec's T5 indicated standalone had no file logging — investigation showed `add_file_logging()` was already called in `first_run.py:46`. No bug, but spec/implementation mismatch noted. (Superseded in Session 7 — `add_file_logging()` deleted, replaced by complete-run capture.)
- 3 questions in `USER-FILES/07.TEMP/questions.md` remain unanswered. Implementation proceeded from code examples in the spec rather than waiting for resolution.

### Remaining (2026-08-04)
- `_build_inputs()` still dynamically imports `engine_{platform}` — `EngineInputFile` protocol validates the constructor signature at import time, but the per-platform dynamic import remains inherently fragile at module-load time (no way to statically verify all engines)
- ~~`_resolve_engine_for_studiolot()` load_engine/load_engine_or_install asymmetry~~ Mostly resolved in Session 14 — both run modes now share `_load_engine_with_ctx()`; standalone first-run still uses `load_engine_or_install()` by design (install fallback + STANDBY seed belong to first run only).
- ~~2 pre-existing test failures~~ Fixed in Session 14 — suite is fully green (62/62).
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

### External Repo Handoff (Session 12 — error placeholders)
- **engine-replicate**: DONE — `OutputFile.expected_path` + precomputed destination names on all error paths (Session 12, 39/39 tests).
- **engine-fal / engine-openrouter / engine-google**: Need the same `expected_path` field on error `OutputFile` (precompute destination name before the API call). Until updated, the Vehicle logs a loud error per failed slot and skips the placeholder (deliberate — see Q2). No Vehicle-side fallback naming.

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
