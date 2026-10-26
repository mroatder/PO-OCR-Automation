# 🛡️ QTY GUARD - ตรวจผลลัพธ์ของทุก Engine หลังดึงข้อมูลเสร็จ (ไม่แก้ค่าที่ Engine อ่านได้ แค่ติดธงเตือน)
#
# ตรวจ 1 (ราย item): จำนวน (qty) ที่ได้ ต้องมีอยู่จริงในคอลัมน์ Quantity (zone "qty" ของ Template) ในแนวบรรทัดเดียวกับ item
#                   → ถ้าไม่เจอ แปลว่าอาจหยิบตัวเลขมาจากที่อื่น (เช่น KG ใน Description, ราคา, บรรทัดข้างเคียง)
# ตรวจ 2 (รายหน้า): ในคอลัมน์ Quantity มีตัวเลขหน้าตาแบบเดียวกับ qty ที่อ่านได้ แต่ไม่มี item ไหนใช้
#                   → อาจมีรายการตกหล่น
#
# ผลลัพธ์:  row["qty_check"] = {"ok": bool, "reason": str}
#           check_page(...) คืนรายการข้อความเตือนของหน้านั้น (ใส่ใน pages.json → หน้าตรวจสอบแสดง ⚠️)
import re

COL_TOL = 0.03      # เผื่อขอบซ้าย/ขวาของคอลัมน์ Quantity (สัดส่วนความกว้างหน้า)
ROW_TOL = 0.035     # เผื่อแนวตั้งรอบบรรทัดของ item (สัดส่วนความสูงหน้า)

_NUM_TOKEN = re.compile(r'\d(?:[\d,.\' ]*\d)?')


def _fix_ocr_digits(txt):
    """O→0, I/l/|→1 เฉพาะตัวที่อยู่ติดกับตัวเลข (OCR สับสนบ่อย)"""
    t = str(txt)
    for _ in range(2):
        t = re.sub(r'(?<=\d)[Oo]|[Oo](?=\d)', '0', t)
        t = re.sub(r'(?<=\d)[Il|]|[Il|](?=\d)', '1', t)
    return t


def _to_number(tok):
    """แปลงสตริงตัวเลข 1 ก้อนเป็น float - ตัวคั่นตัวสุดท้ายที่ตามด้วย 3 หลักพอดี = หลักพัน นอกนั้นคือจุดทศนิยม
    เช่น '4,000' = 4000, '20.00' = 20, '35.2600' = 35.26 (ราคา 4 ตำแหน่ง), '1.234,5' = 1234.5"""
    tok = tok.strip().replace("'", ",")
    if not tok:
        return None
    seps = [m.start() for m in re.finditer(r'[,. ]', tok)]
    if seps:
        last = seps[-1]
        tail = tok[last + 1:]
        if tok[last] in ",." and tail.isdigit() and len(tail) != 3:
            int_part = re.sub(r'[,. ]', '', tok[:last])
            tok = f"{int_part}.{tail}"
        else:
            tok = re.sub(r'[,. ]', '', tok)
    try:
        return float(tok)
    except ValueError:
        return None


def parse_qty(value):
    """ค่า qty จาก Engine → float (None ถ้าอ่านไม่ได้)"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    toks = _NUM_TOKEN.findall(_fix_ocr_digits(value))
    if not toks:
        return None
    return _to_number(max(toks, key=len))


def numbers_in_text(txt):
    """ทุกตัวเลขที่เป็นไปได้ในข้อความ OCR 1 ก้อน (รวมกรณีช่องว่างคั่นหลักพัน เช่น '4 000' และกรณีเลขหลายตัวติดกัน)"""
    out = set()
    for tok in _NUM_TOKEN.findall(_fix_ocr_digits(txt)):
        n = _to_number(tok)
        if n is not None:
            out.add(n)
        if " " in tok:                       # "10 20.00" อาจเป็นเลข 2 ตัว
            for part in tok.split():
                n = _to_number(part)
                if n is not None:
                    out.add(n)
        for part in re.split(r"[']", tok):   # 1'000 แบบสวิส
            n = _to_number(part)
            if n is not None:
                out.add(n)
        m = re.fullmatch(r'(\d[\d,. ]*?)[,.](\d{3})', tok.strip())
        if m:                                # '200,000' แบบเวียดนาม/ยุโรป = 200 (ทศนิยม 3 ตำแหน่ง)
            try:
                out.add(float(re.sub(r'[,. ]', '', m.group(1)) + "." + m.group(2)))
            except ValueError:
                pass
    return out


def _flatten(box):
    """กล่องได้หลายรูปแบบจากแต่ละ Engine: [[x,y]*4] / [[[x,y]*4], ...] / None"""
    pts = []
    def walk(b):
        if b is None:
            return
        if isinstance(b, (list, tuple)) and len(b) == 2 and all(isinstance(v, (int, float)) for v in b):
            pts.append((float(b[0]), float(b[1])))
        elif isinstance(b, (list, tuple)):
            for x in b:
                walk(x)
    walk(box)
    return pts


def _norm_pts(pts, w, h):
    if not pts:
        return []
    if all(x <= 1.5 and y <= 1.5 for x, y in pts):      # บาง Engine ส่งพิกัดแบบสัดส่วน (0-1) มาแล้ว
        return pts
    return [(x / w, y / h) for x, y in pts]


def _zone(template, field):
    for z in (template or {}).get("zones", []):
        if z.get("field") == field:
            return z
    return None


_MONTHS = r'JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC'
_DATE_RE = re.compile(r"\d\s*[-./' ]?\s*(" + _MONTHS + r")|(" + _MONTHS + r")[A-Z]*\s*[-./' ]?\s*\d|\b\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}\b", re.I)
_DATE_FULL_RE = re.compile(r"\b\d{1,2}\s*[-./' ]\s*(" + _MONTHS + r")[A-Z]*\s*[-./' ]?\s*\d{2,4}\b|\b\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}\b", re.I)
_TOTAL_RE = re.compile(r'TOTAL|合计|合計|小计|總計', re.I)


def _is_sentence(txt):
    """ข้อความยาวที่มีตัวเลขปน (เช่น '30DAYS AFTER INVOICE DATE') ไม่ใช่จำนวนสินค้า - หน่วยของ qty มักสั้น เช่น PCS, UN, KILOGRAM"""
    words = re.findall(r'[A-Za-z]{2,}', str(txt))
    return len(words) >= 3 or sum(len(x) for x in words) > 12


def _strip_dates(txt):
    """ตัดส่วนที่เป็นวันที่ออกก่อนเทียบตัวเลข - qty 20 ต้องไม่ 'เจอ' ใน '20-MAR-26' (คอลัมน์ Quantity/Need By Date ของ 3VTTT)"""
    return _DATE_FULL_RE.sub(" ", str(txt))


def _looks_like_date(txt):
    return bool(_DATE_RE.search(str(txt)))


def _shape(txt):
    """หน้าตาของตัวเลข: (รูปแบบตัวเลขหลัก, มีตัวอักษรนำหน้าไหม, มีหน่วยตามหลังไหม)
    เช่น '4,000 UN' → ('9,9', False, True), '20.00' → ('9.9', False, False), 'ETD18-Apr-25' → ('9', True, True)
    ไม่สนว่าหน่วยสะกดอะไร เพราะ OCR อ่านหน่วยเพี้ยนบ่อย ('PCS' / 'PC' / 'CS')"""
    t = _fix_ocr_digits(txt)
    toks = _NUM_TOKEN.findall(t)
    if not toks:
        return None
    main = max(toks, key=len)
    dec = re.search(r'[,.](\d{1,2})$', main.strip())
    num_shape = f"9.{len(dec.group(1))}" if dec else "9"   # สนแค่จำนวนทศนิยม: '1,000.00' = '40.00' → '9.2', '3,456' = '720' → '9'
    i = t.find(main)
    return num_shape, bool(re.search(r'[A-Za-z]', t[:i])), bool(re.search(r'[A-Za-z]', t[i + len(main):]))


def _row_band(row, w, h):
    """ช่วงแนวตั้งของ item: ใช้กล่อง item_code + description (ไม่ใช้กล่อง qty เพราะอาจผิดเอง)"""
    bx = row.get("boxes") or {}
    pts = []
    for k in ("item_code", "description"):
        pts += _norm_pts(_flatten(bx.get(k)), w, h)
    if not pts:
        pts = _norm_pts(_flatten(bx.get("qty")), w, h)
    if not pts:
        return None
    ys = [p[1] for p in pts]
    return min(ys), max(ys)


def _qty_center(row, w, h):
    pts = _norm_pts(_flatten((row.get("boxes") or {}).get("qty")), w, h)
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def line_values(points, y, line_h, x_min):
    """ตัวเลขในบรรทัดเดียวกันทางขวาของคอลัมน์ qty (ราคา/ยอด) เรียงซ้าย→ขวา - แต่ละก้อนเป็นชุดค่าที่เป็นไปได้
    ('32.150' อาจเป็น 32.15 หรือ 32,150 ขึ้นกับประเทศ) · ข้ามวันที่, ตัวเลขติดหน่วย ('18KG' = ขนาดบรรจุ), รหัสตัวเลขยาว"""
    nodes = sorted([p for p in points if abs(p["cy"] - y) <= line_h and p["cx"] > x_min], key=lambda p: p["cx"])
    out = []
    for p in nodes:
        t = str(p["txt"])
        if _looks_like_date(t) or re.search(r"[A-Za-z]{2,}", t) or (len(re.sub(r"\D", "", t)) >= 8 and not re.search(r"[,.]", t)):
            continue
        vals = {v for v in numbers_in_text(t) if v > 0}
        if vals:
            out.append(vals)
    return out


def price_check(qty, nums):
    """ยอดเงิน (ตัวเลขขวาสุด) = qty × ราคา (ตัวเลขก่อนหน้า) ไหม → ('ok' | 'conflict' | 'na', qty ที่ยอด÷ราคาให้)
    conflict เฉพาะเมื่อไม่มีการตีความไหนเข้ากับ qty และ ยอด ÷ ราคา ลงตัว (ทศนิยม ≤ 2 ตำแหน่ง) - ไม่มีราคา/ยอด = 'na'"""
    if qty is None or len(nums) < 2:
        return "na", None
    amounts, implied = nums[-1], []
    for prices in nums[:-1]:
        for a in prices:
            for b in amounts:
                if a <= 0 or b < a * 0.999:
                    continue
                if abs(qty * a - b) <= max(0.006 * b, 0.02):
                    return "ok", None
                q2 = b / a
                if q2 >= 1 and abs(q2 - round(q2, 2)) <= 1e-6 * q2 and abs(q2 - qty) > 1e-6:
                    implied.append(round(q2, 2))
    if implied:
        return "conflict", min(implied, key=lambda q: abs(q - qty))
    return "na", None


SKEW_WARN_DEG = 1.0   # เอียงเกินนี้ = เตือนทั้งหน้า (ทดสอบแล้ว: เอียง 3° อ่านผิดเกือบทุกแถว, ไฟล์จริง 156 ไฟล์ไม่มีไฟล์ไหนเกิน 1°)


def page_skew(points):
    """มุมเอียงของหน้า (องศา) จากแนวกล่องข้อความยาวๆ - ใช้ค่ากลาง (median) กันกล่องที่ OCR ตีเพี้ยน"""
    import math, statistics
    angs = []
    for p in points:
        b = p.get("box")
        if b is None:
            continue
        wdt, hgt = b[1][0] - b[0][0], b[2][1] - b[1][1]
        if wdt > 4 * max(hgt, 1):
            angs.append(math.degrees(math.atan2(b[1][1] - b[0][1], wdt)))
    return statistics.median(angs) if len(angs) >= 5 else 0.0


SCAN_WARN_CONF = 0.92   # ความมั่นใจ OCR เฉลี่ยของหน้าต่ำกว่านี้ = สแกนไม่ชัด (วัดจากหน้าที่เก็บไว้ 397 หน้า: มัธยฐาน 97.7%, 5% ล่างสุด 95.2%, หน้าสแกนไม่ชัดของ SAMPLE-001 อยู่ 89.5-90.2%)


def scan_quality_warning(points):
    """ข้อความเตือนถ้าทั้งหน้าสแกนไม่ชัด (ค่าเฉลี่ยความมั่นใจของ OCR ทุกก้อนข้อความในหน้า) - ไม่ชัด = อ่านผิดได้ทุกช่อง รวมถึงค่าที่ดูถูกรูปแบบ"""
    confs = [p.get("conf") for p in points if str(p.get("txt", "")).strip() and isinstance(p.get("conf"), (int, float))]
    if len(confs) < 15:
        return None
    avg = sum(confs) / len(confs)
    if avg < SCAN_WARN_CONF:
        return f"สแกนไม่ชัด (ความมั่นใจ OCR เฉลี่ยทั้งหน้า {avg * 100:.0f}%) - อาจอ่านผิดได้ทุกช่อง แม้ค่าที่ได้จะดูถูกรูปแบบ กรุณาตรวจทุกรายการในหน้านี้กับเอกสาร"
    return None


def skew_warning(points):
    """ข้อความเตือนถ้าหน้าเอียงเกินกำหนด (ไม่เอียง = None)"""
    sk = page_skew(points)
    if abs(sk) > SKEW_WARN_DEG:
        return f"กระดาษเอียง {sk:+.1f}° (สแกนเอียง) - ระบบอาจจับคู่ qty/item ผิดบรรทัด กรุณาตรวจทุกรายการในหน้านี้กับเอกสาร"
    return None


# คำหัวคอลัมน์ของตารางสินค้า (จำนวน / สินค้า / ราคา / ยอด) หลายภาษา - ทดสอบกับ 363 หน้า: หน้าที่มีรายการจริงเจอคำเหล่านี้ทุกหน้า
_TABLE_HEADER_RE = re.compile(r"Q'?TY|QUANT|ORDERED|MENGE|AANTAL|CANTIDAD|数量|DESCRIPTION|DESRIPTION|MATERIAL|PRODUCT|ARTICLE|"
                              r"ITEMNO|ITEMCODE|ITEMNAME|COMM\.?NAME|商品|PRICE|RATE|单价|AMOUNT|NETVALUE|金额", re.I)


def has_item_table(points):
    """หน้านี้มีหัวตารางสินค้าไหม - ไม่เจอคำหัวคอลัมน์ใดๆ เลย = หน้าปก / ท้ายเอกสาร / เงื่อนไข (ไม่ต้องเตือนว่าไม่มีรายการ)
    ตั้งใจให้หลวม: ถ้าไม่แน่ใจ ถือว่ามีตาราง (ระบบจะเตือน) ดีกว่าปล่อยหน้าที่มีรายการผ่านไปเงียบๆ"""
    return any(_TABLE_HEADER_RE.search(str(p.get("txt", "")).replace(" ", "")) for p in points)


def _rows_found(rows, nodes):
    """จำนวน item ที่หาเลข qty ของตัวเองเจอในกลุ่มโหนดนี้"""
    n = 0
    for r in rows:
        v = parse_qty(r.get("qty"))
        if v and any(any(abs(x - v) < 1e-6 for x in numbers_in_text(_strip_dates(p["txt"]))) for p in nodes):
            n += 1
    return n


HOLE_RATIO = 1.7   # ช่องว่างแนวตั้งใหญ่กว่าระยะบรรทัดปกติของตารางนี้เกินกี่เท่าถึงเตือน


def blank_hole_warnings(rows, points, w, h):
    """ช่องว่างผิดปกติระหว่างรายการ: ระยะระหว่างบรรทัดข้อความในตาราง (ช่วง item แรก→สุดท้าย) ห่างกว่าปกติของตารางนี้มาก
    = บรรทัดหนึ่งอาจหายไปจาก OCR ทั้งบรรทัด (รวมตัวเลข qty ด้วย ตรวจ 2 ของ check_page จึงมองไม่เห็น)
    เทียบกับระยะบรรทัดปกติ "ของหน้านี้เอง" (median) จึงไม่ขึ้นกับฟอร์ม · มีข้อความแทรก (comment) = ไม่ใช่ช่องว่าง ไม่เตือน"""
    import statistics
    if len(rows) < 2 or not w or not h:
        return []
    mids, xs = [], []
    for r in rows:
        band = _row_band(r, w, h)
        if not band:
            return []
        mids.append((band[0] + band[1]) / 2)
        bx = r.get("boxes") or {}
        for k in ("item_code", "description", "qty"):
            xs += [p[0] for p in _norm_pts(_flatten(bx.get(k)), w, h)]
    if not xs:
        return []
    xa, xb, y0, y1 = min(xs), max(xs), min(mids), max(mids)
    hts = sorted(abs(p["box"][2][1] - p["box"][0][1]) / h for p in points if p.get("box") is not None)
    line_h = hts[len(hts) // 2] if hts else 0.01
    ys = sorted(p["cy"] for p in points if xa <= p["cx"] <= xb and y0 <= p["cy"] <= y1)
    lines = []                                   # รวมโหนดที่อยู่บรรทัดเดียวกันเป็นหนึ่งบรรทัด
    for y in ys:
        if not lines or y - lines[-1] > line_h * 0.5:
            lines.append(y)
    diffs = [b - a for a, b in zip(lines, lines[1:])]
    if len(diffs) < 3:
        return []
    med = statistics.median(diffs)
    out = []
    for a, b in zip(lines, lines[1:]):
        if b - a > med * HOLE_RATIO and b - a > line_h * 1.5:
            out.append(f"พบช่องว่างผิดปกติระหว่างบรรทัดในตารางสินค้า (ที่ตำแหน่ง ~{(a + b) / 2 * 100:.0f}% ของความสูงหน้า) - อาจมีรายการตกหล่นที่ OCR อ่านไม่ได้ ตรวจกับเอกสารจริง")
    return out


# Opt-in: enable only for templates verified on real files with zero false warnings
TOTAL_CHECK_TEMPLATES = set()
TOTAL_WINDOW = 0.40     # บรรทัดรวมต้องอยู่ใต้รายการสุดท้ายไม่เกินกี่เท่าของความสูงหน้า 
_TOTAL_LABEL_RE = re.compile(r"(^\s*(sub\s*)?total)|(^\s*sum\s*[:.]?)|(total\s*(amount|usd|value|po))|(net\s*amount)|(grand\s*total)|(^\s*amount\s*$)|(^\s*q.?ty\s*$)", re.I)


def total_check_warnings(rows, points, w, h):
    """ยอดรวมท้ายตารางในเอกสาร (Sum / Total ...) ต้องเท่ากับ "ผลรวม qty" หรือ "ผลรวมยอดเงินรายแถว" ของรายการที่อ่านได้
    ไม่ตรง = รายการอาจตกหล่นทั้งบรรทัด (OCR ไม่เห็นบรรทัดนั้นเลย ตรวจ 1–2 ของ check_page มองไม่เห็น) หรืออ่านผิด
    ติดธงเท่านั้น · ไม่มีบรรทัดรวม/ไม่มีตัวเลขให้เทียบ/อ่านยอดเงินรายแถวไม่ครบ = ไม่เตือน (ไม่รู้ ไม่ใช่ผิด)"""
    if not rows or not w or not h:
        return []
    bands = [_row_band(r, w, h) for r in rows]
    if any(b is None for b in bands):
        return []
    last = max(b[1] for b in bands)
    hts = sorted(abs(p["box"][2][1] - p["box"][0][1]) / h for p in points if p.get("box") is not None)
    lh = (hts[len(hts) // 2] if hts else 0.01) * 0.8
    labs = sorted([p for p in points if p["cy"] > last and p["cy"] - last < TOTAL_WINDOW and len(str(p["txt"])) < 45
                   and _TOTAL_LABEL_RE.search(str(p["txt"]))], key=lambda p: p["cy"])
    if not labs:
        return []
    nums = set()
    for lab in labs[:3]:
        for p in points:
            if p is not lab and abs(p["cy"] - lab["cy"]) <= lh and p["cx"] > lab["cx"] - 0.02:
                nums |= {v for v in numbers_in_text(str(p["txt"])) if v > 0}
    if not nums:
        return []
    sum_qty = sum(parse_qty(r.get("qty")) or 0 for r in rows)
    amt, amt_ok = 0.0, True
    for r in rows:
        qc = _qty_center(r, w, h)
        lv = line_values(points, qc[1], lh, qc[0]) if qc else []
        if len(lv) < 2:      # ต้องมีทั้งราคาและยอดเงิน - มีตัวเดียว (ยอดเงินอ่านไม่ได้) = ไม่เอามารวม ไม่งั้นเตือนผิด
            amt_ok = False
            continue
        amt += max(lv[-1])

    def hit(target):
        return any(abs(n - target) <= max(0.005 * n, 0.02) for n in nums)

    if hit(sum_qty) or not amt_ok or hit(amt):
        return []       # ตรงกัน หรือ อ่านยอดเงินรายแถวไม่ครบ (เทียบยอดเงินไม่ได้) = ไม่รู้ ไม่เตือน
    shown = ", ".join(f"{n:g}" for n in sorted(nums)[:4])
    return [f"ยอดรวมท้ายตาราง ({shown}) ไม่ตรงกับผลรวมของรายการที่อ่านได้ (qty รวม {sum_qty:g}" + (f" / ยอดเงินรวม {amt:g}" if amt_ok else "")
            + ") - อาจมีรายการตกหล่นหรืออ่านผิด ตรวจกับเอกสาร"]


ROW_NO_TEMPLATES = set()  # opt-in, same rule as above     # เปิดเฉพาะ Template ที่มีคอลัมน์ 'No.' เรียง 1,2,3… และทดสอบกับไฟล์จริงแล้วเตือนผิด 0
_ROW_NO_HEAD_RE = re.compile(r"^NO\.?$")
_ROW_NO_VAL_RE = re.compile(r"^\W*(\d{1,3})\W*$")      # ทนเครื่องหมายแปลกปลอมที่ OCR ติดมา เช่น '2 *'


def row_number_warnings(rows, points, w, h):
    """เลขลำดับแถวในคอลัมน์ 'No.' ต้องเรียงต่อกัน (1,2,3…) · หน้าแรกต้องเริ่มที่ 1
    ขาดเลขกลางลำดับ/หน้าแรกไม่เริ่มที่ 1 = บรรทัดหนึ่งอาจหายจาก OCR ทั้งบรรทัด (เลขลำดับหายไปพร้อมบรรทัด) · ติดธงเท่านั้น
    จับไม่ได้: แถวสุดท้ายหาย (ลำดับยังเรียงต่อ) · ไม่เจอหัวคอลัมน์ 'No.' หรือเจอเลขน้อยกว่า 2 ตัว = ไม่เตือน"""
    if not rows or not w or not h:
        return []
    bands = [_row_band(r, w, h) for r in rows]
    if any(b is None for b in bands):
        return []
    top, bot = min(b[0] for b in bands), max(b[1] for b in bands)
    heads = [p for p in points if _ROW_NO_HEAD_RE.match(str(p["txt"]).strip().upper().replace(" ", "")) and p["cy"] < top and top - p["cy"] < 0.2]
    if not heads:
        return []
    head = max(heads, key=lambda p: p["cy"])          # หัวคอลัมน์ที่อยู่ใกล้รายการแรกที่สุด
    seq = []
    for p in sorted(points, key=lambda p: p["cy"]):
        m = _ROW_NO_VAL_RE.match(str(p["txt"]))
        if m and abs(p["cx"] - head["cx"]) <= 0.025 and head["cy"] < p["cy"] <= bot + 0.01:
            seq.append(int(m.group(1)))
    if len(seq) < 2:
        return []
    out = []
    gaps = [(a, b) for a, b in zip(seq, seq[1:]) if b != a + 1]
    if gaps:
        out.append("เลขลำดับแถวไม่ต่อเนื่อง (" + ", ".join(str(n) for n in seq) + ") - อาจมีรายการตกหล่นที่ OCR อ่านไม่ได้ ตรวจกับเอกสาร")
    elif seq[0] != 1 and str((rows[0].get("page_image") or "")).endswith("_p1.png"):
        out.append("เลขลำดับแถวหน้าแรกไม่เริ่มที่ 1 (" + ", ".join(str(n) for n in seq) + ") - อาจมีรายการแรกตกหล่นที่ OCR อ่านไม่ได้ ตรวจกับเอกสาร")
    return out


def check_page(rows, points, template, w, h, raw_template=None):
    """ตรวจทุก item ในหน้า (เขียนผลลง row['qty_check']) และคืนข้อความเตือนระดับหน้า
    raw_template = Template ก่อนปรับพิกัด (ใช้แทนเมื่อการปรับพิกัดเพี้ยน ทำให้ zone qty ไม่ทับคอลัมน์จริง)"""
    warnings = []
    qz = _zone(template, "qty")
    if not rows:
        return warnings
    if not qz:
        for r in rows:
            r["qty_check"] = {"ok": True, "reason": "ไม่มี zone qty ใน Template - ข้ามการตรวจ"}
        return warnings

    def column(z):
        a, b = min(z["x1"], z["x2"]) - COL_TOL, max(z["x1"], z["x2"]) + COL_TOL

        def starts_in_column(p):
            # OCR อ่านทั้งแถวติดเป็นก้อนเดียว ('32.00Drum29 Nov2025USD937...') → จุดกึ่งกลางหลุดคอลัมน์ แต่ "จุดเริ่ม" + ตัวเลขแรกอยู่ในคอลัมน์
            if p.get("box") is None or not w or not re.match(r"\s*\d", str(p.get("txt", ""))):
                return False
            xs = [pt[0] / w for pt in p["box"]]
            if max(xs) - min(xs) < 3 * (b - a):
                return False     # เฉพาะก้อนยาวผิดปกติ (ทั้งแถวติดกัน) - กันรหัสสินค้าที่เริ่มชิดขอบคอลัมน์ (3FCJJ)
            return a <= min(xs) <= b

        return [p for p in points if a <= p["cx"] <= b or starts_in_column(p)]

    col_nodes, tpl_used = column(qz), template
    raw_qz = _zone(raw_template, "qty")
    if raw_qz:
        raw_nodes = column(raw_qz)
        if _rows_found(rows, raw_nodes) > _rows_found(rows, col_nodes):
            qz, col_nodes, tpl_used = raw_qz, raw_nodes, raw_template

    # จับคู่ item ↔ ตัวเลขในคอลัมน์ Quantity: ตัวเลข 1 ก้อนเป็นของได้แค่ 1 item (item ที่อยู่ใกล้ที่สุดได้ก่อน)
    # → ถ้า item ไปหยิบ qty ของบรรทัดข้างเคียงมา ก้อนนั้นจะถูก item เจ้าของจริงจองไปแล้ว → item นี้ไม่มีคู่ → เตือน
    pairs, has_cands, unreadable = [], {}, set()
    for i, r in enumerate(rows):
        val = parse_qty(r.get("qty"))
        if val is None or val <= 0:
            unreadable.add(i)
            continue
        band = _row_band(r, w, h)
        qc = _qty_center(r, w, h)      # ตำแหน่งที่ Engine บอกว่าอ่าน qty มา (ช่วยจับคู่ในแบบฟอร์มที่ qty อยู่คนละบรรทัดกับ item code)
        cands = [p for p in col_nodes if any(abs(n - val) < 1e-6 for n in numbers_in_text(_strip_dates(p["txt"])))]
        has_cands[i] = bool(cands)
        for p in cands:
            if band:
                if not (band[0] - ROW_TOL <= p["cy"] <= band[1] + ROW_TOL):
                    continue
                gap = max(band[0] - p["cy"], 0, p["cy"] - band[1])          # 0 = อยู่ในแนวบรรทัดของ item
                if qc:
                    gap = min(gap, abs(p["cy"] - qc[1]))
                pairs.append((gap, abs(p["cy"] - (band[0] + band[1]) / 2), i, p))
            else:
                pairs.append((0, 0, i, p))
    pairs.sort(key=lambda t: (t[0], t[1]))
    owner, claimed = {}, []
    for gap, _, i, p in pairs:
        if i in owner or any(c is p for c in claimed):
            continue
        owner[i] = p; claimed.append(p)
    for i, r in enumerate(rows):
        if i in unreadable:
            r["qty_check"] = {"ok": False, "reason": f"อ่านจำนวนไม่ได้ ('{r.get('qty')}')"}
        elif i in owner:
            r["qty_check"] = {"ok": True, "reason": ""}
        elif has_cands.get(i):
            r["qty_check"] = {"ok": False, "reason": f"เลข {r.get('qty')} ในคอลัมน์ Quantity ไม่ได้อยู่บรรทัดเดียวกับ item นี้ หรือเป็นของรายการอื่น (อาจสลับบรรทัด)"}
        else:
            r["qty_check"] = {"ok": False, "reason": f"ไม่พบเลข {r.get('qty')} ในคอลัมน์ Quantity (อาจอ่านมาจากคอลัมน์อื่น)"}

    # ── ตรวจ 1b: qty × ราคาต่อหน่วย = ยอดเงิน ในบรรทัดเดียวกัน (ENGINE_GUIDE §7 X-3) ──
    # จับกรณี OCR อ่านเลขผิดแต่ยังอยู่ในคอลัมน์ถูก (เช่น '90' อ่านเป็น '06') ที่ตรวจ 1 จับไม่ได้
    # ปิดได้ราย Template ด้วย "cross_check_price": false (เช่น qty เป็น KG แต่ราคาเป็นต่อกระป๋อง)
    if (raw_template or template or {}).get("cross_check_price", True) is not False and owner:
        hts = sorted(abs(p["box"][2][1] - p["box"][0][1]) / h for p in points if p.get("box") is not None)
        lh = hts[len(hts) // 2] * 0.6 if hts else 0.006
        x_right = max(qz["x1"], qz["x2"]) + 0.01
        for i, node in owner.items():
            r = rows[i]
            st, implied = price_check(parse_qty(r.get("qty")), line_values(points, node["cy"], lh, x_right))
            if st == "conflict":
                r["qty_check"] = {"ok": False, "reason": f"Qty {r.get('qty')} × ราคาต่อหน่วย ไม่เท่ากับยอดเงินในบรรทัด (ยอด ÷ ราคา = {implied:g}) - OCR อาจอ่านตัวเลขผิด"}

    # ── ตรวจ 2: ตัวเลขหน้าตาเดียวกับ qty ในคอลัมน์ Quantity ที่ไม่มี item ไหนใช้ → อาจมีรายการตกหล่น ──
    if claimed:
        shapes = {_shape(p["txt"]) for p in claimed}
        heights = sorted(abs(p["box"][2][1] - p["box"][0][1]) / h for p in claimed if p.get("box") is not None)
        line_h = heights[len(heights) // 2] if heights else 0.01
        y_top = min(qz["y1"], qz["y2"]) - 0.01
        th = _zone(tpl_used, "table_header")
        if th:                                   # รายการแรกอาจอยู่สูงกว่า zone qty ที่ mark ไว้ → เริ่มนับจากใต้หัวตาราง
            y_top = min(y_top, max(th["y1"], th["y2"]) + 0.003)
        first_y = min(c["cy"] for c in claimed)
        labels = [p["cy"] for p in col_nodes if p["cy"] < first_y and not re.search(r'\d', str(p["txt"]))]
        if labels:                               # หัวคอลัมน์จริงในหน้า (เช่น 'QTY') อยู่เหนือรายการแรก → นับตั้งแต่ใต้หัวคอลัมน์
            y_top = min(y_top, max(labels) + 0.003)
        y_bot = max(qz["y1"], qz["y2"]) + 0.01
        last_y = max(c["cy"] for c in claimed)
        ys = sorted(c["cy"] for c in claimed)
        gaps = sorted(b - a for a, b in zip(ys, ys[1:]) if b - a > line_h * 0.5)
        pitch = gaps[len(gaps) // 2] if gaps else line_h * 1.5
        y_bot = max(y_bot, last_y + pitch * 2.5)   # ตารางยาวเกิน zone ที่ mark ไว้ → ดูต่อใต้รายการสุดท้ายอีก ~2 บรรทัด
        # หยุดที่บรรทัด Total ใต้ตาราง (ส่วนท้าย/ลายเซ็น/ตราประทับไม่ใช่รายการสินค้า)
        totals = [p["cy"] for p in points if p["cy"] > last_y and _TOTAL_RE.search(str(p["txt"]))]
        if totals:
            y_bot = min(y_bot, min(totals))
        page_sum = sum(parse_qty(r.get("qty")) or 0 for r in rows if r.get("qty_check", {}).get("ok"))
        claimed_ids = {id(p) for p in claimed}
        for p in col_nodes:
            if id(p) in claimed_ids or not (y_top <= p["cy"] <= y_bot):
                continue
            sp = _shape(p["txt"])
            if _looks_like_date(p["txt"]) or _is_sentence(p["txt"]) or not sp:
                continue
            # ต้องหน้าตาเหมือน qty ที่อ่านได้: ทศนิยม + ตัวอักษรนำหน้าต้องตรง / หน่วยท้ายต้องตรงเมื่อเป็นเลขจำนวนเต็ม
            # (เลขมีทศนิยมโดดเด่นพอ ไม่ต้องสนหน่วย เช่น '16.00Drum' กับ '96.00')
            if not any(sp[0] == s0 and sp[1] == s1 and (sp[2] == s2 or sp[0] != "9") for s0, s1, s2 in shapes):
                continue
            nums = [n for n in numbers_in_text(p["txt"]) if n > 0]
            if not nums:
                continue
            if any(abs(p["cy"] - c["cy"]) < line_h * 0.8 for c in claimed):
                continue     # บรรทัดเดียวกับ item ที่อ่านได้แล้ว
            if p["cy"] > last_y and any(abs(n - page_sum) < 0.01 for n in nums):
                continue     # บรรทัดยอดรวม qty ใต้ตาราง (= ผลรวม qty ของหน้านี้)
            warnings.append(f"พบจำนวน '{p['txt']}' ในคอลัมน์ Quantity ที่ไม่มีรายการใดใช้ - อาจมีรายการตกหล่น")
    try:
        warnings += blank_hole_warnings(rows, points, w, h)
    except Exception:
        pass     # ตัวตรวจเสริมล้มเหลวต้องไม่กระทบการอ่านค่า
    try:
        if str((template or {}).get("template_name", "")).upper() in TOTAL_CHECK_TEMPLATES:
            warnings += total_check_warnings(rows, points, w, h)
        if str((template or {}).get("template_name", "")).upper() in ROW_NO_TEMPLATES:
            warnings += row_number_warnings(rows, points, w, h)
    except Exception:
        pass
    return warnings


ITEM_CONF_MIN = 0.90   # ค่าความมั่นใจ OCR ของ node รหัสสินค้า ต่ำกว่านี้ = ให้คนตรวจกับเอกสาร (ทดสอบ 652 แถวที่ตรง Master: ติดธง 5 แถว < 1%)


def item_confidence_check(rows, points, threshold=ITEM_CONF_MIN):
    """ติดธงรายการที่ OCR ไม่มั่นใจในรหัสสินค้า - แม้รหัสนั้นจะบังเอิญตรง Master (เสี่ยงอ่านผิดเป็นอีกรหัสที่มีจริง)
    เขียนผลลง row['item_check'] = {"ok": False, "conf": float, "reason": str} เฉพาะแถวที่ติดธง · ไม่แก้ item_code
    เทียบเฉพาะ node ที่ข้อความตรงกับรหัสทั้งก้อน (ไม่ตรง = ไม่รู้ว่า node ไหน → ไม่ติดธง) · คืนจำนวนแถวที่ติดธง"""
    flagged = 0
    norm = lambda t: re.sub(r"\s+", "", str(t or "")).upper()
    for r in rows:
        code = norm(r.get("item_code"))
        if len(code) < 5 or code in ("UNKNOWN", "NONE"):
            continue
        confs = [float(p["conf"]) for p in points
                 if isinstance(p.get("conf"), (int, float)) and norm(p.get("txt")) == code]
        if not confs:
            continue
        c = min(confs)
        if c < threshold:
            r["item_check"] = {"ok": False, "conf": round(c, 3),
                               "reason": f"OCR มั่นใจรหัสสินค้านี้ต่ำ ({c:.0%}) - ตรวจกับเอกสารว่าอ่านครบและตรงทุกตัวอักษร"}
            flagged += 1
    return flagged


def attach_printed_qty(rows, points, w, h):
    """เก็บ qty "ตามที่พิมพ์บนกระดาษ" (เช่น '5,000.00', '23,00', '4000') ไว้ที่ row['qty_printed'] เพื่อแสดงบนรูปเอกสาร
    ดึงจาก node OCR ของช่อง qty (กล่อง boxes.qty) เอาเฉพาะตัวเลขที่ค่าตรงกับ qty ที่อ่านได้ · ไม่เจอ = ไม่ใส่ (หน้าจอใช้ค่า qty เดิม)
    ไม่แก้ row['qty'] · ตารางในหน้าตรวจสอบยังใช้ qty เดิม"""
    n = 0
    if not rows or not points or not w or not h:
        return 0
    for r in rows:
        bx = (r.get("boxes") or {}).get("qty")
        q = parse_qty(r.get("qty"))
        if not bx or q is None:
            continue
        node = _node_for_box(points, bx, w, h)
        if not node:
            continue
        for tok in _NUM_TOKEN.findall(str(node.get("txt", ""))):
            if any(abs(v - q) < 1e-6 for v in numbers_in_text(tok)):      # รองรับ '200,000' (เวียดนาม = 200) / '23,00' (= 23) ที่ตีความได้หลายแบบ
                r["qty_printed"] = tok.strip()
                n += 1
                break
    return n


# ───────── ความมั่นใจของ OCR ที่ node qty / PO (ติดธงสีส้ม ไม่แก้ค่า) ─────────
# เกณฑ์วัดจากไฟล์จริง 173 ไฟล์ (1,019 แถว): < 0.90 ติดธง ~2.5% ของแถว เกือบทั้งหมดอยู่ใน SAMPLE-001 (สแกนแย่) · < 0.95 ติด 7% กระจาย 37 ไฟล์ (มากเกินไป)
# ข้อควรรู้: ค่าที่ OCR อ่านผิดจริงมักมีความมั่นใจสูง (เจอ 0.992 / 0.999) → ตัวนี้เป็นตัวเสริมสำหรับสแกนจาง ไม่ใช่ตัวหลัก
QTY_CONF_MIN = 0.90
PO_CONF_MIN = 0.90
SMALL_TEXT_RATIO = 0.6     # ความสูงตัวอักษรเทียบค่ากลางของหน้า ต่ำกว่านี้ = ตัวเล็กผิดปกติ (ในไฟล์ที่มีแทบไม่พบ ต่ำสุด 0.55 มี 1 แถว)


def _node_for_box(points, box, w, h):
    pts = _norm_pts(_flatten(box), w, h)
    if not pts or not points:
        return None
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    best = min(points, key=lambda p: (p["cx"] - cx) ** 2 + (p["cy"] - cy) ** 2)
    if abs(best["cx"] - cx) > 0.05 or abs(best["cy"] - cy) > 0.02:
        return None
    return best


def value_confidence_check(rows, points, w, h):
    """ติดธง qty / เลข PO ที่ OCR ไม่มั่นใจ (ความมั่นใจต่ำ หรือตัวอักษรเล็กกว่าปกติของหน้า)
    เขียน row['qty_conf_check'] / row['po_conf_check'] = {"ok": False, "conf": float, "reason": str} เฉพาะที่ติดธง · ไม่แก้ค่า · คืนจำนวนธง"""
    flagged = 0
    if not rows or not points or not w or not h:
        return 0
    hts = sorted(abs(p["box"][2][1] - p["box"][0][1]) / h for p in points if p.get("box") is not None)
    med = hts[len(hts) // 2] if hts else None
    for r in rows:
        bx = r.get("boxes") or {}
        for key, field, lim, label in (("qty", "qty_conf_check", QTY_CONF_MIN, "จำนวน"), ("po_number", "po_conf_check", PO_CONF_MIN, "เลข PO")):
            if not bx.get(key):
                continue
            node = _node_for_box(points, bx.get(key), w, h)
            if not node:
                continue
            reasons, c = [], node.get("conf")
            if isinstance(c, (int, float)) and c < lim:
                reasons.append(f"OCR ไม่มั่นใจ{label} ({c:.0%})")
            if med and node.get("box") is not None:
                hr = (abs(node["box"][2][1] - node["box"][0][1]) / h) / med
                if hr < SMALL_TEXT_RATIO:
                    reasons.append(f"ตัวอักษร{label} เล็กกว่าปกติของหน้านี้ ({hr:.0%})")
            if reasons:
                r[field] = {"ok": False, "conf": round(float(c), 3) if isinstance(c, (int, float)) else None,
                            "reason": " / ".join(reasons) + " - ตรวจกับเอกสาร"}
                flagged += 1
    return flagged


# ───────── ตัวตรวจรูปแบบ (ติดธงเท่านั้น ไม่แก้ค่า) ─────────
# รูปแบบเลข PO ที่เคยพบจริงของ Template ที่ OCR ทำตัวอักษรหลุดได้โดยไม่เตือน (audit L1) - ไม่ตรง = ให้คนตรวจกับเอกสาร
# Template ใหม่/ฟอร์มใหม่ที่ไม่ตรงรูปแบบจะขึ้นธงด้วย (ปลอดภัยกว่าปล่อยเงียบ) - เพิ่มรูปแบบที่นี่เมื่อเจอฟอร์มใหม่ของลูกค้านั้น
PO_FORMATS = {
    # "TEMPLATE_ID": [r"^PO\d{6}$"],   # example: expected PO number patterns per template
}


def po_format_check(rows, template_name):
    """เลข PO ไม่ตรงรูปแบบที่เคยพบของ Template นี้ → row['po_check'] = {"ok": False, "reason": ...} · คืนจำนวนแถวที่ติดธง"""
    pats = [re.compile(p) for p in PO_FORMATS.get(str(template_name or "").upper(), [])]
    if not pats:
        return 0
    n = 0
    for r in rows:
        po = str(r.get("po_number") or "").strip()
        if po and po != "Unknown" and not any(p.match(po) for p in pats):
            r["po_check"] = {"ok": False, "reason": f"เลข PO '{po}' ไม่ตรงรูปแบบที่เคยพบของฟอร์มนี้ - ตรวจกับเอกสารว่าอ่านครบทุกตัวอักษร"}
            n += 1
    return n


# Template ที่ช่อง qty พิมพ์ทศนิยมสองตำแหน่งเสมอ (เช่น 68.00) - OCR ทำจุดหาย (6800) แล้วตัวเลขผิดเป็นร้อยเท่าโดยไม่เตือน (audit L1)
QTY_DECIMAL_TEMPLATES = set()  # templates whose qty is always printed with 2 decimals


def qty_decimal_check(rows, points, w, h, template_name):
    """qty ที่ node ไม่มีจุดทศนิยม (และมีตัวเลขตั้งแต่ 3 หลัก) → row['qty_check'] ไม่ผ่าน · คืนจำนวนแถวที่ติดธง"""
    if str(template_name or "").upper() not in QTY_DECIMAL_TEMPLATES or not w or not h:
        return 0
    texts = []
    for r in rows:
        box = _norm_pts(_flatten((r.get("boxes") or {}).get("qty")), w, h)
        if not box:
            texts.append(None); continue
        x0, x1, y0, y1 = min(p[0] for p in box), max(p[0] for p in box), min(p[1] for p in box), max(p[1] for p in box)
        near = [p for p in points if x0 - 0.005 <= p["cx"] <= x1 + 0.005 and y0 - 0.005 <= p["cy"] <= y1 + 0.005]
        nums = [str(p.get("txt", "")) for p in near if re.search(r"\d", str(p.get("txt", "")))]
        texts.append(nums[0] if nums else None)
    n = 0
    for r, t in zip(rows, texts):
        if t and not re.search(r"\d\.\d", t) and len(re.sub(r"\D", "", t)) >= 3:
            r["qty_check"] = {"ok": False, "reason": f"ช่อง qty อ่านได้ '{t}' ไม่มีจุดทศนิยม ทั้งที่ฟอร์มนี้พิมพ์ทศนิยมเสมอ (เช่น 68.00) - จุดอาจหายจาก OCR ตรวจจำนวนกับเอกสาร"}
            n += 1
    return n
