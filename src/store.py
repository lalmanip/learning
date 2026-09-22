"""Shared config and CSV helpers for B R Machinery Stores GST MVP."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

# Seller (from sample sales invoice)
SELLER_NAME = "B R MACHINERY STORES"
SELLER_GSTIN = "10AMAPR5995H1ZW"
SELLER_ADDR = "MANPUR SHIV CHARAN LANE, GAYA"
DEFAULT_POS = "10"  # Bihar
GSTR_VERSION = "GST3.2.2"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SALES_INVOICES = DATA_DIR / "sales_invoices.csv"
SALES_ITEMS = DATA_DIR / "sales_items.csv"
PURCHASES = DATA_DIR / "purchases.csv"
PURCHASE_ITEMS = DATA_DIR / "purchase_items.csv"
BUYERS = DATA_DIR / "buyers.csv"

SALES_INVOICE_FIELDS = [
    "inum",
    "idt",
    "buyer_name",
    "buyer_gstin",
    "buyer_addr",
    "buyer_phone",
    "pos",
    "inv_typ",
    "rchrg",
    "round_off",
    "grand_total",
]

BUYER_FIELDS = [
    "buyer_name",
    "buyer_gstin",
    "buyer_addr",
    "buyer_phone",
]

SALES_ITEM_FIELDS = [
    "inum",
    "line_num",
    "item_name",
    "hsn",
    "qty",
    "uqc",
    "rate",
    "gst_pct",
    "taxable",
    "gst_amt",
]

PURCHASE_FIELDS = [
    "inum",
    "idt",
    "supplier_name",
    "supplier_gstin",
    "supplier_addr",
    "pos",
    "inv_typ",
    "rchrg",
    "round_off",
    "grand_total",
]

PURCHASE_ITEM_FIELDS = [
    "inum",
    "line_num",
    "item_name",
    "hsn",
    "qty",
    "uqc",
    "rate",
    "gst_pct",
    "taxable",
    "gst_amt",
]


def _migrate_csv_columns(path: Path, fields: list[str]) -> None:
    """Add any missing columns (e.g. buyer_phone) without dropping data."""
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()
        return
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing = list(reader.fieldnames or [])
        rows = list(reader)
    if existing == fields:
        return
    rewritten = [{k: row.get(k, "") for k in fields} for row in rows]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rewritten)


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path, fields in (
        (SALES_INVOICES, SALES_INVOICE_FIELDS),
        (SALES_ITEMS, SALES_ITEM_FIELDS),
        (PURCHASES, PURCHASE_FIELDS),
        (PURCHASE_ITEMS, PURCHASE_ITEM_FIELDS),
        (BUYERS, BUYER_FIELDS),
    ):
        _migrate_csv_columns(path, fields)


def read_csv(path: Path) -> list[dict[str, str]]:
    ensure_data_files()
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def buyer_label(row: dict[str, str]) -> str:
    name = (row.get("buyer_name") or "").strip() or "(unnamed)"
    gstin = (row.get("buyer_gstin") or "").strip()
    return f"{name} ({gstin})" if gstin else f"{name} (no GSTIN)"


def find_buyer_index(rows: list[dict[str, str]], name: str, gstin: str) -> int | None:
    name_n = name.strip().lower()
    gstin_n = gstin.strip().upper()
    for i, row in enumerate(rows):
        if gstin_n and (row.get("buyer_gstin") or "").strip().upper() == gstin_n:
            return i
        if not gstin_n and (row.get("buyer_name") or "").strip().lower() == name_n:
            return i
    return None


def upsert_buyer(
    name: str,
    gstin: str,
    addr: str,
    phone: str,
) -> None:
    """Insert or update a buyer (match GSTIN if present, else name)."""
    ensure_data_files()
    rows = read_csv(BUYERS)
    payload = {
        "buyer_name": name.strip(),
        "buyer_gstin": gstin.strip().upper(),
        "buyer_addr": addr.strip(),
        "buyer_phone": phone.strip(),
    }
    idx = find_buyer_index(rows, payload["buyer_name"], payload["buyer_gstin"])
    if idx is None:
        rows.append(payload)
    else:
        rows[idx] = payload
    rewrite_csv(BUYERS, BUYER_FIELDS, rows)


def append_rows(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    ensure_data_files()
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def rewrite_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    ensure_data_files()
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def line_taxable(qty: float, rate: float) -> float:
    return money(qty * rate)


def line_gst(taxable: float, gst_pct: float) -> float:
    return money(taxable * gst_pct / 100.0)


def split_cgst_sgst(gst_amt: float) -> tuple[float, float]:
    half = money(gst_amt / 2.0)
    # Keep camt + samt == gst_amt after rounding
    return half, money(gst_amt - half)
