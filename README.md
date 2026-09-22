# B R Machinery Stores — GST retail MVP

Local inventory + sales app for Indian GST retail (CSV storage, GSTR-style JSON export).

**Seller:** B R Machinery Stores · GSTIN `10AMAPR5995H1ZW` · Place of supply Bihar (`10`)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Seed sample invoice (Inv 934)

Handwritten GST invoice: Deepa Handlooms, 31-08-2026, 3 lines, round-off +0.42 → ₹1892.

`data/sales_*.csv` already includes this invoice; `data/buyers.csv` includes Deepa Handlooms. To re-seed:

```bash
python3 scripts/seed_sample_invoice.py --force
```

## Run the app

```bash
python3 -m streamlit run app.py
```

Pages:

1. **Add sale** — pick buyer from dropdown (or new), calendar date, line items
2. **Add purchase** — same shape for supplier bills
3. **Buyers** — list / add / edit / delete parties (`data/buyers.csv`)
4. **List documents** — view saved sales/purchases from `data/*.csv`
5. **Export GSTR JSON** — enter filing period `fp` (e.g. `082026`) and download JSON shaped like the reference sample (`b2b`, `hsn`, `doc_issue`)

## Data files

| File | Purpose |
|------|---------|
| `data/buyers.csv` | Buyer name, GSTIN, address, phone |
| `data/sales_invoices.csv` | Sale headers (includes buyer phone for records) |
| `data/sales_items.csv` | Sale line items |
| `data/purchases.csv` | Purchase headers |
| `data/purchase_items.csv` | Purchase line items |

## Quick check (no UI)

```bash
python3 scripts/seed_sample_invoice.py --force
python3 -c "
import sys; sys.path.insert(0,'src')
from gstr_export import build_gstr
import json
print(json.dumps(build_gstr('082026'), indent=2))
"
```

Expect B2B buyer `10EVGPK1973R1ZY`, invoice `934`, `val` 1892.00, HSN rows for `8448` and `848210`.

## Plan

See [`docs/vyapar-replacement-plan.md`](docs/vyapar-replacement-plan.md).
