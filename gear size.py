"""
齿轮箱模数校合方案生成器1.0

功能：
1. 根据用户输入的参数（目标扭矩、材料等）生成可行的模数设计方案
2. 支持强度校核
3. 结果可导出为结构化的Excel文件

作者：黄沛
版本：1.1
最后更新：2025-03-31
"""
import math
from decimal import Decimal
import pandas as pd

def get_decimal_places(number):
    # 使用Decimal确定步长的小数位数
    d = Decimal(str(number))
    if d.as_tuple().exponent < 0:
        return -d.as_tuple().exponent
    else:
        return 0

def generate_modulus_list(m_min, m_max, step):
    decimal_places = get_decimal_places(step)
    modulus_list = []
    current = m_min
    while current <= m_max + 1e-9:  # 处理浮点精度误差
        rounded = round(current, decimal_places)
        modulus_list.append(rounded)
        current += step
    # 去重并过滤超出范围的值
    modulus_list = sorted(list(set(modulus_list)))
    modulus_list = [m for m in modulus_list if m <= m_max]
    return modulus_list, decimal_places

def export_to_excel(valid_modulus, m_min_calc, file_name):
    """将结果导出到Excel文件"""
    data = {
        "符合强度要求的模数": valid_modulus
    }
    df = pd.DataFrame(data)
    df.to_excel(file_name, index=False)
    print(f"✅ 结果已导出到 {file_name}")

# 用户输入
T = float(input("请输入扭矩 (N·m): "))
tau = float(input("请输入材料的剪切强度 (MPa): "))
sigma = float(input("请输入材料的拉伸强度 (MPa): "))
num_results = int(input("请输入需要的结果数量: "))
m_min_user = float(input("请输入最小模数 (mm): "))
m_max_user = float(input("请输入最大模数 (mm): "))
step = float(input("请输入步长: "))

# 计算最小允许模数（基于简化的强度公式）
m_shear = (T / tau) ** (1/3)
m_tensile = (T / sigma) ** (1/3)
m_min_calc = max(m_shear, m_tensile)

# 生成模数库
modulus_list, decimal_places = generate_modulus_list(m_min_user, m_max_user, step)

# 筛选符合强度要求的模数
valid_modulus = [m for m in modulus_list if m >= m_min_calc]

# 结果输出
print("\n计算结果:")
print(f"根据强度要求计算的最小模数为: {m_min_calc:.3f} mm")
print(f"生成的模数库包含 {len(modulus_list)} 个候选值")
print(f"符合强度要求的模数共 {len(valid_modulus)} 个:")

for m in valid_modulus:
    # 根据步长的小数位数格式化输出
    print(f"{m:.{decimal_places}f}")

# 导出结果到Excel文件
export = input("\n是否导出到Excel文件？(y/n): ").lower()
if export == 'y':
    file_name = input("输入文件名（默认:齿轮模数计算结果.xlsx）: ") or "齿轮模数计算结果.xlsx"
    if not file_name.endswith('.xlsx'):
        file_name += ".xlsx"
    export_to_excel(valid_modulus, m_min_calc, file_name)