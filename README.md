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

Seeds (if missing): `data/buyers.csv` (Deepa Handlooms), `data/items.csv` (Steel Temple Rolls / NBC 6304Z / Bush), plus invoice 934 in sales CSVs. Seed does **not** deduct stock for 934.

```bash
python3 scripts/seed_sample_invoice.py --force
```

## Run the app

```bash
python3 -m streamlit run app.py
```

Pages:

1. **Add sale** — pick buyer + inventory items, calendar date; **blocks** if stock too low
2. **Add purchase** — pick/create items; **increases** stock (creates master rows if new)
3. **Buyers** — list / add / edit / delete parties
4. **Items** — inventory master: HSN, UQC, rate, GST%, stock (set or +/-)
5. **List documents** — view saved sales/purchases
6. **Export GSTR JSON** — filing period `fp` (e.g. `082026`)

## Stock convention

- `stock_qty` is numeric in the item’s stored **UQC** (e.g. DOZ for Steel Temple Rolls, NOS for Bush). No dozen↔piece conversion.
- Sale of an item in the master **decreases** stock; insufficient stock → sale **not saved** (clear error).
- Custom sale lines not in the master leave stock unchanged.
- Purchase lines **increase** stock and upsert the items master.

## Data files

| File | Purpose |
|------|---------|
| `data/buyers.csv` | Buyer name, GSTIN, address, phone |
| `data/items.csv` | Item master + stock qty |
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
from store import read_csv, ITEMS, stock_shortfalls, apply_sale_stock, apply_purchase_stock, fnum
import json
print('items:', read_csv(ITEMS))
print(json.dumps(build_gstr('082026'), indent=2)[:400], '...')
"
```

Expect B2B buyer `10EVGPK1973R1ZY`, invoice `934`, `val` 1892.00, HSN rows for `8448` and `848210`.

## Plan

See [`docs/vyapar-replacement-plan.md`](docs/vyapar-replacement-plan.md).
