from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from app.gui.theme.ui_metrics import TypographyMetrics, UiMetrics


# macOS exposes the complete built-in SF Mono family under the internal
# ``.SF NS Mono`` name. Prefer it over a user-installed partial family.
LATIN_MONO_FONT_CANDIDATES = [".SF NS Mono", "SF Mono", "Menlo", "Consolas", "Courier New"]
UI_LATIN_SANS_FONT_CANDIDATES = [
    ".AppleSystemUIFont",
    "SF Pro Text",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
]
CJK_SANS_FONT_CANDIDATES = [
    "Source Han Sans SC",
    "Noto Sans CJK SC",
    "PingFang SC",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "SimHei",
]
CJK_SERIF_FONT_CANDIDATES = [
    "Source Han Serif SC",
    "Source Han Serif CN",
    "Noto Serif CJK SC",
    "Songti SC",
    "STSong",
    "SimSun",
]

COLOR_APP = "#f6f6f4"
COLOR_SURFACE = "#ffffff"
COLOR_SURFACE_ALT = "#f8f8f6"
COLOR_EDITOR = "#fcfcfb"
COLOR_BORDER = "#dcdcd7"
COLOR_BORDER_SOFT = "#e8e8e4"
COLOR_TEXT = "#202321"
COLOR_TEXT_MUTED = "#666b67"
COLOR_TEXT_FAINT = "#6f746f"
COLOR_HOVER = "#f4f4f1"
COLOR_PRESSED = "#e8e8e3"
COLOR_SELECTED = "#fdf1e0"
COLOR_ACCENT = "#b45309"
COLOR_ACCENT_HOVER = "#92400e"
COLOR_SUCCESS = "#2f7d4e"
COLOR_WARNING = "#a7661b"
COLOR_ERROR = "#b3261e"
COLOR_GUTTER = "#f5f5f3"
COLOR_CURRENT_LINE = "#f1f1ee"
COLOR_SYNTAX_COMMAND = "#355f87"
COLOR_SYNTAX_ENVIRONMENT = "#3d6d57"
COLOR_SYNTAX_REFERENCE = "#8a5727"
COLOR_SYNTAX_ARGUMENT = "#666b67"
COLOR_SYNTAX_OPTION = "#6f746f"
COLOR_SYNTAX_MATH = "#7b526f"
COLOR_SYNTAX_COMMENT = "#6c716b"

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
RADIUS_SMALL = 6
RADIUS_MEDIUM = 10
RADIUS_LARGE = 12
CONTROL_HEIGHT = 32
PANEL_HEADER_HEIGHT = 38

_SYSTEM_SF_MONO_FONT_ID: int | None = None


def ui_font(size: int = 12, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(_ui_font_stack())
    font.setPointSize(size)
    font.setWeight(weight)
    return font


def editor_font(size: int = 13) -> QFont:
    font = QFont()
    font.setFamilies(_editor_font_stack())
    font.setPointSize(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font


def log_font(size: int = 11) -> QFont:
    font = editor_font(size)
    return font


def heading_font(size: int = 15, weight: QFont.Weight = QFont.Weight.Bold) -> QFont:
    font = QFont()
    font.setFamilies(_heading_font_stack())
    font.setPointSize(size)
    font.setWeight(weight)
    return font


def apply_theme(app: QApplication) -> None:
    _register_platform_fonts()
    app.setStyle("Fusion")
    app.setFont(ui_font())
    if hasattr(app.styleHints(), "setColorScheme"):
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(light_palette())
    app.setStyleSheet(stylesheet())


def light_palette() -> QPalette:
    palette = QPalette()
    surface = QColor(COLOR_SURFACE)
    app_bg = QColor(COLOR_APP)
    text = QColor(COLOR_TEXT)
    muted = QColor(COLOR_TEXT_MUTED)
    selected = QColor(COLOR_SELECTED)
    accent = QColor(COLOR_ACCENT)
    disabled_bg = QColor(COLOR_SURFACE_ALT)
    disabled_text = QColor(COLOR_TEXT_FAINT)

    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        palette.setColor(group, QPalette.ColorRole.Window, app_bg)
        palette.setColor(group, QPalette.ColorRole.WindowText, text)
        palette.setColor(group, QPalette.ColorRole.Base, surface)
        palette.setColor(group, QPalette.ColorRole.AlternateBase, QColor(COLOR_SURFACE_ALT))
        palette.setColor(group, QPalette.ColorRole.ToolTipBase, surface)
        palette.setColor(group, QPalette.ColorRole.ToolTipText, text)
        palette.setColor(group, QPalette.ColorRole.Text, text)
        palette.setColor(group, QPalette.ColorRole.Button, surface)
        palette.setColor(group, QPalette.ColorRole.ButtonText, text)
        palette.setColor(group, QPalette.ColorRole.BrightText, QColor(COLOR_ERROR))
        palette.setColor(group, QPalette.ColorRole.Highlight, selected)
        palette.setColor(group, QPalette.ColorRole.HighlightedText, text)
        palette.setColor(group, QPalette.ColorRole.Link, accent)
        palette.setColor(group, QPalette.ColorRole.PlaceholderText, muted)

    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, app_bg)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, disabled_bg)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.AlternateBase, disabled_bg)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, disabled_bg)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(COLOR_BORDER))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled_text)
    return palette


def stylesheet(
    metrics: UiMetrics | None = None,
    typography: TypographyMetrics | None = None,
) -> str:
    metrics = metrics or UiMetrics(1.0)
    typography = typography or TypographyMetrics(1.0)
    fs_body = round(typography.body_pt)
    fs_caption = round(typography.caption_pt)
    fs_section = round(typography.section_title_pt)
    fs_page = round(typography.page_title_pt)
    fs_dialog_title = round(15 * metrics.scale)
    fs_mono = round(typography.monospace_pt)
    minh_control = metrics.control_height
    minh_compact = metrics.compact_control_height
    minh_row = metrics.row_height
    minh_tab = round(32 * metrics.scale)
    minh_tab_compact = round(26 * metrics.scale)
    icon_large = metrics.large_icon_size
    eng_min_width = round(112 * metrics.scale)
    ui_stack = _qss_font_stack(_ui_font_stack())
    editor_stack = _qss_font_stack(_editor_font_stack())
    heading_stack = _qss_font_stack(_heading_font_stack())
    return f"""
    QMainWindow {{
        background: {COLOR_APP};
        color: {COLOR_TEXT};
        font-family: {ui_stack};
        font-size: {fs_body}px;
    }}

    QDialog {{
        background: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        font-family: {ui_stack};
        font-size: {fs_body}px;
    }}

    QMenuBar {{
        background: {COLOR_SURFACE};
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
        padding: 2px 8px;
    }}

    QMenuBar::item {{
        border-radius: {RADIUS_SMALL}px;
        padding: 5px 11px;
        color: {COLOR_TEXT_MUTED};
    }}

    QMenuBar::item:selected {{
        background: {COLOR_HOVER};
        color: {COLOR_TEXT};
    }}

    QMenu {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_MEDIUM}px;
        padding: 7px;
    }}

    QMenu::item {{
        border-radius: {RADIUS_SMALL}px;
        color: {COLOR_TEXT};
        padding: 7px 26px;
    }}

    QMenu::item:selected {{
        background: {COLOR_HOVER};
        color: {COLOR_TEXT};
    }}

    QToolTip {{
        background: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_SMALL}px;
        padding: 5px 7px;
    }}

    QToolBar {{
        background: {COLOR_SURFACE};
        border: 0;
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
        spacing: 2px;
        padding: 6px 10px;
    }}

    QToolBar::separator {{
        background: {COLOR_BORDER_SOFT};
        width: 1px;
        margin: 6px 7px;
    }}

    QToolButton {{
        color: {COLOR_TEXT_MUTED};
        background: transparent;
        border: 1px solid transparent;
        border-radius: {RADIUS_SMALL}px;
        padding: 5px 9px;
        min-height: {minh_compact}px;
    }}

    QToolButton:hover {{
        background: {COLOR_HOVER};
        border-color: {COLOR_BORDER_SOFT};
        color: {COLOR_TEXT};
    }}

    QToolButton:pressed {{
        background: {COLOR_PRESSED};
    }}

    QToolButton#primaryAction {{
        background: {COLOR_ACCENT};
        color: {COLOR_SURFACE};
        border-color: {COLOR_ACCENT};
        font-weight: 600;
        padding-left: 10px;
        padding-right: 10px;
    }}

    QToolButton#primaryAction:hover {{
        background: {COLOR_ACCENT_HOVER};
        border-color: {COLOR_ACCENT_HOVER};
        color: {COLOR_SURFACE};
    }}

    QToolButton#primaryAction:disabled {{
        background: #ecc9a8;
        border-color: #ecc9a8;
        color: {COLOR_SURFACE};
    }}

    QAbstractButton#autoCompileToggle {{
        background: transparent;
        border: 0;
    }}

    QSplitter::handle {{
        background: transparent;
    }}

    QSplitter::handle:horizontal {{
        width: 7px;
        border-left: 1px solid {COLOR_BORDER_SOFT};
    }}

    QSplitter::handle:vertical {{
        height: 7px;
        border-top: 1px solid {COLOR_BORDER_SOFT};
    }}

    QSplitter::handle:hover {{
        background: #e7e1d8;
    }}

    QDockWidget {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER_SOFT};
        color: {COLOR_TEXT};
    }}

    QDockWidget::title {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
        padding: 8px 12px;
        font-weight: 650;
        text-align: left;
    }}

    QDockWidget#toolboxDock {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER_SOFT};
        color: {COLOR_TEXT};
    }}

    QDockWidget#toolboxDock::title {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
        padding: 7px 10px;
        font-weight: 650;
        text-align: left;
    }}

    QWidget#panel {{
        background: {COLOR_SURFACE};
        border: 0;
    }}

    QWidget#panelHeader {{
        background: {COLOR_SURFACE_ALT};
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
    }}

    QToolButton#panelHeaderButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: {RADIUS_SMALL}px;
        padding: 3px;
    }}

    QToolButton#panelHeaderButton:hover {{
        background: {COLOR_HOVER};
        border-color: {COLOR_BORDER_SOFT};
    }}

    QLabel#panelTitle {{
        color: {COLOR_TEXT};
        font-size: {fs_section}px;
        font-weight: 650;
    }}

    QWidget#toolboxNavigation,
    QStackedWidget#toolboxStack {{
        background: {COLOR_SURFACE};
        border: 0;
    }}

    QWidget#toolboxRail {{
        background: {COLOR_SURFACE_ALT};
        border-right: 1px solid {COLOR_BORDER_SOFT};
    }}

    QToolButton#toolboxNavButton {{
        color: {COLOR_TEXT_MUTED};
        background: transparent;
        border: 0;
        border-left: 2px solid transparent;
        border-radius: {RADIUS_SMALL}px;
        padding: 4px 2px;
        font-size: 10px;
        font-weight: 500;
    }}

    QToolButton#toolboxNavButton:hover {{
        background: {COLOR_HOVER};
        color: {COLOR_TEXT};
    }}

    QToolButton#toolboxNavButton:checked {{
        background: {COLOR_SELECTED};
        color: {COLOR_ACCENT};
        border-left-color: {COLOR_ACCENT};
        font-weight: 650;
    }}

    QFrame#toolboxDivider {{
        color: {COLOR_BORDER_SOFT};
        background: {COLOR_BORDER_SOFT};
        max-height: 1px;
        margin: 5px 8px;
    }}

    QLabel#panelHint {{
        color: {COLOR_TEXT_FAINT};
        font-size: 11px;
    }}

    QLabel#dialogTitle {{
        color: {COLOR_TEXT};
        font-family: {heading_stack};
        font-size: {fs_dialog_title}px;
        font-weight: 700;
        padding: 3px 0 7px 0;
    }}

    QTextBrowser {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {RADIUS_MEDIUM}px;
        padding: 12px 14px;
        font-family: {ui_stack};
        font-size: 12px;
    }}

    QWidget#welcomePage {{
        background: {COLOR_EDITOR};
    }}

    QScrollArea#welcomeScroll {{
        background: {COLOR_EDITOR};
        border: 0;
    }}

    QWidget#welcomeContent {{
        background: {COLOR_EDITOR};
    }}

    QLabel#welcomeCover {{
        background: transparent;
        border: 0;
    }}

    QLabel#welcomeKicker {{
        color: {COLOR_TEXT_FAINT};
        font-size: {fs_caption}px;
        font-weight: 650;
        letter-spacing: 1px;
        text-transform: uppercase;
    }}

    QLabel#welcomeTitle {{
        color: {COLOR_TEXT};
        font-family: {heading_stack};
        font-size: {fs_page}px;
        font-weight: 750;
        letter-spacing: -0.4px;
    }}

    QLabel#welcomeSubtitle {{
        color: {COLOR_TEXT_MUTED};
        font-size: 13px;
    }}

    QLabel#welcomeSectionTitle {{
        color: {COLOR_TEXT};
        font-size: {fs_section}px;
        font-weight: 650;
    }}

    QLabel#welcomeMuted {{
        color: {COLOR_TEXT_MUTED};
        font-size: 12px;
    }}

    QLabel#welcomeMuted[state="ready"] {{ color: {COLOR_SUCCESS}; }}
    QLabel#welcomeMuted[state="warning"] {{ color: {COLOR_WARNING}; }}

    QFrame#welcomeBox {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {RADIUS_MEDIUM}px;
    }}

    QPushButton#welcomeRecent {{
        text-align: left;
        background: transparent;
        border-color: transparent;
    }}

    QPushButton#welcomeRecent:hover {{
        background: {COLOR_HOVER};
        border-color: {COLOR_BORDER_SOFT};
    }}

    QWidget#diagnosticsPanel {{
        background: {COLOR_SURFACE};
    }}

    QTreeView {{
        background: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        border: 0;
        padding: 5px 4px;
        alternate-background-color: {COLOR_SURFACE_ALT};
        outline: 0;
    }}

    QAbstractItemView {{
        background: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        alternate-background-color: {COLOR_SURFACE_ALT};
        selection-background-color: {COLOR_SELECTED};
        selection-color: {COLOR_TEXT};
        outline: 0;
    }}

    QTreeView::item {{
        border-radius: {RADIUS_SMALL}px;
        min-height: {minh_row}px;
        padding: 2px 6px;
    }}

    QTreeView::item:hover {{
        background: {COLOR_HOVER};
    }}

    QTreeView::item:selected {{
        background: {COLOR_SELECTED};
        color: {COLOR_TEXT};
    }}

    QScrollArea#sidebarScroll {{
        background: {COLOR_SURFACE};
        border: 0;
    }}

    QWidget#insertPanel,
    QWidget#templatesPanel,
    QWidget#referencesPanel,
    QWidget#labelsPanel {{
        background: {COLOR_SURFACE};
    }}

    QWidget#templatesPanel QComboBox {{
        min-height: 30px;
        font-weight: 600;
    }}

    QPushButton#toolCard {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        color: {COLOR_TEXT};
        font-weight: 600;
        padding: 7px 9px;
        text-align: left;
    }}

    QPushButton#toolCard:hover {{
        background: {COLOR_HOVER};
        border-color: {COLOR_BORDER_SOFT};
        color: {COLOR_TEXT};
    }}

    QPushButton#toolCard:pressed {{
        background: {COLOR_PRESSED};
    }}

    QTabWidget::pane {{
        border: 0;
        background: {COLOR_SURFACE};
    }}

    QTabBar::tab {{
        background: transparent;
        color: {COLOR_TEXT_MUTED};
        border: 1px solid transparent;
        border-bottom: 0;
        border-radius: 8px;
        min-height: {minh_tab}px;
        padding: 6px 14px;
        margin-right: 2px;
    }}

    QTabBar::tab:hover {{
        background: {COLOR_HOVER};
        color: {COLOR_TEXT};
    }}

    QTabBar::tab:selected {{
        background: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        border-color: {COLOR_BORDER_SOFT};
        border-bottom-color: {COLOR_ACCENT};
        font-weight: 600;
    }}

    QTabWidget#bottomTabs QTabBar::tab {{
        min-height: {minh_tab_compact}px;
        padding: 5px 12px;
    }}

    QPlainTextEdit {{
        background: {COLOR_EDITOR};
        color: {COLOR_TEXT};
        border: 0;
        padding: 16px 18px;
        selection-background-color: #d9dde2;
        selection-color: #111315;
        font-family: {editor_stack};
        font-size: {fs_mono}px;
    }}

    QTextEdit {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT};
        border: 0;
        padding: 8px 11px;
        selection-background-color: #d9dde2;
        selection-color: #111315;
        font-family: {editor_stack};
        font-size: 11px;
    }}

    QWidget#findReplaceBar,
    QWidget#pdfToolbar {{
        background: {COLOR_SURFACE_ALT};
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
    }}

    QWidget#pdfEmptyState {{
        background: #f3f3f1;
        border: 0;
    }}

    QLabel#pdfFreshnessBanner {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT_MUTED};
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
        padding: 3px 10px;
        font-size: 11px;
    }}

    QLabel#pdfFreshnessBanner[severity="success"] {{ color: {COLOR_SUCCESS}; }}
    QLabel#pdfFreshnessBanner[severity="warning"] {{ color: {COLOR_WARNING}; }}
    QLabel#pdfFreshnessBanner[severity="error"] {{ color: {COLOR_ERROR}; }}

    QLabel#pdfEmptyIcon {{
        background: transparent;
        border: 0;
    }}

    QLabel#pdfEmptyTitle {{
        color: {COLOR_TEXT};
        font-family: {heading_stack};
        font-size: 13px;
        font-weight: 650;
    }}

    QWidget#findReplaceBar QLabel,
    QWidget#pdfToolbar QLabel {{
        color: {COLOR_TEXT_MUTED};
    }}

    QWidget#findReplaceBar QPushButton,
    QWidget#pdfToolbar QPushButton {{
        padding: 3px 7px;
        min-height: 22px;
    }}

    QWidget#pdfToolbar QPushButton#iconButton {{
        min-width: {icon_large}px;
        max-width: {icon_large}px;
        min-height: {icon_large}px;
        max-height: {icon_large}px;
        padding: 0;
        border-color: transparent;
    }}

    QWidget#findReplaceBar QLineEdit,
    QWidget#pdfToolbar QLineEdit {{
        min-width: 140px;
    }}

    QTableWidget {{
        background: {COLOR_SURFACE};
        alternate-background-color: {COLOR_SURFACE_ALT};
        border: 0;
        gridline-color: {COLOR_BORDER_SOFT};
        selection-background-color: {COLOR_SELECTED};
        selection-color: {COLOR_TEXT};
    }}

    QHeaderView::section {{
        background: {COLOR_SURFACE_ALT};
        color: {COLOR_TEXT_MUTED};
        border: 0;
        border-bottom: 1px solid {COLOR_BORDER_SOFT};
        padding: 6px 8px;
        font-weight: 600;
    }}

    QPushButton {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        color: {COLOR_TEXT};
        padding: 7px 13px;
        min-height: {minh_control}px;
    }}

    QPushButton:hover {{
        background: {COLOR_HOVER};
        border-color: #cfcfca;
    }}

    QPushButton:pressed {{
        background: {COLOR_PRESSED};
    }}

    QPushButton:focus {{
        border-color: {COLOR_ACCENT};
    }}

    QPushButton#primaryButton {{
        background: {COLOR_ACCENT};
        border-color: {COLOR_ACCENT};
        color: {COLOR_SURFACE};
        font-weight: 600;
    }}

    QPushButton#primaryButton:hover {{
        background: {COLOR_ACCENT_HOVER};
        border-color: {COLOR_ACCENT_HOVER};
    }}

    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        color: {COLOR_TEXT};
        padding: 6px 10px;
        min-height: {minh_compact}px;
    }}

    QLineEdit:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus,
    QComboBox:focus {{
        border-color: {COLOR_ACCENT};
        background: {COLOR_SURFACE};
    }}

    QComboBox#engineSelector {{
        padding: 5px 28px 5px 10px;
        min-height: {minh_compact}px;
        min-width: {eng_min_width}px;
    }}

    QComboBox#engineSelector:hover {{
        background: {COLOR_HOVER};
        border-color: #cfcfca;
    }}

    QComboBox::drop-down {{
        border: 0;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background: {COLOR_SURFACE};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER};
        selection-background-color: {COLOR_SELECTED};
        selection-color: {COLOR_TEXT};
        padding: 4px;
    }}

    QComboBox QAbstractItemView::item {{
        min-height: 30px;
        padding: 7px 12px;
    }}

    QComboBox QAbstractItemView::item:selected {{
        background: {COLOR_SELECTED};
        color: {COLOR_TEXT};
    }}

    QComboBox QAbstractItemView::item:hover {{
        background: {COLOR_HOVER};
        color: {COLOR_TEXT};
    }}

    QProgressBar#compileProgress {{
        background: {COLOR_HOVER};
        border: 1px solid {COLOR_BORDER};
        border-radius: {RADIUS_MEDIUM}px;
        height: 9px;
        text-align: center;
    }}

    QProgressBar#compileProgress::chunk {{
        background: {COLOR_ACCENT};
        border-radius: 6px;
    }}

    QLabel#compileTimer {{
        color: {COLOR_TEXT_MUTED};
        min-width: 92px;
    }}

    QLabel#statusPill {{
        color: {COLOR_TEXT_MUTED};
        background: {COLOR_SURFACE_ALT};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: 8px;
        padding: 4px 9px;
        margin-left: 3px;
    }}

    QLabel#statusPill[state="active"] {{
        color: {COLOR_ACCENT};
        background: {COLOR_SELECTED};
        border-color: #f0d9b8;
    }}

    QLabel#compileTimer[state="active"] {{ color: {COLOR_ACCENT}; }}
    QLabel#compileTimer[state="success"] {{ color: {COLOR_SUCCESS}; }}
    QLabel#compileTimer[state="error"] {{ color: {COLOR_ERROR}; }}

    QLabel#wordCountMeta {{
        color: {COLOR_TEXT_MUTED};
        font-size: 12px;
    }}

    QWidget#wordHighlightPanel {{
        background: {COLOR_SURFACE};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {RADIUS_MEDIUM}px;
        padding: 8px;
    }}

    QLabel#wordHighlightLegend {{
        color: {COLOR_TEXT_MUTED};
        font-size: 11px;
    }}

    QTextBrowser#wordHighlightPreview {{
        background: {COLOR_EDITOR};
        color: {COLOR_TEXT};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {RADIUS_MEDIUM}px;
        padding: 10px 12px;
        selection-background-color: #d9dde2;
        selection-color: #111315;
        font-family: {editor_stack};
    }}

    QScrollArea#wordScroll {{
        background: {COLOR_SURFACE};
        border: none;
    }}

    QWidget#wordPanel {{
        background: {COLOR_SURFACE};
    }}

    QWidget#wordStat {{
        background: {COLOR_SURFACE_ALT};
        border: 1px solid {COLOR_BORDER_SOFT};
        border-radius: {RADIUS_MEDIUM}px;
        min-height: 68px;
    }}

    QLabel#wordStatLabel {{
        color: {COLOR_TEXT_MUTED};
        font-size: 11px;
        font-weight: 600;
        min-height: 16px;
    }}

    QLabel#wordStatValue {{
        color: {COLOR_TEXT};
        font-size: 19px;
        font-weight: 700;
        min-height: 28px;
    }}

    QWidget#wordBreakdown {{
        background: transparent;
        border: none;
    }}

    QLabel#wordBreakdownTitle {{
        color: {COLOR_TEXT};
        font-size: 12px;
        font-weight: 650;
    }}

    QLabel#wordBreakdownHint {{
        color: {COLOR_TEXT_MUTED};
        font-size: 11px;
    }}

    QLabel#wordCategoryLabel,
    QLabel#wordCategoryValue {{
        color: {COLOR_TEXT_MUTED};
        font-size: 11px;
    }}

    QLabel#wordCategoryValue {{
        color: {COLOR_TEXT};
        font-weight: 600;
    }}

    QProgressBar#wordCategoryBar {{
        background: #e8e9e6;
        border: none;
        border-radius: 6px;
    }}

    QProgressBar#wordCategoryBar::chunk {{
        background: #587f8c;
        border-radius: 6px;
    }}

    QProgressBar#wordCategoryBar[category="effective"]::chunk {{ background: #3478c4; }}
    QProgressBar#wordCategoryBar[category="headers"]::chunk {{ background: #7a62a3; }}
    QProgressBar#wordCategoryBar[category="captions"]::chunk {{ background: #348568; }}
    QProgressBar#wordCategoryBar[category="math_inline"]::chunk {{ background: #c47a36; }}
    QProgressBar#wordCategoryBar[category="math_display"]::chunk {{ background: #b85869; }}
    QProgressBar#wordCategoryBar[category="numbers"]::chunk {{ background: #587f8c; }}

    QStatusBar {{
        background: {COLOR_SURFACE};
        border-top: 1px solid {COLOR_BORDER_SOFT};
        color: {COLOR_TEXT_MUTED};
        padding: 3px 8px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 9px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical {{
        background: #c9c9c2;
        border-radius: 4px;
        min-height: 28px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #a9aaa4;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 9px;
        margin: 2px;
    }}

    QScrollBar::handle:horizontal {{
        background: #c9c9c2;
        border-radius: 4px;
        min-width: 28px;
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    """


def _ui_font_stack() -> list[str]:
    return _resolved_font_stack(UI_LATIN_SANS_FONT_CANDIDATES, CJK_SANS_FONT_CANDIDATES)


def _editor_font_stack() -> list[str]:
    return _resolved_font_stack(LATIN_MONO_FONT_CANDIDATES, CJK_SERIF_FONT_CANDIDATES)


def _heading_font_stack() -> list[str]:
    return _resolved_font_stack(UI_LATIN_SANS_FONT_CANDIDATES, CJK_SERIF_FONT_CANDIDATES)


def _resolved_font_stack(*candidate_groups: list[str]) -> list[str]:
    available = set(QFontDatabase.families())
    resolved: list[str] = []
    for candidates in candidate_groups:
        family = next((candidate for candidate in candidates if candidate in available), None)
        if family is not None and family not in resolved:
            resolved.append(family)
    return resolved or [candidate_groups[0][-1]]


def _qss_font_stack(families: list[str]) -> str:
    return ", ".join(f'"{family}"' for family in families)


def _register_platform_fonts() -> None:
    global _SYSTEM_SF_MONO_FONT_ID
    if sys.platform != "darwin" or _SYSTEM_SF_MONO_FONT_ID is not None:
        return
    system_sf_mono = Path("/System/Library/Fonts/SFNSMono.ttf")
    _SYSTEM_SF_MONO_FONT_ID = (
        QFontDatabase.addApplicationFont(str(system_sf_mono)) if system_sf_mono.is_file() else -1
    )
