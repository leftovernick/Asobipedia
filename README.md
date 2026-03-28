# Asobipedia Viewer

Local HTML viewer for browsing every monster outside the game.

## Regenerate Data

```bash
python3 tools/Asobipedia/generate_viewer.py
```

## Open Viewer

Recommended:

```bash
python3 tools/Asobipedia/run_viewer.py
```

Fallback:

```bash
cd /Users/nickgray/Documents/GitHub/PlayMonsters
python3 -m http.server 8765
```

Then open:

```text
http://127.0.0.1:8765/tools/Asobipedia/index.html
```

Some browsers are flaky about loading sprite sheets correctly from `file://`, so serving it locally is the reliable path.
