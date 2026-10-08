# -*- coding: utf-8 -*-
"""
main.py — WetBulb Calculator 湿球计算器 · v1.3.1（程序入口）
=================================================================
本文件 = 原 WetBulb_Calculator.py 中【除计算引擎外的全部功能】：
  - GUI 主窗口、事件绑定、输入校验、单位换算
  - CalculatorMemory（结果/迭代存储与展示）
  - 批量计算、扩展参数、关于/单位对话框
所有计算（公式注册表、饱和蒸气压、牛顿迭代等）统一调用 src/core.py。
计算函数通过 on_result / on_iter 回调把结果写回 CalculatorMemory。

仓库结构（v1.3.1 起整理）：
    main.py            本文件，程序入口
    src/core.py        计算核心（零 GUI 依赖）
    src/ui/*.py        pyuic5 生成的界面代码
    assets/            图标与默认配置
    tests/ docs/ legacy/ examples/
运行：在项目根目录执行 `python main.py`（见 README「安装与运行」）。
"""
import os
import sys

# 让 src/ 与 src/ui/ 可被 import —— 这一步必须在导入 core / 界面模块之前完成。
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_HERE, 'src'), os.path.join(_HERE, 'src', 'ui')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Dispatch before importing any GUI dependencies.
if __name__ == '__main__' and '--cli' in sys.argv[1:]:
    from cli import main as cli_main
    args = sys.argv[1:]
    args.remove('--cli')
    raise SystemExit(cli_main(args))

import math
import webbrowser

# ---------------------------------------------------------------------------
# 单位换算的**唯一定义**（v1.3.2 起）
#
# 【为什么单独立出来】旧版把 mmHg / cmHg 的换算系数写死成 1.33322 / 13.3322，
# 而 README 与 core.py 的注释都用"1 mmHg = 133.322387415 Pa 是**定义值**"
# 来论证删除"本地重力加速度"是合理的——两处说的不是同一个数（相对差 2.9e-6）。
# 更实际的问题是：单位对话框向用户公布的区间（375~825 mmHg）与 check_input
# 实际强制的区间对不上，`375 mmHg × 1.33322 = 499.9575 hPa < 500` 被拒，
# 而界面刚刚告诉用户 375 是下限。
# 现在系数只在这里写一次，区间由它反推，"公布的"与"强制的"不可能再打架。
MMHG_HPA = 133.322387415 / 100.0     # 1 mmHg = 133.322387415 Pa（定义值）= 1.33322387415 hPa
CMHG_HPA = MMHG_HPA * 10.0
# 界面压强域（hPa）：比 core.check_pressure 的 (0,1200] 收得紧，只服务交互路径
UI_P_MIN_HPA, UI_P_MAX_HPA = 500.0, 1100.0
# 界面温度域（℃）：与 core.T_MIN / T_MAX 一致
UI_T_MIN_C, UI_T_MAX_C = -150.0, 200.0

# ---------------------------------------------------------------------------
# Windows 下"中文路径"会让 PySide2 找不到 Qt 平台插件（v1.3.1 修）
#
# 现象：项目放在含中文的目录（例如本仓库所在的 …\projpy\晴雨表\）时，程序启动即崩，
# 退出码 0xC0000409，stderr 只有一句：
#     qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""
#     This application failed to start because no Qt platform plugin could be initialized.
#
# 根因：PySide2 把自己的包目录交给 Qt 时要经过一次窄字符(ANSI)转换，
# 非 ASCII 的路径会变成 "???"：
#     QLibraryInfo.location(PluginsPath) ->
#     '<某个含中文的路径>/???/.venv/lib/site-packages/PySide2/plugins'   ← exists = False
#   （实测时用的是本机的虚拟环境；此处写成通用示例，避免把个人路径带进公开仓库。）
# 于是 Qt 的插件搜索路径是空的，连 qwindows.dll 都找不到。
# 注意：`import main` 不会触发它（不需要平台插件），只有真正建 QApplication 才炸——
# 所以"导入通过"不等于"能启动"。
#
# 修法：把真实路径显式写进 QT_PLUGIN_PATH（Qt 从环境变量读取原始 Unicode 字符串），
# 绕开那次有损转换。已实测：设了变量就能在中文目录里正常启动。
# 打包成 exe 后同样有效（exe 放在中文目录里也不会再崩）。
try:
    import PySide2 as _pyside2
    _qt_plugins = os.path.join(os.path.dirname(os.path.abspath(_pyside2.__file__)), 'plugins')
    if os.path.isdir(_qt_plugins):
        os.environ.setdefault('QT_PLUGIN_PATH', _qt_plugins)
except Exception:      # 没有 PySide2 时不影响其它检查（例如 CI 里只跑计算核心）
    pass

import matplotlib.pyplot as plt
from batch import calculate_file

from PySide2.QtCore import QStringListModel, Qt
from PySide2.QtWidgets import QApplication, QWidget, QAbstractItemView, QFileDialog, QDialog
from PySide2.QtGui import QIcon, QColor
from qfluentwidgets import ToolTipFilter, ToolTipPosition, InfoBar, InfoBarPosition, setThemeColor

from calculator1 import Ui_wetbulb
from unit import Ui_Dia
from about import Ui_Dialog


def _cfg_title_color():
    """把 cfg.json 的 title_color（"R, G, B"）解析为 QColor。
    qfluentwidgets 的强调色（主按钮/设置按钮/输入框点击后的颜色条等）
    全部统一使用该颜色；解析失败时回退默认青色 rgb(71, 148, 157)。

    load_title_color 只由 core.py 提供（此前 src/ui/calculator1.py 里有一份重复实现）。"""
    try:
        parts = [int(x.strip()) for x in load_title_color().split(',')]
        if len(parts) == 3 and all(0 <= p <= 255 for p in parts):
            return QColor(*parts)
    except Exception:
        pass
    return QColor(71, 148, 157)


# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# ======================================================================
# 计算核心与配置统一由 src/core.py 提供（版本号、精度、公式引擎）
# ======================================================================
from core import (tot as default_tol, APP_ICON, resource_path,
                  load_title_color, calculate_wetbulb, calculate_dewpoint,
                  calculate_both, derive_moist_air)

# 迭代容差（界面上"精度"滑条可调，见 update_tol）。初值取 core.py 的默认值，
# 之后由**本模块自己持有**：
#   - core 的计算函数是按 `tol=` 参数取值的，改 core.tot 不影响任何计算；
#   - 旧版用 `global tot` 去改 core 的模块变量，既是死状态，也让静态检查
#     分不清"导入的 tot"与"被赋值的 tot"（pyflakes 4.0.2 在 Python 3.12 上
#     会把 `from core import tot` 报成 unused，3.10/3.11 上不报 —— 同一个
#     提交在两个矩阵任务里得到相反结论，这本身就是该改写法的信号）。
tot = default_tol

# 【已删除的死代码 · v1.3.1】此处原有 16 行被注释掉的 load_g_value / save_g_value 副本，
# 引用的还是整理前的 `resource_path('cfg.json')`。配置读写现在只在 src/core.py 实现一次
# （见 tests/test_repo_hygiene.py::test_config_helpers_are_defined_only_once）。
# 【已移除 · 打包重建】上面那句里提到的两个函数现已彻底删除：cfg.json 只剩 title_color，
# "本地重力加速度" 这个从不参与计算的参数连界面一起拿掉了（见 B-20）。
# 版本号同理：v1.3.0 起只在 core.py 定义 `tag`。

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 指定默认字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# ======================================================================
# CalculatorMemory：存储各公式计算结果与迭代过程（供列表展示/收敛图）
# ======================================================================
class CalculatorMemory:
    def __init__(self):
        self.methods = []
        self.iteration_data = {}

    def add_result(self, method_name, result1, result2=None, rh=None):
        self.methods.append({
            "method": method_name,
            "result1": result1,
            "result2": result2,
            "rh": rh
        })

    def show_results(self, mode1, mode2=None, temperature_unit='℃'):
        """把结果格式化成多行文本。

        temperature_unit 由调用方显式传入（原来是读模块全局 `main_window.temperature_unit`）：
        那个写法只在"以 __main__ 运行"时成立——因为文件底部的 `main_window = main_window()`
        会把模块全局从**类**换成**实例**；一旦有人 `import main` 再用，
        `main_window` 仍是类，取 `.temperature_unit` 就抛 AttributeError，
        而 validate_and_calculate 的兜底 except 会把它变成一个错误条 —— **计算静默地什么都不显示**。
        （这就是编年史 Bug 档案里的 B-07，v1.3.1 修。）
        """
        if mode2:
            output = f"计算公式 | {mode1} | {mode2}:\n"
        else:
            output = f"计算公式 | {mode1} | 相对湿度:\n"

        for item in self.methods:
            result1 = item['result1']
            result2 = item.get('result2')

            if isinstance(result1, float):
                if temperature_unit == 'K':
                    display_temp1 = result1 + 273.15
                elif temperature_unit == '℉':
                    display_temp1 = result1 * 9/5 + 32
                else:
                    display_temp1 = result1

                result1_str = f"{display_temp1:.4f}{temperature_unit}"
            else:
                result1_str = f"{result1}"

            if result2 is not None:
                if isinstance(result2, float):
                    if temperature_unit == 'K':
                        display_temp2 = result2 + 273.15
                    elif temperature_unit == '℉':
                        display_temp2 = result2 * 9/5 + 32
                    else:
                        display_temp2 = result2
                    result2_str = f"{display_temp2:.4f}{temperature_unit}"
                else:
                    result2_str = f"{result2}"

                rh_str = ""
                if item['rh'] == 0 :
                    rh_str = ""
                elif item['rh'] is not None:
                    rh_str = f"  {item['rh']*100:.2f}%"
                    
                output += f"{item['method']}:  {result1_str}  {result2_str}  {rh_str}\n"
            else:
                if item['rh']:
                    rh = item['rh']*100
                    output += f"{item['method']}:  {result1_str}  {rh:.2f}%\n"
                else:
                    output += f"{item['method']}:  {result1_str}\n"

        output += "点击任意行以继续…"
        return output

    def add_iteration(self,method,iteration,T_w,residual):
        if method not in self.iteration_data:
            self.iteration_data[method] = {
                'iterations':[],
                'temperatures':[],
                'residuals':[]
            }
        self.iteration_data[method]['iterations'].append(iteration)
        self.iteration_data[method]['temperatures'].append(T_w)
        self.iteration_data[method]['residuals'].append(abs(residual))

    def show_convergence(self):
        plt.figure(figsize=(12,6))
        plt.subplot(1,2,1)   # 温度变化子图
        for method,data in self.iteration_data.items():
            if len(data['iterations']) <= 1:
                continue  # 跳过只有一次迭代的数据
                
            iterations = data['iterations'][1:]   # 跳过第一次迭代（索引0对应的数据）
            temperatures = data['temperatures'][1:]
            plt.plot(iterations,temperatures,
                     marker='o',label=method)
        plt.xlabel('迭代次数')
        plt.ylabel('温度估计值 (°C)')
        plt.title('温度迭代过程')
        plt.grid(True)
        plt.legend()

        plt.subplot(1,2,2)          # 残差变化子图
        for method,data in self.iteration_data.items():
            if len(data['iterations']) <= 1:
                continue  # 跳过只有一次迭代的数据
                
            iterations = data['iterations'][1:]
            residuals = data['residuals'][1:]
            plt.semilogy(iterations,residuals,
                         marker='s',label=method)
        plt.xlabel('迭代次数')
        plt.ylabel('残差 (对数刻度)')
        plt.title('残差收敛过程')
        plt.grid(True)
        plt.legend()

        plt.tight_layout()
        plt.show()

# ======================================================================
# 主窗口
# ======================================================================
class main_window(QWidget, Ui_wetbulb):
    def __init__(self):
        super().__init__()    #操作父级
        self.setupUi(self)
        self.setWindowIcon(QIcon(resource_path(APP_ICON)))
        # v1.3.0: 全局强调色统一使用 cfg.json 的 title_color ——
        # 使主按钮(pushButton_7 批量计算)、工具按钮(pushButton_5 设置)、
        # 输入框点击后的颜色条、进度条等 qfluentwidgets 强调色控件全部与标题同色。
        setThemeColor(_cfg_title_color())
        
        # 初始化变量
        self.calculator = None
        self.temperature_unit = '℃'
        self.pressure_unit = 'hPa'
        self.temp_min = -150
        self.temp_max = 200
        self.pressure_min = 500
        self.pressure_max = 1100
        self.initial_guess_strategy = "Td"
        self.list_model = QStringListModel()
        self.list_model_2 = QStringListModel()
        
        # 初始化界面
        self.widget_iteration.setVisible(True)
        self.ProgressBar.setVisible(False)
        self.ComboBox.setCurrentIndex(0)
        self.ComboBox_2.setCurrentIndex(0)
        self.LineEdit.setClearButtonEnabled(True)
        self.LineEdit_2.setClearButtonEnabled(True)
        self.LineEdit_3.setClearButtonEnabled(True)
        self.dial.setNotchesVisible(True)
        self.dial.setRange(2, 10)
        self.dial.setValue(7)
        self.dial.setSingleStep(1)
        self.listView.setModel(self.list_model)
        self.listView_2.setModel(self.list_model_2)
        self.listView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.listView_2.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pushButton_2.setToolTip('清空')
        self.pushButton_3.setToolTip('截屏')
        self.pushButton_4.setToolTip('软件信息')
        self.pushButton_5.setToolTip('设置单位')
        self.pushButton_7.setToolTip('计算当前目录下xlsx\n中的所有数据！')
        self.pushButton_2.installEventFilter(ToolTipFilter(self.pushButton_2,100,ToolTipPosition.BOTTOM))
        self.pushButton_3.installEventFilter(ToolTipFilter(self.pushButton_3,100,ToolTipPosition.BOTTOM))
        self.pushButton_4.installEventFilter(ToolTipFilter(self.pushButton_4,100,ToolTipPosition.BOTTOM))
        self.pushButton_5.installEventFilter(ToolTipFilter(self.pushButton_5,100,ToolTipPosition.BOTTOM))
        self.pushButton_7.installEventFilter(ToolTipFilter(self.pushButton_7,100,ToolTipPosition.RIGHT))

        # 设置单位显示
        self.update_input_labels()
        
        # 绑定事件
        self.bind_events()
        
    def bind_events(self):
        # 模式切换
        self.ComboBox.currentIndexChanged.connect(self.update_input_labels)
        self.ComboBox.currentIndexChanged.connect(self.clearall)
        
        # 计算按钮
        self.pushButton_6.clicked.connect(self.validate_and_calculate)
        self.LineEdit_2.returnPressed.connect(self.validate_and_calculate)
        self.LineEdit_2.returnPressed.connect(lambda: self.list_model_2.setStringList([]))
        self.LineEdit_2.returnPressed.connect(lambda: self.check_input(self.LineEdit_2, "大气压强"))
        
        # 批量计算
        self.pushButton_7.clicked.connect(self.process_excel_file)
        
        # 单位设置
        self.pushButton_5.clicked.connect(self.show_unit_dialog)
        
        # 关于按钮
        self.pushButton_4.clicked.connect(self.show_about_dialog)
        
        # 转换焦点
        self.LineEdit_3.returnPressed.connect(lambda: self.LineEdit.setFocus())
        self.LineEdit_3.returnPressed.connect(lambda: self.check_input(self.LineEdit_3, "干球温度"))
        self.LineEdit.returnPressed.connect(lambda: self.LineEdit_2.setFocus())
        self.LineEdit.returnPressed.connect(lambda: self.check_input(self.LineEdit, self.label_2.text().rstrip("：")))
        
        # 【已移除 · 打包重建】此处原有"重力加速度输入"三行绑定（LineEdit_4 →
        # check_input / update_g_value / clear）。该输入框从不参与任何计算（B-20），
        # 控件本身也已删除，故绑定一并拿掉。
        
        # 迭代图按钮
        self.pushButton.clicked.connect(self.show_convergence_plot)
        self.ComboBox_2.currentIndexChanged.connect(self.clearall)
        
        # 精度旋钮
        self.dial.valueChanged.connect(self.update_tol)
        
        # 清空按钮
        self.pushButton_2.clicked.connect(self.clearall)
        
        # 截屏按钮
        self.pushButton_3.clicked.connect(self.take_screenshot)
        
        # 进一步计算
        self.listView.clicked.connect(self.on_list_item_clicked)

    def createSuccessInfoBar(self,message):
        InfoBar.success(
            title='处理成功！',
            content=f"{message}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def createErrorInfoBar(self,message):
        InfoBar.error(
            title='错误！',
            content=f"{message}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=5000,  
            parent=self
        )

    def update_tol(self, value):
        """界面上的"精度"滑条：把迭代容差设为 10^(-value)。

        这里改的是**本模块的** tot（见文件顶部定义），不再用 `global` 去改
        core.py 的模块变量 —— core 的计算函数是按 `tol=` 参数取值的，
        改 `core.tot` 不会影响任何一次计算，只是死状态。
        """
        global tot
        tot = 10 ** (-value)

    def update_input_labels(self):
        if self.ComboBox.currentIndex() == 0:  # 已知露点求湿球
            self.label_2.setText("露点温度：")
            self.widget_iteration.setVisible(True)
            self.LineEdit.setPlaceholderText(f"{self.temp_min}~{self.temp_max}{self.temperature_unit}")
        elif self.ComboBox.currentIndex() == 1:  # 已知湿球求露点
            self.label_2.setText("湿球温度：")
            self.widget_iteration.setVisible(False)
            self.LineEdit.setPlaceholderText(f"{self.temp_min}~{self.temp_max}{self.temperature_unit}")
        elif self.ComboBox.currentIndex() == 2:  # 已知相对湿度
            self.label_2.setText("相对湿度：")
            self.widget_iteration.setVisible(True)
            self.LineEdit.setPlaceholderText("0~100%")

    def show_convergence_plot(self):
        if self.calculator:
            self.calculator.show_convergence()
        else:
            self.createErrorInfoBar("请先执行计算！")

    def clearall(self):
        self.list_model.setStringList([])
        self.list_model_2.setStringList([])
        self.LineEdit.clear()
        self.LineEdit_2.clear()
        self.LineEdit_3.clear()
        self.calculator = None

    def take_screenshot(self):
        pixmap = self.grab()
        file_path, _ = QFileDialog.getSaveFileName(self, "保存截图", "", "PNG 图片 (*.png);;JPEG 图片 (*.jpg)")
        if file_path:
            try:
                pixmap.save(file_path)
                print(f"截图已保存至：{file_path}")
            except Exception as e:
                self.createErrorInfoBar(f"保存失败：{str(e)}")

    def changepre(self, P):
        if self.pressure_unit == 'hPa':
            return P
        elif self.pressure_unit == 'Pa':
            P /= 100
        elif self.pressure_unit == 'mmHg':
            P *= MMHG_HPA
        elif self.pressure_unit == 'cmHg':
            P *= CMHG_HPA
        elif self.pressure_unit == 'bar':
            P *= 1000
        return P

    def prechange(self, P):
        if self.pressure_unit == 'Pa':
            P *= 100
        elif self.pressure_unit == 'mmHg':
            P /= MMHG_HPA
        elif self.pressure_unit == 'cmHg':
            P /= CMHG_HPA
        elif self.pressure_unit == 'bar':
            P /= 1000
        else:
            P = P
        return P

    def changetemp(self, temperature):
        if self.temperature_unit == 'K':
            temperature -= 273.15
        elif self.temperature_unit == '℉':
            temperature = (temperature - 32) * 5/9
        else:
            temperature = temperature
        return temperature

    def tempchange(self, temperature):
        if self.temperature_unit == 'K':
            temperature += 273.15
        elif self.temperature_unit == '℉':
            temperature = temperature * 9/5 + 32
        else:
            temperature = temperature
        return temperature

    def get_initial_guess(self, T, T_other):
        """湿球迭代的初值策略。注意：**结果与初值无关**（core 的求解器
        用带括号的牛顿法，见 core._solve_wetbulb）；这里只影响收敛图的形状。"""
        if self.ComboBox_2.currentIndex() == 1:  # Tw=T-n
            return T - 2 if T < 0 else T - 5
        # 0 = Tw=Td；其它（不可达的）取值一律退回 Tw=Td，
        # 而不是像旧版那样掉出函数返回 None（那会让 core 报 '错误: …' 并当成结果打印）
        return T_other

    def check_input(self, line_edit, field_name):
        """解析并校验一个输入框，返回**换算到标准单位（℃ / hPa）后的数值**；
        失败返回 None 并弹错误条。

        【v1.3.2 修 · 这里原本有两个真缺陷】
        旧版只返回 True/False，而且它拿"**过滤掉非数字字符之后的串**"去做校验，
        调用方随后却对**原文本**再 float() 一次 —— 校验的和用的根本不是同一个数：

          · `60%`：过滤成 "60" 通过校验，紧接着 `float("60%")` 抛 ValueError，
            用户看到 `could not convert string to float: '60%'`。
            而相对湿度框的占位符恰恰写着 "0~100%" —— 是界面自己在引诱用户加 %。
          · `1e3`：过滤成 "13"，于是按 13 hPa 判"超出范围"并清空输入框，
            可 1e3 hPa 本来完全合法。反过来 `3e2` 按 32 hPa 放行、
            计算时却按 300 hPa 算 —— 校验拦下的和实际计算用的可以毫不相干。

        现在解析只发生一次：`float(原文本)`，随后按字段换算并检查区间。
        返回数值而不是布尔量，是让"校验过的那一个数"和"拿去算的那一个数"
        在类型上就不可能分家。
        """
        text = line_edit.text().strip()
        if not text:
            self.createErrorInfoBar(f"{field_name}不能为空！")
            line_edit.clear()
            return None
        try:
            value = float(text)
        except ValueError:
            self.createErrorInfoBar(f"{field_name}必须是有效数字（收到「{text}」）")
            line_edit.clear()
            return None
        if not math.isfinite(value):
            self.createErrorInfoBar(f"{field_name}必须是有限数值（收不到 NaN / 无穷大）")
            line_edit.clear()
            return None

        if "温度" in field_name:
            value_C = self.changetemp(value)
            if not (UI_T_MIN_C <= value_C <= UI_T_MAX_C):
                min_ui = self.tempchange(UI_T_MIN_C)
                max_ui = self.tempchange(UI_T_MAX_C)
                self.createErrorInfoBar(
                    f"{field_name}需在 [{min_ui:.2f}, {max_ui:.2f}]{self.temperature_unit} 范围内")
                line_edit.clear()
                return None
            return value_C

        if "压强" in field_name:
            value_hPa = self.changepre(value)
            if not (UI_P_MIN_HPA <= value_hPa <= UI_P_MAX_HPA):
                min_ui = self.prechange(UI_P_MIN_HPA)
                max_ui = self.prechange(UI_P_MAX_HPA)
                self.createErrorInfoBar(
                    f"{field_name}需在 [{min_ui:.2f}, {max_ui:.2f}]{self.pressure_unit} 范围内")
                line_edit.clear()
                return None
            return value_hPa

        if "相对湿度" in field_name:
            # 与 core.check_relative_humidity 一致：下界是**开区间**，RH=0 时 e=0、露点无定义
            if not (0.0 < value <= 100.0):
                self.createErrorInfoBar("相对湿度必须在 (0, 100] % 之间！")
                line_edit.clear()
                return None
            return value

        return value

    def _run_calc(self, fn, *args, **kwargs):
        """调用 core.py 的计算函数，把结果/迭代通过回调写回 CalculatorMemory。"""
        calc = CalculatorMemory()
        fn(*args, on_result=lambda d: calc.add_result(d['method'], d['result1'], d['result2'], d['rh']),
           on_iter=calc.add_iteration, **kwargs)
        return calc

    def validate_and_calculate(self):
        try:
            # check_input 返回**换算到标准单位后的数值**（℃ / hPa），失败返回 None。
            # 【v1.3.2 修 · 代理复核发现】不能写成 `if not self.check_input(...)`：
            # 干球温度 0 ℃（或 32 ℉ / 273.15 K）是合法且常见的输入，而 `not 0.0` 为真 ——
            # 于是点"计算"什么都不发生、连错误条都没有。这里直接用返回值，
            # 顺带消灭"校验的是过滤后的串、算的是原文本"那种分家。
            T = self.check_input(self.LineEdit_3, "干球温度")
            if T is None:
                return
            
            # 获取输入模式
            mode = self.ComboBox.currentIndex()
            target_label = self.label_2.text().replace(' ', '').rstrip("：")

            T_other_input = self.check_input(self.LineEdit, target_label)
            if T_other_input is None:
                return

            if mode == 2:  # 已知相对湿度：该框的值就是百分数（check_input 已按 (0,100] 校验）
                rh = T_other_input
            else:         # 温度框：check_input 已换算成 ℃
                T_other = T_other_input

            P = self.check_input(self.LineEdit_2, "大气压强")
            if P is None:
                return

            if mode <= 1 and T_other >= T:
                raise ValueError(f"{target_label}不能高于干球温度！")

            if mode == 0:  # 已知露点求湿球
                try:
                    initial_guess = self.get_initial_guess(T, T_other)
                except ValueError as e:
                    self.createErrorInfoBar(str(e))
                    return
                self.calculator = self._run_calc(calculate_wetbulb, initial_guess, T, T_other, P, tol=tot)
                output = self.calculator.show_results("湿球温度", temperature_unit=self.temperature_unit)
                
            elif mode == 1:  # 已知湿球求露点
                self.calculator = self._run_calc(calculate_dewpoint, T, T_other, P, tol=tot)
                output = self.calculator.show_results("露点温度", temperature_unit=self.temperature_unit)
                
            elif mode == 2:  # 已知相对湿度同时求露点和湿球
                try:
                    initial_guess = self.get_initial_guess(T, T)  # v1.2.1: RH模式下无T_other，以T占位
                except ValueError as e:
                    self.createErrorInfoBar(str(e))
                    return
                self.calculator = self._run_calc(calculate_both, initial_guess, T, tol=tot,
                                                 rh_pct=rh, P=P)
                output = self.calculator.show_results("露点温度", "湿球温度", temperature_unit=self.temperature_unit)
            
            self.list_model.setStringList(output.split('\n'))  # 按行分割字符串

        except Exception as e:
            self.createErrorInfoBar(str(e))
        
    def on_list_item_clicked(self, index):
        row = index.row()
        self.list_model_2.setStringList([])
        if row <= 0 or row > len(self.calculator.methods):
            return
        method_data = self.calculator.methods[row-1]
        method_name = method_data['method']
        result1 = method_data.get('result1')
        result2 = method_data.get('result2')
        rh = method_data.get('rh')

        mode = self.ComboBox.currentIndex()
        if mode == 0 or mode == 1:
            if not isinstance(result1, float):
                return
        elif mode == 2:
            if not isinstance(result1, float) or not isinstance(result2, float):
                return

        if rh is None and (mode == 0 or mode == 1):
            return

        try:
            T_g_input = float(self.LineEdit_3.text())
            T_g = self.changetemp(T_g_input)

            if mode == 0:  # 已知露点求湿球
                Td = self.changetemp(float(self.LineEdit.text()))
                Tw = result1
            elif mode == 1:  # 已知湿球求露点
                Tw = self.changetemp(float(self.LineEdit.text()))
                Td = result1
            elif mode == 2:  # 已知相对湿度计算两者
                Td = result1
                Tw = result2
                # rh可能在计算中直接使用输入值
                if rh is None:
                    rh_input = float(self.LineEdit.text())
                    rh = rh_input / 100  # 转换为小数

            P_input = float(self.LineEdit_2.text())
            P_hPa = self.changepre(P_input)

            # 派生量统一交给 core.derive_moist_air（纯函数、无 GUI 依赖、可被 tests/ 覆盖）。
            # 旧版在 GUI 回调里手写这 60 行，其中比热容误用摩尔气体常数、
            # 水汽密度误用 esw、饱和混合率误用 e —— 详见 core.py 中的注释。
            derived = derive_moist_air(T_g, Tw, Td, rh_frac=rh, P=P_hPa, method=method_name)

            es1 = self.prechange(derived['es'])
            esw1 = self.prechange(derived['esw'])
            e1 = self.prechange(derived['e'])
            P_dry1 = self.prechange(derived['P_dry'])

            virtual_temp1 = self.tempchange(derived['virtual_temp_K'] - 273.15)  # 虚温
            theta = self.tempchange(derived['theta_K'] - 273.15)                 # 位温THTA
            theta_E = self.tempchange(derived['theta_e_K'] - 273.15)             # 相当位温THTE
            theta_V = self.tempchange(derived['theta_v_K'] - 273.15)             # 虚位温THTV

            # 抬升凝结高度（Bolton 公式）；rh<=0 或不可解时 core 返回 nan
            if math.isnan(derived['t_lcl_C']):
                t_lcl = float('nan')
                p_lcl = float('nan')
            else:
                t_lcl = self.tempchange(derived['t_lcl_C'])
                p_lcl = self.prechange(derived['p_lcl_hPa'])

            base_info = [
                f"{method_name} | 常用气象参数",
                f"相对湿度: {rh*100:.2f}%",
                f"绝对湿度: {derived['absolute_humidity']:.3f} g/m³",
                f"比湿: {derived['specific_humidity']:.3f} g/kg",
                f"蒸气压: {e1:.2f} {self.pressure_unit}",
                f"饱和蒸气压: {es1:.2f} {self.pressure_unit}",
                f"干空气分压: {P_dry1:.1f} {self.pressure_unit}",
                f"干空气密度: {derived['ro_dry']:.3f} kg/m³",
                f"水蒸气密度: {derived['ro_vapor']:.3f} kg/m³",
                f"空气密度: {derived['ro']:.3f} kg/m³",
                f"焓值: {derived['han']:.2f} kJ/kg",
                f"蒸发潜热: {derived['L_v']:.1f} kJ/kg",
                f"含湿量: {derived['dm1']:.3f} g/kg",
                f"饱和混合率: {derived['sat_mixing_ratio']:.3f} g/kg",
                f"位温: {theta:.2f} {self.temperature_unit}",
                f"相当位温: {theta_E:.2f} {self.temperature_unit}",
                f"虚温: {virtual_temp1:.2f} {self.temperature_unit}",
                f"虚位温: {theta_V:.2f} {self.temperature_unit}",
            ]

            lcl_info = []
            if not math.isnan(t_lcl) and not math.isnan(p_lcl):
                lcl_info = [
                    f"lcl温度: {t_lcl:.2f} {self.temperature_unit}",
                    f"lcl压强: {p_lcl:.1f} {self.pressure_unit}",
                ]

            additional_info = [
                f"水蒸气摩尔分数: {derived['x']*100:.1f} %",
                f"湿空气绝热指数: {derived['gamma_mix']:.2f}",
                f"空气中声速: {derived['v_sound']:.1f} m/s",
                f"湿球蒸气压: {esw1:.2f} {self.pressure_unit}",
            ]

            results = base_info + lcl_info + additional_info
            self.list_model_2.setStringList(results)

        except Exception as e:
            self.createErrorInfoBar(f"计算错误: {str(e)}")
            
    def process_excel_file(self):
        current_dir = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else _HERE
        files = sorted(fi for fi in os.listdir(current_dir)
                       if fi.lower().endswith('.xlsx') and not fi.startswith(('result_', '~$')))
        if len(files) != 1:
            self.createErrorInfoBar('请在程序目录保留一个输入 xlsx 文件（不含 result_ 输出文件）。')
            return
        self.ProgressBar.setVisible(True)
        self.pushButton_7.setEnabled(False)
        try:
            output = calculate_file(
                os.path.join(current_dir, files[0]),
                os.path.join(current_dir, 'result_' + files[0]),
                mode=self.ComboBox.currentIndex(), to_celsius=self.changetemp,
                to_hpa=self.changepre, from_celsius=self.tempchange,
                temperature_unit=self.temperature_unit, pressure_unit=self.pressure_unit,
                progress=lambda done, total: QApplication.processEvents())
            self.createSuccessInfoBar('已存储至路径' + str(output))
        except Exception as exc:
            self.createErrorInfoBar('处理Excel文件时出错：' + str(exc))
        finally:
            self.ProgressBar.setVisible(False)
            self.pushButton_7.setEnabled(True)

    def show_unit_dialog(self):
        unit_dialog = UnitDialog(self)
        unit_dialog.exec_()

    def show_about_dialog(self):
        about_dialog = AboutDialog()
        about_dialog.exec_()

class AboutDialog(QDialog, Ui_Dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon(resource_path(APP_ICON)))
        self.PushButton.clicked.connect(self.close)
        self.ToolButton.clicked.connect(lambda: webbrowser.open("https://github.com/x1shang/Wetbulb-Calculator"))

class UnitDialog(QDialog, Ui_Dia):
    def __init__(self, main_window):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon(resource_path(APP_ICON)))
        self.main_window = main_window
        
        # 设置当前单位选中状态
        self._setup_current_units()
        
        # 绑定按钮事件
        self.PrimaryPushButton.clicked.connect(self.update_units)
        self.PrimaryPushButton.clicked.connect(self.close)
        self.PrimaryPushButton.clicked.connect(lambda: self.main_window.clearall())
        self.PushButton.clicked.connect(self.close)
        
    def _setup_current_units(self):
        # 设置压强单位选中状态
        if self.main_window.pressure_unit == 'Pa':
            self.RadioButton.setChecked(True)
        elif self.main_window.pressure_unit == 'hPa':
            self.RadioButton_2.setChecked(True)
        elif self.main_window.pressure_unit == 'mmHg':
            self.RadioButton_3.setChecked(True)
        elif self.main_window.pressure_unit == 'cmHg':
            self.RadioButton_4.setChecked(True)
        elif self.main_window.pressure_unit == 'bar':
            self.RadioButton_5.setChecked(True)
            
        # 设置温度单位选中状态
        if self.main_window.temperature_unit == 'K':
            self.RadioButton_6.setChecked(True)
        elif self.main_window.temperature_unit == '℃':
            self.RadioButton_7.setChecked(True)
        elif self.main_window.temperature_unit == '℉':
            self.RadioButton_8.setChecked(True)
        
    def update_units(self):
        # 压强单位映射
        pressure_units = {
            self.RadioButton: ('Pa', 50000, 110000),
            self.RadioButton_2: ('hPa', 500, 1100),
            self.RadioButton_3: ('mmHg', 375, 825),
            self.RadioButton_4: ('cmHg', 37.5, 82.5),
            self.RadioButton_5: ('bar', 0.5, 1.1)
        }
        # 温度单位映射
        temperature_units = {
            self.RadioButton_6: ('K', 123.15, 473.15),  # -150℃=123.15K, 200℃=473.15K
            self.RadioButton_7: ('℃', -150, 200),
            self.RadioButton_8: ('℉', -238, 392)        # -150℃=-238℉, 200℃=392℉
        }

        for rb, (unit, min_val, max_val) in pressure_units.items():
            if rb.isChecked():
                self.main_window.pressure_min = min_val
                self.main_window.pressure_max = max_val
                self.main_window.pressure_unit = unit
                self.main_window.LineEdit_2.setPlaceholderText(
                    f"{min_val}~{max_val}{unit}"
                )
                break
                
        for rb, (unit, min_val, max_val) in temperature_units.items():
            if rb.isChecked():
                self.main_window.temp_min = min_val
                self.main_window.temp_max = max_val
                self.main_window.temperature_unit = unit
                self.main_window.LineEdit_3.setPlaceholderText(
                    f"{min_val}~{max_val}{unit}"
                )
                self.main_window.LineEdit.setPlaceholderText(
                    f"{min_val}~{max_val}{unit}"
                )
                break

if __name__ == '__main__':
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "Round"

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)  # 添加高DPI支持
    app.setWindowIcon(QIcon(resource_path(APP_ICON)))  #图标设置

    main_window = main_window()
    main_window.show()
    
    if '--smoke-test' in sys.argv:
        from gui_smoke import run
        output = sys.argv[sys.argv.index('--smoke-test') + 1]
        run(main_window, app, AboutDialog, UnitDialog, output)
        sys.exit(0)
    sys.exit(app.exec_())
