THEMES = {
    "midnight": """
        QWidget {
            background: #0c0d14;
            color: #ececff;
            font-size: 13px;
        }
        #sidebar {
            background: #111323;
            border: 1px solid #252944;
            border-radius: 18px;
        }
        #card {
            background: #121522;
            border: 1px solid #242943;
            border-radius: 16px;
        }
        #pageTitle {
            font-size: 25px;
            font-weight: 700;
        }
        #pageSubtitle, .muted, #cardHint, #sidebarFooter {
            color: #9299bd;
        }
        #cardTitle {
            font-size: 15px;
            font-weight: 700;
            color: #f6f4ff;
        }
        #statusPill {
            background: #1a2233;
            border: 1px solid #313b5f;
            border-radius: 9px;
            padding: 7px 9px;
            color: #bcb4ff;
        }
        #statusValue {
            color: #bdaeff;
            font-weight: 700;
            letter-spacing: 1px;
        }
        #metricValue {
            font-size: 20px;
            font-weight: 700;
        }
        QPushButton {
            background: #1b2031;
            border: 1px solid #313852;
            border-radius: 10px;
            padding: 9px 12px;
        }
        QPushButton:hover {
            background: #252b42;
            border-color: #6f63b8;
        }
        QPushButton:pressed {
            background: #171b29;
        }
        QPushButton[navButton="true"] {
            text-align: left;
            background: transparent;
            border: 1px solid transparent;
            padding: 11px 12px;
            color: #a7acc9;
        }
        QPushButton[navButton="true"]:hover {
            background: #191e30;
        }
        QPushButton[navButton="true"]:checked {
            background: #272144;
            border-color: #584d8c;
            color: #eeeaff;
        }
        QLineEdit, QComboBox, QDoubleSpinBox, QPlainTextEdit, QListWidget {
            background: #0f121c;
            border: 1px solid #2a3047;
            border-radius: 10px;
            padding: 8px 10px;
            selection-background-color: #51458e;
        }
        QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus, QListWidget:focus {
            border-color: #6c5fc0;
        }
        QCheckBox {
            spacing: 8px;
        }
        QTabWidget::pane {
            border: none;
        }
        QTableWidget {
            background: #0f121c;
            border: 1px solid #292f45;
            border-radius: 10px;
            gridline-color: #22273a;
            alternate-background-color: #111522;
        }
        QHeaderView::section {
            background: #171b29;
            color: #9ca4c6;
            border: none;
            border-bottom: 1px solid #2a3047;
            padding: 9px;
            font-weight: 700;
        }
        QTableWidget::item {
            padding: 6px;
        }
        QTableWidget::item:selected {
            background: #2a2550;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 10px;
        }
        QScrollBar::handle:vertical {
            background: #343a55;
            border-radius: 5px;
            min-height: 30px;
        }
    """,
    "violet": """
        QWidget { background: #110d18; color: #f5ecfb; font-size: 13px; }
        #sidebar { background: #181020; border: 1px solid #3b2850; border-radius: 18px; }
        #card { background: #17101f; border: 1px solid #3c2950; border-radius: 16px; }
        #pageTitle { font-size: 25px; font-weight: 700; }
        #pageSubtitle, .muted, #cardHint, #sidebarFooter { color: #b5a7bd; }
        #cardTitle { font-size: 15px; font-weight: 700; }
        #statusPill { background: #241732; border: 1px solid #5b3b76; border-radius: 9px; padding: 7px 9px; color: #dfbaff; }
        #statusValue { color: #d7a8ff; font-weight: 700; letter-spacing: 1px; }
        #metricValue { font-size: 20px; font-weight: 700; }
        QPushButton { background: #24182e; border: 1px solid #54366c; border-radius: 10px; padding: 9px 12px; }
        QPushButton:hover { background: #30203c; border-color: #8d5ab2; }
        QPushButton[navButton="true"] { text-align: left; background: transparent; border: 1px solid transparent; padding: 11px 12px; color: #b7a8c1; }
        QPushButton[navButton="true"]:hover { background: #21172a; }
        QPushButton[navButton="true"]:checked { background: #372249; border-color: #70438c; color: #fff1ff; }
        QLineEdit, QComboBox, QDoubleSpinBox, QPlainTextEdit, QListWidget { background: #110d17; border: 1px solid #432c56; border-radius: 10px; padding: 8px 10px; selection-background-color: #6a4783; }
        QCheckBox { spacing: 8px; }
        QTableWidget { background: #110d17; border: 1px solid #432c56; border-radius: 10px; gridline-color: #2f203b; alternate-background-color: #17101f; }
        QHeaderView::section { background: #20162a; color: #c2aecf; border: none; border-bottom: 1px solid #432c56; padding: 9px; font-weight: 700; }
        QTableWidget::item:selected { background: #3b2650; }
    """,
    "dawn": """
        QWidget { background: #f3f4fb; color: #262936; font-size: 13px; }
        #sidebar { background: #ffffff; border: 1px solid #d8dbe8; border-radius: 18px; }
        #card { background: #ffffff; border: 1px solid #d9dce8; border-radius: 16px; }
        #pageTitle { font-size: 25px; font-weight: 700; }
        #pageSubtitle, .muted, #cardHint, #sidebarFooter { color: #72778c; }
        #cardTitle { font-size: 15px; font-weight: 700; }
        #statusPill { background: #f0effa; border: 1px solid #d7d2ef; border-radius: 9px; padding: 7px 9px; color: #65579f; }
        #statusValue { color: #6b5aa4; font-weight: 700; letter-spacing: 1px; }
        #metricValue { font-size: 20px; font-weight: 700; }
        QPushButton { background: #eef0f7; border: 1px solid #d4d7e3; border-radius: 10px; padding: 9px 12px; }
        QPushButton:hover { background: #e4e6f0; border-color: #aaa2cf; }
        QPushButton[navButton="true"] { text-align: left; background: transparent; border: 1px solid transparent; padding: 11px 12px; color: #64697c; }
        QPushButton[navButton="true"]:checked { background: #eeeafb; border-color: #d2cce9; color: #4d416d; }
        QLineEdit, QComboBox, QDoubleSpinBox, QPlainTextEdit, QListWidget { background: #fbfbfe; border: 1px solid #d5d8e4; border-radius: 10px; padding: 8px 10px; selection-background-color: #c7c0e6; }
        QTableWidget { background: #fbfbfe; border: 1px solid #d5d8e4; border-radius: 10px; gridline-color: #e4e6ee; alternate-background-color: #f6f7fb; }
        QHeaderView::section { background: #f0f1f6; color: #656a7b; border: none; border-bottom: 1px solid #d5d8e4; padding: 9px; font-weight: 700; }
        QTableWidget::item:selected { background: #e6e1f6; }
    """,
}
