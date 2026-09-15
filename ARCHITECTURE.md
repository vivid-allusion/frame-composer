# Architecture — how the projects fit together

AI Studio Lot is a free, open-source suite for AI media generation. It runs on
your own machine, works in plain text, and is driven from a terminal TUI. This
page describes the pieces and how they talk to each other, so you know where a
change belongs.

## The three nodes

```
Local machine ──▶ B2 bucket ──▶ AI APIs
(project files,   (media as       (Replicate, Fal,
 markdown, TUI)    public URLs)    Google, OpenRouter, Evolink…)
```

1. **Local machine** — your projects live as ordinary folders. Markdown files
   describe what to generate; the TUI is the interface.
2. **B2 object storage** — the bridge. Remote models can only read media they
   can fetch by public URL, so media is uploaded to a bucket before a prompt
   references it.
3. **AI APIs** — receive a prompt plus media URLs and return generated images,
   video, or text.

## The pieces

- **AI Studio Lot TUI (`studiolot`)** — the dashboard. It manages projects,
  applications, presets, the generation queue, and sync. It decides *what* to
  run and composes the configuration for each run.
- **Vehicles (`frame-composer`, `motion-conductor`)** — the generation scripts.
  Frame Composer makes images; Motion Conductor makes video. A Vehicle parses
  the inputs, loads an Engine, runs the generation, and writes the results and
  logs.
- **Engines (`engine-*`)** — thin, uniform wrappers around one provider's SDK
  each. They hold the provider-specific logic and endpoint metadata.
- **Extensions** — community apps, in-process plugins, and utilities, built from
  the `extension-starter-*` templates.

> **The core contract: the Vehicle orchestrates, the Engine executes, the
> profile configures.** A Vehicle never imports a provider SDK directly — it
> calls the Engine. That is what lets new models and providers drop in without
> touching the generation scripts.

## The data model

### Bullets

A job is a markdown file called a **bullet**. One format everywhere:

```
Line 1:  the prompt
Line 2+: ![](url-to-an-image-or-video)
[optional] duration: 5
[optional] ![slot](url)     # alt text names a payload slot
```

The media type follows the URL — an `.mp4`/`.mov` URL makes the bullet video.
That is why a video model can be used from the same input format with no
special casing.

### The sidecar

Every generated image or video gets a matching `.md` sidecar holding its public
URL. The sidecar *is* the next bullet — syncing creates bullets, so there is no
separate "make a bullet" step.

### Copy forward, keep everything

Generated files are never moved or deleted. Keepers are **copied** forward into
the next stage; the output archive keeps growing, newest first. Any keeper can
re-enter any input list, so the pipeline is iterative rather than linear.

## Profiles and endpoints

A **profile** is the configuration for one run: platform, endpoint, parameters,
prompt prefix/suffix, and paths. When you generate from the TUI, the profile is
*composed* for you from the application instance plus the selected prompt
preset. Run a Vehicle standalone and it reads a profile from its own
`USER-FILES/03.PROFILES/` folder instead.

**Endpoint definitions** (the catalog of models and their parameters) live in
the Engine repos as TOML files. Adding a model is usually a single TOML file —
one of the highest-impact contributions you can make.

## Where your change belongs

| Change | Repo / area |
|---|---|
| TUI behaviour, project model, sync, queue | `studiolot` (`console/`, `pipeline/`) |
| A new model endpoint or provider parameter | the relevant `engine-*` repo (TOML catalog) |
| Provider SDK logic, auth, request shaping | the relevant `engine-*` repo (Engine code) |
| Generation behaviour for images | `frame-composer` |
| Generation behaviour for video | `motion-conductor` |
| A community app, plugin, or utility | start from `extension-starter-*` |

Interface changes follow one rule: **`engine-replicate` is the reference.** A
change to the Engine interface lands there first, is proven by its tests, and is
then rolled out to the other Engines.
