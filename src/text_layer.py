# 📄 TEXT LAYER CHECK - เทียบค่าที่ OCR อ่านได้ (PO / รหัสสินค้า / qty) กับ "ตัวอักษรจริงที่ฝังอยู่ในไฟล์ PDF"
#
# ใช้กับ PDF ดิจิทัล (พิมพ์จากระบบลูกค้า ไม่ผ่านเครื่องสแกน) ที่มีตัวอักษรฝังอยู่ในไฟล์ → เป็นหลักฐานอิสระจาก OCR
# ติดธงเท่านั้น: ผล = row["text_check"] = {"ok": bool, "reason": str} · ไม่แก้ค่าที่อ่านได้เด็ดขาด · ไม่แตะ OCR / การแปลง PDF→ภาพ
#
# เงื่อนไขที่ "ตัดสิน" (ไม่เข้าเงื่อนไข = ข้ามเงียบๆ ไม่ติดธง ไม่ถือว่าผิด):
#   1) หน้านั้นไม่มีรูปภาพ  (ไฟล์สแกนมี text layer ที่เครื่องสแกนทำ OCR ใส่ไว้เอง เชื่อถือไม่ได้)
#   2) ตัวอักษรในหน้า "ครอบคลุมตาราง": พบรหัสสินค้าที่ OCR อ่านได้อย่างน้อยครึ่งหนึ่งของแถวในหน้านั้น
#      (บางไฟล์แปลงตัวอักษรในตารางเป็นเส้นโค้ง เหลือแค่หัวกระดาษ เช่น SAMPLE-001 → เทียบไม่ได้ ต้องไม่เตือนผิด)
#   เมื่อครอบคลุมแล้ว: ค่าใดไม่พบในตัวอักษรของไฟล์ = ติดธง (PO, รหัสสินค้า หรือ qty)
import os, re, subprocess

MIN_TEXT_CHARS = 150        # หน้าที่มีตัวอักษรน้อยกว่านี้ = ไม่มี text layer ที่ใช้ได้
MIN_COVERAGE = 0.5          # สัดส่วนแถวที่ต้องพบรหัสสินค้าในตัวอักษร จึงถือว่า text layer ครอบคลุมตาราง
WIN_BEFORE, WIN_AFTER = 3, 1   # qty ต้องอยู่ในบรรทัดรอบรหัสสินค้าของแถวนั้น (ก่อน 3 / หลัง 1 บรรทัด) ไม่ใช่เลขที่ไหนก็ได้ในหน้า (เช่น '50' ใน '50 G')
TIMEOUT = 20


def _exe(name, poppler_dir):
    cands = []
    if poppler_dir:
        cands += [os.path.join(poppler_dir, name + ".exe"), os.path.join(poppler_dir, name)]
    cands += [name]
    for c in cands:
        if os.path.isabs(c) and not os.path.exists(c):
            continue
        return c
    return name


def _run(args):
    r = subprocess.run(args, capture_output=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)      # --windowed ไม่มี console: ระบุ stdin กัน WinError 6
    return r.stdout.decode("utf-8", errors="ignore") if r.returncode == 0 else None


def page_text_and_images(pdf_path, page_no, poppler_dir=None):
    """(ข้อความของหน้า, จำนวนรูปภาพในหน้า) — ล้มเหลว = (None, None)"""
    try:
        txt = _run([_exe("pdftotext", poppler_dir), "-f", str(page_no), "-l", str(page_no), "-layout", pdf_path, "-"])
        lst = _run([_exe("pdfimages", poppler_dir), "-list", "-f", str(page_no), "-l", str(page_no), pdf_path])
        if txt is None or lst is None:
            return None, None
        n_img = max(0, len([l for l in lst.splitlines() if l.strip()]) - 2)
        return txt, n_img
    except Exception:
        return None, None


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def check_rows(pdf_path, pages, rows, poppler_dir=None):
    """ตรวจแถวของ PDF นี้กับ text layer — เขียน row["text_check"] เฉพาะหน้าที่ตัดสินได้ + เพิ่มคำเตือนระดับหน้า
    คืนสรุป {"pages_checked", "rows_checked", "rows_ok", "rows_mismatch"} (ใช้ใน log) — ห้ามโยน error ออกไป"""
    out = {"pages_checked": 0, "rows_checked": 0, "rows_ok": 0, "rows_mismatch": 0}
    try:
        import qty_guard
        if not rows or not pdf_path or not os.path.exists(pdf_path):
            return out
        by_page = {}
        for r in rows:
            m = re.search(r"_p(\d+)\.png$", str(r.get("page_image") or ""))
            if m:
                by_page.setdefault(int(m.group(1)), []).append(r)
        for pno, prows in sorted(by_page.items()):
            txt, n_img = page_text_and_images(pdf_path, pno, poppler_dir)
            if txt is None or n_img is None or n_img > 0 or len(re.sub(r"\s", "", txt)) < MIN_TEXT_CHARS:
                continue                                        # สแกน / ไม่มี text layer → ไม่ตัดสิน
            tn = _norm(txt)
            nums = qty_guard.numbers_in_text(txt)
            lines = [l for l in txt.splitlines() if l.strip()]      # นับเฉพาะบรรทัดที่มีตัวอักษร (บรรทัดว่างคั่นระหว่างรหัสสินค้ากับ qty ไม่นับ)
            lines_n = [_norm(l) for l in lines]
            judged = [r for r in prows if len(_norm(r.get("item_code"))) >= 4 and _norm(r.get("item_code")) not in ("UNKNOWN",)]
            if not judged:
                continue
            covered = sum(1 for r in judged if _norm(r.get("item_code")) in tn)
            if covered / len(judged) < MIN_COVERAGE:
                continue                                        # ตัวอักษรในไฟล์ไม่ครอบคลุมตาราง (เช่นตารางเป็นเส้นโค้ง) → ไม่ตัดสิน
            out["pages_checked"] += 1
            bad_rows = 0
            for r in prows:
                reasons = []
                item = _norm(r.get("item_code"))
                if len(item) >= 4 and item != "UNKNOWN" and item not in tn:
                    reasons.append(f"รหัสสินค้า {r.get('item_code')} ไม่พบในตัวอักษรของไฟล์ PDF")
                q = qty_guard.parse_qty(r.get("qty"))
                row_nums = nums     # หารหัสสินค้าของแถวในตัวอักษร → ใช้เฉพาะตัวเลขในบรรทัดรอบๆ (ไม่เจอ = ใช้ทั้งหน้า)
                if len(item) >= 4 and item != "UNKNOWN":
                    idxs = [i for i, l in enumerate(lines_n) if item in l]
                    if idxs:
                        row_nums = set()
                        for i in idxs:
                            row_nums |= qty_guard.numbers_in_text("\n".join(lines[max(0, i - WIN_BEFORE): i + WIN_AFTER + 1]))
                if q is not None and q > 0 and not any(abs(n - q) < 1e-6 for n in row_nums):
                    reasons.append(f"จำนวน {r.get('qty')} ไม่พบในตัวอักษรของไฟล์ PDF")
                po = _norm(r.get("po_number"))
                if len(po) >= 4 and po != "UNKNOWN" and po not in tn:
                    reasons.append(f"เลข PO {r.get('po_number')} ไม่พบในตัวอักษรของไฟล์ PDF")
                out["rows_checked"] += 1
                if reasons:
                    r["text_check"] = {"ok": False, "reason": " / ".join(reasons)}
                    bad_rows += 1
                    out["rows_mismatch"] += 1
                else:
                    r["text_check"] = {"ok": True, "reason": "ตรงกับตัวอักษรในไฟล์ PDF"}
                    out["rows_ok"] += 1
            if bad_rows:
                for pg in pages:
                    if pg.get("page") == pno:
                        pg["warnings"] = (pg.get("warnings") or []) + [
                            f"พบ {bad_rows} แถวที่ค่าไม่ตรงกับตัวอักษรในไฟล์ PDF (ไฟล์ดิจิทัล) - ไม่แน่ใจว่าอ่านถูก โปรดตรวจกับเอกสาร"]
                        break
    except Exception:
        pass
    return out
