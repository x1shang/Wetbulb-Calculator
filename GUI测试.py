from PySide2.QtWidgets import QApplication
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QObject

class MainWindow(QObject):
    def __init__(self):
        super().__init__()
        # 加载主窗口
        self.ui = QUiLoader().load('calculator.ui')
        # 绑定信号
        self.bind_events()
        # 初始化模式
        self.update_input_labels()
        self.ui.widget_iteration.setVisible(True)
        self.temp_min = -150
        self.temp_max = 200
        self.pressure_min = 500
        self.pressure_max = 1100

    def bind_events(self):
        """绑定按钮和单选按钮事件"""
        # 模式切换
        self.ui.radioButton_2.toggled.connect(self.update_input_labels)
        self.ui.radioButton.toggled.connect(self.update_input_labels)
        # 计算按钮
        self.ui.lineEdit_2.returnPressed.connect(self.validate_and_calculate)
        self.ui.lineEdit_2.returnPressed.connect(lambda:self.check_input(self.ui.lineEdit_2,"大气压强",*self.upp()))
        # 单位切换
        self.ui.pushButton_5.clicked.connect(self.show_unit_dialog)
        # 关于按钮
        self.ui.pushButton_4.clicked.connect(self.show_about_dialog)
        # 转换焦点
        self.ui.lineEdit_3.returnPressed.connect(lambda:self.ui.lineEdit.setFocus())
        self.ui.lineEdit_3.returnPressed.connect(lambda:self.check_input(self.ui.lineEdit_3,"干球温度",*self.upt()))
        self.ui.lineEdit.returnPressed.connect(lambda:self.ui.lineEdit_2.setFocus())
        self.ui.lineEdit.returnPressed.connect(
            lambda:self.check_input(self.ui.lineEdit,self.ui.label_2.text(),*self.upt())
        )

    def upp(self):
        return (self.pressure_min,self.pressure_max)

    def upt(self):
        return (self.temp_min,self.temp_max)

    def update_input_labels(self):
        """根据模式更新输入标签"""
        if self.ui.radioButton_2.isChecked():  # 已知露点求湿球
            self.ui.label_2.setText("露点温度：")
            self.ui.widget_iteration.setVisible(True)
        else:  # 已知湿球求露点
            self.ui.label_2.setText("湿球温度：")
            self.ui.widget_iteration.setVisible(False)

    def check_input(self, line_edit, field_name, min_v, max_v):
        text = line_edit.text().strip()
        if not text:
            self.show_error_dialog(f"{field_name}不能为空！")
            line_edit.clear()
            return False
        try:
            # 清理非数字字符（保留负号和小数点）
            cleaned_text = ''.join(filter(lambda x: x.isdigit() or x in ('.', '-'), text))
            value = float(cleaned_text)
            if value < min_v or value > max_v:
                self.show_error_dialog(f"输入值需在 [{min_v}, {max_v}] 范围内")
                line_edit.clear()
                return False
            return True
        except ValueError:
            self.show_error_dialog(f"{field_name}必须是有效数字！")
            line_edit.clear()
            return False

    def validate_and_calculate(self):
        try:
            # 验证干球温度
            if not self.check_input(self.ui.lineEdit_3,"干球温度",self.temp_min,self.temp_max):
                return
            T = float(self.ui.lineEdit_3.text())

            # 验证湿球/露点温度
            target_label = self.ui.label_2.text()
            if not self.check_input(self.ui.lineEdit,target_label,self.temp_min,self.temp_max):
                return
            T_other = float(self.ui.lineEdit.text())

            # 验证压强
            if not self.check_input(self.ui.lineEdit_2,"大气压强",self.pressure_min,self.pressure_max):
                return
            P = float(self.ui.lineEdit_2.text())

            # 检查温度逻辑关系
            if T_other>=T:
                raise ValueError(f"{target_label}不能高于干球温度！")

            # 执行计算...
            print("输入验证通过，执行计算...")

        except Exception as e:
            self.show_error_dialog(str(e))


    def show_error_dialog(self,message):
        """显示错误对话框"""
        error_dialog = QUiLoader().load('err.ui')
        error_dialog.textBrowser.setPlainText(message)
        error_dialog.pushButton.clicked.connect(error_dialog.close)
        error_dialog.exec_()

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
        # 压强单位映射
        pressure_units = {
            self.ui.radioButton:('Pa',50000,110000),
            self.ui.radioButton_3:('hPa',500,1100),
            self.ui.radioButton_4:('mmHg',375,825),
            self.ui.radioButton_5:('cmHg',37.5,82.5),
            self.ui.radioButton_2:('bar',0.5,1.1)
        }
        # 温度单位映射
        temperature_units = {
            self.ui.radioButton_6: ('K', 125, 473),  # -150℃=123.15K, 200℃=473.15K
            self.ui.radioButton_7: ('℃', -150, 200),
            self.ui.radioButton_8: ('℉', -238, 392)        # -150℃=-238℉, 200℃=392℉
        }
        # 更新压强单位
        for rb,(unit,min_val,max_val) in pressure_units.items():
            if rb.isChecked():
                self.main_window.pressure_min = min_val
                self.main_window.pressure_max = max_val
                self.main_window.ui.lineEdit_2.setPlaceholderText(f'{min_val}~{max_val}{unit}')
                self.main_window.pressure_unit = unit
                break
        # 更新温度单位
        for rb,(unit,min_val,max_val) in temperature_units.items():
            if rb.isChecked():
                self.main_window.temp_min = min_val
                self.main_window.temp_max = max_val
                self.main_window.ui.lineEdit_3.setPlaceholderText(f'{min_val}~{max_val}{unit}')
                self.main_window.ui.lineEdit.setPlaceholderText(f'{min_val}~{max_val}{unit} 且小于干球')
                self.main_window.temperature_unit = unit
                break
        self.ui.close()

if __name__ == '__main__':
    app = QApplication([])
    main_window = MainWindow()
    main_window.ui.show()
    app.exec_()