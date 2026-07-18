# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A PySide6/Qt desktop app that downloads YouTube videos as **MP4 (H.264/AVC + AAC)**
or audio as **MP3** (with ID3 tags + embedded cover art). The defining constraint is
**TV / in-car playback compatibility**: format choices (avc1 codec, MP4 container,
`+faststart`, FAT32-safe filenames, 1080p cap) exist to play on hardware decoders that
reject VP9/AV1/Opus. Keep this constraint in mind before changing any format-selection
logic. The UI and code comments are in Turkish.

## Commands

```bash
./run.sh                                    # Run app (creates .venv on first run)
python -m youtube_downloader.app            # Run directly (needs deps + system ffmpeg)

.venv/bin/python -m pytest -q               # Run tests (pytest)
.venv/bin/python tests/test_core.py         # Run tests WITHOUT pytest (self-contained runner)
.venv/bin/python -m pytest tests/test_core.py::test_format_aliases   # Single test

packaging/build_linux.sh                    # Build dist/youtube-downloader + .deb
packaging\build_windows.bat                 # Build .exe (Windows host only — no cross-compile)
```

- **ffmpeg** must be installed on the system (`sudo apt install ffmpeg`) — required for
  merging/conversion. The `.deb` declares it as a `Depends:`; Windows builds embed it.
- **A JavaScript runtime (Deno or Node)** must be present at runtime. YouTube now requires
  one to solve signature/`n` challenges; without it many formats are missing and downloads
  fail with `Requested format is not available`. The `yt-dlp-ejs` pip dependency supplies
  the solver scripts locally (no runtime network fetch). See "JS runtime" below.
- CI ([.github/workflows/build.yml](.github/workflows/build.yml)) builds both `.deb` and
  `.exe` on a `v*` tag push (e.g. `git tag v1.0.0 && git push origin v1.0.0`).
- Bump the version in [youtube_downloader/__init__.py](youtube_downloader/__init__.py)
  (`__version__`) — the `.deb` build reads it from there.

## Architecture

Strict **core / GUI separation** — the `core` layer has **no Qt imports**, which is what
makes the business logic testable. Never import PySide6 into `core/`.

```
youtube_downloader/
├── core/           # UI-independent logic (no Qt)
│   ├── models.py       # MediaFormat, JobStatus, DownloadJob; format aliases (video/mp4, mp3/ses/audio…)
│   ├── parser.py       # parse_input(): pure fn, "URL | format" lines → jobs + per-line errors
│   └── downloader.py   # yt-dlp wrapper: format selection, playlist expansion, cancel, progress
├── gui/            # PySide6 presentation
│   ├── worker.py       # DownloadWorker (QObject) — runs in a QThread; two-phase resolve→download
│   ├── theme.py        # Single PALETTE dict → light-blue theme
│   └── main_window.py  # Window; presentation/orchestration only
├── resources.py    # bundled_ffmpeg_location() — locates ffmpeg in frozen vs source runs
└── app.py          # Entry point → gui.main_window.run()
```

### Download flow (the key thing to understand)

`DownloadWorker.run()` in [gui/worker.py](youtube_downloader/gui/worker.py) runs on a
QThread and has **two phases**, talking to the UI only via Qt signals:

1. **Resolve** — each input line is expanded via `Downloader.expand_entries()`. A single
   video → 1 `DownloadJob`; a playlist → N jobs. Because one input line can produce many
   jobs, `line_number` is NOT a unique id — the worker assigns a unique `job_id` per
   resolved job. Playlist expansion uses `extract_flat` (fast, fewer requests) and handles
   nested playlists recursively in `_entries_from_info` (a pure, network-free function —
   this is what the tests exercise).
2. **Download** — resolved jobs are downloaded **sequentially** (preserves user order and
   is gentler on YouTube). Cancellation is a `threading.Event`; the yt-dlp progress hook
   raises `DownloadCancelled` mid-stream when it's set.

### Format selection (downloader.py)

- Video: `_video_format_selector()` builds a preference string favoring `avc1` video +
  `mp4a` audio, capped at `max_height` (default 1080). Output forced to MP4 via
  `FFmpegVideoRemuxer` + `-movflags +faststart`.
- MP3: `bestaudio` → `FFmpegExtractAudio` at `mp3_quality`, plus `FFmpegMetadata` and
  `EmbedThumbnail` for ID3 tags + cover art.
- To change the 1080p cap: edit `main_window._selected_max_height` and `Downloader.max_height`.

### JS runtime (signature/challenge solving)

`resources.available_js_runtimes()` probes PATH for `deno`/`node`/`bun`/`qjs` and returns a
dict shaped for yt-dlp's `js_runtimes` option (`{name: {"path": bin}}`). `downloader._js_runtime_opts()`
injects it into both `_base_opts()` (download) and `expand_entries()` (resolve). If none is
found the key is omitted (don't pass an empty/`None` config — yt-dlp's Python API needs
`{name: {}}` at minimum, and a runtime binary must actually exist). `main_window._start_downloads`
warns the user when no runtime is found. The solver scripts come from the `yt-dlp-ejs`
package, so `remote_components` (runtime GitHub fetch) is intentionally NOT used.

### Cookies / anti-bot

`cookies_from_browser` (e.g. `"chrome"`, `"firefox"`) sets yt-dlp's `cookiesfrombrowser`
to bypass "Sign in to confirm you're not a bot" and access private playlists. Set via
Settings in the UI.

## Conventions

- Parsing is **pure and side-effect-free**; it returns valid jobs and per-line errors
  separately so the UI can surface both. Preserve this contract.
- `core` must stay Qt-free and network access must stay out of `_entries_from_info` (tests
  depend on it). New core logic should be unit-testable the same way.
- Downloads are intentionally **sequential** and **cancellable** — don't parallelize job
  execution.
- `resources.py` handles both source runs and PyInstaller-frozen runs; when touching
  bundled-asset paths, account for both `sys._MEIPASS` (onefile) and the exe dir.
