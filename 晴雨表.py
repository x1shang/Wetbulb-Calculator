import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

    
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 指定默认字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

MAGNUS_FORMULAS = {
    'magnus_water': lambda T: (6.112, 17.62, 243.12),
    'august_water': lambda T: (6.1094, 17.625, 243.04),
    'tetens_water': lambda T: (6.1078, 17.269, 237.3),
    'buck_water': lambda T: (6.1121, 17.502, 240.97),
    'arden_water': lambda T: (6.1121, 18.678, 257.14),
    'magnus_ice': lambda T: (6.112, 22.46, 272.62),
    'buck_ice': lambda T: (6.1115, 22.452, 272.55),
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


class CalculatorMemory:
    def __init__(self):
        self.methods = []
        self.iteration_data = {}

    def add_result(self, method_name, result, rh=None):
        self.methods.append({
            "method": method_name, 
            "result": result,
            "rh": rh
        })

    def show_results(self, mode):
        print(f"\n{mode}温度|相对湿度:")
        for item in self.methods:
            result = item['result']
            if isinstance(result, float):
                rh = item['rh'] * 100 if item['rh'] else 0
                print(f"{item['method']}: {result:.4f}°C   {rh:.2f}%")
            else:
                print(f"{item['method']}: {result}")

    def add_iteration(self, method, iteration, T_w, residual):
        """记录单次迭代数据"""
        if method not in self.iteration_data:
            self.iteration_data[method] = {
                'iterations': [],
                'temperatures': [],
                'residuals': []
            }
        self.iteration_data[method]['iterations'].append(iteration)
        self.iteration_data[method]['temperatures'].append(T_w)
        self.iteration_data[method]['residuals'].append(abs(residual))

    def show_convergence(self):
        """绘制收敛过程图"""
        plt.figure(figsize=(12, 6))
    
        # 温度变化子图
        plt.subplot(1, 2, 1)
        for method, data in self.iteration_data.items():
            # 跳过第一次迭代（索引0对应的数据）
            iterations = data['iterations'][1:]
            temperatures = data['temperatures'][1:]
            plt.plot(iterations, temperatures, 
                    marker='o', label=method)
        plt.xlabel('迭代次数')
        plt.ylabel('湿球温度估计值 (°C)')
        plt.title('温度迭代过程')
        plt.grid(True)
        plt.legend()
    
        # 残差变化子图
        plt.subplot(1, 2, 2)
        for method, data in self.iteration_data.items():
            iterations = data['iterations'][1:]
            residuals = data['residuals'][1:]
            plt.semilogy(iterations, residuals,
                        marker='s', label=method)
        plt.xlabel('迭代次数')
        plt.ylabel('残差 (对数刻度)')
        plt.title('残差收敛过程')
        plt.grid(True)
        plt.legend()
    
        plt.tight_layout()
        plt.show()

methods = [
        ('Goff-水面', 'goff_water', lambda T_w: -10 <= T_w <= 100),
        ('Wexler-水面', 'wexler_water', lambda T_w: -10 <= T_w <= 200),
        ('Buck-水面', 'buck_water', lambda T_w: 0 <= T_w <= 80),
        ('Tetens-水面', 'tetens_water', lambda T_w: 0 <= T_w <= 50),
        ('Magnus-水面', 'magnus_water', lambda T_w: 0 <= T_w <= 60),
        ('August-水面', 'august_water', lambda T_w: 0 <= T_w <= 60),
        ('Arden-水面', 'arden_water', lambda T_w: 0 <= T_w <= 100),
        ('Gili-水面', 'gili_water', lambda T_w: -10 <= T_w <= 20),
        ('Goff2-水面', 'goff_new', lambda T_w: -10 <= T_w <= 100),
        ('Goff-冰面', 'goff_ice', lambda T_w: -100 <= T_w <= 10),
        ('Wexler-冰面', 'wexler_ice', lambda T_w: -150 <= T_w <= 10),
        ('Magnus-冰面', 'magnus_ice', lambda T_w: -65 <= T_w <= 0),
        ('Buck-冰面', 'buck_ice', lambda T_w: -80 <= T_w <= 0),
        ('Marti-冰面', 'marti_ice', lambda T_w: -150 <= T_w <= 0),   
    ]

def check_input(prompt, num_type=float, min_v=None, max_v=None):
    
    while True:
        try:
            value = num_type(input(prompt).strip())
            if (min_v is not None and value < min_v) or (max_v is not None and value > max_v):
                print(f"输入值需在[{min_v}, {max_v}]范围内")
                continue
            return value
        except ValueError:
            print(f"请输入有效的{num_type.__name__}值")

def check_temp(prompt,T):
    while True:
        T1 = check_input(f"请输入{prompt}温度(℃): ", min_v=-150, max_v=200)
        if T1 > T:
            print(f"错误：{prompt}温度不能高于干球温度！")
            continue
        else:
            return T1

def calculate_esat(T_w, method='magnus'):

    T_k = T_w + 273.15
    
    if method in MAGNUS_FORMULAS:
        A, B, C = MAGNUS_FORMULAS[method](T_w)
        return A * math.exp(B * T_w / (C + T_w))
    
    elif method in GOFF_FORMULAS:
        A, B, C, D, E, F, G, H, I = GOFF_FORMULAS[method](T_w)
        term1 = B * (1 - A/T_k)
        term2 = C * math.log10(T_k/A)
        term3 = D * (1 - 10**(E*(T_k/A - 1)))
        term4 = F * (10**(G*(1 - A/T_k)) - 1)
        term5 = I * (1 - T_k/A)
        return 10**(term1 + term2 + term3 + term4 + term5 + H)

    elif method in WEXLER_FORMULAS:
        A, B, C, D, E, F, G = WEXLER_FORMULAS[method](T_w)
        term1 = A / T_k
        term2 = B 
        term3 = C * T_k  
        term4 = D * T_k**2 
        term5 = E * T_k**3
        term6 = F * T_k**4
        term7 = G * math.log(T_k)
        ln_esat = term1 + term2 + term3 + term4 + term5 + term6 + term7
        return math.exp(ln_esat) / 100
    
    elif method == 'gili_water':
        term1 = -3.142305 * (1e3/T_k - 1e3/373.16)
        term2 = 8.2 * math.log10(373.16/T_k)
        term3 = -0.0024804 * (373.16 - T_k)
        return 980.66 * 10**(0.00141966 + term1 + term2 + term3)

    elif method == 'marti_ice':
        lg_esat = -2663.5 / T_k + 12.537
        return 10**lg_esat / 100
    
    else:
        raise ValueError("无效的计算方法")


def calculate_dedt(T_w, method, P=1013.25, delta=0.001):

    T_k = T_w + 273.15

    if method in MAGNUS_FORMULAS:
        A, B, C = MAGNUS_FORMULAS[method](T_w)
        e_sat = calculate_esat(T_w, method)
        return e_sat * (B*C) / (C + T_w)**2

    elif method in GOFF_FORMULAS:
        A, B, C, D, E, F, G, H, I = GOFF_FORMULAS[method](T_w)
        term1 = B*A/T_k**2
        term2 = C/A * math.log10(T_k/A) * math.log(10)
        term3 = -D*E/A * math.log(10) * 10**(E*(T_k/A - 1))
        term4 = A*F*G/T_k**2 * 10**(G*(1 - A/T_k)) * math.log(10) 
        term5 = -I/A
        e_sat = calculate_esat(T_w, method)
        return e_sat * math.log(10) * (term1+term2+term3+term4+term5)

    elif method in WEXLER_FORMULAS:
        e_sat = calculate_esat(T_w, method)
        A, B, C, D, E, F, G = WEXLER_FORMULAS[method](T_w)
        d_sat = -A / T_k**2 + C + 2*D*T_k + 3*E*T_k**2 + 4*F*T_k**3 + G/T_k
        return e_sat*d_sat

    elif method == 'gili_water':
        term1 = -3.142305 * (1e3/T_k - 1e3/373.16)
        term2 = 8.2 * math.log10(373.16/T_k)
        term3 = -0.0024804 * (373.16 - T_k)
        term4 = 3142.305/T_k**2 - 3.561215/T_k + 0.0024804
        return 980.66 * 10**(0.00141966 + term1 + term2 + term3) * math.log(10) * term4

    elif method == 'marti_ice':
        lg_esat = -2663.5 / T_k + 12.537
        return 10**lg_esat / 100 * math.log(10) * 2663.5 / T_k**2
    
    else:
        e1 = calculate_esat(T_w - delta, method)
        e2 = calculate_esat(T_w + delta, method)
        return (e2 - e1) / (2*delta)

def esat_calculate(e,method,max_iter,tol,mint=-150,maxt=200):

    if method in MAGNUS_FORMULAS:
        A, B, C = MAGNUS_FORMULAS[method](e)
        term1 = math.log(e/A)
        return C*term1/(B-term1)

    for iter_num in range(max_iter):
        t = (mint + maxt) / 2
        ft = calculate_esat(t,method) - e
        if abs(ft) < tol and not iter_num < 99:
            return t
        if ft > 0:
            maxt = t
        else:
            mint = t
    return (mint + maxt)/2


def calculate_wetbulb(T, Td, P=1013.25, max_iter=50, tol=1e-6):
    global f
    calculator = CalculatorMemory()
    
    print("\n请选择迭代初始值：\n1. 使用T_w=Td\n2. 使用T_w=T-n")
    while True:
        choice = input("请输入您的选择（1,2）：")
        if choice == "1":
            initial_guess = Td
            break
        elif choice == "2":
            initial_guess = T-2 if T < 0 else T-5
            break
        print("无效操作！")

    for name, method, condition in methods:

        e = calculate_esat(Td, method)
        if not condition(initial_guess):  
            calculator.add_result(name, '不适用')
            continue
        T_w = initial_guess
        last_rh = None
        for iter_num in range(max_iter):
            try:
                e_sat = calculate_esat(T_w, method)
                gamma = 0.000667 * (1 + 0.00115 * T_w) * P
                f = e_sat - gamma * (T - T_w) - e
                de_dT = calculate_dedt(T_w, method, P)  
                df_dT = de_dT + gamma - 0.00066 * 0.00115 * P * (T - T_w)
                T_w_new = T_w - f / df_dT
                calculator.add_iteration(name, iter_num+1, T_w, abs(f))
                
                if abs(T_w_new - T_w) < tol and not iter_num < 4:
                    last_rh = e / calculate_esat(T_w_new, method)
                    if last_rh <= 1 and last_rh >= 0:
                        calculator.add_result(name,T_w_new, last_rh)
                        break
                    else:
                        calculator.add_result(name, "结果不符常理")
                        break
                        
                elif abs(f) > 1e3:  
                    calculator.add_result(name, "残差过大")
                    break
                
                T_w = T_w_new
              
            except OverflowError:
                calculator.add_result(name, '数值溢出')
                break
            except Exception as e:
                calculator.add_result(name, f'错误: {str(e)}')
                break
            except:
                calculator.add_result(name, '计算失败')
                break
        else:
            calculator.add_result(name, '未收敛')
            calculator.add_iteration(name, max_iter, T_w, abs(f))
    
    return calculator

def calculate_dewpoint(T_g, T_w, P,max_iter=500,tol=1e-6):
    calculator = CalculatorMemory()
    for name, method, condition in methods:
        if not condition(T_w) and not condition(T_g):  
            calculator.add_result(name, '不适用')
            continue
        
        es_wet = calculate_esat(T_w,method)
        es_dry = calculate_esat(T_g,method)
        gamma = 0.000667 * (1 + 0.00115 * T_w) * P
        e = es_wet - gamma * (T_g-T_w)
        rh = e/es_wet
        if e >= es_dry or rh >= 1:
            calculator.add_result(name,T_g,rh=1)
        else:
            try:
                Td = esat_calculate(e,method,max_iter,tol)
                calculator.add_result(name, Td, rh)
            except ZeroDivisionError:
                Td = T_g
                calculator.add_result(name, Td, rh)
            except:
                calculator.add_result(name,"计算失败")
    return calculator

class TemperatureConverter:
    @staticmethod
    def C_to_F(c):
        return c*9/5+32

    @staticmethod
    def F_to_C(f):
        return (f-32)*5/9

    @staticmethod
    def hPa_to_mmHg(hpa):
        return hpa*0.750062

    @staticmethod
    def mmHg_to_hPa(mmhg):
        return mmhg/0.750062

class TemperatureApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("多功能温度计 v2.0")
        self.geometry("900x600")
        self.create_widgets()
        self.setup_units()
        self.calculator = None

    def setup_units(self):
        self.temp_units = {
            "℃ (摄氏度)":("temp",lambda x:x),
            "℉ (华氏度)":("temp",TemperatureConverter.C_to_F)
        }
        self.pressure_units = {
            "hPa (百帕)":("pressure",lambda x:x),
            "mmHg (毫米汞柱)":("pressure",TemperatureConverter.mmHg_to_hPa)
        }

    def create_widgets(self):
        # 单位选择
        unit_frame = ttk.LabelFrame(self,text="单位设置")
        unit_frame.pack(pady=10,fill=tk.X)

        ttk.Label(unit_frame,text="温度单位:").grid(row=0,column=0,padx=5)
        self.temp_unit = ttk.Combobox(unit_frame,values=list(self.temp_units.keys()))
        self.temp_unit.current(0)
        self.temp_unit.grid(row=0,column=1,padx=5)

        ttk.Label(unit_frame,text="压力单位:").grid(row=0,column=2,padx=5)
        self.press_unit = ttk.Combobox(unit_frame,values=list(self.pressure_units.keys()))
        self.press_unit.current(0)
        self.press_unit.grid(row=0,column=3,padx=5)

        # 输入参数
        input_frame = ttk.LabelFrame(self,text="输入参数")
        input_frame.pack(pady=10,fill=tk.X)

        self.mode_var = tk.IntVar(value=1)
        tk.Radiobutton(input_frame,text="已知干球和露点",variable=self.mode_var,value=1).grid(row=0,column=0)
        tk.Radiobutton(input_frame,text="已知干球和湿球",variable=self.mode_var,value=2).grid(row=0,column=1)

        self.entries = {}
        params = [("dry_bulb","干球温度"),("wet_dew","湿球/露点温度"),("pressure","大气压")]
        for i,(key,label) in enumerate(params):
            ttk.Label(input_frame,text=label).grid(row=1,column=i*2)
            self.entries[key] = ttk.Entry(input_frame,width=10)
            self.entries[key].grid(row=1,column=i*2+1)

        # 计算按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame,text="计算",command=self.calculate).pack(side=tk.LEFT,padx=5)
        ttk.Button(btn_frame,text="显示图表",command=self.show_chart).pack(side=tk.LEFT,padx=5)
        ttk.Button(btn_frame,text="清空",command=self.clear).pack(side=tk.LEFT,padx=5)

        # 结果展示
        self.result_tree = ttk.Treeview(self,columns=("method","result","rh"),show="headings")
        self.result_tree.heading("method",text="计算方法")
        self.result_tree.heading("result",text="结果")
        self.result_tree.heading("rh",text="相对湿度")
        self.result_tree.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)

    def convert_units(self,value,unit_type):
        if unit_type == "temp":
            selected = self.temp_units[self.temp_unit.get()]
        else:
            selected = self.pressure_units[self.press_unit.get()]

        return selected[1](value) if selected[0] == unit_type else value

    def get_converted_value(self,value,unit_type):
        if unit_type == "temp":
            selected = self.temp_units[self.temp_unit.get()]
        else:
            selected = self.pressure_units[self.press_unit.get()]

        if selected[0] == "temp":
            return TemperatureConverter.C_to_F(value) if "华氏" in self.temp_unit.get() else value
        else:
            return TemperatureConverter.hPa_to_mmHg(value) if "汞柱" in self.press_unit.get() else value

    def calculate(self):
        try:
            # 获取并转换输入值
            T = float(self.entries["dry_bulb"].get())
            T = self.convert_units(T,"temp")

            second_val = float(self.entries["wet_dew"].get())
            second_val = self.convert_units(second_val,"temp")

            P = float(self.entries["pressure"].get())
            P = self.convert_units(P,"pressure")

            mode = self.mode_var.get()

            if mode == 1:
                self.calculator = calculate_wetbulb(T,second_val,P)
            else:
                self.calculator = calculate_dewpoint(T,second_val,P)

            self.show_results()

        except ValueError as e:
            messagebox.showerror("输入错误","请输入有效的数值")
        except Exception as e:
            messagebox.showerror("计算错误",str(e))

    def show_results(self):
        self.result_tree.delete(*self.result_tree.get_children())

        for item in self.calculator.methods:
            result = item['result']
            rh = item['rh']

            if isinstance(result,float):
                # 转换结果单位
                converted = self.get_converted_value(result,"temp")
                unit = "℉" if "华氏" in self.temp_unit.get() else "℃"
                result_str = f"{converted:.2f}{unit}"
                rh_str = f"{rh*100:.1f}%" if rh else ""
            else:
                result_str = result
                rh_str = ""

            self.result_tree.insert("","end",values=(item['method'],result_str,rh_str))

    def show_chart(self):
        if self.calculator and hasattr(self.calculator,"show_convergence"):
            self.calculator.show_convergence()

    def clear(self):
        for entry in self.entries.values():
            entry.delete(0,tk.END)
        self.result_tree.delete(*self.result_tree.get_children())
        self.calculator = None

if __name__ == "__main__":
    app = TemperatureApp()
    app.mainloop()