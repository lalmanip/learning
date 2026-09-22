# Vyapar replacement MVP — B R Machinery Stores

Short plan for a local GST retail inventory + sales app.

## Stack

- **Python 3 + Streamlit** — one-command UI, no DB server
- **CSV under `data/`** — enough for small monthly volumes
- **stdlib `csv` / `json`** — no ORM

Seller: **B R Machinery Stores**, GSTIN `10AMAPR5995H1ZW`, POS Bihar `"10"`.

## CSV schema

### `data/buyers.csv`
| Column | Notes |
|--------|--------|
| buyer_name | Party name |
| buyer_gstin | Blank = treat as B2C on sales |
| buyer_addr | Address |
| buyer_phone | Store contact only — **not** in GSTR JSON |

UI: **Buyers** page. **Add sale** picks a buyer and auto-fills fields.

### `data/items.csv` (inventory)
| Column | Notes |
|--------|--------|
| item_name | Match key (case-insensitive) |
| hsn | Default HSN for lines / HSN summary |
| uqc | Unit of measure (`DOZ`, `NOS`, …) |
| rate, gst_pct | Defaults for sale/purchase lines |
| stock_qty | On-hand count **in that UQC** (no dozen↔piece conversion) |

UI: **Items** page (list / add / edit / set stock / +/- adjust).  
**Add sale** / **Add purchase** pick inventory rows to auto-fill name/HSN/rate/GST/UQC.

**Stock rules**
- Sale: **block** if matched item qty exceeds stock (clear error). Custom lines not in master do not change stock.
- Purchase: **increase** stock; create master row if missing.
- Seed invoice 934 does **not** deduct stock (historical).

### `data/sales_invoices.csv`
| Column | Notes |
|--------|--------|
| inum | Invoice no (e.g. 934) |
| idt | Date `DD-MM-YYYY` |
| buyer_name, buyer_gstin, buyer_addr, buyer_phone | Party (phone for records) |
| pos | Place of supply (`10`) |
| inv_typ | `R` regular |
| rchrg | `N` / `Y` |
| round_off | +/- adjustment |
| grand_total | Invoice value (`val` in GSTR) |

### `data/sales_items.csv`
| Column | Notes |
|--------|--------|
| inum, line_num | Link to header |
| item_name, hsn, qty, uqc | Line details |
| rate, gst_pct | Unit rate, GST % |
| taxable | qty × rate |
| gst_amt | taxable × gst_pct / 100 |

CGST/SGST = half of `gst_amt` when POS is Bihar (intra-state). IGST unused in sample.

### Purchases
Same shape: `purchases.csv` + `purchase_items.csv` (supplier_* instead of buyer_*). Stored for books; **not** in GSTR outward export. Saving a purchase updates `items.csv` stock.

## GSTR mapping (`fp` = MMYYYY)

Matches `/internal/gstr-sample.json` shape:

| JSON | Source |
|------|--------|
| `gstin`, `fp`, `version` | Config / user input (`GST3.2.2`) |
| `b2b[].ctin` | Buyer GSTIN (blank GSTIN → skip / B2C stub) |
| `inv[].inum, idt, val, pos, inv_typ, rchrg` | Sales header |
| `itms[].itm_det` | **Group lines by `gst_pct`**: `rt`, `txval` sum, `camt`/`samt` = half GST, `iamt`/`csamt` = 0 |
| `hsn.hsn_b2b` | Group B2B lines by HSN + rate: qty, txval, camt, samt |
| `hsn.hsn_b2c` | Zero stub row if no B2C |
| `doc_issue` | Min/max `inum` for period, `totnum`, `cancel: 0` |

`hash` left as `"hash"`. Phone / stock are never exported.

## Sample invoice (seed)

Inv **934**, **31-08-2026**, Deepa Handlooms / `10EVGPK1973R1ZY` (also in `buyers.csv`).

Items seeded into `items.csv` if missing: Steel Temple Rolls (DOZ), NBC 6304Z (NOS), Bush (NOS).

Run: `python3 scripts/seed_sample_invoice.py`

## How to run

```bash
pip install -r requirements.txt
python3 scripts/seed_sample_invoice.py   # optional
python3 -m streamlit run app.py
```

UI pages: Add Sale, Add Purchase, Buyers, Items, List docs, Export GSTR JSON.
