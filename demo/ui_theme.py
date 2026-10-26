# 🎨 PO OCR THEME - Tesla-inspired Light (Warm Cream)
# แก้สี/ฟอนต์ที่ไฟล์นี้ที่เดียว ทุกหน้าจอจะเปลี่ยนตาม
# สีที่มีความหมาย (แดง = ต้องตรวจ, เขียว = ผ่าน) และสีกรอบไฮไลท์บนรูป PDF ไม่ได้อยู่ที่นี่ และไม่ได้เปลี่ยน
import os
import sys

# --- Color tokens (Tesla Light - Clean Pure White) ---
BG = "#FFFFFF"                   # พื้นหลักขาวบริสุทธิ์
BG_WHITE = "#FFFFFF"             # พื้นขาวจริง (การ์ด, ตาราง)
SURFACE = "#F9FAFB"              # พื้นเทาอ่อนจางมาก (ปุ่มรอง, panel, drop zone)
SURFACE_HOVER = "#F3F4F6"        # Hover state บน Surface
SURFACE_RAISED = "#FFFFFF"       # Raised panels, modals

TEXT = "#000000"                 # ตัวหนังสือหลัก (ดำสนิท)
TEXT_2 = "#000000"               # ตัวหนังสือรอง / หัวคอลัมน์ (ดำสนิท)
TEXT_3 = "#9CA3AF"               # คำอธิบายเล็ก / disabled
TEXT_MUTED = "#9CA3AF"           # muted text (light grey)
BORDER = "#E5E7EB"               # ขอบบาง (เทาอ่อน)
BORDER_STRONG = "#D1D5DB"        # ขอบช่องกรอก, divider ชัด
HEADER_BG = "#E8EBF1"            # พื้นหัวคอลัมน์ตาราง (เทาอมน้ำเงินจาง เข้ากับ ACCENT)
HEADER_TEXT = "#000000"          # ตัวหนังสือหัวคอลัมน์ (ดำสนิท)

ACCENT = "#3D5A99"               # 🔵 Navy Blue - สีเน้นหลัก (ปุ่มหลัก, Prepare Export)
ACCENT_HOVER = "#2D4373"         # Hover บนปุ่มหลัก
ACCENT_SOFT = "rgba(61, 90, 153, 0.08)"   # แถวที่เลือก / selection tint

WARN = "#C2410C"                 # ⚠️ ส้มเข้ม - item ที่ต้องตรวจ
WARN_BG = "#FFF7ED"              # พื้นหลัง warning badge
WARN_BORDER = "#FED7AA"          # ขอบ warning

DANGER = "#DC2626"               # แดงจัด - ลบ, error
DANGER_BG = "#FEF2F2"            # พื้นหลังปุ่ม Delete
DANGER_BORDER = "#FECACA"        # ขอบปุ่ม Delete

SUCCESS = "#16A34A"              # สีเขียว - ค่าความถูกต้องสูง

NAV_ACTIVE_BG = "#FFFFFF"        # Tab ที่เลือกอยู่
NAV_ACTIVE_BORDER = "#1A1A1A"    # ขอบล่าง tab ที่เลือก

# --- Fonts ---
UI_FAMILIES = ["Segoe UI", "IBM Plex Sans Thai", "Kanit"]   # คมชัด Standard Windows UI → ไทย → สำรอง
MONO_FAMILIES = ["IBM Plex Mono", "Consolas"]               # รหัส / ตัวเลข


def _assets_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def load_fonts():
    """โหลดทุกฟอนต์ใน fonts/ เข้าโปรแกรม (ไม่ต้องติดตั้งลง Windows)"""
    from PyQt6.QtGui import QFontDatabase
    fonts_dir = os.path.join(_assets_dir(), "fonts")
    if not os.path.isdir(fonts_dir):
        return
    for f in os.listdir(fonts_dir):
        if f.lower().endswith((".ttf", ".otf")):
            QFontDatabase.addApplicationFont(os.path.join(fonts_dir, f))


def ui_font(size=11, weight=None):
    from PyQt6.QtGui import QFont
    f = QFont(); f.setFamilies(UI_FAMILIES); f.setPointSize(size)
    if weight is not None: f.setWeight(weight)
    return f


def mono_font(size=11, weight=None):
    from PyQt6.QtGui import QFont
    f = QFont(); f.setFamilies(MONO_FAMILIES); f.setPointSize(size)
    f.setStyleHint(QFont.StyleHint.Monospace)
    if weight is not None: f.setWeight(weight)
    return f


def app_qss():
    arrow = os.path.join(_assets_dir(), "static", "chevron-down.svg").replace("\\", "/")
    return f"""
    QWidget {{ color: {TEXT}; font-size: 14px; }}
    QMainWindow, QDialog, QWidget#Central {{ background: {BG}; }}
    QLabel {{ background: transparent; }}
    QToolTip {{ background: {TEXT}; color: {BG_WHITE}; border: none; padding: 6px 10px; border-radius: 6px; font-size: 12px; }}

    /* Menu */
    QMenuBar {{ background: {BG_WHITE}; border-bottom: 1px solid {BORDER}; padding: 4px 8px; }}
    QMenuBar::item {{ background: transparent; padding: 6px 14px; border-radius: 6px; color: {TEXT_2}; font-weight: 500; }}
    QMenuBar::item:selected, QMenuBar::item:pressed {{ background: {SURFACE_HOVER}; color: {TEXT}; }}
    QMenu {{ background: {BG_WHITE}; border: 1px solid {BORDER}; padding: 6px; border-radius: 10px; }}
    QMenu::item {{ padding: 8px 24px; border-radius: 6px; color: {TEXT}; }}
    QMenu::item:selected {{ background: {SURFACE_HOVER}; color: {TEXT}; }}
    QMenu::item:disabled {{ color: {TEXT_3}; }}
    QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

    /* Buttons: Default = พื้นขาว ขอบครีม, Primary = น้ำเงินเข้ม, Danger = ขอบแดง */
    QPushButton {{ background: {BG_WHITE}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
                  padding: 8px 18px; font-weight: 600; }}
    QPushButton:hover {{ background: {SURFACE}; border-color: {TEXT_MUTED}; }}
    QPushButton:pressed {{ background: {SURFACE_HOVER}; }}
    QPushButton:focus {{ border-color: {ACCENT}; }}
    QPushButton:disabled, QPushButton:disabled:hover {{ background: {SURFACE}; color: {TEXT_3}; border-color: {BORDER}; }}
    QPushButton#PrimaryBtn {{ background: {ACCENT}; color: #FFFFFF; border: none; border-radius: 10px; font-weight: 700; }}
    QPushButton#PrimaryBtn:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#PrimaryBtn:pressed {{ background: #243659; }}
    QPushButton#PrimaryBtn:focus {{ border: 2px solid {ACCENT_HOVER}; padding: 7px 17px; }}
    QPushButton#PrimaryBtn:disabled {{ background: {SURFACE}; color: {TEXT_3}; border: 1px solid {BORDER}; }}
    QPushButton#DangerBtn {{ background: {DANGER_BG}; color: {DANGER}; border: 1px solid {DANGER_BORDER}; }}
    QPushButton#DangerBtn:hover {{ background: #FEE2E2; border-color: {DANGER}; }}
    QPushButton#DangerBtn:pressed {{ background: #FECACA; }}
    QPushButton#IconBtn {{ padding: 4px; font-size: 16px; border-radius: 8px; }}

    /* Inputs */
    QLineEdit, QComboBox, QDateEdit {{ background: {BG_WHITE}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
                  border-radius: 8px; padding: 6px 10px; min-height: 24px; }}
    QLineEdit, QComboBox, QDateEdit {{ selection-background-color: {ACCENT}; selection-color: #FFFFFF; }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 1px solid {ACCENT}; }}
    QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{ background: {SURFACE}; color: {TEXT_3}; border-color: {BORDER}; }}
    QLineEdit:read-only {{ background: {SURFACE}; }}
    QComboBox:hover, QDateEdit:hover {{ border: 1px solid {TEXT_MUTED}; }}
    QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{arrow}"); width: 12px; height: 12px; }}
    QComboBox QAbstractItemView {{ background: {BG_WHITE}; border: 1px solid {BORDER}; outline: none; padding: 4px;
                  selection-background-color: {SURFACE}; selection-color: {TEXT}; border-radius: 8px; }}
    QCalendarWidget QWidget {{ alternate-background-color: {SURFACE}; }}
    QCalendarWidget QToolButton {{ color: {TEXT}; background: transparent; padding: 6px; font-weight: 600; }}
    QCalendarWidget QAbstractItemView:enabled {{ selection-background-color: {ACCENT}; selection-color: #FFFFFF; }}

    /* Tables: Clean cream grid, subtle row separation */
    QTableWidget, QTableView {{ background: {BG_WHITE}; border: none; gridline-color: transparent; outline: none;
                  alternate-background-color: {BG}; selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT}; }}
    QTableWidget::item {{ padding: 8px 10px; border: none; border-bottom: 1px solid {BORDER}; outline: none; }}
    QTableWidget::item:hover {{ background: {SURFACE}; }}
    QTableWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; border: none; border-bottom: 1px solid {BORDER}; outline: none; }}
    QTableWidget::item:focus {{ border: none; border-bottom: 1px solid {BORDER}; outline: none; }}
    QHeaderView {{ background: {HEADER_BG}; border: none; outline: none; }}
    QHeaderView::section {{ background: {HEADER_BG}; color: {HEADER_TEXT}; border: none; border-bottom: 2px solid {BORDER};
                  padding: 10px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
    QTableWidget QLineEdit {{ border: 1px solid {ACCENT}; border-radius: 4px; padding: 2px 6px; }}

    /* Scrollbars: Ultra-thin, beige */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; border: none; }}
    QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; min-height: 30px; margin: 0 2px; border-radius: 3px; }}
    QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; border: none; }}
    QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; min-width: 30px; margin: 2px 0; border-radius: 3px; }}
    QScrollBar::handle:horizontal:hover {{ background: {TEXT_MUTED}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: none; border: none; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* Panels / Modals */
    QFrame#ModalHeader {{ background: {BG_WHITE}; border: none; border-bottom: 1px solid {BORDER}; }}
    QFrame#ModalFooter {{ background: {BG_WHITE}; border: none; border-top: 1px solid {BORDER}; }}
    QFrame#BulkBar {{ background: {BG_WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}
    QFrame#TablePanel {{ background: {BG_WHITE}; border: none; }}
    QFrame#ViewerPanel {{ background: {SURFACE}; border: none; border-radius: 10px; }}
    QFrame#NavBar {{ background: {BG_WHITE}; border: none; }}
    QLabel#PageInfo {{ font-size: 13px; font-weight: 700; }}

    QSplitter::handle {{ background: {BORDER}; }}
    QSplitter::handle:hover {{ background: {ACCENT}; }}
    QScrollArea {{ border: none; background: {SURFACE}; }}
    QProgressBar {{ border: none; border-radius: 3px; background: {SURFACE}; min-height: 4px; max-height: 4px; color: transparent; }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
    QStatusBar {{ background: {BG}; color: {TEXT_2}; font-size: 12px; border-top: 1px solid {BORDER}; }}

    /* Dialogs */
    QMessageBox {{ background: {BG_WHITE}; }}
    QMessageBox QLabel {{ font-size: 13px; color: {TEXT}; }}
    QMessageBox QPushButton {{ background: {ACCENT}; color: #FFFFFF; min-width: 80px; padding: 8px 18px; border: none; border-radius: 8px; }}
    QMessageBox QPushButton:hover {{ background: {ACCENT_HOVER}; }}
    QMessageBox QPushButton:focus {{ border: 2px solid {ACCENT_HOVER}; padding: 7px 17px; }}
    QMessageBox QPushButton[text="No"], QMessageBox QPushButton[text="&No"],
    QMessageBox QPushButton[text="Cancel"], QMessageBox QPushButton[text="&Cancel"] {{ background: {BG_WHITE}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; }}
    """


APP_ID = "Demo.POOCR.Automation.v1"


def init_app_id():
    """ต้องเรียกก่อนหรือพร้อมกับการสร้าง QApplication เพื่อให้ Windows Taskbar จัดกลุ่ม icon ได้ถูกต้อง"""
    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass


def get_app_icon():
    from PyQt6.QtGui import QIcon
    assets = _assets_dir()
    ico_path = os.path.join(assets, "static", "logo.ico")
    png_path = os.path.join(assets, "static", "logo.png")
    if os.path.exists(ico_path):
        return QIcon(ico_path)
    elif os.path.exists(png_path):
        return QIcon(png_path)
    return QIcon()


def logo_pixmap(height, dpr=1.0):
    """โลโก้บริษัท (logo/logo.jpg) ปรับความสูงเป็นพิกเซลจริง (height x dpr) ให้คมบนจอ scale สูง · ไม่เจอไฟล์/โหลดไม่ได้ = คืน None (ผู้เรียกข้ามเงียบๆ)"""
    try:
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        px = QPixmap(os.path.join(_assets_dir(), "logo", "logo.jpg"))
        if px.isNull():
            return None
        px = px.scaledToHeight(max(1, int(height * dpr)), Qt.TransformationMode.SmoothTransformation)
        px.setDevicePixelRatio(dpr)
        return px
    except Exception:
        return None


def apply(app):
    """เรียกครั้งเดียวหลังสร้าง QApplication"""
    init_app_id()
    from PyQt6.QtWidgets import QStyleFactory
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")
    load_fonts()
    app.setFont(ui_font(11))
    app.setStyleSheet(app_qss())
    icon = get_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
