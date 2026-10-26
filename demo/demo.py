"""Run the verification layer against a fictional PO under simulated OCR failures.

    python demo/make_sample.py     # once: creates sample_po.pdf + template.json
    python demo/demo.py

The text nodes come from the PDF's embedded text (a stand-in for PaddleOCR output, so the
demo needs no OCR install). Failures are injected into those nodes the way real OCR fails.
"""
import copy
import json
import os
import re
import sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import qty_guard  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

qty_guard.TOTAL_CHECK_TEMPLATES.add("DEMO")      # opt-in per template, as in the real tool


# ---------------------------------------------------------------- "OCR" nodes
def load_nodes(pdf_path):
    page = fitz.open(pdf_path)[0]
    w, h = page.rect.width, page.rect.height
    nodes = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                x0, y0, x1, y1 = sp["bbox"]
                nodes.append({"txt": sp["text"], "box": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                              "cx": (x0 + x1) / 2 / w, "cy": (y0 + y1) / 2 / h})
    return nodes, w, h


def refresh(n, w, h):
    xs = [p[0] for p in n["box"]]; ys = [p[1] for p in n["box"]]
    n["cx"], n["cy"] = (min(xs) + max(xs)) / 2 / w, (min(ys) + max(ys)) / 2 / h


# ------------------------------------------------- engine: read ONLY from zones
def in_zone(n, z):
    return min(z["x1"], z["x2"]) <= n["cx"] <= max(z["x1"], z["x2"]) and \
           min(z["y1"], z["y2"]) <= n["cy"] <= max(z["y1"], z["y2"])


def zone(tpl, field):
    return next(z for z in tpl["zones"] if z["field"] == field)


def extract_rows(nodes, tpl):
    items = sorted([n for n in nodes if in_zone(n, zone(tpl, "item_code"))], key=lambda n: n["cy"])
    rows = []
    for it in items:
        same = lambda z: [n for n in nodes if in_zone(n, zone(tpl, z)) and abs(n["cy"] - it["cy"]) < 0.01]
        q, d = same("qty"), same("description")
        rows.append({"item_code": it["txt"], "qty": q[0]["txt"] if q else "Unknown",
                     "description": d[0]["txt"] if d else "",
                     "boxes": {"item_code": it["box"], "description": d[0]["box"] if d else None,
                               "qty": q[0]["box"] if q else None}})
    po = [n["txt"] for n in nodes if in_zone(n, zone(tpl, "po_number"))]
    return (po[0] if po else "Unknown"), rows


# ------------------------------------------------------------ failure scenarios
def sc_clean(nodes, rows, w, h):
    return "Clean scan"


def sc_digit(nodes, rows, w, h):
    for n in nodes:                      # OCR reads '90' as '96' (a digit that still looks valid)
        if n["txt"] == "90":
            n["txt"] = "96"
    return "OCR misreads a digit: qty 90 -> 96"


def sc_row_lost(nodes, rows, w, h):
    gone = [n for n in nodes if abs(n["cy"] - (300 + 2 * 24 - 4) / h) < 0.012]
    for n in gone:
        nodes.remove(n)
    return "OCR misses an entire line (row 3 vanishes)"


def sc_dot(nodes, rows, w, h):
    for n in nodes:                      # decimal point lost in the amount column: 912.00 -> 91200
        if n["txt"] == "912.00":
            n["txt"] = "91200"
    for n in nodes:
        if n["txt"] == "24":
            n["txt"] = "2400"            # and the same glitch inflates the qty
    return "Quantity inflated x100 (24 -> 2400)"


def sc_wrong_column(nodes, rows, w, h):
    return "Engine bug: qty read from the unit-price column"


SCENARIOS = [sc_clean, sc_digit, sc_row_lost, sc_dot, sc_wrong_column]


# ------------------------------------------------------------------------ run
TRUE_QTY = ("90", "24", "150", "6")


def load_all():
    pdf = os.path.join(HERE, "sample_po.pdf")
    if not os.path.exists(pdf):
        import make_sample
        make_sample.build()
    with open(os.path.join(HERE, "template.json"), encoding="utf-8") as f:
        tpl = json.load(f)
    base, w, h = load_nodes(pdf)
    return pdf, tpl, base, w, h


def run_scenario(sc, tpl, base, w, h):
    """Inject one failure, extract rows from the zones, run the guard. Returns a result dict."""
    nodes = copy.deepcopy(base)
    title = sc(nodes, None, w, h)
    for n in nodes:
        refresh(n, w, h)
    po, rows = extract_rows(nodes, tpl)
    if sc is sc_wrong_column:
        for r in rows:                              # simulate the engine reading the neighbouring column
            yc = (r["boxes"]["item_code"][0][1] + r["boxes"]["item_code"][2][1]) / 2 / h
            near = [n for n in nodes if abs(n["cy"] - yc) < 0.01 and 425 / w < n["cx"] < 470 / w]
            if near:
                r["qty"] = near[0]["txt"]; r["boxes"]["qty"] = near[0]["box"]
    warns = qty_guard.check_page(rows, nodes, tpl, w, h)
    silent = any(r["qty"] not in TRUE_QTY for r in rows) and         all(r.get("qty_check", {}).get("ok") for r in rows) and not warns
    return {"title": title, "po": po, "rows": rows, "warnings": warns, "silent": silent, "nodes": nodes}


def main():
    pdf, tpl, base, w, h = load_all()
    print("Fail-loud verification demo (fictional PO, 4 line items, true qty 90/24/150/6)\n")
    for sc in SCENARIOS:
        res = run_scenario(sc, tpl, base, w, h)
        print(f"== {res['title']}")
        print(f"   PO {res['po']}")
        for r in res["rows"]:
            c = r.get("qty_check", {})
            tag = "OK  " if c.get("ok") else "FLAG"
            print(f"   [{tag}] {r['item_code']:<8} qty={r['qty']:<7} {c.get('reason', '')[:110]}")
        for wmsg in res["warnings"]:
            print(f"   [PAGE] {wmsg[:140]}")
        print("   -> SILENT WRONG VALUE!" if res["silent"] else
              "   -> all green, values correct" if sc is sc_clean else "   -> nothing wrong passes silently")
        print()


if __name__ == "__main__":
    main()
