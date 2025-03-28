
from PySide2.QtWidgets import QApplication, QMessageBox, QWidget
from PySide2.QtUiTools import QUiLoader

class Stats:

    def __init__(self):
        self.ui = QUiLoader().load('calculator.ui')


app = QApplication([])
stats = Stats()
stats.ui.show()
app.exec_()