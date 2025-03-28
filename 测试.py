from PySide2.QtWidgets import QApplication,QWidget,QDialog,QMessageBox
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QDoubleValidator  # 改用QDoubleValidator
from PySide2.QtCore import Qt,QObject

class MainWindow(QObject):
    def __init__(self):
        super().__init__()
        self.ui = QUiLoader().load('calculator.ui')
        self.init_units()
        self.bind_events()
        self.update_input_labels()
        self.toggle_iteration_area(False)

    def init_units(self):
        """初始化验证器"""
        # 大气压验证器（使用QDoubleValidator）
        self.pressure_validator = QDoubleValidator()
        self.pressure_validator.setNotation(QDoubleValidator.StandardNotation)
        self.ui.lineEdit_2.setValidator(self.pressure_validator)
        self.update_pressure_validator(500,1100)  # 初始范围

        # 温度验证器（支持负数）
        self.temp_validator = QDoubleValidator()
        self.temp_validator.setNotation(QDoubleValidator.StandardNotation)
        self.ui.lineEdit_3.setValidator(self.temp_validator)
        self.ui.lineEdit.setValidator(self.temp_validator)
        self.update_temperature_validator(-150,200)  # 初始范围

    def bind_events(self):
        self.ui.radioButton_2.toggled.connect(self.update_input_labels)
        self.ui.radioButton.toggled.connect(self.update_input_labels)
        self.ui.pushButton.clicked.connect(self.validate_and_calculate)
        self.ui.pushButton_5.clicked.connect(self.show_unit_dialog)
        self.ui.pushButton_4.clicked.connect(self.show_about_dialog)

    def update_input_labels(self):
        if self.ui.radioButton_2.isChecked():
            self.ui.label_2.setText("露点温度：")
            self.toggle_iteration_area(True)
        else:
            self.ui.label_2.setText("湿球温度：")
            self.toggle_iteration_area(False)

    def toggle_iteration_area(self,visible):
        self.ui.widget_iteration.setVisible(visible)

    def validate_and_calculate(self):
        try:
            T = self.get_input_value(self.ui.lineEdit_3,"干球温度")
            T_other = self.get_input_value(self.ui.lineEdit,self.ui.label_2.text().strip("："))
            P = self.get_input_value(self.ui.lineEdit_2,"大气压强")

            if T_other>=T:
                raise ValueError(f"{self.ui.label_2.text()}不能高于干球温度！")

            print("输入验证通过，执行计算...")

        except Exception as e:
            self.show_error_dialog(str(e))

    def get_input_value(self,line_edit,field_name):
        text = line_edit.text().strip()
        if not text:
            raise ValueError(f"{field_name}不能为空！")
        try:
            value = float(text)
        except:
            raise ValueError(f"{field_name}必须是有效数字！")

        validator = line_edit.validator()
        if isinstance(validator,QDoubleValidator):
            bottom,top = validator.bottom(),validator.top()
            if not (bottom<=value<=top):
                raise ValueError(f"{field_name}需在[{bottom}, {top}]范围内")
        return value

    def show_error_dialog(self,message):
        error_dialog = QUiLoader().load('err.ui')
        error_dialog.textBrowser.setPlainText(message)
        error_dialog.pushButton.clicked.connect(error_dialog.close)
        error_dialog.exec_()

    def update_pressure_validator(self,min_val,max_val):
        """直接更新QDoubleValidator的范围"""
        self.pressure_validator.setRange(min_val,max_val)

    def update_temperature_validator(self,min_val,max_val):
        """更新温度验证范围"""
        self.temp_validator.setRange(min_val,max_val)

    def show_unit_dialog(self):
        unit_dialog = UnitDialog(self)
        unit_dialog.ui.exec_()

    def show_about_dialog(self):
        about_dialog = AboutDialog()
        about_dialog.ui.exec_()

class AboutDialog:
    def __init__(self):
        self.ui = QUiLoader().load('关于.ui')
        self.ui.pushButton.clicked.connect(self.ui.close)

class UnitDialog:
    def __init__(self,main_window):
        self.ui = QUiLoader().load('单位.ui')
        self.main_window = main_window
        self.ui.pushButton.clicked.connect(self.update_units)
        self.ui.pushButton_2.clicked.connect(self.ui.close)

    def update_units(self):
        pressure_units = {
            self.ui.radioButton:('Pa',50000,110000),
            self.ui.radioButton_3:('hPa',500,1100),
            self.ui.radioButton_4:('mmHg',375,825),
            self.ui.radioButton_5:('cmHg',37.5,82.5),
            self.ui.radioButton_2:('bar',0.5,1.1)
        }
        for rb,(unit,min_val,max_val) in pressure_units.items():
            if rb.isChecked():
                self.main_window.ui.lineEdit_2.setPlaceholderText(f'{min_val}~{max_val}{unit}')
                self.main_window.update_pressure_validator(min_val,max_val)
                break
        self.ui.close()

if __name__ == '__main__':
    app = QApplication([])
    main_window = MainWindow()
    main_window.ui.show()
    app.exec_()