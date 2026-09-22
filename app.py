"""
B R Machinery Stores — GST retail MVP (sales, purchases, GSTR JSON export).
Run: streamlit run app.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from gstr_export import build_gstr  # noqa: E402
from store import (  # noqa: E402
    BUYER_FIELDS,
    BUYERS,
    DEFAULT_POS,
    PURCHASE_FIELDS,
    PURCHASE_ITEM_FIELDS,
    PURCHASE_ITEMS,
    PURCHASES,
    SALES_INVOICE_FIELDS,
    SALES_INVOICES,
    SALES_ITEM_FIELDS,
    SALES_ITEMS,
    SELLER_ADDR,
    SELLER_GSTIN,
    append_rows,
    buyer_label,
    ensure_data_files,
    line_gst,
    line_taxable,
    money,
    read_csv,
    rewrite_csv,
    split_cgst_sgst,
    upsert_buyer,
)

st.set_page_config(page_title="B R Machinery — GST MVP", layout="wide")
ensure_data_files()

st.title("B R Machinery Stores")
st.caption(f"{SELLER_ADDR} · GSTIN {SELLER_GSTIN}")

page = st.sidebar.radio(
    "Menu",
    ["Add sale", "Add purchase", "Buyers", "List documents", "Export GSTR JSON"],
)

NEW_BUYER = "— New buyer —"


def _blank_line() -> dict:
    return {
        "item_name": "",
        "hsn": "",
        "qty": 1.0,
        "uqc": "OTH",
        "rate": 0.0,
        "gst_pct": 18.0,
    }


def _invoice_exists(path, inum: str) -> bool:
    return any(r.get("inum") == inum for r in read_csv(path))


def _format_idt(d: date) -> str:
    """Store/export as DD-MM-YYYY (CSV + GSTR idt)."""
    return d.strftime("%d-%m-%Y")


def _init_sale_buyer_fields() -> None:
    for key, default in (
        ("sale_buyer_name", ""),
        ("sale_buyer_gstin", ""),
        ("sale_buyer_addr", ""),
        ("sale_buyer_phone", ""),
    ):
        if key not in st.session_state:
            st.session_state[key] = default


def _apply_buyer_to_sale_form(buyer: dict[str, str] | None) -> None:
    if buyer is None:
        st.session_state["sale_buyer_name"] = ""
        st.session_state["sale_buyer_gstin"] = ""
        st.session_state["sale_buyer_addr"] = ""
        st.session_state["sale_buyer_phone"] = ""
    else:
        st.session_state["sale_buyer_name"] = buyer.get("buyer_name", "")
        st.session_state["sale_buyer_gstin"] = buyer.get("buyer_gstin", "")
        st.session_state["sale_buyer_addr"] = buyer.get("buyer_addr", "")
        st.session_state["sale_buyer_phone"] = buyer.get("buyer_phone", "")


def _render_line_editor(key: str) -> list[dict]:
    if key not in st.session_state:
        st.session_state[key] = [_blank_line(), _blank_line(), _blank_line()]

    st.subheader("Line items")
    cols = st.columns([1, 1])
    if cols[0].button("Add line", key=f"{key}_add"):
        st.session_state[key].append(_blank_line())
        st.rerun()
    if cols[1].button("Remove last line", key=f"{key}_rm") and len(st.session_state[key]) > 1:
        st.session_state[key].pop()
        st.rerun()

    edited: list[dict] = []
    for i, line in enumerate(st.session_state[key]):
        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 1, 1, 2, 1])
        item_name = c1.text_input("Item", value=line["item_name"], key=f"{key}_name_{i}")
        hsn = c2.text_input("HSN", value=line["hsn"], key=f"{key}_hsn_{i}")
        qty = c3.number_input("Qty", min_value=0.0, value=float(line["qty"]), key=f"{key}_qty_{i}", format="%.2f")
        uqc = c4.text_input("UQC", value=line["uqc"], key=f"{key}_uqc_{i}")
        rate = c5.number_input("Rate", min_value=0.0, value=float(line["rate"]), key=f"{key}_rate_{i}", format="%.2f")
        gst_pct = c6.number_input("GST%", min_value=0.0, value=float(line["gst_pct"]), key=f"{key}_gst_{i}", format="%.2f")
        taxable = line_taxable(qty, rate)
        gst_amt = line_gst(taxable, gst_pct)
        st.caption(f"Line {i + 1}: taxable ₹{taxable:.2f} · GST ₹{gst_amt:.2f}")
        edited.append(
            {
                "item_name": item_name,
                "hsn": hsn,
                "qty": qty,
                "uqc": uqc or "OTH",
                "rate": rate,
                "gst_pct": gst_pct,
                "taxable": taxable,
                "gst_amt": gst_amt,
            }
        )
    st.session_state[key] = [
        {k: edited[i][k] for k in ("item_name", "hsn", "qty", "uqc", "rate", "gst_pct")}
        for i in range(len(edited))
    ]
    return edited


def _totals_panel(lines: list[dict], round_off: float) -> tuple[float, float, float, float, float]:
    taxable = money(sum(l["taxable"] for l in lines))
    gst = money(sum(l["gst_amt"] for l in lines))
    camt, samt = split_cgst_sgst(gst)
    grand = money(taxable + gst + round_off)
    st.info(
        f"Taxable **₹{taxable:.2f}** · GST **₹{gst:.2f}** "
        f"(CGST ₹{camt:.2f} + SGST ₹{samt:.2f}) · Round-off **₹{round_off:.2f}** · "
        f"Grand total **₹{grand:.2f}**"
    )
    return taxable, gst, camt, samt, grand


# --- Add sale ---
if page == "Add sale":
    st.header("Add sales invoice")
    _init_sale_buyer_fields()

    c1, c2, c3 = st.columns(3)
    inum = c1.text_input("Invoice no.", value="")
    idt_date = c2.date_input("Invoice date", value=date.today(), format="DD/MM/YYYY", key="sale_idt")
    pos = c3.text_input("Place of supply", value=DEFAULT_POS)

    st.subheader("Buyer")
    buyers = read_csv(BUYERS)
    labels = [NEW_BUYER] + [buyer_label(b) for b in buyers]
    pick = st.selectbox(
        "Select buyer",
        labels,
        key="sale_buyer_pick",
        help="Pick a saved buyer, or choose New buyer and fill the fields (optionally save them).",
    )
    if pick != st.session_state.get("_sale_buyer_applied"):
        st.session_state["_sale_buyer_applied"] = pick
        if pick == NEW_BUYER:
            _apply_buyer_to_sale_form(None)
        else:
            _apply_buyer_to_sale_form(buyers[labels.index(pick) - 1])
        st.rerun()

    buyer_name = st.text_input("Buyer name", key="sale_buyer_name")
    buyer_gstin = st.text_input("Buyer GSTIN (blank = B2C)", key="sale_buyer_gstin")
    buyer_addr = st.text_input("Buyer address", key="sale_buyer_addr")
    buyer_phone = st.text_input("Buyer phone", key="sale_buyer_phone")
    save_buyer = st.checkbox(
        "Save / update this buyer in buyers.csv",
        value=(pick == NEW_BUYER),
        key="sale_save_buyer",
    )
    st.caption("Manage the full buyer list under **Buyers** in the sidebar.")

    c4, c5, c6 = st.columns(3)
    inv_typ = c4.selectbox("Invoice type", ["R"], index=0)
    rchrg = c5.selectbox("Reverse charge", ["N", "Y"], index=0)
    round_off = c6.number_input("Round-off", value=0.0, step=0.01, format="%.2f")

    lines = _render_line_editor("sale_lines")
    _, _, _, _, grand = _totals_panel(lines, round_off)

    if st.button("Save sale", type="primary"):
        idt = _format_idt(idt_date)
        if not inum.strip():
            st.error("Invoice no. is required.")
        elif _invoice_exists(SALES_INVOICES, inum.strip()):
            st.error(f"Sale invoice {inum} already exists.")
        elif not any(l["item_name"].strip() for l in lines):
            st.error("Add at least one line item with a name.")
        else:
            if save_buyer and buyer_name.strip():
                upsert_buyer(buyer_name, buyer_gstin, buyer_addr, buyer_phone)
            append_rows(
                SALES_INVOICES,
                SALES_INVOICE_FIELDS,
                [
                    {
                        "inum": inum.strip(),
                        "idt": idt,
                        "buyer_name": buyer_name.strip(),
                        "buyer_gstin": buyer_gstin.strip().upper(),
                        "buyer_addr": buyer_addr.strip(),
                        "buyer_phone": buyer_phone.strip(),
                        "pos": pos.strip() or DEFAULT_POS,
                        "inv_typ": inv_typ,
                        "rchrg": rchrg,
                        "round_off": f"{money(round_off):.2f}",
                        "grand_total": f"{grand:.2f}",
                    }
                ],
            )
            item_rows = []
            for i, line in enumerate(lines, start=1):
                if not line["item_name"].strip():
                    continue
                item_rows.append(
                    {
                        "inum": inum.strip(),
                        "line_num": str(i),
                        "item_name": line["item_name"].strip(),
                        "hsn": line["hsn"].strip(),
                        "qty": f"{money(line['qty']):.2f}",
                        "uqc": line["uqc"],
                        "rate": f"{money(line['rate']):.2f}",
                        "gst_pct": f"{money(line['gst_pct']):.2f}",
                        "taxable": f"{line['taxable']:.2f}",
                        "gst_amt": f"{line['gst_amt']:.2f}",
                    }
                )
            append_rows(SALES_ITEMS, SALES_ITEM_FIELDS, item_rows)
            st.success(f"Saved sale invoice {inum.strip()} (₹{grand:.2f}).")
            st.session_state["sale_lines"] = [_blank_line(), _blank_line(), _blank_line()]

# --- Add purchase ---
elif page == "Add purchase":
    st.header("Add purchase invoice")
    c1, c2, c3 = st.columns(3)
    inum = c1.text_input("Supplier invoice no.", value="")
    idt_date = c2.date_input("Invoice date", value=date.today(), format="DD/MM/YYYY", key="purchase_idt")
    pos = c3.text_input("Place of supply", value=DEFAULT_POS, key="p_pos")
    supplier_name = st.text_input("Supplier name")
    supplier_gstin = st.text_input("Supplier GSTIN")
    supplier_addr = st.text_input("Supplier address")
    c4, c5, c6 = st.columns(3)
    inv_typ = c4.selectbox("Invoice type", ["R"], index=0, key="p_typ")
    rchrg = c5.selectbox("Reverse charge", ["N", "Y"], index=0, key="p_rchrg")
    round_off = c6.number_input("Round-off", value=0.0, step=0.01, format="%.2f", key="p_ro")

    lines = _render_line_editor("purchase_lines")
    _, _, _, _, grand = _totals_panel(lines, round_off)

    if st.button("Save purchase", type="primary"):
        idt = _format_idt(idt_date)
        if not inum.strip():
            st.error("Invoice no. is required.")
        elif _invoice_exists(PURCHASES, inum.strip()):
            st.error(f"Purchase invoice {inum} already exists.")
        elif not any(l["item_name"].strip() for l in lines):
            st.error("Add at least one line item with a name.")
        else:
            append_rows(
                PURCHASES,
                PURCHASE_FIELDS,
                [
                    {
                        "inum": inum.strip(),
                        "idt": idt,
                        "supplier_name": supplier_name.strip(),
                        "supplier_gstin": supplier_gstin.strip().upper(),
                        "supplier_addr": supplier_addr.strip(),
                        "pos": pos.strip() or DEFAULT_POS,
                        "inv_typ": inv_typ,
                        "rchrg": rchrg,
                        "round_off": f"{money(round_off):.2f}",
                        "grand_total": f"{grand:.2f}",
                    }
                ],
            )
            item_rows = []
            for i, line in enumerate(lines, start=1):
                if not line["item_name"].strip():
                    continue
                item_rows.append(
                    {
                        "inum": inum.strip(),
                        "line_num": str(i),
                        "item_name": line["item_name"].strip(),
                        "hsn": line["hsn"].strip(),
                        "qty": f"{money(line['qty']):.2f}",
                        "uqc": line["uqc"],
                        "rate": f"{money(line['rate']):.2f}",
                        "gst_pct": f"{money(line['gst_pct']):.2f}",
                        "taxable": f"{line['taxable']:.2f}",
                        "gst_amt": f"{line['gst_amt']:.2f}",
                    }
                )
            append_rows(PURCHASE_ITEMS, PURCHASE_ITEM_FIELDS, item_rows)
            st.success(f"Saved purchase {inum.strip()} (₹{grand:.2f}).")
            st.session_state["purchase_lines"] = [_blank_line(), _blank_line(), _blank_line()]

# --- Buyers ---
elif page == "Buyers":
    st.header("Buyers")
    st.caption("Saved parties for sales. Phone is for store records only — not exported in GSTR JSON.")

    buyers = read_csv(BUYERS)
    if buyers:
        st.dataframe(pd.DataFrame(buyers), use_container_width=True)
    else:
        st.write("No buyers yet. Add one below, or run `python3 scripts/seed_sample_invoice.py`.")

    st.subheader("Add or edit buyer")
    edit_labels = ["— Add new —"] + [buyer_label(b) for b in buyers]
    edit_pick = st.selectbox("Load existing to edit", edit_labels, key="buyer_edit_pick")

    if edit_pick != st.session_state.get("_buyer_edit_applied"):
        st.session_state["_buyer_edit_applied"] = edit_pick
        if edit_pick == "— Add new —":
            st.session_state["buyer_form_name"] = ""
            st.session_state["buyer_form_gstin"] = ""
            st.session_state["buyer_form_addr"] = ""
            st.session_state["buyer_form_phone"] = ""
            st.session_state["buyer_edit_idx"] = None
        else:
            b = buyers[edit_labels.index(edit_pick) - 1]
            st.session_state["buyer_form_name"] = b.get("buyer_name", "")
            st.session_state["buyer_form_gstin"] = b.get("buyer_gstin", "")
            st.session_state["buyer_form_addr"] = b.get("buyer_addr", "")
            st.session_state["buyer_form_phone"] = b.get("buyer_phone", "")
            st.session_state["buyer_edit_idx"] = edit_labels.index(edit_pick) - 1
        st.rerun()

    for key in ("buyer_form_name", "buyer_form_gstin", "buyer_form_addr", "buyer_form_phone"):
        if key not in st.session_state:
            st.session_state[key] = ""

    name = st.text_input("Buyer name", key="buyer_form_name")
    gstin = st.text_input("Buyer GSTIN", key="buyer_form_gstin")
    addr = st.text_input("Buyer address", key="buyer_form_addr")
    phone = st.text_input("Buyer phone", key="buyer_form_phone")

    bc1, bc2 = st.columns(2)
    if bc1.button("Save buyer", type="primary"):
        if not name.strip():
            st.error("Buyer name is required.")
        else:
            upsert_buyer(name, gstin, addr, phone)
            st.session_state["_buyer_edit_applied"] = None
            st.success(f"Saved buyer {name.strip()}.")
            st.rerun()

    if bc2.button("Delete selected buyer") and st.session_state.get("buyer_edit_idx") is not None:
        idx = st.session_state["buyer_edit_idx"]
        rows = read_csv(BUYERS)
        if 0 <= idx < len(rows):
            removed = rows.pop(idx)
            rewrite_csv(BUYERS, BUYER_FIELDS, rows)
            st.session_state["_buyer_edit_applied"] = None
            st.session_state["buyer_edit_idx"] = None
            st.success(f"Deleted {removed.get('buyer_name', '')}.")
            st.rerun()

# --- List ---
elif page == "List documents":
    st.header("Saved documents")
    tab_s, tab_p = st.tabs(["Sales", "Purchases"])
    with tab_s:
        sales = read_csv(SALES_INVOICES)
        items = read_csv(SALES_ITEMS)
        if not sales:
            st.write("No sales yet. Seed with `python3 scripts/seed_sample_invoice.py`.")
        else:
            st.dataframe(pd.DataFrame(sales), use_container_width=True)
            pick = st.selectbox("View items for invoice", [s["inum"] for s in sales])
            st.dataframe(
                pd.DataFrame([i for i in items if i["inum"] == pick]),
                use_container_width=True,
            )
    with tab_p:
        purchases = read_csv(PURCHASES)
        pitems = read_csv(PURCHASE_ITEMS)
        if not purchases:
            st.write("No purchases yet.")
        else:
            st.dataframe(pd.DataFrame(purchases), use_container_width=True)
            pick = st.selectbox("View items for purchase", [p["inum"] for p in purchases])
            st.dataframe(
                pd.DataFrame([i for i in pitems if i["inum"] == pick]),
                use_container_width=True,
            )

# --- Export GSTR ---
else:
    st.header("Export GSTR JSON")
    st.write("Builds outward-supply JSON matching the sample shape (`gstin`, `fp`, `version`, `b2b`, `hsn`, `doc_issue`).")
    fp = st.text_input("Filing period `fp` (MMYYYY)", value="082026")
    gstin = st.text_input("Seller GSTIN", value=SELLER_GSTIN)
    if st.button("Generate JSON", type="primary"):
        if len(fp.strip()) != 6 or not fp.strip().isdigit():
            st.error("fp must be 6 digits MMYYYY, e.g. 082026 for Aug 2026.")
        else:
            payload = build_gstr(fp.strip(), gstin=gstin.strip())
            text = json.dumps(payload, indent=2)
            st.code(text, language="json")
            st.download_button(
                "Download JSON",
                data=text,
                file_name=f"gstr_{gstin.strip()}_{fp.strip()}.json",
                mime="application/json",
            )
            n_b2b = sum(len(b["inv"]) for b in payload["b2b"])
            st.success(f"Exported {n_b2b} B2B invoice(s) for fp={fp.strip()}.")
