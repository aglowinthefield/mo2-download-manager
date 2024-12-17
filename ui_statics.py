try:
    import PyQt6.QtWidgets as QtWidgets
    from PyQt6.QtWidgets import QHeaderView
except ImportError:
    import PyQt5.QtWidgets as QtWidgets
    from PyQt5.QtWidgets import QHeaderView


def create_basic_table_widget():
    """Set the model after creating this. Cleans up window code"""
    table = QtWidgets.QTableView()
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.setSizeAdjustPolicy(
        QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
    )
    table.setShowGrid(False)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(
        QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
        | QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
    )
    table.setMouseTracking(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    return table


def button_with_handler(text, parent, handler):
    button = QtWidgets.QPushButton(text, parent)
    button.clicked.connect(handler)
    return button


def bool_emoji(value: bool):
    if value:
        return "✅"
    return "🚫"
