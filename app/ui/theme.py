from __future__ import annotations


def style_for_theme(theme: str) -> str:
    return LIGHT_STYLE if theme == "light" else DARK_STYLE


DARK_STYLE = """
QWidget {
    background: #0F131A;
    color: #E7ECF3;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}
*:focus {
    outline: none;
}
QFrame[panel="true"], QListView, QTableView, QPlainTextEdit, QLineEdit, QScrollArea {
    background: #151B24;
    border: 1px solid #2B3546;
    border-radius: 10px;
}
QPushButton {
    background: #1B2330;
    border: 1px solid #2B3546;
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 20px;
    outline: none;
}
QPushButton:focus { outline: none; }
QPushButton:hover { background: #222C3B; }
QPushButton[primary="true"] {
    background: #7B61FF;
    border-color: #7B61FF;
}
QPushButton[primary="true"]:hover {
    background: #8B74FF;
    border-color: #9A86FF;
}
QPushButton[primary="true"]:pressed {
    background: #6047D9;
    border-color: #6047D9;
    padding-top: 8px;
    padding-bottom: 6px;
}
QFrame[choiceBar="true"] {
    background: transparent;
    border: none;
}
QPushButton[choiceButton="true"] {
    padding: 6px 10px;
    min-height: 18px;
}
QPushButton[choiceButton="true"]:checked {
    background: #334057;
    border-color: #7B61FF;
    color: #FFFFFF;
}
QPushButton[choiceButton="true"]:hover {
    background: #273348;
    border-color: #7B61FF;
}
QPushButton[choiceButton="true"]:pressed {
    background: #202A3B;
}
QPushButton[danger="true"] {
    background: #3A2030;
    border-color: #FF5C7A;
}
QPushButton[titleButton="true"] {
    background: transparent;
    border: none;
    padding: 0;
}
QPushButton[titleButton="true"]:hover { background: #222C3B; }
QPushButton[closeButton="true"]:hover { background: #B93245; }
QLabel[muted="true"] { color: #93A0B3; }
QLabel[ok="true"] { color: #76E2A7; }
QLabel[ok="false"] { color: #FFB86B; }
QFrame QLabel, QWidget QLabel, QCheckBox {
    background: transparent;
}
QLineEdit, QPlainTextEdit { padding: 8px; selection-background-color: #7B61FF; }
QLineEdit#ChipEditor {
    padding: 0 2px;
    border: none;
    background: transparent;
}
QCheckBox { spacing: 6px; background: transparent; }
QTabBar::tab {
    background: #151B24;
    border: 1px solid #2B3546;
    padding: 9px 18px;
    border-radius: 8px;
    margin-right: 6px;
}
QTabBar::tab:selected { background: #222C3B; border-color: #7B61FF; }
QTabWidget::pane {
    background: #0F131A;
    border: 1px solid #2B3546;
    border-radius: 10px;
    top: -1px;
}
QSplitter::handle { background: #2B3546; }
QListView:focus, QTableView:focus, QScrollArea:focus, QPlainTextEdit:focus, QLineEdit:focus {
    outline: none;
    border-color: #2B3546;
}
QScrollArea > QWidget > QWidget {
    background: #151B24;
}
QScrollBar:vertical { width: 12px; background: transparent; }
QScrollBar::handle:vertical { background: #2B3546; border-radius: 6px; min-height: 28px; }
QSlider::groove:horizontal { height: 6px; background: #2B3546; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; background: #7B61FF; border-radius: 8px; }
QProgressBar {
    height: 6px;
    background: #2B3546;
    border: none;
    border-radius: 3px;
}
QProgressBar::chunk {
    background: #7B61FF;
    border-radius: 3px;
}
QTableView {
    gridline-color: #2B3546;
    background: #151B24;
    alternate-background-color: #151B24;
    selection-background-color: #2D285A;
    selection-color: #FFFFFF;
}
QTableView::item { padding: 6px; }
QTableView::item:selected { background: #2D285A; color: #FFFFFF; }
QHeaderView::section { background: #1B2330; border: none; padding: 7px; }
QPushButton#ChipCloseButton {
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    padding: 0;
    border-radius: 9px;
}
QPushButton#ChipCloseButton:disabled {
    color: transparent;
    border-color: transparent;
    background: transparent;
}
QFrame[section="true"] {
    background: #111823;
    border: 1px solid #2B3546;
    border-radius: 10px;
}
"""


LIGHT_STYLE = """
QWidget {
    background: #F4F7FB;
    color: #172033;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}
*:focus {
    outline: none;
}
QFrame[panel="true"], QListView, QTableView, QPlainTextEdit, QLineEdit, QScrollArea {
    background: #FFFFFF;
    border: 1px solid #D7DFEC;
    border-radius: 10px;
}
QPushButton {
    background: #EEF3FA;
    border: 1px solid #D7DFEC;
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 20px;
    outline: none;
}
QPushButton:focus { outline: none; }
QPushButton:hover { background: #E4EBF6; }
QPushButton[primary="true"] {
    background: #5A6CFF;
    border-color: #5A6CFF;
    color: #FFFFFF;
}
QPushButton[primary="true"]:hover {
    background: #6C7CFF;
    border-color: #7F8DFF;
}
QPushButton[primary="true"]:pressed {
    background: #4354D9;
    border-color: #4354D9;
    padding-top: 8px;
    padding-bottom: 6px;
}
QFrame[choiceBar="true"] {
    background: transparent;
    border: none;
}
QPushButton[choiceButton="true"] {
    padding: 6px 10px;
    min-height: 18px;
}
QPushButton[choiceButton="true"]:checked {
    background: #DDE5FF;
    border-color: #5A6CFF;
    color: #172033;
}
QPushButton[choiceButton="true"]:hover {
    background: #EAF0FF;
    border-color: #5A6CFF;
}
QPushButton[choiceButton="true"]:pressed {
    background: #D4DEFF;
}
QPushButton[danger="true"] {
    background: #FFEAF0;
    border-color: #E04C67;
    color: #7A1F32;
}
QPushButton[titleButton="true"] {
    background: transparent;
    border: none;
    padding: 0;
}
QPushButton[titleButton="true"]:hover { background: #E4EBF6; }
QPushButton[closeButton="true"]:hover { background: #E04C67; color: #FFFFFF; }
QLabel[muted="true"] { color: #68778D; }
QLabel[ok="true"] { color: #168354; }
QLabel[ok="false"] { color: #B96E13; }
QFrame QLabel, QWidget QLabel, QCheckBox {
    background: transparent;
}
QLineEdit, QPlainTextEdit { padding: 8px; selection-background-color: #5A6CFF; }
QLineEdit#ChipEditor {
    padding: 0 2px;
    border: none;
    background: transparent;
}
QCheckBox { spacing: 6px; background: transparent; }
QTabBar::tab {
    background: #FFFFFF;
    border: 1px solid #D7DFEC;
    padding: 9px 18px;
    border-radius: 8px;
    margin-right: 6px;
}
QTabBar::tab:selected { background: #EAF0FF; border-color: #5A6CFF; }
QTabWidget::pane {
    background: #F4F7FB;
    border: 1px solid #D7DFEC;
    border-radius: 10px;
    top: -1px;
}
QSplitter::handle { background: #D7DFEC; }
QListView:focus, QTableView:focus, QScrollArea:focus, QPlainTextEdit:focus, QLineEdit:focus {
    outline: none;
    border-color: #D7DFEC;
}
QScrollArea > QWidget > QWidget {
    background: #FFFFFF;
}
QScrollBar:vertical { width: 12px; background: transparent; }
QScrollBar::handle:vertical { background: #C7D2E2; border-radius: 6px; min-height: 28px; }
QSlider::groove:horizontal { height: 6px; background: #D7DFEC; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; background: #5A6CFF; border-radius: 8px; }
QProgressBar {
    height: 6px;
    background: #D7DFEC;
    border: none;
    border-radius: 3px;
}
QProgressBar::chunk {
    background: #5A6CFF;
    border-radius: 3px;
}
QTableView {
    gridline-color: #D7DFEC;
    background: #FFFFFF;
    alternate-background-color: #FFFFFF;
    selection-background-color: #DDE5FF;
    selection-color: #172033;
}
QTableView::item { padding: 6px; }
QTableView::item:selected { background: #DDE5FF; color: #172033; }
QHeaderView::section { background: #EEF3FA; border: none; padding: 7px; }
QPushButton#ChipCloseButton {
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
    padding: 0;
    border-radius: 9px;
}
QPushButton#ChipCloseButton:disabled {
    color: transparent;
    border-color: transparent;
    background: transparent;
}
QFrame[section="true"] {
    background: #FFFFFF;
    border: 1px solid #D7DFEC;
    border-radius: 10px;
}
"""


STYLE = DARK_STYLE
