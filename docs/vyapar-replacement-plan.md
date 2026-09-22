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

UI: **Buyers** page (list / add / edit / delete). **Add sale** picks a buyer from a dropdown and auto-fills fields; optional “save/update buyer” on the sale form.

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
| item_name, hsn, qty, uqc | Line details (`uqc` default `OTH`) |
| rate, gst_pct | Unit rate, GST % |
| taxable | qty × rate |
| gst_amt | taxable × gst_pct / 100 |

CGST/SGST = half of `gst_amt` when POS is Bihar (intra-state). IGST unused in sample.

### Purchases
Same shape: `purchases.csv` + `purchase_items.csv` (supplier_* instead of buyer_*). Stored for books; **not** in GSTR outward export.

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

`hash` left as `"hash"` (portal fills real hash). Phone is never exported.

## Sample invoice (seed)

Inv **934**, **31-08-2026**, Deepa Handlooms / `10EVGPK1973R1ZY` (also seeded into `buyers.csv`):

1. Steel Temple Rolls — HSN 8448 — 2 Dz @ 540 — 18% — taxable 1080 — GST 194.40  
2. NBC 6304Z — HSN 848210 — 1 @ 159.54 — 18% — taxable 159.54 — GST 28.72  
3. Bush — HSN 8448 — 607 @ 0.60 — 18% — taxable 364.20 — GST 65.56  

Round-off +0.42 → grand total **1892.00**. Filing period `082026`.

Run: `python3 scripts/seed_sample_invoice.py`

## How to run

```bash
pip install -r requirements.txt
python3 scripts/seed_sample_invoice.py   # optional
python3 -m streamlit run app.py
```

UI pages: Add Sale, Add Purchase, Buyers, List docs, Export GSTR JSON.
