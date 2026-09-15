# Contributing

Thanks for considering a contribution. The projects under the `vivid-allusion`
org — **AI Studio Lot (`studiolot`)**, **Frame Composer**, **Motion Conductor**,
and the **`engine-*`** wrappers — are free, open source, and built in the open.
Issues, pull requests, and documentation improvements are all welcome.

The highest-impact contribution right now is **model endpoints**: adding a new
or niche model is often a single TOML file.

## Before you start

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) so you know where your change belongs.
The short version: the TUI decides *what* to run, Vehicles do the generation,
and Engines talk to providers.

## Setup

Each repo is a normal Python project. For **studiolot** (AI Studio Lot):

```bash
git clone https://github.com/vivid-allusion/studiolot
cd studiolot
pip install -e .        # Python 3.11+
studiolot               # launches the TUI (first run onboards you)
```

For the Vehicles and Engines, clone the repo you're changing and install its
requirements (each repo's `README.md` has the specifics). The `run.py`
bootstrap in each Vehicle creates and repairs its own virtual environment, so
`python run.py` works from a clean checkout.

## Tests

Run the suite for the repo you touch before opening a PR.

**studiolot (Python):**

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

**Vehicles (Python):**

```bash
python -m pytest tests/ -v
```

**studiolot (JavaScript installers):**

```bash
node --test deploy/tests/test_*.mjs
```

Tests are designed to be fast and hermetic — they use temporary directories and
never make real network calls or need API keys. If a test you added requires a
full environment, mark it `integration` so it can be skipped.

## Conventions

- **Python:** PEP 8. `ruff` for linting, `mypy` for types (studiolot); `black` +
  `ruff` (Vehicles). Type hints on function signatures, `pathlib.Path` for file
  work.
- **Keep files focused.** Split before a file sprawls; small, cohesive modules
  beat clever ones.
- **Fail loud.** Don't silently change a user's intent — reject or surface the
  problem.
- **TOML:** model endpoint definitions (see below). `YAML`: pipeline config
  only. `Markdown`: follow the project's docs style.
- **Conventional commits:**

  ```
  feat: add describe tool integration
  fix: handle B2 upload timeout gracefully
  docs: explain the merge rule for underscore folders
  chore: bump Textual to 0.52.0
  style: format pipeline.yaml comments
  refactor: extract profile resolution into a shared module
  ```

## Pull request flow

1. Fork the repo and branch: `feat/my-change` or `fix/my-fix`.
2. Make one focused change. Follow the conventions above.
3. Add or update tests for the affected module. Run the full suite.
4. Commit with a conventional message.
5. Open a PR against `main`.

**One concern per PR.** A PR that adds a model endpoint should not also refactor
the parser — small, atomic PRs are reviewed faster and safer.

## Adding a model endpoint

Endpoints live in the relevant **Engine** repo as TOML files.

1. Create a `.toml` file in the Engine's endpoint catalog.
2. Fill in the required fields: `id`, `label`, `category`, `platform`,
   `endpoint`, `description`.
3. Add a `[pricing]` section and a `[params.<name>]` section per parameter
   (`type`, `default`, valid `options`).
4. Verify it appears in the model selector, then open a PR with the single
   `.toml` file.

Only use model IDs that appear in the provider's own documentation — don't guess
IDs. An Engine's endpoint catalog must mirror the provider's real API.

## Prompt presets

Presets are `.preset` files (TOML syntax) holding only `name`, `media_type`
(`image` / `video` / `text`), `prefix`, and `suffix`. They deliberately carry no
model, parameters, or paths, so a preset outlives the models it was written
against.

## Reporting bugs

Open a GitHub issue with:

1. **What you did** — exact steps, including any options selected.
2. **What you expected** — what should have happened.
3. **What happened** — error messages, unexpected behaviour, screenshots.
4. **Environment** — OS, Python version, terminal emulator.

For generation bugs, include the bullet content, the error shown, and the model
and endpoint used. For TUI bugs, a terminal recording helps a lot.

## License

Each repo carries its own license (see `LICENSE` in the repo). By contributing,
you agree your contributions are licensed under the same terms.
