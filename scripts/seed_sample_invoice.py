"""Seed the sample handwritten GST invoice (Inv 934) into CSV."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from store import (  # noqa: E402
    BUYER_FIELDS,
    BUYERS,
    SALES_INVOICE_FIELDS,
    SALES_INVOICES,
    SALES_ITEM_FIELDS,
    SALES_ITEMS,
    ensure_data_files,
    find_buyer_index,
    line_gst,
    line_taxable,
    money,
    read_csv,
    rewrite_csv,
    split_cgst_sgst,
    upsert_buyer,
)


SAMPLE_BUYER = {
    "buyer_name": "Deepa Handlooms",
    "buyer_gstin": "10EVGPK1973R1ZY",
    "buyer_addr": "Manpur Shiv charan lane",
    "buyer_phone": "",
}

SAMPLE_HEADER = {
    "inum": "934",
    "idt": "31-08-2026",
    "buyer_name": SAMPLE_BUYER["buyer_name"],
    "buyer_gstin": SAMPLE_BUYER["buyer_gstin"],
    "buyer_addr": SAMPLE_BUYER["buyer_addr"],
    "buyer_phone": SAMPLE_BUYER["buyer_phone"],
    "pos": "10",
    "inv_typ": "R",
    "rchrg": "N",
    "round_off": "0.42",
    "grand_total": "1892.00",
}

SAMPLE_LINES = [
    {
        "line_num": "1",
        "item_name": "Steel Temple Rolls",
        "hsn": "8448",
        "qty": 2.0,
        "uqc": "DOZ",
        "rate": 540.0,
        "gst_pct": 18.0,
    },
    {
        "line_num": "2",
        "item_name": "NBC 6304Z",
        "hsn": "848210",
        "qty": 1.0,
        "uqc": "NOS",
        "rate": 159.54,
        "gst_pct": 18.0,
    },
    {
        "line_num": "3",
        "item_name": "Bush",
        "hsn": "8448",
        "qty": 607.0,
        "uqc": "NOS",
        "rate": 0.60,
        "gst_pct": 18.0,
    },
]


def build_item_rows(inum: str) -> list[dict]:
    rows = []
    for line in SAMPLE_LINES:
        taxable = line_taxable(line["qty"], line["rate"])
        gst_amt = line_gst(taxable, line["gst_pct"])
        rows.append(
            {
                "inum": inum,
                "line_num": line["line_num"],
                "item_name": line["item_name"],
                "hsn": line["hsn"],
                "qty": f"{line['qty']:.2f}",
                "uqc": line["uqc"],
                "rate": f"{line['rate']:.2f}",
                "gst_pct": f"{line['gst_pct']:.2f}",
                "taxable": f"{taxable:.2f}",
                "gst_amt": f"{gst_amt:.2f}",
            }
        )
    return rows


def seed_buyer() -> None:
    ensure_data_files()
    rows = read_csv(BUYERS)
    idx = find_buyer_index(rows, SAMPLE_BUYER["buyer_name"], SAMPLE_BUYER["buyer_gstin"])
    if idx is None:
        upsert_buyer(
            SAMPLE_BUYER["buyer_name"],
            SAMPLE_BUYER["buyer_gstin"],
            SAMPLE_BUYER["buyer_addr"],
            SAMPLE_BUYER["buyer_phone"],
        )
        print("Seeded buyer: Deepa Handlooms")
    else:
        print("Buyer Deepa Handlooms already present.")


def seed(force: bool = False) -> None:
    ensure_data_files()
    seed_buyer()
    headers = read_csv(SALES_INVOICES)
    items = read_csv(SALES_ITEMS)
    exists = any(h.get("inum") == "934" for h in headers)
    if exists and not force:
        print("Invoice 934 already present. Use --force to replace.")
        return
    if exists:
        headers = [h for h in headers if h.get("inum") != "934"]
        items = [i for i in items if i.get("inum") != "934"]
    headers.append(SAMPLE_HEADER)
    items.extend(build_item_rows("934"))
    rewrite_csv(SALES_INVOICES, SALES_INVOICE_FIELDS, headers)
    rewrite_csv(SALES_ITEMS, SALES_ITEM_FIELDS, items)

    item_rows = build_item_rows("934")
    taxable = money(sum(float(r["taxable"]) for r in item_rows))
    gst = money(sum(float(r["gst_amt"]) for r in item_rows))
    camt, samt = split_cgst_sgst(gst)
    print(f"Seeded invoice 934: taxable={taxable}, gst={gst}, CGST={camt}, SGST={samt}, grand=1892.00")


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
