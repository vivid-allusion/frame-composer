# Vivid Allusion Frame Composer

## Purpose

Frame Composer (the **Vehicle**) processes markdown prompt files into generated images. It does not talk to any AI provider directly — all provider logic lives in **Engine** plugins ("The Vehicle orchestrates. The Engine executes. The profile configures."). Supported platforms: `replicate`, `fal`, `openrouter`, `google`.

## Architecture

| Component | Role |
|---|---|
| `src/` | Vehicle: CLI, markdown parsing, profiles, auth, payload embedding, placeholders, run logs |
| `ENGINES/engine-<platform>/` | Engine plugins (git clones or pip packages), loaded via `src/engine_loader.py` |
| `USER-FILES/03.PROFILES/` | Active profile YAML (model + parameters) — pick one from `02.STANDBY/` |

### Run modes

1. **Standalone** (no path flags): profile from `USER-FILES/03.PROFILES/`, inputs from `USER-FILES/04.INPUT/`, outputs to `USER-FILES/05.OUTPUT/YYMMDD_HHMMSS_IMG/`.
2. **Studiolot** (`--profile --input_dir --output_dir`): explicit paths; Engine discovered by walking up from `output_dir` to `00_APPLICATIONS/ENGINES/`.

## Directory Structure

```
frame-composer/
├── run.py               # Bootstrap: venv + deps + launches src.main_simple
├── src/                 # Vehicle code
├── tests/               # pytest suite
├── ENGINES/             # Engine plugin clones (auto-installed on first run)
├── USER-FILES/
│   ├── 01.CONFIG/       # Legacy config (unused by current code)
│   ├── 02.STANDBY/      # Engine-seeded standby profiles
│   ├── 03.PROFILES/     # Active profile (copy one here from 02.STANDBY/)
│   ├── 04.INPUT/        # Markdown prompt files (read-only)
│   ├── 05.OUTPUT/       # Timestamped generation output
│   └── 07.TEMP/         # Specs, reports, scratch notes
├── requirements.txt
├── AGENTS.md
└── pyproject.toml
```

## Usage

```bash
python3 run.py                    # standalone run
python3 run.py --dry-run          # validate without API calls
python3 run.py --cost-estimation  # price the batch, no API calls
python3 run.py --verbose          # INFO-level logging
python3 run.py --debug            # DEBUG-level logging
python3 run.py --force-png        # merge force_png=true into request params
python3 run.py --no-save-payloads # skip embedding payload metadata in images
python3 run.py --install-default-engine=replicate   # first-run auto-install
python3 run.py --profile P.yaml --input_dir DIR --output_dir DIR  # studiolot mode
python3 run.py --platform fal     # override the profile's platform
```

First run: the engine is checked, the interactive wizard installs the missing Engine automatically (no confirmation prompt), then sets the API key (saved to `.env`), and standby profiles are seeded into `02.STANDBY/`.

## Profile YAML

Copy a standby profile into `USER-FILES/03.PROFILES/` and edit:

```yaml
platform: replicate            # engine platform
endpoint: owner/model:version  # model identifier
parameters:                    # passed to the API unchanged
  aspect_ratio: "16:9"
  output_format: "png"
prompt_prefix: ""
prompt_suffix: ""
pricing:
  base_cost: 0.05              # used by --cost-estimation
paths:
  input: USER-FILES/04.INPUT   # optional overrides for standalone mode
  output: USER-FILES/05.OUTPUT
delay_between_requests: 0
```

## Markdown Input Format

Each `.md` file in the input folder is one generation job:

```markdown
A cinematic portrait in soft lighting

![reference](https://example.com/portrait.jpg)
![reference](https://example.com/side-view.jpg)
```

- Line 1: text prompt
- Following lines: markdown image URLs or raw `https://` URLs (text-to-image works with no URLs)
- Files are processed in natural-numeric order (`1.md`, `2.md`, `10.md`)
- Output folders mirror the input folder structure

## Outputs

```
USER-FILES/05.OUTPUT/YYMMDD_HHMMSS_IMG/
├── 1_rw-260905_150000.png    # generated image
├── 1_rw-260905_150000.log    # per-file run log (header, payload, console, summary)
└── subdir/2_rw-260905_150100.png   # mirrors nested input structure
```

- Each image embeds its generation payload (prompt, endpoint, parameters) as XMP metadata in PNG/JPEG/WebP — inspect with exiftool/ImageMagick
- Failed generations (in a mixed run) get red error-placeholder images so the output serial stays intact
- All-failed runs exit 1 with a fallback `frame_composer_<ts>.log`

## Authentication

Four-tier resolution per platform (`REPLICATE_API_TOKEN`, `FAL_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`):

1. Environment variable
2. `pass show studiolot/<key>` (GPG store, optional)
3. `.env` file in the project root
4. Interactive wizard (TTY only) — prompts for platform, installs the missing Engine automatically, saves the key to `.env`

## Dependencies

`loguru`, `PyYAML`, `python-dotenv`, `rich`, `Pillow`. Engines declare their own SDK dependencies in their own `requirements.txt`.

## Protection Rules

- Never modifies files in `USER-FILES/` without explicit permission
- `04.INPUT/` is read-only; outputs go only to `05.OUTPUT/`
- No automatic archiving or cleanup of user files
