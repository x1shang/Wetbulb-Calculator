# version 2.0.0

import numpy as np
import time
import math

print("warning\n本程序尝试使用迭代法估算湿球温度\n因操作不当导致的误差我们不负任何责任")

class wetbulb:
    def __init__(self,name,resu):
        self.name = name
        self.resu = resu

def check_value(prompt,num_type=float,min_v=None,max_v=None):
    while True:
        try:
            n = num_type(input(prompt).strip())
            if (min_v is not None and n < min_v) or (max_v is not None and n > max_v):
                print("数值超出程序计算能力")
                time.sleep(0.5)
                continue
            else:
                return n
        except ValueError:
            print(f"请输入有效的{num_type.__name__}！")
    
def magnus_water(T_w):
    e_sat = 6.112 * np.exp(17.62 * T_w / (243.12 + T_w))

def magnus_ice(T_w):
    e_sat = 6.112 * np.exp(22.46 * T_w / (272.62 + T_w))

def goff_gratch_water(T_w):
    T_k = T_w + 273.15  
    T_st = 273.15     
    term1 = 10.79574 * (1 - T_st/T)
    term2 = -5.028 * math.log10(T/T_st)
    term3 = 1.50475e-4 * (1 - 10**(-8.2969*(T/T_st - 1)))
    term4 = 0.42873e-3 * (10**(4.76955*(1 - T_st/T)) - 1)
    log_esat = term1 + term2 + term3 + term4 + 0.78614
    e_sat = 10**log_esat

def goff_gratch_ice(T_w):
    T_k = T_w + 273.15  
    T_st = 273.15     
    term1 = -9.09718 * (T_st/T - 1)
    term2 = -3.56654 * math.log10(T_st/T)
    term3 = 0.876793 * (1 - T/T_st)
    log_esat = term1 + term2 + term3 + 0.78614
    e_sat = 10**log_esat

def calculate_t_wet(T, Td, P=1013.25, max_iter=100, tol=1e-4):

    # 实际水汽压e
    e = 6.112 * np.exp(17.62 * Td / (243.12 + Td))

    print(f"\n请选择迭代初始猜测值：\n（若不确定请选1）")
    print("1. 使用T_w=Td")
    print("2. 使用T_w=T-n")
    while True:
        choice = input("请输入您的选择（1,2,3）：")

        if choice == "1":
            T_w = Td
            break
        elif choice == "2":
            b_a = check_value("请输入n值：",min_v=-10,max_v=10)
            T_w = T-b_a
            break
        else:
            print("无效操作！")
            continue

    num = 0
    answer = []

    while num < 5:
        num += 1
        T_wax = T_w
        if num == 1:
            for _ in range(max_iter):
                e_sat = magnus_water(T_wax)
                # 计算湿度常数gamma
                gamma = 0.00066 * (1 + 0.00115 * T_wax) * P
                f = e_sat - gamma * (T - T_wax) - e
                de_sat_dT = e_sat * (17.62 * 243.12) / (243.12 + T_wax)**2
                df_dT = de_sat_dT + gamma - 0.00066 * 0.00115 * P * (T - T_wax)
                T_wax_new = T_wax - f / df_dT
                # 判断收敛
                if abs(T_wax_new - T_wax) < tol:
                    return T_wax_new
                T_wax = T_wax_new
        answer.append(wetbulb("magnus_water",T_wax))
        elif num == 2:
            for _ in range(max_iter):
                e_sat = magnus_ice(T_wax)
                gamma = 0.00066 * (1 + 0.00115 * T_wax) * P
                f = e_sat - gamma * (T - T_wax) - e
                de_sat_dT = e_sat * (17.62 * 243.12) / (243.12 + T_wax)**2
                df_dT = de_sat_dT + gamma - 0.00066 * 0.00115 * P * (T - T_wax)
                T_wax_new = T_wax - f / df_dT
                if abs(T_wax_new - T_wax) < tol:
                    return T_wax_new
                T_wax = T_wax_new
        answer.append(wetbulb("magnus_ice",T_wax))
        elif num == 3:
            for _ in range(max_iter):
                e_sat = goff_gratch_water(T_wax)
                gamma = 0.00066 * (1 + 0.00115 * T_wax) * P
                f = e_sat - gamma * (T - T_wax) - e
                de_sat_dT = e_sat * (17.62 * 243.12) / (243.12 + T_wax)**2
                df_dT = de_sat_dT + gamma - 0.00066 * 0.00115 * P * (T - T_wax)
                T_wax_new = T_wax - f / df_dT
                if abs(T_wax_new - T_wax) < tol:
                    return T_wax_new
                T_wax = T_wax_new
        answer.append(wetbulb("goff_gratch_water",T_wax))
        elif num == 4:
            for _ in range(max_iter):
                e_sat = goff_gratch_ice(T_wax)
                gamma = 0.00066 * (1 + 0.00115 * T_wax) * P
                f = e_sat - gamma * (T - T_wax) - e
                de_sat_dT = e_sat * (17.62 * 243.12) / (243.12 + T_wax)**2
                df_dT = de_sat_dT + gamma - 0.00066 * 0.00115 * P * (T - T_wax)
                T_wax_new = T_wax - f / df_dT
                if abs(T_wax_new - T_wax) < tol:
                    return T_wax_new
                T_wax = T_wax_new
        answer.append(wetbulb("goff_gratch_ice",T_wax))
        else:
            return answer
             
while True:
    Tx = check_value("请输入干球温度(℃)：",min_v=-60,max_v=60)
    Tdx = check_value("请输入露点温度(℃)：",min_v=-60,max_v=60)
    Px = check_value("请输入大气压(hPa)：",min_v=99,max_v=1500)
    itx = check_value("请输入迭代次数（整数）：",num_type=int,min_v=1)
    Tw = calculate_t_wet(T=Tx, Td=Tdx, P=Px, max_iter=itx)
    print(f"\n输入验证：\n干球温度：{Tx:.3f}℃\n露点温度：{Tdx:.3f}℃\n大气压：{Px:.4f}hPa\n迭代次数：{itx}")
    print("\n湿球温度估算值: ")
    for idx, wetbulb in enumerate(answer, 1):
        print(f"{name}：{resu:.5f}(°C)")
    reload = input("继续输入请按1")
    if reload == "1":
        continue
    else:
        print("谢谢使用\n exit with code 0")
        exit()
