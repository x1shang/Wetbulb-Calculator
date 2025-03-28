from PySide2.QtWidgets import QApplication, QWidget, QDialog
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QDoubleValidator  # 正确导入QDoubleValidator
from PySide2.QtCore import Qt

class MainWindow:
    def __init__(self):
        # 加载主窗口
        self.ui = QUiLoader().load('calculator.ui')
        # 初始化默认单位
        self.pressure_unit = 'hPa'
        self.temperature_unit = '℃'
        # 设置初始验证器和提示
        self.update_pressure_validator(500, 1100)
        self.update_temperature_validator(-150, 200)
        # 连接按钮事件
        self.ui.pushButton_4.clicked.connect(self.show_about)
        self.ui.pushButton_5.clicked.connect(self.show_unit)

    def update_pressure_validator(self, min_val, max_val):
        # 更新大气压验证器
        validator = QDoubleValidator(min_val, max_val, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.ui.lineEdit_2.setValidator(validator)

    def update_temperature_validator(self, min_val, max_val):
        # 更新温度验证器（干球和湿球）
        validator = QDoubleValidator(min_val, max_val, 2)
        for line_edit in [self.ui.lineEdit_3, self.ui.lineEdit]:
            line_edit.setValidator(validator)

    def show_about(self):
        about_dialog = AboutDialog()
        about_dialog.ui.exec_()

    def show_unit(self):
        unit_dialog = UnitDialog(self)
        unit_dialog.ui.exec_()

class AboutDialog:
    def __init__(self):
        self.ui = QUiLoader().load('关于.ui')
        self.ui.pushButton.clicked.connect(self.ui.close)

class UnitDialog:
    def __init__(self, main_window):
        self.ui = QUiLoader().load('单位.ui')
        self.main_window = main_window
        self.ui.pushButton.clicked.connect(self.update_units)
        self.ui.pushButton_2.clicked.connect(self.ui.close)

    def update_units(self):
        # 压强单位映射
        pressure_units = {
            self.ui.radioButton: ('Pa', 50000, 110000),
            self.ui.radioButton_3: ('hPa', 500, 1100),
            self.ui.radioButton_4: ('mmHg', 375, 825),
            self.ui.radioButton_5: ('cmHg', 37.5, 82.5),
            self.ui.radioButton_2: ('bar', 0.5, 1.1)
        }
        # 温度单位映射
        temperature_units = {
            self.ui.radioButton_6: ('K', 123.15, 473.15),  # -150℃=123.15K, 200℃=473.15K
            self.ui.radioButton_7: ('℃', -150, 200),
            self.ui.radioButton_8: ('℉', -238, 392)        # -150℃=-238℉, 200℃=392℉
        }
        # 更新压强单位
        for rb, (unit, min_val, max_val) in pressure_units.items():
            if rb.isChecked():
                self.main_window.ui.lineEdit_2.setPlaceholderText(f'{min_val}~{max_val}{unit}')
                self.main_window.update_pressure_validator(min_val, max_val)
                self.main_window.pressure_unit = unit
                break
        # 更新温度单位
        for rb, (unit, min_val, max_val) in temperature_units.items():
            if rb.isChecked():
                # 更新干球和湿球输入的提示
                self.main_window.ui.lineEdit_3.setPlaceholderText(f'{min_val}~{max_val}{unit}')
                self.main_window.ui.lineEdit.setPlaceholderText(f'{min_val}~{max_val}{unit} 且小于干球')
                self.main_window.update_temperature_validator(min_val, max_val)
                self.main_window.temperature_unit = unit
                break
        self.ui.close()

if __name__ == '__main__':
    app = QApplication([])
    main_window = MainWindow()
    main_window.ui.show()
    app.exec_()