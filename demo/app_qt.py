"""Desktop demo of the review screen (PyQt6), same layout and styling as the production tool.

    pip install PyQt6 PyMuPDF
    python demo/app_qt.py

Everything shown is fictional test data. Each "page" is one simulated OCR failure; the
verdicts come from the real verification layer (src/qty_guard.py).

    python demo/app_qt.py --shot out.png [--page N] [--dialog]    # save a screenshot and exit
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PyQt6.QtCore import QDate, QLocale, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDateEdit, QDialog,  # noqa: E402
                             QFrame, QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
                             QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

import demo  # noqa: E402
import gui   # noqa: E402  (reuses the page renderer and the message translations)
import ui_theme as theme  # noqa: E402

PDF, TPL, BASE, W, H = gui.PDF, gui.TPL, gui.BASE, gui.W, gui.H
IMG_SCALE = gui.ZOOM
CUSTOMER = "DEMO1"
WARN_COL, OK_COL = QColor(theme.WARN), QColor(theme.SUCCESS)
SALES = ["SALES01", "SALES02"]
COORDS = ["*", "COORD-A", "COORD-B"]
CURR = ["USD", "THB", "EUR"]
FIELD = "padding: 2px 8px; height: 30px; border: 1px solid #D1D5DB; background: white; border-radius: 6px;"


def _combo(items, blank=False):
    c = QComboBox(); c.setStyleSheet(FIELD)
    if blank:
        c.addItem("- select -")
    c.addItems(items)
    return c


def _date():
    d = QDateEdit(); d.setCalendarPopup(True); d.setDisplayFormat("dd/MM/yyyy")
    d.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
    d.setDate(QDate(2026, 10, 26)); d.setStyleSheet(FIELD)
    return d


class ExportDialog(QDialog):
    def __init__(self, pos, parent):
        super().__init__(parent)
        self.setWindowTitle("PREPARE DATA BY PO"); self.resize(1100, 560)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        h = QFrame(); h.setFixedHeight(70); h.setObjectName("ModalHeader"); hl = QVBoxLayout(h)
        hl.addWidget(QLabel("PO EXPORT PREPARATION", styleSheet="font-weight: 800; font-size: 16px;"))
        hl.addWidget(QLabel("Items are grouped by PO Number. Line No starts from 1 per PO.", styleSheet="font-size: 11px;"))
        lay.addWidget(h)

        bar = QFrame(); bar.setObjectName("BulkBar")
        bar.setStyleSheet("QFrame#BulkBar { background: #F9FAFB; border: none; border-bottom: 1px solid #E5E7EB; border-radius: 0px; }")
        bl = QHBoxLayout(bar); bl.setContentsMargins(16, 10, 16, 10); bl.setSpacing(6)
        bl.addWidget(QLabel("Set all POs:", styleSheet="font-weight: 800; border: none;"))
        for label, w in [("Coordinator", _combo(COORDS)), ("Salesperson", _combo(SALES)),
                         ("Currency", _combo(CURR)), ("Delivery", _date())]:
            bl.addWidget(QLabel(label, styleSheet="font-size: 11px; border: none;")); bl.addWidget(w); bl.addSpacing(12)
        bl.addWidget(QLabel("Changing a value updates every PO in the table", styleSheet="font-size: 11px; border: none;"))
        bl.addStretch(); lay.addWidget(bar)

        t = QTableWidget(len(pos), 7)
        t.setHorizontalHeaderLabels(["PO NUMBER", "ITEMS", "CUSTOMER", "COORDINATOR ID", "SALESPERSON", "CUSTOM CURRENCY", "DELIVERY DATE"])
        t.verticalHeader().setVisible(False); t.setShowGrid(False); t.horizontalHeader().setStretchLastSection(False)
        mono = QFont(); mono.setFamilies(theme.MONO_FAMILIES); mono.setPointSize(11); mono.setWeight(QFont.Weight.DemiBold)
        for i, (po, n) in enumerate(pos):
            t.setRowHeight(i, 40)
            it = QTableWidgetItem(po); it.setFont(mono); t.setItem(i, 0, it)
            t.setItem(i, 1, QTableWidgetItem(f"{n} Line(s)")); t.setItem(i, 2, QTableWidgetItem(CUSTOMER))
            t.setCellWidget(i, 3, _combo(COORDS)); t.setCellWidget(i, 4, _combo(SALES, blank=True))
            t.setCellWidget(i, 5, _combo(CURR)); t.setCellWidget(i, 6, _date())
        for c, wd in enumerate([170, 100, 100, 180, 150, 160, 160]):
            t.setColumnWidth(c, wd)
        lay.addWidget(t)

        f = QFrame(); f.setFixedHeight(70); f.setObjectName("ModalFooter"); fl = QHBoxLayout(f)
        ok = QPushButton("Confirm && Export CSV"); ok.setFixedSize(220, 42)
        ok.setStyleSheet("background: #3D5A99; color: #fff; font-weight: 800; border-radius: 10px; border: none;")
        ok.clicked.connect(self._confirm); fl.addStretch(); fl.addWidget(ok); lay.addWidget(f)

    def _confirm(self):
        QMessageBox.information(self, "Demo", "Demo only: no file is written.\nThe real tool exports the ERP import CSV here.")


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PO OCR (demo, fictional data)"); self.resize(1500, 860)
        self.results = [demo.run_scenario(s, TPL, BASE, W, H) for s in demo.SCENARIOS]
        self.cur, self.zoom_f = 0, 1.0
        self.pm_cache = {}

        mb = self.menuBar()
        for name in ("File", "View", "Settings", "About"):
            mb.addMenu(name)
        mb.setCornerWidget(self._logo(), Qt.Corner.TopLeftCorner)

        central = QWidget(); central.setObjectName("Central"); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(16, 12, 16, 16); root.setSpacing(12)

        nav = QHBoxLayout(); root.addLayout(nav)
        self.btn_prev, self.btn_next = QPushButton("Previous"), QPushButton("Next")
        self.lbl_page = QLabel("-"); self.lbl_page.setObjectName("PageInfo")
        self.btn_prev.clicked.connect(lambda: self.load(max(0, self.cur - 1)))
        self.btn_next.clicked.connect(lambda: self.load(min(len(self.results) - 1, self.cur + 1)))
        nav.addWidget(self.btn_prev); nav.addWidget(self.lbl_page); nav.addWidget(self.btn_next); nav.addStretch()

        self.btn_zout = QPushButton("-"); self.btn_zout.setObjectName("IconBtn")
        self.btn_zin = QPushButton("+"); self.btn_zin.setObjectName("IconBtn")
        self.btn_zreset = QPushButton("Reset")
        self.btn_zout.clicked.connect(lambda: self.zoom(0.8)); self.btn_zin.clicked.connect(lambda: self.zoom(1.2))
        self.btn_zreset.clicked.connect(lambda: self.zoom(0))
        self.sel = QComboBox(); self.sel.addItems([f"{i + 1}. {r['title']}" for i, r in enumerate(self.results)])
        self.sel.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.sel.setMinimumContentsLength(18); self.sel.setMaximumWidth(330)
        self.sel.setStyleSheet("QComboBox { padding: 0px 10px; min-height: 34px; }")
        self.sel.currentIndexChanged.connect(self.load)
        self.btn_delete = QPushButton("Delete Row"); self.btn_delete.setObjectName("DangerBtn")
        self.btn_delete.clicked.connect(self.delete_row)
        self.btn_scan = QPushButton("Scan Files")
        self.btn_scan.clicked.connect(lambda: QMessageBox.information(self, "Demo", "Scanning is disabled in the demo."))
        self.btn_prep = QPushButton("Prepare Export"); self.btn_prep.setObjectName("PrimaryBtn")
        self.btn_prep.clicked.connect(self.prepare)
        for w in (self.btn_zout, self.btn_zreset, self.btn_zin, self.sel, self.btn_delete, self.btn_scan, self.btn_prep):
            nav.addWidget(w)
        for w in (self.btn_prev, self.btn_next, self.btn_zout, self.btn_zreset, self.btn_zin, self.sel,
                  self.btn_delete, self.btn_scan, self.btn_prep):
            w.setFixedHeight(38)
        self.btn_zout.setFixedWidth(38); self.btn_zin.setFixedWidth(38); self.btn_zreset.setFixedWidth(80)
        self.btn_delete.setFixedWidth(110); self.btn_scan.setFixedWidth(110); self.btn_prep.setFixedWidth(140)

        split = QSplitter(Qt.Orientation.Horizontal); split.setHandleWidth(12)
        split.setStyleSheet("QSplitter::handle { background: transparent; }")
        card = "QFrame#%s { background: #FFF; border: 1px solid #E5E7EB; border-radius: 10px; }"
        tc = QFrame(); tc.setObjectName("TableCard"); tc.setStyleSheet(card % "TableCard")
        tl = QVBoxLayout(tc); tl.setContentsMargins(8, 8, 8, 8)
        self.banner = QLabel(); self.banner.setWordWrap(True); self.banner.setTextFormat(Qt.TextFormat.RichText); self.banner.hide()
        self.banner.setStyleSheet(f"background: {theme.WARN_BG}; color: {theme.WARN}; border: 1px solid {theme.WARN_BORDER};"
                                  " border-radius: 8px; padding: 8px 12px; font-size: 13px;")
        tl.addWidget(self.banner)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["No.", "PO No", "Cus Code", "Item Code", "Description", "Qty", "CLARITY", "TRUST"])
        self.table.verticalHeader().setVisible(False); self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = self.table.horizontalHeader()
        for c, wd in [(0, 40), (1, 150), (2, 76), (3, 150), (5, 84), (6, 72), (7, 66)]:
            self.table.setColumnWidth(c, wd)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch); hdr.setStretchLastSection(False)
        self.table.itemSelectionChanged.connect(self.on_select)
        tl.addWidget(self.table)

        vc = QFrame(); vc.setObjectName("ViewerCard"); vc.setStyleSheet(card % "ViewerCard")
        vl = QVBoxLayout(vc); vl.setContentsMargins(8, 8, 8, 8)
        self.scroll = QScrollArea(); self.scroll.setStyleSheet("QScrollArea { background: #EEF0F3; border: none; border-radius: 6px; }")
        self.img = QLabel(); self.img.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll.setWidget(self.img); self.scroll.setWidgetResizable(True); vl.addWidget(self.scroll)
        split.addWidget(tc); split.addWidget(vc); split.setSizes([880, 560]); split.setChildrenCollapsible(False)
        root.addWidget(split)
        self.statusBar().showMessage("Demo with fictional data. Pick a simulated OCR failure from the dropdown.")
        self.load(0)

    def _logo(self):
        l = QLabel("PO OCR"); l.setContentsMargins(14, 0, 14, 0)
        l.setStyleSheet(f"color: {theme.ACCENT}; font-weight: 900; font-size: 18px; letter-spacing: 1px;")
        return l

    # ---------------------------------------------------------------- data
    def load(self, i):
        self.cur = i
        self.sel.blockSignals(True); self.sel.setCurrentIndex(i); self.sel.blockSignals(False)
        self.lbl_page.setText(f"PAGE {i + 1}/{len(self.results)}")
        res = self.results[i]
        warns = [gui.en(w) for w in res["warnings"]]
        self.banner.setVisible(bool(warns))
        self.banner.setText("&#9888; PAGE WARNING: " + "<br>&#9888; ".join(warns) if warns else "")
        self.table.blockSignals(True)
        self.table.setRowCount(0); self.table.setRowCount(len(res["rows"]))
        for r, row in enumerate(res["rows"]):
            qc = row.get("qty_check", {}); row_ok = bool(qc.get("ok"))
            ok = row_ok and not warns
            reason = gui.en(qc.get("reason", ""))
            trust = "99%" if ok else ("41%" if not row_ok else "70%")
            vals = [str(r + 1), res["po"], CUSTOMER, row["item_code"], row["description"], row["qty"], "95%", trust]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c in (0, 6, 7):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 5:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 7:
                    it.setForeground(OK_COL if ok else WARN_COL)
                if c == 6:
                    it.setForeground(OK_COL)
                if not row_ok and c in (3, 5):
                    it.setForeground(QColor(theme.DANGER)); f = it.font(); f.setBold(True); it.setFont(f)
                it.setToolTip(reason or ("Verified" if ok else "See the page warning above the table"))
                self.table.setItem(r, c, it)
            self.table.setRowHeight(r, 38)
        self.table.blockSignals(False)
        self.zoom_f = 1.0
        if res["rows"]:
            self.table.selectRow(0)
        else:
            self.draw(None)

    def delete_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def on_select(self):
        r = self.table.currentRow()
        rows = self.results[self.cur]["rows"]
        if r < 0 or r >= len(rows):
            return
        qc = rows[r].get("qty_check", {})
        self.statusBar().showMessage(gui.en(qc.get("reason", "")) or f"{rows[r]['item_code']}: quantity verified against the document")
        self.draw(r)

    # --------------------------------------------------------------- viewer
    def base_pixmap(self):
        if self.cur not in self.pm_cache:
            pm = QPixmap(); pm.loadFromData(gui.render_png(self.cur)); self.pm_cache[self.cur] = pm
        return self.pm_cache[self.cur].copy()

    def draw(self, row_idx):
        pm = self.base_pixmap()
        fit = max(200, self.scroll.viewport().width() - 6) / pm.width()      # fit page to the panel, zoom on top
        pm = pm.scaledToWidth(int(pm.width() * fit * self.zoom_f), Qt.TransformationMode.SmoothTransformation)
        k = pm.width() / (W * IMG_SCALE) * IMG_SCALE      # PDF points -> screen pixels
        rows = self.results[self.cur]["rows"]
        if row_idx is not None and 0 <= row_idx < len(rows):
            row = rows[row_idx]
            p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            mono = QFont(); mono.setFamilies(theme.MONO_FAMILIES); mono.setBold(True); mono.setPointSize(10); p.setFont(mono)

            def badge(text, box, above):
                xs = [q[0] for q in box]; ys = [q[1] for q in box]
                x, y = min(xs) * k, (min(ys) if above else max(ys)) * k
                fm = p.fontMetrics(); w, h = fm.horizontalAdvance(text) + 10, fm.height() + 2
                top = y - h - 2 if above else y + 2
                p.fillRect(int(x), int(top), w, h, QColor("#FFEB00")); p.setPen(QColor("#000"))
                p.drawText(int(x) + 5, int(top) + fm.ascent() + 1, text)

            if row["boxes"].get("qty"):
                badge(f"QTY:{row['qty']}", row["boxes"]["qty"], True)
            badge(f"ID:{row['item_code']}", row["boxes"]["item_code"], False)
            p.end()
        self.img.setPixmap(pm)

    def zoom(self, f):
        self.zoom_f = 1.0 if f == 0 else max(0.5, min(3.0, self.zoom_f * f))
        r = self.table.currentRow()
        self.draw(r if r >= 0 else None)

    def prepare(self):
        ExportDialog([("PO260123", 4), ("PO260124", 2), ("PO260125", 3)], self).exec()


def main():
    app = QApplication(sys.argv)
    theme.apply(app)
    win = DemoWindow()
    if "--page" in sys.argv:
        win.load(int(sys.argv[sys.argv.index("--page") + 1]))
    if "--shot" in sys.argv:
        out = sys.argv[sys.argv.index("--shot") + 1]
        win.show(); app.processEvents(); win.draw(win.table.currentRow()); app.processEvents()
        if "--dialog" in sys.argv:
            d = ExportDialog([("PO260123", 4), ("PO260124", 2), ("PO260125", 3), ("PO260126", 1), ("PO260127", 5)], win)
            d.show(); app.processEvents(); d.grab().save(out)
        else:
            win.grab().save(out)
        return
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
