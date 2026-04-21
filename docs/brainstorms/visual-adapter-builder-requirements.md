---
date: 2026-04-17
topic: visual-adapter-builder
---

# Visual Adapter Builder

## Problem Frame

Today, every new vendor invoice template requires a developer to write a Python adapter (see `backend/src/adapters/*.py`). With the current corpus of 194 PDFs, 44 are already parsing only partially and 8 cannot be read at all (image-only), and the distribution of templates keeps growing as new suppliers are added. This bottleneck blocks the non-technical finance/ops analyst who owns the invoice corpus from onboarding new suppliers on their own.

The goal is a dashboard feature that lets an ops analyst **teach the parser a new template visually**, directly from a failed or partial invoice, without writing code. The teaching act must produce a reusable vendor-level adapter that automatically applies to every future invoice from the same supplier.

Target user: **finance/ops analyst inside a single org**, non-technical, self-service. Not a developer; not a multi-tenant SaaS customer.

## Visual Flow

```text
Dashboard ── click partial row ──► Builder (modal or sub-page)
                                       │
   ┌───────────────────────────────────┴────────────────────────────────────┐
   │  Rendered PDF preview (left)          Field panel (right)              │
   │  ┌──────────────────────┐             ┌───────────────────────────┐    │
   │  │  Crayon A/S          │             │ • Invoice_no   [ missing ]│    │
   │  │  ...                 │             │ • Vendor       [Crayon…✓ ]│    │
   │  │  Fakturanummer       │             │ • Customer     [Energinet]│    │
   │  │  4139526   <click>   │ ───tag────► │ • Due_Date     [ missing ]│    │
   │  │  ...                 │             │ • Gross_Total  [ missing ]│    │
   │  │  Fakturatotal        │             │ • Billing_Type [Invoice ✓]│    │
   │  │  7 237 127,76 DKK    │             │ • Currency     [ missing ]│    │
   │  └──────────────────────┘             └───────────────────────────┘    │
   │                                                                        │
   │  System proposes vendor signature:  "Crayon A/S"    [Confirm|Edit]     │
   │                                                                        │
   │  [ Preview on 3 similar PDFs ]   [ Save adapter ]                      │
   └────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
   Saved to SQLite. Next parse run routes matching PDFs to this adapter.
```

## Requirements

**Entry point and context**

- R1. The builder opens contextually from a partial or failed invoice row on the main dashboard. There is no standalone "create adapter" entry point in v1.
- R2. The builder shows the specific PDF that the analyst clicked, rendered on screen, not just its extracted text.
- R3. The builder shows which canonical fields are currently missing or low-confidence for the opened invoice, and which are already populated (by the cascade that already ran).

**Mapping mechanic**

- R4. The analyst teaches a field by clicking directly on its value inside the rendered PDF (e.g., clicks "4139526"), then assigning it to a canonical field (e.g., "Invoice_no") via a side panel.
- R5. Each tag captures both (a) the nearest preceding/surrounding label text ("Fakturanummer") and (b) an approximate spatial region, so the resulting rule is resilient to minor layout shifts within the same vendor's invoices.
- R6. The analyst only needs to tag the fields that are missing. Fields already extracted correctly by the base cascade are shown pre-filled, editable, but not required to re-tag.
- R7. The canonical field set the analyst can tag is exactly the seven canonical fields already defined in `backend/src/domain/invoice.py` (`invoice_no`, `vendor`, `customer`, `due_date`, `gross_total_amount`, `billing_type`, `currency`). No new fields are introduced by this feature.

**Vendor identification and routing**

- R8. On save, the system auto-proposes a **vendor signature** — a text phrase (or short set of phrases) that appears on the current PDF but does not appear on any other vendor's invoices the system already knows about. The analyst confirms or edits the proposed phrase before save.
- R9. Future parse runs route a PDF to a user-authored adapter when that PDF's text contains the adapter's signature phrase. Built-in adapters (SAP, KMD, Crayon, Microsoft DK, etc.) retain precedence on signature ties so user adapters cannot silently override them.
- R10. If two user adapters match the same PDF, the system uses the one with the more specific (longer / higher-selectivity) signature and surfaces a warning in the parse result, so the analyst can resolve the ambiguity.

**Persistence**

- R11. User-authored adapters persist across server restarts, stored in a SQLite database alongside the (currently in-memory) parse-result store. Built-in Python adapters remain code-based and are not migrated to the database.
- R12. The analyst can view the list of user-authored adapters (implied by R11 for debugging/audit, but no full management UI is required in v1 — see R18).

**Preview / trust**

- R13. Before saving, the analyst can preview how the new rule applies to other invoices already in the corpus that match the proposed signature. The preview shows each invoice's extracted canonical fields so the analyst can catch systematic mistakes.
- R14. After save, the builder re-parses the current invoice using the new adapter and moves the row from "partial"/"failed" to "parsed" on the dashboard if all canonical fields are now filled, without requiring a full folder re-parse.

## Success Criteria

- The ops analyst can onboard a new supplier template end-to-end without developer assistance, in under 5 minutes per template, for any digital (text-extractable) PDF.
- At least 80% of the 44 current partials are resolvable by the analyst through this feature alone, after adapters are authored for the top 5 unhandled vendors.
- Built-in adapter accuracy does not regress. User adapters must not silently override or modify the behavior of the existing vendor-specific adapters.
- Re-importing the same corpus after saving an adapter moves matching invoices from "partial"/"failed" to "parsed" on the next parse run with no additional user action.

## Scope Boundaries

- **Out of scope:** OCR for image-only / scanned PDFs (the 8 current failures). Stays deferred; the feature only supports PDFs with extractable text, matching the existing parser's scope.
- **Out of scope (v1):** Editing, deleting, or versioning user adapters through UI. Listing exists for visibility, but mutation post-creation happens by deleting the row and re-authoring.
- **Out of scope (v1):** Editing built-in Python adapters from the UI. Code-based adapters stay code-based.
- **Out of scope:** Multi-tenant isolation, per-user adapter visibility, RBAC. Single-org tool.
- **Out of scope:** LLM-backed field inference or auto-tagging. The whole feature is deterministic and self-contained so that behavior is predictable, auditable, and free of per-invoice cost.
- **Out of scope (v1):** Proactive "add a new supplier before importing" flow and a CMS-style adapter management page. Authoring is strictly failure-led.
- **Out of scope (v1):** Handling new canonical fields or custom/user-defined field types. Only the seven existing canonical fields.

## Key Decisions

- **Target user is the ops analyst** (non-technical, one org). Rules out regex authoring, per-user isolation, and multi-tenant concerns. Shapes the UX toward direct manipulation with minimal jargon.
- **Entry is failure-led, not onboarding-led.** Simpler to ship (only one entry point), and every authoring act is grounded in a concrete broken invoice, which also defines a natural acceptance test for the new adapter.
- **Click-to-tag on the rendered PDF**, not LLM-assisted or text-span only. Keeps the feature deterministic, avoids per-invoice LLM cost, and matches the analyst's mental model ("I point at the value"). Captures both label-anchored and spatial context per R5 so the rule survives small layout jitter.
- **System auto-proposes the vendor signature, analyst confirms.** Lowest friction while keeping the analyst in control; avoids the analyst having to manually craft or reason about routing logic.
- **SQLite persistence, user adapters only.** Built-in adapters stay in Python because they can encode more complex behaviors (stacked footers, ordinal dates, etc.) that a declarative rule format would not capture cleanly. User adapters are constrained to what the UI can express, which is exactly what the declarative store can represent.
- **Built-in adapters take precedence over user adapters on signature ties** (R9). Prevents a well-meaning but broad user adapter from hijacking a vendor that already has a polished built-in implementation.

## Dependencies / Assumptions

- Frontend can render PDFs with word-level positional metadata so clicks can be mapped to specific text tokens. PDF.js (or equivalent) provides this and is broadly used; treating this as a standard capability rather than a research risk.
- Current in-memory `ParseStore` (`backend/src/pipeline.py`) continues to hold parse *results*; only user adapter definitions move to SQLite. Mixing in-memory results with persisted adapters is acceptable because parse results are cheap to regenerate whereas adapter definitions represent real user labor.
- The seven canonical fields in `backend/src/domain/invoice.py` are stable. If they change, user adapters may need migration.
- "Vendor signature = distinctive text phrase" holds for digital invoices in practice (confirmed across SAP, KMD, Crayon, Microsoft in the current corpus, each of which has a unique vendor-name string). Edge cases where two vendors share a signature are rare enough to surface as a runtime warning (R10) rather than designed-for in v1.

## Outstanding Questions

### Resolve Before Planning

_None — all product-shape decisions resolved._

### Deferred to Planning

- [Affects R4, R5][Technical] What exactly does a "user adapter rule" look like on disk? Likely a JSON-ish structure per field: `{label_anchor: "Fakturanummer", direction: "below"|"right"|"same-line", token_pattern: "numeric", bbox_hint: {...}}`. Planning should define the full schema and its evaluator.
- [Affects R8, R10][Technical] What signature-generation algorithm does the backend use? Candidates: rarest n-gram in this PDF vs the rest of the corpus; longest line that appears only in this PDF; a fixed "first N chars of the vendor address block" heuristic. Planning should evaluate trade-offs.
- [Affects R2][Technical] Which PDF-rendering library on the frontend? PDF.js is the obvious default, but tradeoffs (bundle size, token-level click-through support, annotation APIs) warrant a short spike.
- [Affects R13][Technical] Is the preview run synchronously via a new `/api/preview-adapter` endpoint against all in-memory PDFs, or as a background job? Depends on corpus size expectations beyond 194.
- [Affects R9][Needs research] When user adapters are stored in SQLite and built-in adapters are Python, how does the `parse_pdf` cascade in `backend/src/parsers/pdf_parser.py` interleave them cleanly? Prefer a single unified ranking loop over two separate cascades.
- [Affects R11][Technical] Migration path if the canonical-field set changes later: simplest is a versioned schema on the user-adapter rows, migrated on read.

## Next Steps

-> `/ce:plan` for structured implementation planning.
