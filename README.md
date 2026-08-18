# Faceless content pipeline

Trends flow in, a script gets written, voice and video get assembled
automatically, a human approves, then it publishes and reports back on
performance. Eight modules, one mandatory human checkpoint.

This repo is a from-scratch implementation of the build spec: Modules 1
and 2 (trend finder, script generator) are fully working end-to-end and
covered by tests. Modules 3–8 are real, runnable implementations wired
against their target integrations (Kokoro, faster-whisper, Pexels/Pixabay,
YouTube Data/Analytics APIs, Telegram/Discord) with honest fallbacks where
an external dependency (ffmpeg, model weights, API approval) isn't
available in a given environment — see each module's status below.

## What works with zero API keys / signups

- **Trends**: Google Trends and TikTok trending both need no key at all.
- **Voice**: Kokoro is self-hosted and free (Apache 2.0); `pip install
  kokoro soundfile` and the model weights download once from Hugging
  Face on first use — no account, no key.
- **Captions**: burned in either way — faster-whisper (free, local, one
  model download) if installed, otherwise an even-split fallback with no
  download at all.
- **Video background**: `ffmpeg`'s own built-in filters generate an
  animated gradient with zero network calls — no Pexels/Pixabay signup
  needed to get a real rendered video.
- **ffmpeg itself**: `apt-get install ffmpeg` (or your OS's package
  manager) — free, one-time, no account.

**Script generation (Module 2)** needs some LLM to write the script
text — there's no zero-network way around that — but it isn't locked to
one paid API. `SCRIPT_PROVIDER` in `.env` picks between five, all behind
the same JSON contract (`_call_llm` in `generator.py`), so everything
downstream (voice, video, review, publish) runs identically no matter
which one produced the script:

| `SCRIPT_PROVIDER` | Cost | Setup |
|---|---|---|
| `anthropic` (default) | Paid | `ANTHROPIC_API_KEY` from [console.anthropic.com](https://console.anthropic.com) |
| `ollama` | Free, local | Install [Ollama](https://ollama.com), `ollama pull llama3.2`, `ollama serve` |
| `openai` | Paid | `OPENAI_API_KEY` from [platform.openai.com](https://platform.openai.com/api-keys) |
| `gemini` | Has a free tier | `GEMINI_API_KEY` from [aistudio.google.com](https://aistudio.google.com/apikey) |
| `groq` | Has a free tier | `GROQ_API_KEY` from [console.groq.com](https://console.groq.com/keys), runs open models on fast inference hardware |

Ollama setup, since it's the only one with no key at all:

```bash
# one-time setup, on your own machine
curl -fsSL https://ollama.com/install.sh | sh   # or brew install ollama
ollama pull llama3.2                            # one-time model download, ~2GB
ollama serve                                     # keep this running (or install as a service)
```

```bash
# .env
SCRIPT_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434   # default, change if Ollama runs elsewhere
OLLAMA_MODEL=llama3.2                    # any model you've pulled
```

For the paid/free-tier ones, set `SCRIPT_PROVIDER` plus that provider's
`*_API_KEY` (and optionally `*_MODEL`/`*_BASE_URL` to override the
defaults) — see `.env.example` for the full list. `openai` and `groq`
share one HTTP call internally since Groq's hosted API deliberately
mirrors OpenAI's `/chat/completions` shape.

Every video in this pipeline can still be made end-to-end with $0 spent
and no account signups, using `SCRIPT_PROVIDER=ollama` + Kokoro voice +
the procedural ffmpeg background.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"      # editable install of the src/ package + every module's deps
cp .env.example .env         # fill in the keys you have; everything else degrades gracefully

uvicorn faceless_pipeline.main:app --reload   # backend on :8000, docs at /docs

cd dashboard
npm install
npm run dev                  # dashboard on :5173, proxies /api to :8000
```

Installing only what a given module needs (e.g. on a lean cron box that
only runs the trend finder) works the same way: `pip install -e ".[trends]"`.
See the `[project.optional-dependencies]` groups in `pyproject.toml`.

Run the test suite: `pytest`

## Architecture

`src/faceless_pipeline/` is a proper installable package (`pip install -e .`)
rather than a loose `app/` folder, so it can be imported the same way in
tests, cron entry points, and Docker without path hacks.

```
pyproject.toml          Package metadata + per-module dependency groups
src/faceless_pipeline/
  main.py                FastAPI app (mounts every module's router under /api)
  config.py               Settings loaded from .env
  db.py                    SQLAlchemy engine/session
  models.py                trends / scripts / videos / performance tables
  api/                     pipeline status + manual-trigger endpoints, settings status
  modules/
    trends/                Module 1
    scripts/                Module 2
    voice/                  Module 3
    video/                  Module 4
    review/                 Module 5
    publisher/              Module 6
    analytics/              Module 8
dashboard/                Module 7 — React + Tailwind + Vite
tests/                     pytest suite, imports faceless_pipeline directly
```

Each module is independently runnable via its own `run.py` (CLI entry
point) as well as through the dashboard's manual trigger buttons and the
`/api/pipeline/trigger/*` endpoints — there's no monolith wiring them
together beyond the DB tables they share.

## Module status

### Module 1 — Trend finder — `built`, five sources
- [x] Google Trends related/rising queries for seed keywords (`pytrends`)
- [x] YouTube trending pull (optional, needs `YOUTUBE_API_KEY`)
- [x] Reddit trending posts via PRAW (optional, needs Reddit app credentials)
- [x] TikTok trending hashtags (optional, no key needed — reads TikTok
      Creative Center's public trend listing; unofficial/undocumented, so
      it's defensive-by-design and can be turned off with
      `ENABLE_TIKTOK_TRENDS=false` if it ever breaks)
- [x] News headlines via NewsAPI.org (optional, needs `NEWSAPI_KEY`) —
      catches what's breaking right now, not just what's already trending
- [x] Fuzzy dedup of near-identical topics (`rapidfuzz`) before ranking, across all five sources
- [x] History persisted to `trends` table so a topic is never resurfaced
- [x] `scripts/cron_trend_finder.sh` — daily cron entry point

All five sources run every time the trend finder fires; each one degrades
to an empty list (not an error) when its key is unset or the call fails,
so a missing/broken source never blocks the others.

### Module 2 — Script generator — `built`
- [x] Hook / promise / body / payoff / CTA via any of 5 `SCRIPT_PROVIDER`
      options — `anthropic` (default), `ollama` (free/local), `openai`,
      `gemini`, `groq` — same JSON contract either way, dispatched by
      `_call_llm` in `generator.py`; see the zero-API-keys section above
- [x] Style presets: listicle, story, explainer, hot take
- [x] Length variants: 15s / 30s / 60s (word-count targets)
- [x] Regenerate with feedback — edit note round-trips into a rewrite, original marked `superseded`
- [x] Per-topic script history check blocks accidental duplicates
- [x] **Storyboard**: the same Claude call also plans what's on screen for
      each beat — a one-sentence visual description plus footage search
      keywords, one shot per hook/promise/body/payoff/cta. No extra API
      call (script generation already needs one). If the model omits it
      or returns something malformed, it degrades to a generated default
      per beat rather than losing the whole script over a formatting
      slip — see `_validate_storyboard`/`_default_storyboard` in
      `generator.py`. Module 4 uses this to cut between a distinct
      background per beat instead of one static background for the
      whole video; shown in the dashboard's Script library and Review
      queue so the human sees the shot-by-shot plan before approving.
- [x] **Automatically chains into video assembly**: `POST
      /api/pipeline/trigger/script` (what the dashboard's "Generate"
      button calls) generates the script and then immediately assembles
      the video for it, recording both stages on the pipeline status.
      Per the spec, "voice and video get assembled automatically" once a
      script exists — this isn't a separate step a human has to remember
      to trigger from the CLI. Trend → script stays a deliberate choice
      (you pick a topic); script → video does not.

### Module 3 — Voice generation — `built`, Kokoro requires local install
- [x] Kokoro integration (`src/faceless_pipeline/modules/voice/kokoro_tts.py`) — install `kokoro`+`soundfile` to activate
- [x] Voice profile selection (`voice_profiles.py`)
- [x] Fallback to a paid API (ElevenLabs by default) when Kokoro is unavailable/low quality
- [x] Word-level timestamps deferred to Whisper in Module 4, per spec
- [x] Loudness normalization via ffmpeg `loudnorm`
- If neither Kokoro nor the fallback API is available, a silent placeholder
  wav is written so the rest of the pipeline stays testable end-to-end.

### Module 4 — Video assembly — `built`, verified against real ffmpeg
- [x] faster-whisper word-level captions, with an even-split fallback if it's not installed
- [x] Pexels/Pixabay stock footage search + download by script keyword
- [x] **Zero-API-key fallback**: when no `PEXELS_API_KEY`/`PIXABAY_API_KEY`
      is set (or nothing matches), `procedural_background.py` renders an
      animated gradient using only ffmpeg's own built-in `gradients`
      filter — no network call, no signup, no model download. This used
      to be a hard failure (`final_path=None`, no video at all); now the
      pipeline always produces a real, watchable render. The look
      (color pair + gradient type + animation seed) is picked from a
      curated palette deterministically per topic, so the same script
      keeps a consistent look but different topics get variety.
- [x] **Storyboard-driven backgrounds** (`storyboard.py`): when the
      script has a storyboard, each beat gets its own background segment
      instead of one background for the whole video — real stock footage
      per beat's keywords if available, otherwise a procedural gradient
      described by that beat's own visual text. Segment durations come
      from word-level caption timestamps (`compute_beat_timing`), sliced
      off the same real audio duration used elsewhere — not padded to a
      fixed length, since assemble_video()'s `-shortest` would silently
      truncate later beats' visuals (while their captions, timed
      independently, kept playing) if the total ran long. Falls back to
      the single-background flow for scripts with no storyboard (e.g.
      generated before this feature) or when caption timing isn't
      available.
- [x] ffmpeg pipeline: background + voiceover + burned-in captions (`assemble.py`)
- [x] Vertical 9:16 output (1080x1920 scale+crop)
- [x] Background music mix under the voiceover (`amix` filter)
- [x] Thumbnail frame extraction
- [x] `metadata.json` sidecar (title/description/tags)
- Verified against a real `ffmpeg` install (background scaling/looping,
  caption burn-in, music mixing, thumbnail extraction, full
  `assemble_pipeline` orchestration) — not just the "ffmpeg unavailable"
  degraded path. Two real bugs only showed up once real ffmpeg actually
  ran: `normalize_loudness()` left audio at an oversampled rate that
  Python's `wave` module couldn't parse (silently defeating the
  narration-duration fix above), and `build_background()` sized its clip
  loop off a hardcoded 6s-per-clip guess instead of each clip's real
  duration, so short clips could under-fill the requested length and get
  truncated by `assemble_video()`'s `-shortest`. Both fixed; see
  `tests/test_normalize_loudness_output_format.py` and
  `tests/test_build_background_duration.py` (both skip automatically if
  `ffmpeg`/`ffprobe` aren't on PATH). If `ffmpeg` genuinely isn't
  installed, the orchestrator (`run.py`) catches that and still creates
  the `videos` row without a rendered file, so Module 5 stays testable.

### Module 5 — Review checkpoint — `built`
- [x] Dashboard queue of pending videos
- [x] Preview: video player / thumbnail, script text
- [x] Approve / Reject / Regenerate (routes back to Module 2 or Module 4 with a note)
- [x] Light script-text edit before approval
- [x] Approve triggers Module 6 publish as a background task
- [x] Telegram / Discord webhook notification on new pending video

### Module 6 — Publisher — `built` (YouTube), TikTok blocked on app review
- [x] YouTube Data API `videos.insert` + OAuth (installed-app flow, token cached)
- [x] Quota-exceeded handling (`YouTubeQuotaExceeded`)
- [ ] TikTok Content Posting API — stubbed; **apply for API access now**, it
      takes weeks, and the stub in `publisher/tiktok.py` is ready to fill in
      once approved
- [ ] Instagram Reels (stretch goal, not started)
- [x] Scheduling (`scheduled_for`) — immediate publish or queue for later
- [x] Publish history + platform video IDs stored on the `videos` row

### Module 7 — Dashboard — `built`, verified end-to-end against a real backend
React + Tailwind + Vite app with all seven views from the spec:
pipeline status (+ manual triggers), trend list, script library (+ generate
by topic), review queue (fully functional against the Module 5 API),
publish history, analytics, and a read-only settings/credentials-status
page. `npm install` + `npm run build` succeed with zero errors, `tsc
--noEmit` type-checks clean, and it's been driven end-to-end with a
headless browser against a real running backend: real seeded trends,
scripts, and a real ffmpeg-rendered video all render correctly, the
review queue's video player pulls real bytes through `/media`, and
clicking Approve / Regenerate through the actual UI hits the real API
and settles into the right state with zero console errors.

### Module 8 — Analytics feedback loop — `built` (YouTube), TikTok blocked on same review
- [x] Weekly job pulls YouTube Analytics (`reports.query`) per published video
- [ ] TikTok reporting API — stubbed, same app-review blocker as Module 6
- [x] Performance stored linked to source topic + script style
- [x] "What's working" aggregation (best hook style / topic by avg views) surfaced via `/api/analytics/best-performers` and the dashboard
- [ ] Feeding top patterns back into the script generator's prompt — not
      wired up yet; `best_performing_patterns()` returns exactly the data
      needed to do this as a next step

## Data models

Matches the spec's table exactly, plus a few operational fields (see
`src/faceless_pipeline/models.py` for the full field list — parent/feedback tracking on
`scripts`, file paths + review notes on `videos`).

| Table | Core fields |
|---|---|
| `trends` | topic, source, score, used, created_at |
| `scripts` | id, topic, script (json), style, created_at, status |
| `videos` | id, script_id, file_path, thumbnail_path, status, platform_ids (json), created_at |
| `performance` | video_id, platform, views, retention_pct, completion_pct, likes, shares, pulled_at |

## Configuration

Everything lives in `.env` (see `.env.example`) — nothing is hardcoded.
Every external integration degrades gracefully when its keys are absent:
the trend finder just skips that source, voice generation falls back to a
silent placeholder, video assembly records the video row without a
rendered file, publishers raise a typed "not configured" error the review
API surfaces rather than crashing.

## Recommended build order (from the spec, for reference)

1. Trend finder — done
2. Script generator — done
3. Voice generation — done (needs Kokoro installed locally)
4. Video assembly — done (needs ffmpeg + footage API keys)
5. Review checkpoint — done
6. Publisher — YouTube done, TikTok pending API approval
7. Full dashboard — skeleton done, expand as the pipeline runs for real
8. Analytics feedback loop — YouTube done, TikTok pending, prompt feedback loop not wired

## Non-functional requirements

- Open source / self-hosted tools throughout to keep ongoing cost near zero
- Every module runs independently via its own `run.py` — no monolith
- Human approval in Module 5 is mandatory before Module 6 can publish —
  there's no code path that skips it
- Credentials only ever live in `.env` / environment variables — the
  dashboard's Settings page reports which keys are configured without ever
  transmitting the values
