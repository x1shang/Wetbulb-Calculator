import math
import matplotlib.pyplot as plt

print("湿球温度计算器 (版本5.1.4)")
print("\n降水相态研究性学习小组 制作")
print("\n引用：\n周西华,梁茵 等 (2007). 饱和水蒸气分压力经验公式的比较[J]. \n辽宁工业技术大学学报, 26(3), 331-333. ")
print("------------------------------------------------------")
    
# 设置中文字体（以微软雅黑为例）
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 指定默认字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

class WetbulbCalculator:
    def __init__(self):
        self.methods = []
        self.iteration_data = {}

    def add_result(self, method_name, result):
        self.methods.append({"method": method_name, "result": result})

    def show_results(self):
        print("\n湿球温度估算值:")
        for item in self.methods:
            result = item['result']
            if isinstance(result, float):
                print(f"{item['method']}: {result:.4f}°C")
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
            plt.plot(data['iterations'], data['temperatures'], 
                    marker='o', label=method)
        plt.xlabel('迭代次数')
        plt.ylabel('湿球温度估计值 (°C)')
        plt.title('温度迭代过程')
        plt.grid(True)
        plt.legend()
        
        # 残差变化子图
        plt.subplot(1, 2, 2)
        for method, data in self.iteration_data.items():
            plt.semilogy(data['iterations'], data['residuals'],
                        marker='s', label=method)
        plt.xlabel('迭代次数')
        plt.ylabel('残差 (对数刻度)')
        plt.title('残差收敛过程')
        plt.grid(True)
        plt.legend()
        
        plt.tight_layout()
        plt.show()

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

def calculate_esat(T_w, method='magnus'):
    """统一计算饱和蒸气压"""
    T_k = T_w + 273.15
    
    if method == 'magnus_water':  #这个就是sonntag公式
        return 6.112 * math.exp(17.62 * T_w / (243.12 + T_w))
    elif method == 'august_water':
        return 6.1094 * math.exp(17.625 * T_w / (T_w + 243.04))
    elif method == 'tetens_water':
        return 6.1078 * math.exp(17.269 * T_w / (T_w + 237.3))
    elif method == 'buck_water':
        return 6.1121 * math.exp(17.502 * T_w / (T_w + 240.97))
    elif method == 'arden_water':
        return 6.1121 * math.exp(18.678 * T_w / (T_w + 257.14))
    
    elif method == 'magnus_ice':  #这个就是sonntag公式
        return 6.112 * math.exp(22.46 * T_w / (272.62 + T_w))
    elif method == 'buck_ice':
        return 6.1115 * math.exp(22.452 * T_w / (T_w + 272.55))

    elif method == 'gili_water':
        term1 = -3.142305 * (1e3/T_k - 1e3/373.16)
        term2 = 8.2 * math.log10(373.16/T_k)
        term3 = -0.0024804 * (373.16 - T_k)
        return 980.66 * 10**(0.00141966 + term1 + term2 + term3)

    elif method == 'goff_water':
        term1 = 10.79574 * (1 - 273.16/T_k)
        term2 = -5.028 * math.log10(T_k/273.16)
        term3 = 1.50475e-4 * (1 - 10**(-8.2969*(T_k/273.16 - 1)))
        term4 = 0.42873e-3 * (10**(4.76955*(1 - 273.16/T_k)) - 1)
        return 10**(term1 + term2 + term3 + term4 + 0.78614)
    elif method == 'goff_ice':
        term1 = -9.09718 * (273.15/T_k - 1)
        term2 = -3.56654 * math.log10(273.15/T_k)
        term3 = 0.876793 * (1 - T_k/273.15)
        return 10**(term1 + term2 + term3 + 0.78614)
    
    #这个就是Hyland_Wexler公式
    elif method == 'wexler_water':
        term1 = -5800.2206 / T_k
        term2 = 1.3914993 
        term3 = -0.048640239 * T_k  
        term4 = 0.41764768e-4 * T_k**2 
        term5 = -0.14452093e-7 * T_k**3
        term6 = 6.5459673 * math.log(T_k)
        ln_esat = term1 + term2 + term3 + term4 + term5 + term6
        return math.exp(ln_esat) / 100  # 转换为hPa
    elif method == 'wexler_ice':
        term1 = -5674.5359 / T_k
        term2 = 6.3925247 
        term3 = -0.009677843 * T_k  
        term4 = 0.62215701e-6 * T_k**2 
        term5 = 0.20747825e-8 * T_k**3
        term6 = -0.9484024e-12 * T_k**4
        term7 = 4.1635019 * math.log(T_k)
        ln_esat = term1 + term2 + term3 + term4 + term5 + term6 + term7
        return math.exp(ln_esat) / 100

    elif method == 'marti_ice':
        lg_esat = -2663.5 / T_k + 12.537
        return 10**lg_esat / 100
    
    else:
        raise ValueError("无效的计算方法")

def calculate_wetbulb(T, Td, P=1013.25, max_iter=10, tol=1e-4):
    """核心计算函数"""
    calculator = WetbulbCalculator()

    e = 6.112 * math.exp(17.62 * Td / (243.12 + Td))  # 实际水汽压
    
    print("\n请选择迭代初始值：\n1. 使用T_w=Td\n2. 使用T_w=T-n\n3. 自动选择")
    while True:
        choice = input("请输入您的选择（1,2,3）：")
        if choice == "1":
            initial_guess = Td
            break
        elif choice == "2":
            n = check_input("请输入n值：", min_v=-10, max_v=10)
            initial_guess = T - n
            break
        elif choice == "3":
            initial_guess = T-2 if T < 0 else T-5
            break
        print("无效操作！")
        
    methods = [
        ('Magnus-水面', 'magnus_water', lambda T_w: 0 <= T_w <= 60),
        ('August-水面', 'august_water', lambda T_w: 0 <= T_w <= 60),
        ('Tetens-水面', 'tetens_water', lambda T_w: 0 <= T_w <= 50),
        ('Buck-水面', 'buck_water', lambda T_w: 0 <= T_w <= 80),
        ('Arden-水面', 'arden_water', lambda T_w: 0 <= T_w <= 100),
        ('Gili-水面', 'gili_water', lambda T_w: -10 <= T_w <= 40),
        ('Goff-水面', 'goff_water', lambda T_w: -10 <= T_w <= 100),
        ('Wexler-水面', 'wexler_water', lambda T_w: -10 <= T_w <= 200),
        ('Magnus-冰面', 'magnus_ice', lambda T_w: -65 <= T_w <= 0),
        ('Buck-冰面', 'buck_ice', lambda T_w: -80 <= T_w <= 0),
        ('Marti-冰面', 'marti_ice', lambda T_w: -150 <= T_w <= 0),
        ('Goff-冰面', 'goff_ice', lambda T_w: -100 <= T_w <= 10),
        ('Wexler-冰面', 'wexler_ice', lambda T_w: -150 <= T_w <= 10),
    ]

    for name, method, condition in methods:
        if not condition(initial_guess):  # 使用初始猜测温度判断
            calculator.add_result(name, '不适用')
            continue
        T_w = initial_guess
        for iter_num in range(max_iter):
            try:
                e_sat = calculate_esat(T_w, method)
                gamma = 0.00066 * (1 + 0.00115 * T_w) * P
                f = e_sat - gamma * (T - T_w) - e
                
                # 计算导数
                if 'magnus' in method:
                    B = 17.62 if 'water' in method else 22.46
                    C = 243.12 if 'water' in method else 272.62
                    de_dT = e_sat * (B * C) / (C + T_w)**2
                else:
                    delta = 0.001  # 数值微分
                    e_sat1 = calculate_esat(T_w - delta, method)
                    e_sat2 = calculate_esat(T_w + delta, method)
                    de_dT = (e_sat2 - e_sat1) / (2*delta) 
                
                df_dT = de_dT + gamma - 0.00066 * 0.00115 * P * (T - T_w)
                T_w_new = T_w - f / df_dT
                calculator.add_iteration(name, iter_num+1, T_w, abs(f))
                
                if abs(T_w_new - T_w) < tol:
                    calculator.add_result(name, T_w_new)
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

if __name__ == "__main__":

    while True:
        T = check_input("请输入干球温度(℃): ", min_v=-150, max_v=200)
        Td = check_input("请输入露点温度(℃): ", min_v=-150, max_v=200)
        if Td > T:
            print("错误：露点温度不能高于干球温度！")
            continue
  
        P = check_input("请输入大气压(hPa): ", min_v=500, max_v=1100)
        # max_iter = check_input("请输入迭代次数（整数）：", num_type=int, min_v=1, max_v=9999)
        
        calculator = calculate_wetbulb(T, Td, P)
        calculator.show_results()

        if input("\n显示收敛过程图？(y/n): ").lower() == 'y':
            calculator.show_convergence()

        if input("\n继续计算？(y/n): ").lower() != 'y':
            print("程序退出")
            break
else:
    print("非法使用软件")
    exit()
