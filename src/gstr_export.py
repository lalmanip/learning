"""Build GSTR-style JSON from saved sales CSVs (shape from gstr-sample.json)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from store import (
    DEFAULT_POS,
    GSTR_VERSION,
    SELLER_GSTIN,
    SALES_INVOICES,
    SALES_ITEMS,
    fnum,
    money,
    read_csv,
    split_cgst_sgst,
)


def _parse_idt(idt: str) -> tuple[int, int, int] | None:
    """Return (day, month, year) from DD-MM-YYYY or D-M-YY."""
    parts = idt.strip().replace("/", "-").split("-")
    if len(parts) != 3:
        return None
    try:
        d, m, y = (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    if y < 100:
        y += 2000
    return d, m, y


def _in_fp(idt: str, fp: str) -> bool:
    """fp is MMYYYY (e.g. 082026)."""
    parsed = _parse_idt(idt)
    if not parsed or len(fp) != 6:
        return False
    _, m, y = parsed
    return f"{m:02d}{y:04d}" == fp


def _norm_idt(idt: str) -> str:
    parsed = _parse_idt(idt)
    if not parsed:
        return idt
    d, m, y = parsed
    return f"{d:02d}-{m:02d}-{y:04d}"


def build_gstr(fp: str, gstin: str = SELLER_GSTIN, version: str = GSTR_VERSION) -> dict[str, Any]:
    invoices = [r for r in read_csv(SALES_INVOICES) if _in_fp(r.get("idt", ""), fp)]
    all_items = read_csv(SALES_ITEMS)
    items_by_inv: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in all_items:
        items_by_inv[row["inum"]].append(row)

    b2b_by_ctin: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hsn_b2b_acc: dict[tuple[str, float], dict[str, float]] = {}
    hsn_b2c_acc: dict[tuple[str, float], dict[str, float]] = {}
    doc_nums: list[str] = []

    for inv in invoices:
        inum = inv["inum"]
        lines = items_by_inv.get(inum, [])
        ctin = (inv.get("buyer_gstin") or "").strip().upper()
        is_b2b = bool(ctin)

        # Group line items by GST rate for itms[]
        by_rate: dict[float, dict[str, float]] = defaultdict(
            lambda: {"txval": 0.0, "gst": 0.0}
        )
        for line in lines:
            rt = fnum(line.get("gst_pct"))
            tx = fnum(line.get("taxable"))
            gst = fnum(line.get("gst_amt"))
            by_rate[rt]["txval"] = money(by_rate[rt]["txval"] + tx)
            by_rate[rt]["gst"] = money(by_rate[rt]["gst"] + gst)

            hsn = (line.get("hsn") or "").strip() or "0"
            key = (hsn, rt)
            bucket = hsn_b2b_acc if is_b2b else hsn_b2c_acc
            if key not in bucket:
                bucket[key] = {"qty": 0.0, "txval": 0.0, "gst": 0.0}
            bucket[key]["qty"] = money(bucket[key]["qty"] + fnum(line.get("qty")))
            bucket[key]["txval"] = money(bucket[key]["txval"] + tx)
            bucket[key]["gst"] = money(bucket[key]["gst"] + gst)

        itms = []
        for i, rt in enumerate(sorted(by_rate.keys()), start=1):
            agg = by_rate[rt]
            camt, samt = split_cgst_sgst(agg["gst"])
            itms.append(
                {
                    "num": i,
                    "itm_det": {
                        "rt": money(rt),
                        "txval": money(agg["txval"]),
                        "iamt": 0.00,
                        "camt": camt,
                        "samt": samt,
                        "csamt": 0.00,
                    },
                }
            )

        inv_obj = {
            "inum": inum,
            "idt": _norm_idt(inv.get("idt", "")),
            "val": money(fnum(inv.get("grand_total"))),
            "pos": inv.get("pos") or DEFAULT_POS,
            "inv_typ": inv.get("inv_typ") or "R",
            "itms": itms,
            "rchrg": inv.get("rchrg") or "N",
        }
        doc_nums.append(inum)

        if is_b2b:
            b2b_by_ctin[ctin].append(inv_obj)

    b2b = [{"ctin": ctin, "inv": invs} for ctin, invs in sorted(b2b_by_ctin.items())]

    def hsn_rows(acc: dict[tuple[str, float], dict[str, float]]) -> list[dict[str, Any]]:
        rows = []
        for num, ((hsn, rt), vals) in enumerate(sorted(acc.items()), start=1):
            camt, samt = split_cgst_sgst(vals["gst"])
            rows.append(
                {
                    "num": num,
                    "hsn_sc": hsn,
                    "uqc": "OTH",
                    "rt": money(rt),
                    "qty": money(vals["qty"]),
                    "txval": money(vals["txval"]),
                    "iamt": 0.00,
                    "camt": camt,
                    "samt": samt,
                    "csamt": 0.00,
                    "desc": "Other",
                }
            )
        return rows

    hsn_b2b = hsn_rows(hsn_b2b_acc)
    hsn_b2c = hsn_rows(hsn_b2c_acc)
    if not hsn_b2c:
        hsn_b2c = [
            {
                "num": 1,
                "hsn_sc": "0",
                "uqc": "OTH",
                "rt": 0.00,
                "qty": 0.00,
                "txval": 0.00,
                "iamt": 0.00,
                "camt": 0.00,
                "samt": 0.00,
                "csamt": 0.00,
                "desc": "Other",
            }
        ]

    # Sort doc numbers as strings that may be numeric
    def sort_key(n: str):
        return (0, int(n)) if n.isdigit() else (1, n)

    sorted_docs = sorted(doc_nums, key=sort_key)
    if sorted_docs:
        from_num, to_num = sorted_docs[0], sorted_docs[-1]
        totnum = len(sorted_docs)
    else:
        from_num = to_num = ""
        totnum = 0

    return {
        "gstin": gstin,
        "fp": fp,
        "version": version,
        "hash": "hash",
        "b2b": b2b,
        "hsn": {"hsn_b2b": hsn_b2b, "hsn_b2c": hsn_b2c},
        "doc_issue": {
            "doc_det": [
                {
                    "doc_num": 1,
                    "doc_typ": "Invoices for outward supply",
                    "docs": [
                        {
                            "num": 1,
                            "from": from_num,
                            "to": to_num,
                            "totnum": totnum,
                            "cancel": 0,
                            "net_issue": totnum,
                        }
                    ],
                }
            ]
        },
    }
