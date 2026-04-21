# PDF Invoice Parser

Parse a folder of PDF invoices into a canonical invoice model using
language-specific extraction adapters plus a keyword-bag fallback for
templates we haven't seen before. Invoices that don't extract cleanly are
surfaced in a dashboard so new adapters can be added iteratively.

## Canonical fields

The target shape every adapter tries to populate:

| Field                | Example          |
| -------------------- | ---------------- |
| `invoice_no`         | `AF-2026-058`    |
| `vendor`             | `Crayon A/S`     |
| `customer`           | `Cue ApS, Aarhus` |
| `due_date`           | `2026-03-15`     |
| `gross_total_amount` | `15250.00`       |
| `billing_type`       | `Invoice`        |
| `currency`           | `DKK`            |

XLSX export uses these exact columns:
`Invoice_no | Vendor | Customer | Due_Date | Gross_Total_Amount | Billing_Type | Currency`.

## Architecture

```
data/pdf_invoices/*.pdf
  │
  ▼
pypdf text extraction
  │
  ▼
Adapter cascade (scored by detect_score)
  ├── DanishAdapter           (Faktura / Fakturanr / Forfald / I alt)
  ├── EnglishAdapter          (Invoice No / Due Date / Total Due)
  ├── BilingualGermanEnglish  (Rechnungsnr. / Invoice No., stacked layout)
  └── GenericKeywordAdapter   (last-resort, multi-language keyword net)
  │
  ▼  primary adapter wins; missing fields filled by subsequent adapters
  ▼
ParseResult { status = parsed | partial | failed, canonical fields,
              adapter_used, missing_fields, warnings, error, text_preview }
  │
  ▼
In-memory store
  │
  ▼
FastAPI ─── JSON + XLSX endpoints ─── React dashboard
```

- **Failure behaviour.** Unreadable PDFs or PDFs where no adapter extracted
  a single canonical field are marked `failed` and surfaced in the
  dashboard with the raw text preview so a new adapter can be built.
- **Partial results.** If some fields were extracted but not all, the
  status is `partial` and `missing_fields` tells you what's still missing.
- **Adding a new adapter.** Implement the `InvoiceAdapter` protocol in
  `backend/src/adapters/` and add it to `ALL_ADAPTERS` in
  `backend/src/adapters/__init__.py`.

**Backend** (`backend/`): Python 3.12+, FastAPI, Pydantic v2, pypdf, openpyxl  
**Frontend** (`frontend/`): React 19, TypeScript, Tailwind CSS v4, Vite

## Quick Start

Drop PDF invoices into `pdf_invoices/` (or point `PDF_INPUT_DIR` at a
different folder), then:

```bash
task setup      # install backend + frontend dependencies
task dev        # start backend + frontend in parallel
```

Backend serves at `http://localhost:8000` (API docs at `/docs`).  
Dashboard serves at `http://localhost:5173`.

### Manual setup

```bash
# Backend
cd backend
uv sync --extra dev
uv run uvicorn src.api.app:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Other commands

```bash
task test       # run backend pytest suite
task lint       # ruff check + format
task parse      # run parser only, no server
```

## Build / Run Windows .exe

### End-user runtime flow

1. Download `pdf-parser.exe` from a GitHub Release artifact.
2. Place the executable next to a folder named `pdf_invoices`.
3. Put invoice PDFs in that `pdf_invoices` folder.
4. Double-click `pdf-parser.exe`.
5. The app starts a local server and opens your default browser at `http://localhost:8765`.

Notes:
- The first launch can take a few seconds because this is a one-file PyInstaller build.
- Windows SmartScreen may show an "Unknown publisher" warning (expected for unsigned binaries).
- If port `8765` is occupied, the app automatically falls back to another local port.

### Build and release flow

- **Local packaging smoke test:** `task build:exe` (builds the frontend and runs PyInstaller).
- **CI packaging:** push a tag like `v0.1.0` (or run the workflow manually) to trigger `.github/workflows/build-windows.yml`.
- The workflow uploads `pdf-parser.exe` as an artifact and also attaches it to the tag release.

## API endpoints

| Endpoint                      | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `GET  /api/summary`           | Counts of parsed / partial / failed + current run info  |
| `GET  /api/invoices?status=…` | All parse results (filter: `all|parsed|partial|failed`) |
| `GET  /api/invoices/failed`   | Shortcut: PDFs that extracted zero canonical fields     |
| `POST /api/reparse`           | Re-run parsing against the configured folder           |
| `GET  /api/export.xlsx`       | XLSX export of fully validated invoices                 |
| `GET  /docs`                  | Interactive Swagger UI                                  |

`GET /api/export.xlsx?include_partial=true` also includes partial rows.

## Project structure

```
data/
  pdf_invoices/         # drop PDFs here (configurable via PDF_INPUT_DIR)

backend/
  src/
    domain/             # CanonicalInvoice, ParseResult, ParseStatus
    adapters/           # InvoiceAdapter implementations (one per template)
    parsers/            # pdf_parser orchestrator + normalization helpers
    api/                # FastAPI app, routes, schemas
    pipeline.py         # parse-folder pipeline + in-memory store
    exporter.py         # XLSX export
    config.py           # AppConfig (env-driven)
  tests/                # adapter unit + pipeline smoke tests

frontend/
  src/
    components/         # SummaryCards, InvoiceTable, InvoiceRow, StatusBadge
    hooks/              # useInvoices (fetch + reparse)
    types/              # TypeScript API interfaces
```

## Environment variables

| Variable            | Default                      | Description                                 |
| ------------------- | ---------------------------- | ------------------------------------------- |
| `PDF_INPUT_DIR`     | `<repo>/pdf_invoices`        | Folder scanned for `*.pdf` files            |
| `LOG_LEVEL`         | `INFO`                       | Python logging level                        |
| `PARSE_ON_STARTUP`  | `1`                          | Set to `0` to skip the startup parse run    |

