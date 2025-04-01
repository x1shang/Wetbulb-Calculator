import math
import sys
import os
import webbrowser
import matplotlib.pyplot as plt
from PySide2.QtWidgets import QApplication,QFileDialog,QAbstractItemView
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import Qt,QObject,QStringListModel
from PySide2.QtGui import QIcon

# 在创建 QApplication 前设置环境变量
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"  # 避免缩放倍数取整

# 创建应用实例
app = QApplication(sys.argv)
app.setAttribute(Qt.AA_EnableHighDpiScaling)  # 启用高 DPI 缩放
app.setAttribute(Qt.AA_UseHighDpiPixmaps)     # 支持高 DPI 图标

def resource_path(relative_path):
    """ 动态获取资源文件的绝对路径，兼容开发环境和打包后的EXE """
    if hasattr(sys, '_MEIPASS'):
        # 打包后的临时资源目录
        base_path = sys._MEIPASS
    else:
        # 开发环境下的当前目录
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 指定默认字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

MAGNUS_FORMULAS = {
    'Magnus-水面':lambda T:(6.112,17.62,243.12),
    'August-水面':lambda T:(6.1094,17.625,243.04),
    'Tetens-水面':lambda T:(6.1078,17.269,237.3),
    'Buck-水面':lambda T:(6.1121,17.502,240.97),
    'Arden-水面':lambda T:(6.1121,18.678,257.14),
    'Magnus-冰面':lambda T:(6.112,22.46,272.62),
    'Buck-冰面':lambda T:(6.1115,22.452,272.55),
}

GOFF_FORMULAS = {
    'Goff-水面':lambda T:(273.15,10.79574,-5.02808,1.50475e-4,-8.2969,0.42873e-3,4.76955,0.78614,0),
    'Goff2-水面':lambda T:(373.15,7.90298,-5.02808,1.3816e-5,-11.344,0.0081328,3.49149,3.0057149,0),
    'Goff-冰面':lambda T:(273.15,9.09718,3.56654,0,0,0,0,0.78614,0.876793),
}

WEXLER_FORMULAS = {
    'Wexler-水面':lambda T:(-5800.2206,1.3914993,-0.048640239,0.41764768e-4,-0.14452093e-7,0,6.5459673),
    'Wexler-冰面':lambda T:(-5674.5359,6.3925247,-0.009677843,0.62215701e-6,0.20747825e-8,-0.9484024e-12,4.1635019),
}

methods = [
    ('Goff-水面',lambda T_w:-10 <= T_w <= 100),
    ('Wexler-水面',lambda T_w:-10 <= T_w <= 200),
    ('Buck-水面',lambda T_w:0 <= T_w <= 80),
    ('Tetens-水面',lambda T_w:0 <= T_w <= 50),
    ('Magnus-水面',lambda T_w:0 <= T_w <= 60),
    ('August-水面',lambda T_w:0 <= T_w <= 60),
    ('Arden-水面',lambda T_w:0 <= T_w <= 100),
    ('Gili-水面',lambda T_w:-10 <= T_w <= 20),
    ('Goff2-水面',lambda T_w:-10 <= T_w <= 100),
    ('Goff-冰面',lambda T_w:-100 <= T_w <= 10),
    ('Wexler-冰面',lambda T_w:-150 <= T_w <= 10),
    ('Magnus-冰面',lambda T_w:-65 <= T_w <= 0),
    ('Buck-冰面',lambda T_w:-80 <= T_w <= 0),
    ('Marti-冰面',lambda T_w:-150 <= T_w <= 0),
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

    def show_results(self, mode):
        output = f"计算公式 | {mode}温度 | 相对湿度:\n"
        for item in self.methods:
            result = item['result']
            if isinstance(result, float):
                rh = item['rh']*100 if item['rh'] else 0
                if main_window.temperature_unit == 'K':
                    display_temp = result + 273.15
                elif main_window.temperature_unit == '℉':
                    display_temp = result * 9/5 + 32
                else:
                    display_temp = result
                output += f"{item['method']}:  {display_temp:.4f}{main_window.temperature_unit}  {rh:.2f}%\n"
            else:
                output += f"{item['method']}:   {result}\n"
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

def calculate_esat(T_w,method='Magnus-水面'):
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

    elif method == 'Gili-水面':
        term1 = -3.142305*(1e3/T_k-1e3/373.16)
        term2 = 8.2*math.log10(373.16/T_k)
        term3 = -0.0024804*(373.16-T_k)
        return 980.66*10**(0.00141966+term1+term2+term3)

    elif method == 'Marti-冰面':
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

    elif method == 'Gili-水面':
        term1 = -3.142305*(1e3/T_k-1e3/373.16)
        term2 = 8.2*math.log10(373.16/T_k)
        term3 = -0.0024804*(373.16-T_k)
        term4 = 3142.305/T_k**2-3.561215/T_k+0.0024804
        return 980.66*10**(0.00141966+term1+term2+term3)*math.log(10)*term4

    elif method == 'Marti-冰面':
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

    for name,condition in methods:

        e = calculate_esat(Td,name)
        if not condition(initial_guess):
            calculator.add_result(name,'不适用')
            continue
        T_w = initial_guess
        for iter_num in range(max_iter):
            try:
                e_sat = calculate_esat(T_w,name)
                gamma = 0.000667*(1+0.00115*T_w)*P
                f = e_sat-gamma*(T-T_w)-e
                de_dT = calculate_dedt(T_w,name,P)
                df_dT = de_dT+gamma-0.000667*0.00115*P*(T-T_w)
                T_w_new = T_w-f/df_dT
                calculator.add_iteration(name,iter_num+1,T_w,abs(f))

                if abs(T_w_new-T_w) < tol and not iter_num < 4:
                    last_rh = e/calculate_esat(T,name)
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
    for name,condition in methods:
        if not condition(T_w) and not condition(T_g):
            calculator.add_result(name,'不适用')
            continue

        es_wet = calculate_esat(T_w,name)
        es_dry = calculate_esat(T_g,name)
        gamma = 0.000667*(1+0.00115*T_w)*P
        e = es_wet-gamma*(T_g-T_w)
        rh = e/es_dry
        if e >= es_dry or rh >= 1:
            calculator.add_result(name,T_g,rh=1)
        else:
            try:
                Td = esat_calculate(e,name,max_iter,tol)
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
        app.setWindowIcon(QIcon(resource_path('app.ico')))
        self.ui = QUiLoader().load(resource_path('calculator.ui'))
        self.ui.setWindowIcon(QIcon(resource_path('app.ico')))
        self.bind_events()
        self.update_input_labels()
        self.ui.widget_iteration.setVisible(True)
        self.temp_min = -150
        self.temp_max = 200
        self.pressure_min = 500
        self.pressure_max = 1100
        self.calculator = None
        self.list_model = QStringListModel()
        self.list_model_2 = QStringListModel()
        self.ui.listView.setModel(self.list_model)  # 绑定到左下角的 listView
        self.ui.listView_2.setModel(self.list_model_2)
        self.ui.listView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.listView_2.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ui.dial.setRange(2,10)
        self.ui.dial.setValue(6)
        self.ui.dial.setNotchesVisible(True)
        self.ui.dial.setSingleStep(1)
        self.initial_guess_strategy = "Td"
        self.temperature_unit = '℃'
        self.pressure_unit = 'hPa'

    def bind_events(self):
        # 模式切换
        self.ui.radioButton_2.toggled.connect(self.update_input_labels)
        self.ui.radioButton_2.toggled.connect(self.clearall)
        self.ui.radioButton.toggled.connect(self.update_input_labels)
        self.ui.radioButton.toggled.connect(self.clearall)
        # 计算按钮
        self.ui.pushButton_6.clicked.connect(self.validate_and_calculate)
        self.ui.lineEdit_2.returnPressed.connect(self.validate_and_calculate)
        self.ui.lineEdit_2.returnPressed.connect(lambda:self.list_model_2.setStringList([]))
        self.ui.lineEdit_2.returnPressed.connect(lambda:self.check_input(self.ui.lineEdit_2,"大气压强"))
        # 单位切换
        self.ui.pushButton_5.clicked.connect(self.show_unit_dialog)
        # 关于按钮
        self.ui.pushButton_4.clicked.connect(self.show_about_dialog)
        # 转换焦点
        self.ui.lineEdit_3.returnPressed.connect(lambda:self.ui.lineEdit.setFocus())
        self.ui.lineEdit_3.returnPressed.connect(lambda:self.check_input(self.ui.lineEdit_3,"干球温度"))
        self.ui.lineEdit.returnPressed.connect(lambda:self.ui.lineEdit_2.setFocus())
        self.ui.lineEdit.returnPressed.connect(
            lambda:self.check_input(self.ui.lineEdit,self.ui.label_2.text())
        )
        # 迭代图按钮
        self.ui.pushButton.clicked.connect(self.show_convergence_plot)
        # 精度旋钮
        self.ui.dial.valueChanged.connect(self.update_ini)
        # 清空按钮
        self.ui.pushButton_2.clicked.connect(self.clearall)
        # 截屏按钮
        self.ui.pushButton_3.clicked.connect(self.take_screenshot)
        # 进一步计算
        self.ui.listView.clicked.connect(self.on_list_item_clicked)

    def update_ini(self,value):
        global tot
        tot = 10**(-value)

    def on_list_item_clicked(self,index):
        row = index.row()
        self.list_model_2.setStringList([])
        if row <= 0 or row > len(self.calculator.methods):
            return
        method_data = self.calculator.methods[row-1]
        method_name = method_data['method']
        result = method_data['result']
        rh = method_data['rh']
        if not isinstance(result,float):
            return

        try:
            T_g_input = float(self.ui.lineEdit_3.text())
            T_g = self.changetemp(T_g_input)
            T_g_K = T_g+273.15

            if "露点" in self.ui.label_2.text():
                Td = result
                Tw = self.changetemp(float(self.ui.lineEdit.text()))
            else:
                Tw = result
                Td = self.changetemp(float(self.ui.lineEdit.text()))

            P_input = float(self.ui.lineEdit_2.text())
            P_hPa = self.changepre(P_input)

            R = 8.314462618
            Mv = 18.01528
            Md = 28.9647
            Rv = 1000*R/Mv  # 水汽气体常数
            Rd = 1000*R/Md  # 干空气
            Cp = 1004.7463+0.05*T_g  # 定压比热容（精确值）
            Cpw = 1864 # 水的定压比热容
            ups = Mv/Md
            upsilon = (1-ups)/ups

            esd = calculate_esat(Td,method_name)
            esw = calculate_esat(Tw,method_name)
            e = calculate_esat(T_g,method_name)
            P_dry = P_hPa-esw

            ro_dry = P_dry*100/(Rd*T_g_K)
            ro_vapor = esw*100/(Rv*T_g_K)
            ro = ro_dry+ro_vapor
            dm = ro_vapor/ro_dry #含湿量就是混合率
            dm1 = dm*1000
            L_v = 2500.8-2.3665*T_g-0.0023*T_g**2+1.87e-5*T_g**3-4.2e-8*T_g**4 # 蒸发潜热
            han = Cp/1000*T_g+(L_v+Cpw/1000*T_g)*dm

            esd1 = self.prechange(esd)
            esw1 = self.prechange(esw)
            e1 = self.prechange(e)
            P_dry1 = self.prechange(P_dry)

            sat_mixing_ratio = ups*(e/(P_hPa-e))*1000 if P_hPa > e else 0 # 饱和混合率 (g/kg)
            absolute_humidity = (esw*100)/(Rv*T_g_K)*1e3  # 绝对湿度 (g/m³)
            specific_humidity = (ups*esw)/(P_hPa-(1-ups)*esw)*1000 if P_hPa > (1-ups)*esw else 0 # 比湿 (g/kg)

            q = specific_humidity/1000  # 比湿转kg/kg
            virtual_temp_K = T_g_K*(1+upsilon*q)  # 精确系数0.6078
            virtual_temp = self.tempchange(virtual_temp_K-273.15)# 虚温

            theta_K = T_g_K*(1000/P_hPa)**(Rd/Cp)
            theta = self.tempchange(theta_K-273.15)# 位温THTA
            theta_e = theta_K*math.exp(L_v*q/(Cp*T_g_K))# 相当位温THTE
            theta_v = theta_K*(1+upsilon*q)# 虚位温THTV
            theta_E = self.tempchange(theta_e-273.15)
            theta_V = self.tempchange(theta_v-273.15)

            t_lcl0 = 1/(Td+243.5)-math.log(rh)/5423
            t_lcl = self.tempchange(1/t_lcl0-243.5)
            p_lcl0 = P_hPa*(t_lcl0+273.15/T_g_K)**(9.81/(Rd*9.81))
            p_lcl = self.prechange(p_lcl0)

            results = [
                f"{method_name} | 常用气象参数",
                f"相对湿度: {rh*100:.2f}%",
                f"绝对湿度: {absolute_humidity:.3f} g/m³",
                f"比湿: {specific_humidity:.3f} g/kg",
                f"蒸气压: {esw1:.2f} {self.pressure_unit}",
                f"饱和蒸气压: {e1:.2f} {self.pressure_unit}",
                f"干空气分压: {P_dry1:.1f} {self.pressure_unit}",
                f"干空气密度: {ro_dry:.3f} kg/m³",
                f"水蒸气密度: {ro_vapor:.3f} kg/m³",
                f"空气密度: {ro:.3f} kg/m³",
                f"焓值: {han:.2f} kJ/kg",
                f"蒸发潜热: {L_v:.1f} kJ/kg",
                f"含湿量: {dm1:.3f} g/kg",
                f"饱和混合率: {sat_mixing_ratio:.3f} g/kg",
                f"位温: {theta:.2f} {self.temperature_unit}",
                f"相当位温: {theta_E:.2f} {self.temperature_unit}",
                f"虚温: {virtual_temp:.2f} {self.temperature_unit}",
                f"虚位温: {theta_V:.2f} {self.temperature_unit}",
                f"lcl温度: {t_lcl:.2f} {self.temperature_unit}",
                f"lcl压强: {p_lcl:.1f} {self.pressure_unit}",
                f"露点蒸气压: {esd1:.2f} {self.pressure_unit}",
            ]
            self.list_model_2.setStringList(results)

        except Exception as e:
            self.show_error_dialog(f"计算错误: {str(e)}")

    def clearall(self):
        self.list_model.setStringList([])
        self.list_model_2.setStringList([])
        self.ui.lineEdit.clear()
        self.ui.lineEdit_2.clear()
        self.ui.lineEdit_3.clear()
        self.calculator = None

    def take_screenshot(self):
        # 捕获主窗口截图
        pixmap = self.ui.grab()
        # 弹出文件保存对话框
        file_path,_ = QFileDialog.getSaveFileName(self.ui,"保存截图","","PNG 图片 (*.png);;JPEG 图片 (*.jpg)")
        if file_path:
            try:
                pixmap.save(file_path)
                print(f"截图已保存至：{file_path}")
            except Exception as e:
                self.show_error_dialog(f"保存失败：{str(e)}")

    def changepre(self,P):
        if self.pressure_unit == 'hPa':
            return P
        elif self.pressure_unit == 'Pa':
            P /= 100
        elif self.pressure_unit == 'mmHg':
            P *= 1.33322
        elif self.pressure_unit == 'cmHg':
            P *= 13.3322
        elif self.pressure_unit == 'bar':
            P *= 1000
        return P

    def prechange(self,P):
        if self.pressure_unit == 'Pa':
            P *= 100
        elif self.pressure_unit == 'mmHg':
            P /= 1.33322
        elif self.pressure_unit == 'cmHg':
            P /= 13.3322
        elif self.pressure_unit == 'bar':
            P /= 1000
        else:
            P = P
        return P

    def changetemp(self,temperature):
        if self.temperature_unit == 'K':
            temperature -= 273.15
        elif self.temperature_unit == '℉':
            temperature = (temperature-32)*5/9
        else:
            temperature = temperature
        return temperature

    def tempchange(self,temperature):
        if self.temperature_unit == 'K':
            temperature += 273.15
        elif self.temperature_unit == '℉':
            temperature = temperature*9/5+32
        else:
            temperature = temperature
        return temperature

    def get_initial_guess(self, T, T_other):
        if self.ui.radioButton_3.isChecked():
            return T_other
        elif self.ui.radioButton_4.isChecked():
            ini = T-2 if T < 0 else T-5
            return ini

    def update_input_labels(self):
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

    def check_input(self,line_edit,field_name):
        text = line_edit.text().strip()
        if not text:
            self.show_error_dialog(f"{field_name}不能为空！")
            line_edit.clear()
            return False
        try:
            cleaned_text = ''.join(filter(lambda x:x.isdigit() or x in ('.','-'),text))
            value = float(cleaned_text)

            if "温度" in field_name:
                value_C = self.changetemp(value)
                if value_C < -150 or value_C > 200:
                    min_ui = self.tempchange(-150)
                    max_ui = self.tempchange(200)
                    self.show_error_dialog(
                        f"{field_name}需在 [{min_ui:.2f}, {max_ui:.2f}]{self.temperature_unit} 范围内")
                    line_edit.clear()
                    return False
            elif "压强" in field_name:
                value_hPa = self.changepre(value)
                if value_hPa < 500 or value_hPa > 1100:
                    min_ui = self.prechange(500)
                    max_ui = self.prechange(1100)
                    self.show_error_dialog(f"{field_name}需在 [{min_ui:.2f}, {max_ui:.2f}]{self.pressure_unit} 范围内")
                    line_edit.clear()
                    return False

            return True
        except ValueError:
            self.show_error_dialog(f"{field_name}必须是有效数字！")
            line_edit.clear()
            return False

    def validate_and_calculate(self):
        try:
            if not self.check_input(self.ui.lineEdit_3,"干球温度"):
                return
            T_input = float(self.ui.lineEdit_3.text())
            T = self.changetemp(T_input)
            target_label = self.ui.label_2.text().replace(' ','').rstrip("：")
            if not self.check_input(self.ui.lineEdit,target_label):
                return
            T_other_input = float(self.ui.lineEdit.text())
            T_other = self.changetemp(T_other_input)
            if not self.check_input(self.ui.lineEdit_2,"大气压强"):
                return
            P_input = float(self.ui.lineEdit_2.text())
            P = self.changepre(P_input)

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

            if self.ui.radioButton_2.isChecked():  # 已知露点求湿球
                self.calculator = calculate_wetbulb(initial_guess,T,T_other,P,tol=tot)
            else:  # 已知湿球求露点
                self.calculator = calculate_dewpoint(T,T_other,P,tol=tot)

            output = self.calculator.show_results("湿球" if self.ui.radioButton_2.isChecked() else "露点")
            self.list_model.setStringList(output.split('\n'))  # 按行分割字符串

        except Exception as e:
            self.show_error_dialog(str(e))

    def show_error_dialog(self,message):
        error_dialog = QUiLoader().load(resource_path('err.ui'))
        error_dialog.setWindowIcon(QIcon(resource_path('err.ico')))
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
        self.ui = QUiLoader().load(resource_path('关于.ui'))
        self.ui.setWindowIcon(QIcon(resource_path('app.ico')))
        self.ui.pushButton.clicked.connect(self.ui.close)
        self.ui.pushButton_2.clicked.connect(lambda: webbrowser.open("https://github.com/x1shang/Wetbulb-Calculator"))

class UnitDialog:
    def __init__(self,main_window):
        self.ui = QUiLoader().load(resource_path('单位.ui'))
        self.ui.setWindowIcon(QIcon(resource_path('app.ico')))
        self.main_window = main_window
        self.ui.pushButton.clicked.connect(self.update_units)
        self.ui.pushButton.clicked.connect(lambda:self.main_window.clearall())
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
            self.ui.radioButton_6: ('K', 123.15, 473.15),  # -150℃=123.15K, 200℃=473.15K
            self.ui.radioButton_7: ('℃', -150, 200),
            self.ui.radioButton_8: ('℉', -238, 392)        # -150℃=-238℉, 200℃=392℉
        }

        for rb,(unit,_,_) in pressure_units.items():
            if rb.isChecked():
                self.main_window.pressure_unit = unit
                break
        for rb,(unit,_,_) in temperature_units.items():
            if rb.isChecked():
                self.main_window.temperature_unit = unit
                break

        for rb,(unit,min_val,max_val) in pressure_units.items():
            if rb.isChecked():
                self.main_window.pressure_min = min_val
                self.main_window.pressure_max = max_val
                self.main_window.pressure_unit = unit
                self.main_window.ui.lineEdit_2.setPlaceholderText(
                    f"{min_val}~{max_val}{unit}"
                )
                break
        for rb,(unit,min_val,max_val) in temperature_units.items():
            if rb.isChecked():
                self.main_window.temp_min = min_val
                self.main_window.temp_max = max_val
                self.main_window.temperature_unit = unit
                self.main_window.ui.lineEdit_3.setPlaceholderText(
                    f"{min_val}~{max_val}{unit}"
                )
                self.main_window.ui.lineEdit.setPlaceholderText(
                    f"{min_val}~{max_val:}{unit} 且小于干球"
                )
                break
        self.ui.close()

if __name__ == '__main__':
    main_window = MainWindow()
    main_window.ui.show()
    sys.exit(app.exec_())
