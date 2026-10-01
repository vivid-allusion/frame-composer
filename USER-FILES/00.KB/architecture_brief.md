# studiolot Architecture Brief

> Copy this into any new chat working on studiolot, a Generator, or an Engine.
> It gives the LLM enough context to understand how the pieces fit together.

---

## The three layers

```
studiolot (TUI)  →  Generator (script)  →  Engine (SDK wrapper)  →  Provider API
```

- **studiolot** — Textual TUI dashboard. Lists Generators, manages projects,
  drives Generate/Sync. Keyboard-driven (lazygit style).
- **Generator** — an SDK-agnostic generation script. Reads Markdown `.md` files,
  discovers an Engine via `engine_loader.py`, calls `engine.run(inputs)`,
  writes output. Accepts `--input_dir`, `--output_dir`, `--profile` CLI flags.
  Examples: `image-generator` (image), `video-generator` (video).
- **Engine** — a separate repo wrapping one provider's SDK. Exposes a uniform
  `Engine(profile, output_dir, api_key, on_progress).run(inputs)` interface.
  Ships endpoint TOMLs and standby profiles. Cloned into
  `00_APPLICATIONS/ENGINES/engine-<name>/` under studiolot, or `ENGINES/`
  beside a Generator for standalone. Examples: `engine-replicate`,
  `engine-openrouter`, `engine-fal`, `engine-google`.
- **Profile YAML** — the cartridge. Lives in `00_APPLICATIONS/CONFIG/<cat>-PROFILE/`
  (studiolot) or `USER-FILES/03.PROFILES/` (standalone). Carries `platform`,
  `endpoint`, `parameters`, `prompt_prefix`/`prompt_suffix`. An action IS a
  profile — selecting one swaps the YAML passed to the Generator.

## How a generation runs

```
User presses g in TUI
  → Dash reads GENERATORS.selected_index + ACTIONS.selected_index
  → Assembles: python <generator_entry> --input_dir <source> --output_dir <target> --profile <profile.yaml>
  → Generator starts, reads profile, sees platform: replicate
  → Generator walks up filesystem looking for 00_APPLICATIONS/ENGINES/engine-replicate/
  → engine_loader.py imports Engine from engine_replicate package
  → Generator reads Markdown .md files → builds InputFile objects
  → engine.run(inputs) → calls replicate SDK → saves output
  → stdout streams to TUI Generations panel
```

## engine_loader.py — canonical vs vendored

`load_engine()` is the Engine discovery function. Three copies must stay
identical:

| Copy | Path |
|------|------|
| **Canonical** | `studiolot/pipeline/engine_loader.py` |
| **IG vendored** | `image-generator/src/engine_loader.py` |
| **VG vendored** | `video-generator/src/engine_loader.py` |

Update canonical first, then re-vendor into both Generators.

## Repo locations on disk

| Repo | Path |
|------|------|
| studiolot (TUI) | `~/Nextcloud/00-DEVELOPMENT/MISC_DEV_TOOLS/studiolot/` |
| image-generator (Generator, IMG) | `~/Nextcloud/00-PRODUCTION/GENAI_IMG_TOOLS/frame-composer/` |
| video-generator (Generator, VID) | `~/Nextcloud/00-PRODUCTION/GENAI_VID_TOOLS/motion-conductor/` |
| engine-replicate | `~/Nextcloud/00-PRODUCTION/GAI_ENGINES/engine-replicate/` |
| engine-fal | `~/Nextcloud/00-PRODUCTION/GAI_ENGINES/engine-fal/` |
| engine-openrouter | `~/Nextcloud/00-PRODUCTION/GAI_ENGINES/engine-openrouter/` |
| engine-google | `~/Nextcloud/00-PRODUCTION/GAI_ENGINES/engine-google/` |
| IG testing clone | `~/Downloads/frame-composer/` |

## Key architecture docs (in studiolot repo)

| Doc | What it covers |
|-----|---------------|
| `docs/architecture/PHILOSOPHY.md` | Why the project is shaped this way. Markdown-file format, sidecar, folder model, copy-forward flow. |
| `docs/architecture/DASH_CONTRACT.md` | Panel responsibilities, execution paths, keybindings, non-negotiable rules. |
| `docs/architecture/ENGINE_CONTRACT.md` | Engine interface, datatypes, repo structure, profile schema, discovery protocol. |
| `docs/architecture/VEHICLE_CONTRACT.md` | Generator CLI contract, engine discovery, standalone UX, IG/VG specifics. |

## Terminology

| Term | Means |
|------|-------|
| **generator instance** | One row in the TUI's GENERATORS panel. One Generator + one Engine + one profile. |
| **Markdown file** | A `.md` file. Line 1 = prompt, line 2+ = `!(b2-url)`. The universal payload. |
| **Sidecar** | A stem-matched `.md` beside every media file with its B2 URL. The sidecar IS the next Markdown file. |
| **Keeper** | A generated result copied to `06_KEEPERS/`. Ammo for the next pipeline stage. |
| **Profile** | A YAML file containing platform, endpoint, parameters, prefix/suffix. The profile IS the action. |
| **Endpoint TOML** | A `.toml` file in an Engine's `endpoints/` dir. Defines valid parameter ranges for one model. |
| **Dry-Run** | Generates the would-be command + lists Markdown files, but does not execute. No API call. |

## Design constraints

- Plain text first. No database. Files and folders only.
- Copy forward, never move. `05_OUTPUT_GENERATIONS/` is a keep-everything archive.
- Engines own their models. Endpoint TOMLs and standby profiles ship with the Engine, not the Generator.
- Generate is Generate is Generate. One execution path, no branching by tool type.
- Event handlers stay thin. `on_*` methods dispatch, they don't compute.
