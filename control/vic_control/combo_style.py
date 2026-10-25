"""Local combobox colors, independent of the Windows menu palette.

Qt's default QComboMenuDelegate paints selected rows like native menu items.
Use the standard item-view delegate so the popup's QSS selection colors and
disabled model flags are honored together. Text still comes from the model.
"""
from PySide6.QtWidgets import QStyledItemDelegate

COMBO_STYLE = '''
QComboBox {
    color: #1f2937;
    background-color: #ffffff;
    selection-color: #ffffff;
    selection-background-color: #1663d6;
}
QComboBox:disabled {
    color: #64748b;
    background-color: #e8edf4;
}
QComboBox QAbstractItemView {
    color: #1f2937;
    background-color: #ffffff;
    selection-color: #ffffff;
    selection-background-color: #1663d6;
    border: 1px solid #b7c5d8;
    outline: 0;
}
QComboBox QAbstractItemView::item {
    min-height: 26px;
    padding: 2px 8px;
}
QComboBox QAbstractItemView::item:hover:enabled {
    color: #1f2937;
    background-color: #dbeafe;
}
QComboBox QAbstractItemView::item:selected:enabled {
    color: #ffffff;
    background-color: #1663d6;
}
QComboBox QAbstractItemView::item:disabled {
    color: #64748b;
    background-color: #f1f5f9;
}
QComboBox QAbstractItemView::item:selected:disabled {
    color: #475569;
    background-color: #cbd5e1;
}
'''


def style_combo(combo):
    combo.setItemDelegate(QStyledItemDelegate(combo))
    combo.setStyleSheet(COMBO_STYLE)
