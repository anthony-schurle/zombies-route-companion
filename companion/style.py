STYLE = """
QWidget { background: #151a18; color: #e4e8e0; font-size: 13px; }
QWidget#bar { background: #101512; border-bottom: 1px solid #394038; }
QFrame#card { background: #1c221e; border: 1px solid #394139; border-radius: 7px; }
QFrame#nextCard { background: #23261e; border: 1px solid #65583a; border-radius: 7px; }
QWidget#clear, QLabel, QCheckBox, QRadioButton { background: transparent; }
QLabel#brand { font-size: 17px; font-weight: bold; }
QLabel#hero { font-size: 36px; font-weight: bold; color: #f1f1e9; }
QLabel#small, QLabel#dim { color: #a2afa5; }
QLabel#small { font-size: 11px; }
QLabel#kicker, QLabel#gold, QLabel#green, QLabel#metricName { font-size: 10px; font-weight: bold; letter-spacing: 1.2px; }
QLabel#kicker, QLabel#metricName { color: #aeb8ac; }
QLabel#gold { color: #efba62; }
QLabel#green { color: #79dec1; }
QLabel#section { font-size: 17px; font-weight: bold; }
QLabel#action { font-size: 23px; font-weight: bold; color: #f4e9cf; }
QLabel#number { font-size: 23px; font-weight: bold; }
QLabel#status { color: #8bdfc5; font-size: 12px; }
QLabel#error { color: #f1b48d; }
QPushButton, QToolButton { background: #2b322b; border: 1px solid #485247; padding: 7px 12px; border-radius: 4px; font-weight: bold; }
QPushButton:hover, QToolButton:hover { background: #374036; border-color: #788170; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QCheckBox:focus, QTabBar::tab:focus { border: 1px solid #e5ad57; }
QPushButton:disabled { background: #262c25; border-color: #3a4439; color: #849081; }
QPushButton#primary { background: #e6b568; border: 1px solid #ebc480; color: #191c17; }
QPushButton#primary:hover { background: #f5c77e; }
QPushButton#primary:disabled { background: #3e3c2c; color: #a59e84; border: 1px solid #595540; }
QComboBox, QSpinBox { background: #141a16; border: 1px solid #465044; border-radius: 4px; padding: 6px 8px; min-height: 16px; }
QComboBox QAbstractItemView { background: #202820; selection-background-color: #425546; }
QCheckBox { spacing: 9px; padding: 3px 0px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QFrame#rule { color: #3c443b; background: #3c443b; border: none; }
QTabWidget::pane { border: none; }
QTabBar { background: transparent; }
QTabBar::tab { color: #a6b3a7; background: #1c221e; padding: 10px 14px; border-bottom: 2px solid #394139; }
QTabBar::tab:selected { color: #efbd76; border-bottom: 2px solid #e6b568; }
QScrollArea, QTableWidget, QListWidget { border: none; }
QScrollBar:vertical { background: #1b211c; width: 9px; margin: 0; }
QScrollBar::handle:vertical { background: #505a4d; border-radius: 3px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTableWidget { background: #18201a; alternate-background-color: #1d261f; gridline-color: #343e34; }
QHeaderView::section { background: #263027; color: #bac6b9; border: none; padding: 6px; font-size: 11px; }
QToolTip { background: #263027; color: #e4e8e0; border: 1px solid #61715e; padding: 4px; }
"""
