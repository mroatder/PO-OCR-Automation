"""Generate a fictional purchase-order PDF and the matching zone template.

Everything here is made up (company, items, prices). Output: sample_po.pdf, template.json
"""
import json
import os

import fitz  # PyMuPDF

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 595.0, 842.0

# column left edges (pt)
COL = {"no": 50, "item": 85, "desc": 175, "qty": 370, "price": 430, "amount": 500}
ROW_Y0, PITCH = 300.0, 24.0
ITEMS = [
    ("AX-1001", "Sealant 50ml", 90, 12.50),
    ("AX-1002", "Adhesive 1kg", 24, 38.00),
    ("BX-2005", "Cleaner 500ml", 150, 4.20),
    ("CX-3010", "Primer 20L", 6, 210.00),
]


def build():
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    t = lambda x, y, s, size=10: page.insert_text((x, y), s, fontsize=size, fontname="helv")

    t(50, 60, "ACME Industrial Co., Ltd.", 14)
    t(50, 78, "123 Example Road, Sample City", 9)
    t(400, 60, "PURCHASE ORDER", 14)
    t(400, 100, "PO No:", 10)
    t(445, 100, "PO260123", 10)
    t(400, 116, "Date: 15 Oct 2026", 10)

    hy = ROW_Y0 - 30
    for k, label in [("no", "No."), ("item", "Item Code"), ("desc", "Description"),
                     ("qty", "Qty"), ("price", "Unit Price"), ("amount", "Amount")]:
        t(COL[k], hy, label)
    page.draw_line((50, hy + 6), (550, hy + 6))

    total_q = total_a = 0
    for i, (code, desc, qty, price) in enumerate(ITEMS):
        y = ROW_Y0 + i * PITCH
        amt = qty * price
        total_q += qty
        total_a += amt
        t(COL["no"], y, str(i + 1))
        t(COL["item"], y, code)
        t(COL["desc"], y, desc)
        t(COL["qty"], y, f"{qty}")
        t(COL["price"], y, f"{price:,.2f}")
        t(COL["amount"], y, f"{amt:,.2f}")

    ty = ROW_Y0 + len(ITEMS) * PITCH + 10
    page.draw_line((50, ty - 12), (550, ty - 12))
    t(COL["desc"], ty, "Total")
    t(COL["qty"], ty, f"{total_q}")
    t(COL["amount"], ty, f"{total_a:,.2f}")
    t(50, 780, "Authorized signature: ________________", 9)

    doc.save(os.path.join(HERE, "sample_po.pdf"))

    # zones the "user" marked once on this sample (normalized 0-1)
    y1 = (ROW_Y0 - 14) / H
    y2 = (ROW_Y0 + (len(ITEMS) - 1) * PITCH + 6) / H
    zone = lambda f, xa, xb, ya=y1, yb=y2: {"field": f, "x1": xa / W, "x2": xb / W, "y1": ya, "y2": yb}
    tpl = {
        "template_name": "DEMO",
        "zones": [
            zone("item_code", COL["item"] - 4, COL["desc"] - 6),
            zone("description", COL["desc"] - 4, COL["qty"] - 10),
            zone("qty", COL["qty"] - 6, COL["price"] - 8),
            zone("po_number", 440, 520, 90 / H, 106 / H),
        ],
    }
    with open(os.path.join(HERE, "template.json"), "w", encoding="utf-8") as f:
        json.dump(tpl, f, indent=2)
    print("wrote sample_po.pdf and template.json")


if __name__ == "__main__":
    build()
