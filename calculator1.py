# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'C:\Users\zhu_j\Desktop\文件夹\python\晴雨表\calculator1.ui'
#
# Created by: PyQt5 UI code generator 5.15.10
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.

import sys
import os
import json

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        # 打包后的临时资源目录
        base_path = sys._MEIPASS
    else:
        # 开发环境下的当前目录
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_g_value():
    try:
        cfg_path = resource_path('cfg.json')
        with open(cfg_path, 'r') as f:
            config = json.load(f)
            return config.get('g', 9.81)
    except Exception:
        return 9.81

# 全局g值
g = load_g_value()

from PySide2 import QtCore, QtGui, QtWidgets

import qfluentwidgets

class Ui_wetbulb(object):
    def setupUi(self, wetbulb):
        wetbulb.setObjectName("wetbulb")
        wetbulb.resize(618, 635)
        wetbulb.setMinimumSize(QtCore.QSize(618, 635))
        self.verticalLayout_9 = QtWidgets.QVBoxLayout(wetbulb)
        self.verticalLayout_9.setObjectName("verticalLayout_9")
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.verticalLayout_7 = QtWidgets.QVBoxLayout()
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.label8 = QtWidgets.QLabel(wetbulb)
        font = QtGui.QFont()
        font.setFamily("仿宋")
        font.setPointSize(16)
        font.setBold(True)
        font.setUnderline(False)
        font.setWeight(75)
        self.label8.setFont(font)
        self.label8.setStyleSheet("#label8 {\n"
"    color: rgb(71, 148, 157);         /* 文本颜色 */\n"
"    \n"
"}")
        self.label8.setObjectName("label8")
        self.horizontalLayout_6.addWidget(self.label8)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_6.addItem(spacerItem)
        self.verticalLayout_7.addLayout(self.horizontalLayout_6)
        self.horizontalLayout_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label = QtWidgets.QLabel(wetbulb)
        self.label.setObjectName("label")
        self.verticalLayout_3.addWidget(self.label)
        self.label_2 = QtWidgets.QLabel(wetbulb)
        self.label_2.setObjectName("label_2")
        self.verticalLayout_3.addWidget(self.label_2)
        self.label_3 = QtWidgets.QLabel(wetbulb)
        self.label_3.setObjectName("label_3")
        self.verticalLayout_3.addWidget(self.label_3)
        self.horizontalLayout_5.addLayout(self.verticalLayout_3)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.LineEdit_3 = LineEdit(wetbulb)
        self.LineEdit_3.setMinimumSize(QtCore.QSize(181, 33))
        self.LineEdit_3.setObjectName("LineEdit_3")
        self.verticalLayout_2.addWidget(self.LineEdit_3)
        self.LineEdit = LineEdit(wetbulb)
        self.LineEdit.setObjectName("LineEdit")
        self.verticalLayout_2.addWidget(self.LineEdit)
        self.LineEdit_2 = LineEdit(wetbulb)
        self.LineEdit_2.setObjectName("LineEdit_2")
        self.verticalLayout_2.addWidget(self.LineEdit_2)
        self.horizontalLayout_5.addLayout(self.verticalLayout_2)
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.pushButton_6 = qfluentwidgets.PushButton(wetbulb)
        self.pushButton_6.setMinimumSize(QtCore.QSize(41, 111))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.pushButton_6.setFont(font)
        self.pushButton_6.setObjectName("pushButton_6")
        self.horizontalLayout_4.addWidget(self.pushButton_6)
        self.pushButton_7 = qfluentwidgets.PrimaryPushButton(wetbulb)
        self.pushButton_7.setMinimumSize(QtCore.QSize(41, 111))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.pushButton_7.setFont(font)
        self.pushButton_7.setObjectName("pushButton_7")
        self.horizontalLayout_4.addWidget(self.pushButton_7)
        self.horizontalLayout_5.addLayout(self.horizontalLayout_4)
        self.verticalLayout_7.addLayout(self.horizontalLayout_5)
        self.horizontalLayout_7.addLayout(self.verticalLayout_7)
        self.verticalLayout_6 = QtWidgets.QVBoxLayout()
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout()
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.pushButton_2 = qfluentwidgets.ToolButton(wetbulb)
        self.pushButton_2.setObjectName("pushButton_2")
        self.pushButton_2.setIcon(qfluentwidgets.FluentIcon.SYNC)
        self.horizontalLayout.addWidget(self.pushButton_2)
        self.pushButton_3 = qfluentwidgets.ToolButton(wetbulb)
        self.pushButton_3.setObjectName("pushButton_3")
        self.pushButton_3.setIcon(qfluentwidgets.FluentIcon.CAMERA)
        self.horizontalLayout.addWidget(self.pushButton_3)
        self.pushButton_4 = qfluentwidgets.ToolButton(wetbulb)
        self.pushButton_4.setObjectName("pushButton_4")
        self.pushButton_4.setIcon(qfluentwidgets.FluentIcon.TAG)
        self.horizontalLayout.addWidget(self.pushButton_4)
        self.pushButton_5 = qfluentwidgets.PrimaryToolButton(wetbulb)
        self.pushButton_5.setObjectName("pushButton_5")
        self.pushButton_5.setIcon(qfluentwidgets.FluentIcon.SETTING)
        self.horizontalLayout.addWidget(self.pushButton_5)
        self.verticalLayout_4.addLayout(self.horizontalLayout)
        self.ComboBox = qfluentwidgets.ComboBox(wetbulb)
        self.ComboBox.setObjectName("ComboBox")
        self.ComboBox.addItem("")
        self.ComboBox.addItem("")
        self.ComboBox.addItem("")
        self.verticalLayout_4.addWidget(self.ComboBox)
        self.verticalLayout_6.addLayout(self.verticalLayout_4)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout()
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.LineEdit_4 = LineEdit(wetbulb)
        self.LineEdit_4.setMaximumSize(QtCore.QSize(16777215, 33))
        self.LineEdit_4.setObjectName("LineEdit_4")
        self.verticalLayout_5.addWidget(self.LineEdit_4)
        self.label_6 = QtWidgets.QLabel(wetbulb)
        font = QtGui.QFont()
        font.setFamily("AcadEref")
        font.setPointSize(9)
        self.label_6.setFont(font)
        self.label_6.setObjectName("label_6")
        self.verticalLayout_5.addWidget(self.label_6)
        self.label_5 = QtWidgets.QLabel(wetbulb)
        font = QtGui.QFont()
        font.setFamily("AcadEref")
        font.setPointSize(9)
        self.label_5.setFont(font)
        self.label_5.setObjectName("label_5")
        self.verticalLayout_5.addWidget(self.label_5)
        self.horizontalLayout_3.addLayout(self.verticalLayout_5)
        self.dial = QtWidgets.QDial(wetbulb)
        self.dial.setMaximumSize(QtCore.QSize(99, 100))
        self.dial.setObjectName("dial")
        self.horizontalLayout_3.addWidget(self.dial)
        self.verticalLayout_6.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_7.addLayout(self.verticalLayout_6)
        self.verticalLayout_9.addLayout(self.horizontalLayout_7)
        self.horizontalLayout_8 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.widget_iteration = QtWidgets.QGroupBox(wetbulb)
        self.widget_iteration.setMinimumSize(QtCore.QSize(0, 61))
        self.widget_iteration.setObjectName("widget_iteration")
        self.layoutWidget = QtWidgets.QWidget(self.widget_iteration)
        self.layoutWidget.setGeometry(QtCore.QRect(10, 20, 231, 34))
        self.layoutWidget.setObjectName("layoutWidget")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.ComboBox_2 = qfluentwidgets.ComboBox(self.layoutWidget)
        self.ComboBox_2.setObjectName("ComboBox_2")
        self.ComboBox_2.addItem("")
        self.ComboBox_2.addItem("")
        self.horizontalLayout_2.addWidget(self.ComboBox_2)
        self.pushButton = qfluentwidgets.PushButton(self.layoutWidget)
        self.pushButton.setMaximumSize(QtCore.QSize(96, 16777215))
        self.pushButton.setObjectName("pushButton")
        self.horizontalLayout_2.addWidget(self.pushButton)
        self.verticalLayout.addWidget(self.widget_iteration)
        self.listView = QtWidgets.QListView(wetbulb)
        self.listView.setStyleSheet("#listView {\n"
"        background: #f0f0f0;\n"
"        border: 1px solid #ccc;\n"
"        border-radius: 5px;\n"
"    }")
        self.listView.setObjectName("listView")
        self.verticalLayout.addWidget(self.listView)
        self.horizontalLayout_8.addLayout(self.verticalLayout)
        self.verticalLayout_8 = QtWidgets.QVBoxLayout()
        self.verticalLayout_8.setObjectName("verticalLayout_8")
        self.ProgressBar = IndeterminateProgressBar(wetbulb)
        self.ProgressBar.setObjectName("ProgressBar")
        self.verticalLayout_8.addWidget(self.ProgressBar)
        self.listView_2 = QtWidgets.QListView(wetbulb)
        self.listView_2.setStyleSheet("#listView_2 {\n"
"        background: #f0f0f0;\n"
"        border: 1px solid #ccc;\n"
"        border-radius: 5px;\n"
"    }")
        self.listView_2.setObjectName("listView_2")
        self.verticalLayout_8.addWidget(self.listView_2)
        self.horizontalLayout_8.addLayout(self.verticalLayout_8)
        self.verticalLayout_9.addLayout(self.horizontalLayout_8)

        self.retranslateUi(wetbulb)
        QtCore.QMetaObject.connectSlotsByName(wetbulb)

    def retranslateUi(self, wetbulb):
        _translate = QtCore.QCoreApplication.translate
        wetbulb.setWindowTitle(_translate("wetbulb", "湿球温度计"))
        self.label8.setText(_translate("wetbulb", "WetBulb Calculator"))
        self.label.setText(_translate("wetbulb", "干球温度："))
        self.label_2.setText(_translate("wetbulb", "露点温度："))
        self.label_3.setText(_translate("wetbulb", "大气压强："))
        self.LineEdit_3.setPlaceholderText(_translate("wetbulb", "-150~200°C"))
        self.LineEdit.setPlaceholderText(_translate("wetbulb", "-150~200°C"))
        self.LineEdit_2.setPlaceholderText(_translate("wetbulb", "500~1100hPa"))
        self.pushButton_6.setText(_translate("wetbulb", "计\n"
"\n"
"算"))
        self.pushButton_7.setText(_translate("wetbulb", "批\n"
"量\n"
"计\n"
"算"))
        self.ComboBox.setItemText(0, _translate("wetbulb", "已知露点求湿球"))
        self.ComboBox.setItemText(1, _translate("wetbulb", "已知湿球求露点"))
        self.ComboBox.setItemText(2, _translate("wetbulb", "已知相对湿度"))
        self.LineEdit_4.setPlaceholderText(_translate("wetbulb", f"{g:.2f} m/s²"))
        self.label_6.setText(_translate("wetbulb", "<html><head/><body><p align=\"center\">本地重力加速度</p></body></html>"))
        self.label_5.setText(_translate("wetbulb", "<html><head/><body><p align=\"right\">精度调节旋钮</p></body></html>"))
        self.widget_iteration.setTitle(_translate("wetbulb", "迭代区"))
        self.ComboBox_2.setItemText(0, _translate("wetbulb", "Tw=Td"))
        self.ComboBox_2.setItemText(1, _translate("wetbulb", "Tw=T-n"))
        self.pushButton.setText(_translate("wetbulb", "显示迭代图"))
from qfluentwidgets import LineEdit,ProgressBar,IndeterminateProgressBar
