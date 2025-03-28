import sys
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QButtonGroup
)
from PySide2.QtGui import QDoubleValidator
from PySide2.QtCore import Qt

class TemperatureCalculatorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多功能温度计 GUI版")
        self.setup_ui()

    def setup_ui(self):
        # 主布局：垂直排列所有组件
        main_layout = QVBoxLayout()

        # --- 模式选择 ---
        self.mode_group = QButtonGroup(self)
        # 创建两个单选按钮
        self.mode1_radio = QRadioButton("求湿球")
        self.mode2_radio = QRadioButton("求露点")
        self.mode_group.addButton(self.mode1_radio, 1)
        self.mode_group.addButton(self.mode2_radio, 2)
        self.mode1_radio.setChecked(True)  # 默认选择模式1

        # 将单选按钮放入水平布局
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode1_radio)
        mode_layout.addWidget(self.mode2_radio)
        main_layout.addLayout(mode_layout)

        # --- 输入框部分 ---
        input_layout = QVBoxLayout()

        # 干球温度
        self.t_dry_edit = self.create_input("干球温度(℃):", -150, 200)
        input_layout.addLayout(self.t_dry_edit)

        # 动态标签（湿球/露点）
        self.t_secondary_label = QLabel("露点温度(℃):")  # 初始显示露点
        self.t_secondary_edit = QLineEdit()
        self.t_secondary_edit.setValidator(QDoubleValidator(-150, 200, 2))
        input_layout.addWidget(self.t_secondary_label)
        input_layout.addWidget(self.t_secondary_edit)

        # 大气压强
        self.pressure_edit = self.create_input("大气压强(hPa):", 500, 1100)
        input_layout.addLayout(self.pressure_edit)

        main_layout.addLayout(input_layout)

        # --- 计算按钮 ---
        self.calc_btn = QPushButton("开始计算")
        main_layout.addWidget(self.calc_btn, alignment=Qt.AlignCenter)

        # --- 连接信号 ---
        self.mode_group.buttonToggled.connect(self.update_labels)
        self.calc_btn.clicked.connect(self.on_calculate)

        self.setLayout(main_layout)

    def create_input(self, label_text, min_val, max_val):
        """创建带标签和验证器的输入框布局"""
        layout = QHBoxLayout()
        label = QLabel(label_text)
        line_edit = QLineEdit()
        line_edit.setValidator(QDoubleValidator(min_val, max_val, 2))
        layout.addWidget(label)
        layout.addWidget(line_edit)
        return layout

    def update_labels(self, button, checked):
        """根据选择的模式更新标签"""
        if button is self.mode1_radio and checked:
            self.t_secondary_label.setText("露点温度(℃):")
        elif button is self.mode2_radio and checked:
            self.t_secondary_label.setText("湿球温度(℃):")

    def on_calculate(self):
        """点击计算按钮的槽函数"""
        try:
            # 获取输入值
            t_dry = float(self.t_dry_edit.itemAt(1).widget().text())
            t_secondary = float(self.t_secondary_edit.text())
            pressure = float(self.pressure_edit.itemAt(1).widget().text())

            # 根据模式调用不同计算方法
            if self.mode1_radio.isChecked():
                print(f"计算湿球：干球={t_dry}, 露点={t_secondary}, 气压={pressure}")
                # 这里调用你的 calculate_wetbulb 函数
            else:
                print(f"计算露点：干球={t_dry}, 湿球={t_secondary}, 气压={pressure}")
                # 这里调用你的 calculate_dewpoint 函数

        except ValueError:
            print("输入值无效，请检查数字格式和范围")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TemperatureCalculatorGUI()
    window.show()
    sys.exit(app.exec_())