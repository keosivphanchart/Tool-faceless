# IT Report Generator

Upload a CSV/Excel of server metrics, get back a threshold-based health
summary (healthy/warning/critical per server), critical issues, recommended
actions, charts, and a downloadable PDF — plus one-click delivery over email
or Telegram. MVP scope: no auth, no billing — see "Roadmap" below for what a
paid version would add.

## Input format

One row per server. Column names are matched case-insensitively with a few
common aliases (`hostname`/`host`/`name` for server, `state` for status,
`memory`/`mem` for RAM, `storage` for disk). `status` and the metric columns
are all optional per row.

```csv
server,status,cpu,ram,disk
Server01,up,92,40,55
Server02,up,35,50,60
Server03,up,20,30,91
Server04,down,,,
```

See `sample_servers.csv` for a ready-to-upload example.

Thresholds (hardcoded in `app/analyzer.py`): CPU/RAM/disk >= 70/75/80% is a
warning, >= 85/90/90% is critical; `status` of down/offline/unreachable is
always critical.

## Run it

```bash
cd it-report-generator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: fill in SMTP_*/TELEGRAM_* to enable delivery
uvicorn app.main:app --reload --port 8100
```

Open http://localhost:8100 and upload `sample_servers.csv`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## API

- `POST /api/analyze` — multipart file upload, returns the summary/servers/
  issues/recommendations JSON and stores a PDF
- `GET /api/reports` — recent reports
- `GET /api/reports/{id}` — one report's JSON
- `GET /api/reports/{id}/pdf` — download the PDF
- `POST /api/reports/{id}/send-email` / `send-telegram` — deliver the cached
  PDF (400 if the corresponding `.env` vars aren't set)

## Roadmap (not built yet)

- User accounts + the free/paid tiers from the original pitch (5 reports/mo
  free, 50/mo at $5, unlimited + scheduling + auto-delivery at $15)
- Scheduled reports (cron-style, re-pull the same data source on a timer)
- Configurable thresholds per deployment instead of the hardcoded defaults
- Optional OpenAI-written prose summary layered on top of the rule-based one
