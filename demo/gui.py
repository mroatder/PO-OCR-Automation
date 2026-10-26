"""Browser-based demo of the verification screen (standard library + PyMuPDF only).

    python demo/gui.py            # then open http://127.0.0.1:8765

Left: the page as read (injected OCR failures are visible), with boxes around each quantity.
Right: extracted rows with the guard's verdict. A scenario picker injects the failure.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import demo  # noqa: E402

PDF, TPL, BASE, W, H = demo.load_all()
ZOOM = 1.6

# guard messages are Thai (the tool's working language); show English in the demo UI
_TR = [
    (r"Qty (\S+) × ราคาต่อหน่วย ไม่เท่ากับยอดเงินในบรรทัด \(ยอด ÷ ราคา = ([\d.,]+)\).*",
     r"Qty \1 x unit price does not equal the line amount (amount / price = \2) - OCR may have misread a digit"),
    (r"ไม่พบเลข (\S+) ในคอลัมน์ Quantity.*", r"\1 was not found in the Quantity column - possibly read from another column"),
    (r"เลข (\S+) ในคอลัมน์ Quantity ไม่ได้อยู่บรรทัดเดียวกับ.*", r"\1 is in the Quantity column but not on this item's line"),
    (r"อ่านจำนวนไม่ได้.*", "Quantity could not be read"),
    (r"พบจำนวน '([^']+)' ในคอลัมน์ Quantity ที่ไม่มีรายการใดใช้.*",
     r"Found '\1' in the Quantity column that no item uses - a row may be missing"),
    (r"ยอดรวมท้ายตาราง \(([^)]*)\) ไม่ตรงกับผลรวมของรายการที่อ่านได้ \(qty รวม ([\d.,]+)(?: / ยอดเงินรวม ([\d.,]+))?\).*",
     r"Table total (\1) does not match the rows read (qty \2, amount \3) - a row may be missing or misread; check the document"),
]


def en(msg):
    for pat, rep in _TR:
        if re.match(pat, msg):
            return re.sub(pat, rep, msg).replace(", amount )", ")")
    return msg


def render_png(i):
    res = demo.run_scenario(demo.SCENARIOS[i], TPL, BASE, W, H)
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    for n in res["nodes"]:
        xs = [p[0] for p in n["box"]]; ys = [p[1] for p in n["box"]]
        size = max(8, (max(ys) - min(ys)) / 1.35)
        page.insert_text((min(xs), max(ys) - 3.5), n["txt"], fontsize=size, fontname="helv")
    page.draw_line((50, 276), (550, 276), width=0.6)
    for r in res["rows"]:
        ok = r.get("qty_check", {}).get("ok")
        color = (0.1, 0.6, 0.25) if ok else (0.85, 0.15, 0.15)
        q = r["boxes"].get("qty")
        if q:
            xs = [p[0] for p in q]; ys = [p[1] for p in q]
            rect = fitz.Rect(min(xs) - 3, min(ys) - 1, max(xs) + 3, max(ys) + 1)
            page.draw_rect(rect, color=color, fill=color, fill_opacity=0.12, width=1.4)
    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
    return pix.tobytes("png")


def scenario_json(i):
    res = demo.run_scenario(demo.SCENARIOS[i], TPL, BASE, W, H)
    rows = [{"item": r["item_code"], "desc": r["description"], "qty": r["qty"],
             "ok": bool(r.get("qty_check", {}).get("ok")),
             "reason": en(r.get("qty_check", {}).get("reason", ""))} for r in res["rows"]]
    return {"title": res["title"], "po": res["po"], "rows": rows,
            "warnings": [en(w) for w in res["warnings"]], "silent": res["silent"]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        m = re.fullmatch(r"/(page|data)/(\d+)", path)
        if path == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self._send(200, "text/html; charset=utf-8", f.read())
        elif m and int(m.group(2)) < len(demo.SCENARIOS):
            i = int(m.group(2))
            if m.group(1) == "page":
                self._send(200, "image/png", render_png(i))
            else:
                self._send(200, "application/json; charset=utf-8", json.dumps(scenario_json(i)).encode("utf-8"))
        elif path == "/scenarios":
            titles = [demo.run_scenario(s, TPL, BASE, W, H)["title"] for s in demo.SCENARIOS]
            self._send(200, "application/json", json.dumps(titles).encode("utf-8"))
        else:
            self._send(404, "text/plain", b"not found")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"Open http://127.0.0.1:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
