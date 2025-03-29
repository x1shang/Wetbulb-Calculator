import math
import matplotlib.pyplot as plt
from PySide2.QtWidgets import QApplication, QFileDialog
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QObject,QStringListModel
# from PySide2.QtGui import QPixmap

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 指定默认字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

MAGNUS_FORMULAS = {
    'magnus_water':lambda T:(6.112,17.62,243.12),
    'august_water':lambda T:(6.1094,17.625,243.04),
    'tetens_water':lambda T:(6.1078,17.269,237.3),
    'buck_water':lambda T:(6.1121,17.502,240.97),
    'arden_water':lambda T:(6.1121,18.678,257.14),
    'magnus_ice':lambda T:(6.112,22.46,272.62),
    'buck_ice':lambda T:(6.1115,22.452,272.55),
}

GOFF_FORMULAS = {
    'goff_water':lambda T:(273.15,10.79574,-5.02808,1.50475e-4,-8.2969,0.42873e-3,4.76955,0.78614,0),
    'goff_new':lambda T:(373.15,7.90298,-5.02808,1.3816e-5,-11.344,0.0081328,3.49149,3.0057149,0),
    'goff_ice':lambda T:(273.15,9.09718,3.56654,0,0,0,0,0.78614,0.876793),
}

WEXLER_FORMULAS = {
    'wexler_water':lambda T:(-5800.2206,1.3914993,-0.048640239,0.41764768e-4,-0.14452093e-7,0,6.5459673),
    'wexler_ice':lambda T:(-5674.5359,6.3925247,-0.009677843,0.62215701e-6,0.20747825e-8,-0.9484024e-12,4.1635019),
}

methods = [
    ('Goff-水面','goff_water',lambda T_w:-10 <= T_w <= 100),
    ('Wexler-水面','wexler_water',lambda T_w:-10 <= T_w <= 200),
    ('Buck-水面','buck_water',lambda T_w:0 <= T_w <= 80),
    ('Tetens-水面','tetens_water',lambda T_w:0 <= T_w <= 50),
    ('Magnus-水面','magnus_water',lambda T_w:0 <= T_w <= 60),
    ('August-水面','august_water',lambda T_w:0 <= T_w <= 60),
    ('Arden-水面','arden_water',lambda T_w:0 <= T_w <= 100),
    ('Gili-水面','gili_water',lambda T_w:-10 <= T_w <= 20),
    ('Goff2-水面','goff_new',lambda T_w:-10 <= T_w <= 100),
    ('Goff-冰面','goff_ice',lambda T_w:-100 <= T_w <= 10),
    ('Wexler-冰面','wexler_ice',lambda T_w:-150 <= T_w <= 10),
    ('Magnus-冰面','magnus_ice',lambda T_w:-65 <= T_w <= 0),
    ('Buck-冰面','buck_ice',lambda T_w:-80 <= T_w <= 0),
    ('Marti-冰面','marti_ice',lambda T_w:-150 <= T_w <= 0),
]

class CalculatorMemory:
    def __init__(self):
        self.methods = []
        self.iteration_data = {}

    def add_result(self,method_name,result,rh=None):
        self.methods.append({
            "method":method_name,
            "result":result,
            "rh":rh
        })

    def show_results(self,mode):

        output = f"计算公式 | {mode}温度 | 相对湿度:\n"  # 标题行

        for item in self.methods:
            result = item['result']
            if isinstance(result,float):
                rh = item['rh']*100 if item['rh'] else 0
                output += f"{item['method']}: {result:.4f}°C   {rh:.2f}%\n"
            else:
                output += f"{item['method']}: {result}\n"

        return output  # 返回完整字符串

    def add_iteration(self,method,iteration,T_w,residual):
        """记录单次迭代数据"""
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
        """绘制收敛过程图"""
        plt.figure(figsize=(12,6))

        # 温度变化子图
        plt.subplot(1,2,1)
        for method,data in self.iteration_data.items():
            # 跳过第一次迭代（索引0对应的数据）
            iterations = data['iterations'][1:]
            temperatures = data['temperatures'][1:]
            plt.plot(iterations,temperatures,
                     marker='o',label=method)
        plt.xlabel('迭代次数')
        plt.ylabel('湿球温度估计值 (°C)')
        plt.title('温度迭代过程')
        plt.grid(True)
        plt.legend()

        # 残差变化子图
        plt.subplot(1,2,2)
        for method,data in self.iteration_data.items():
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

def calculate_esat(T_w,method='magnus'):
    T_k = T_w+273.15

    if method in MAGNUS_FORMULAS:
        A,B,C = MAGNUS_FORMULAS[method](T_w)
        return A*math.exp(B*T_w/(C+T_w))

    elif method in GOFF_FORMULAS:
        A,B,C,D,E,F,G,H,I = GOFF_FORMULAS[method](T_w)
        term1 = B*(1-A/T_k)
        term2 = C*math.log10(T_k/A)
        term3 = D*(1-10**(E*(T_k/A-1)))
        term4 = F*(10**(G*(1-A/T_k))-1)
        term5 = I*(1-T_k/A)
        return 10**(term1+term2+term3+term4+term5+H)

    elif method in WEXLER_FORMULAS:
        A,B,C,D,E,F,G = WEXLER_FORMULAS[method](T_w)
        term1 = A/T_k
        term2 = B
        term3 = C*T_k
        term4 = D*T_k**2
        term5 = E*T_k**3
        term6 = F*T_k**4
        term7 = G*math.log(T_k)
        ln_esat = term1+term2+term3+term4+term5+term6+term7
        return math.exp(ln_esat)/100

    elif method == 'gili_water':
        term1 = -3.142305*(1e3/T_k-1e3/373.16)
        term2 = 8.2*math.log10(373.16/T_k)
        term3 = -0.0024804*(373.16-T_k)
        return 980.66*10**(0.00141966+term1+term2+term3)

    elif method == 'marti_ice':
        lg_esat = -2663.5/T_k+12.537
        return 10**lg_esat/100

    else:
        raise ValueError("无效的计算方法")

def calculate_dedt(T_w,method,delta=0.001):
    T_k = T_w+273.15

    if method in MAGNUS_FORMULAS:
        A,B,C = MAGNUS_FORMULAS[method](T_w)
        e_sat = calculate_esat(T_w,method)
        return e_sat*(B*C)/(C+T_w)**2

    elif method in GOFF_FORMULAS:
        A,B,C,D,E,F,G,H,I = GOFF_FORMULAS[method](T_w)
        term1 = B*A/T_k**2
        term2 = C/A*math.log10(T_k/A)*math.log(10)
        term3 = -D*E/A*math.log(10)*10**(E*(T_k/A-1))
        term4 = A*F*G/T_k**2*10**(G*(1-A/T_k))*math.log(10)
        term5 = -I/A
        e_sat = calculate_esat(T_w,method)
        return e_sat*math.log(10)*(term1+term2+term3+term4+term5)

    elif method in WEXLER_FORMULAS:
        e_sat = calculate_esat(T_w,method)
        A,B,C,D,E,F,G = WEXLER_FORMULAS[method](T_w)
        d_sat = -A/T_k**2+C+2*D*T_k+3*E*T_k**2+4*F*T_k**3+G/T_k
        return e_sat*d_sat

    elif method == 'gili_water':
        term1 = -3.142305*(1e3/T_k-1e3/373.16)
        term2 = 8.2*math.log10(373.16/T_k)
        term3 = -0.0024804*(373.16-T_k)
        term4 = 3142.305/T_k**2-3.561215/T_k+0.0024804
        return 980.66*10**(0.00141966+term1+term2+term3)*math.log(10)*term4

    elif method == 'marti_ice':
        lg_esat = -2663.5/T_k+12.537
        return 10**lg_esat/100*math.log(10)*2663.5/T_k**2

    else:
        e1 = calculate_esat(T_w-delta,method)
        e2 = calculate_esat(T_w+delta,method)
        return (e2-e1)/(2*delta)

def esat_calculate(e,method,max_iter,tol,mint=-150,maxt=200):
    if method in MAGNUS_FORMULAS:
        A,B,C = MAGNUS_FORMULAS[method](e)
        term1 = math.log(e/A)
        return C*term1/(B-term1)

    for iter_num in range(max_iter):
        t = (mint+maxt)/2
        ft = calculate_esat(t,method)-e
        if abs(ft) < tol and not iter_num < 99:
            return t
        if ft > 0:
            maxt = t
        else:
            mint = t
    return (mint+maxt)/2

def calculate_wetbulb(initial_guess,T,Td,P=1013.25,max_iter=50,tol=1e-6):
    global f
    calculator = CalculatorMemory()

    for name,method,condition in methods:

        e = calculate_esat(Td,method)
        if not condition(initial_guess):
            calculator.add_result(name,'不适用')
            continue
        T_w = initial_guess
        for iter_num in range(max_iter):
            try:
                e_sat = calculate_esat(T_w,method)
                gamma = 0.000667*(1+0.00115*T_w)*P
                f = e_sat-gamma*(T-T_w)-e
                de_dT = calculate_dedt(T_w,method,P)
                df_dT = de_dT+gamma-0.00066*0.00115*P*(T-T_w)
                T_w_new = T_w-f/df_dT
                calculator.add_iteration(name,iter_num+1,T_w,abs(f))

                if abs(T_w_new-T_w) < tol and not iter_num < 4:
                    last_rh = e/calculate_esat(T_w_new,method)
                    if 1 >= last_rh >= 0:
                        calculator.add_result(name,T_w_new,last_rh)
                        break
                    else:
                        calculator.add_result(name,"结果不符常理")
                        break

                elif abs(f) > 1e3:
                    calculator.add_result(name,"残差过大")
                    break

                T_w = T_w_new

            except OverflowError:
                calculator.add_result(name,'数值溢出')
                break
            except Exception as e:
                calculator.add_result(name,f'错误: {str(e)}')
                break
            except:
                calculator.add_result(name,'计算失败')
                break
        else:
            calculator.add_result(name,'未收敛')
            calculator.add_iteration(name,max_iter,T_w,abs(f))

    return calculator

def calculate_dewpoint(T_g,T_w,P,max_iter=500,tol=1e-6):
    calculator = CalculatorMemory()
    for name,method,condition in methods:
        if not condition(T_w) and not condition(T_g):
            calculator.add_result(name,'不适用')
            continue

        es_wet = calculate_esat(T_w,method)
        es_dry = calculate_esat(T_g,method)
        gamma = 0.000667*(1+0.00115*T_w)*P
        e = es_wet-gamma*(T_g-T_w)
        rh = e/es_wet
        if e >= es_dry or rh >= 1:
            calculator.add_result(name,T_g,rh=1)
        else:
            try:
                Td = esat_calculate(e,method,max_iter,tol)
                calculator.add_result(name,Td,rh)
            except ZeroDivisionError:
                Td = T_g
                calculator.add_result(name,Td,rh)
            except:
                calculator.add_result(name,"计算失败")
    return calculator

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
        # memory
        self.calculator = None
        # 初始化输出列表
        self.list_model = QStringListModel()
        self.list_model_2 = QStringListModel()
        self.ui.listView.setModel(self.list_model)  # 绑定到左下角的 listView
        self.ui.listView_2.setModel(self.list_model_2)
        # initial initial guess
        self.initial_guess_strategy = "Td"

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
        # 迭代图按钮
        self.ui.pushButton.clicked.connect(self.show_convergence_plot)
        # 清空按钮
        self.ui.pushButton_2.clicked.connect(self.clearall)
        # 截屏按钮
        self.ui.pushButton_3.clicked.connect(self.take_screenshot)

    def clearall(self):
        self.list_model.setStringList([])
        self.list_model_2.setStringList([])
        self.ui.lineEdit.clear()
        self.ui.lineEdit_2.clear()
        self.ui.lineEdit_3.clear()

    def take_screenshot(self):
        # 捕获主窗口截图
        pixmap = self.ui.grab()

        # 弹出文件保存对话框
        file_path,_ = QFileDialog.getSaveFileName(
            self.ui,
            "保存截图",
            "",
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg)"
        )

        if file_path:
            try:
                pixmap.save(file_path)
                print(f"截图已保存至：{file_path}")
            except Exception as e:
                self.show_error_dialog(f"保存失败：{str(e)}")

    def upp(self):
        return self.pressure_min,self.pressure_max

    def upt(self):
        return self.temp_min,self.temp_max

    def get_initial_guess(self, T, T_other):
        """根据单选按钮状态返回初始猜测值"""
        if self.ui.radioButton_3.isChecked():
            return T_other
        elif self.ui.radioButton_4.isChecked():
            ini = T-2 if T < 0 else T-5
            return ini

    def update_input_labels(self):
        """根据模式更新输入标签"""
        if self.ui.radioButton_2.isChecked():  # 已知露点求湿球
            self.ui.label_2.setText("露点温度：")
            self.ui.widget_iteration.setVisible(True)
        else:  # 已知湿球求露点
            self.ui.label_2.setText("湿球温度：")
            self.ui.widget_iteration.setVisible(False)

    def show_convergence_plot(self):
        if self.calculator:
            self.calculator.show_convergence()
        else:
            self.show_error_dialog("请先执行计算！")

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
            if T_other >= T:
                raise ValueError(f"{target_label}不能高于干球温度！")

            if self.ui.radioButton_2.isChecked():
                try:
                    initial_guess = self.get_initial_guess(T,T_other)
                except ValueError as e:
                    self.show_error_dialog(str(e))
                    return
            else:
                initial_guess = None

            # 执行计算...
            print("输入验证通过，执行计算...")
            if self.ui.radioButton_2.isChecked():  # 已知露点求湿球
                self.calculator = calculate_wetbulb(initial_guess,T,T_other,P)
            else:  # 已知湿球求露点
                self.calculator = calculate_dewpoint(T,T_other,P)

                # 显示结果到左下角列表
            output = self.calculator.show_results("湿球" if self.ui.radioButton_2.isChecked() else "露点")
            self.list_model.setStringList(output.split('\n'))  # 按行分割字符串

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
