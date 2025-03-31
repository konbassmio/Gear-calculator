"""
齿轮箱设计方案生成器1.5

新增功能：
1. 齿轮扭矩计算系统
2. 模数校核功能
3. 方案内独立编号系统
"""

import math
import time
from fractions import Fraction
from itertools import combinations_with_replacement
from math import prod
from dataclasses import dataclass
from typing import List, Tuple, Optional
import pandas as pd

# ==================== 数据结构定义 ====================
@dataclass
class Gear:
    """齿轮类（包含扭矩和模数信息）"""
    id: int
    teeth: int
    stage: int
    is_driver: bool
    axis: int
    torque: float      # 单位：N·mm
    min_module: float  # 单位：mm
    
    def __str__(self):
        role = "主动" if self.is_driver else "从动"
        return f"Z{self.id}({self.teeth}齿,{role},轴{self.axis},模数≥{self.min_module:.2f}mm"

@dataclass
class GearStage:
    """传动级配置"""
    level: int
    ratio: float          # 实际传动比（基于齿数计算）
    driver: Gear
    driven: Gear
    link_type: str
    interstage_link: str
    
    def description(self) -> str:
        link_symbol = "⇄" if self.link_type == 'twin' else "→"
        inter_desc = {
            'twin': '双联连接',
            'mesh': '普通连接',
            'N/A': '无'
        }[self.interstage_link]
        return (f"第{self.level}级: {self.driver} {link_symbol} {self.driven} | "
                f"实际速比={self.ratio:.2f} | "
                f"级间连接: {inter_desc}")

# ==================== 核心算法类 ====================
class GearboxDesigner:
    """齿轮箱设计引擎"""
    
    def __init__(self, max_solutions: int, target_ratio: float, 
                 tolerance_pct: float, min_stages: int, 
                 max_stages: int, z_min: int, z_max: int,
                 T_input: float, tau: float, sigma: float):
        self.max_solutions = max_solutions
        self.target = target_ratio
        self.tolerance = tolerance_pct / 100
        self.min_stages = min_stages
        self.max_stages = max_stages
        self.z_range = (z_min, z_max)
        self.T_input = T_input * 1000  # 转换为N·mm
        self.tau = tau
        self.sigma = sigma
        
        self.valid_ratios = self._precompute_ratios()
        self.ratio_combinations = self._generate_valid_combinations()
    
    def _precompute_ratios(self) -> List[Fraction]:
        """预计算所有可能的速比"""
        z_min, z_max = self.z_range
        ratios = set()
        
        for z1 in range(z_min, z_max + 1):
            for z2 in range(z_min, z_max + 1):
                if z1 == 0:
                    continue
                ratio = z2 / z1
                ratio_rounded = round(ratio, 1)
                ratios.add(Fraction(int(ratio_rounded * 10), 10))
                
        return sorted(ratios, key=lambda x: float(x))
    
    def _get_target_range(self) -> Tuple[float, float]:
        lower = self.target * (1 - self.tolerance)
        upper = self.target * (1 + self.tolerance)
        return max(0.1, lower), upper
    
    def _generate_valid_combinations(self) -> List[Tuple[float, Tuple[Fraction,...]]]:
        """生成有效速比组合"""
        lower, upper = self._get_target_range()
        valid_combos = []
        
        for levels in range(self.min_stages, self.max_stages + 1):
            count = 0
            for combo in combinations_with_replacement(self.valid_ratios, levels):
                product = math.prod([float(r) for r in combo])
                if lower <= product <= upper:
                    valid_combos.append((product, combo))
                    count += 1
                if count >= 10000:
                    break
        return valid_combos
    
    def _generate_gear_pairs(self, ratio: Fraction, prev_driven: Optional[Gear]) -> List[Tuple]:
        """生成有效齿轮对"""
        z_min, z_max = self.z_range
        target_ratio = float(ratio)
        pairs = []
        
        # 普通啮合组合
        for z1 in range(z_min, z_max + 1):
            for z2 in range(z_min, z_max + 1):
                if z1 == 0:
                    continue
                actual_ratio = z2 / z1
                if abs(actual_ratio - target_ratio) <= 0.05:
                    pairs.append(('mesh', z1, z2, 'mesh'))
        
        # 双联齿轮处理
        if prev_driven:
            z1 = prev_driven.teeth
            z2 = round(z1 * target_ratio)
            if z_min <= z2 <= z_max and z2 != z1 and abs(z2/z1 - target_ratio) <= 0.05:
                pairs.append(('twin', z1, z2, 'twin'))
                
        return pairs
    
    def design_gearbox(self) -> List[List[GearStage]]:
        """生成设计方案"""
        solutions = []
        global_axis_id = 1
        lower, upper = self._get_target_range()
        
        for product, ratio_seq in self.ratio_combinations:
            stages = []
            prev_driven = None
            valid = True
            current_axis = global_axis_id
            gear_id = 1
            current_torque = self.T_input
            actual_ratios = []
            
            try:
                for level, ratio in enumerate(ratio_seq, 1):
                    pairs = self._generate_gear_pairs(ratio, prev_driven)
                    if not pairs:
                        valid = False
                        break
                    
                    # 选择最优齿轮对
                    best_pair = min(pairs, key=lambda p: p[1] + p[2])
                    link_type, z1, z2, inter_link = best_pair
                    actual_ratio = z2 / z1
                    actual_ratios.append(actual_ratio)
                    
                    # 计算扭矩
                    driver_torque = current_torque
                    driven_torque = driver_torque * actual_ratio
                    
                    # 轴处理逻辑
                    if link_type == 'twin' and prev_driven:
                        driver_axis = prev_driven.axis
                        current_axis = driver_axis
                    else:
                        driver_axis = current_axis
                    
                    # 创建齿轮对象
                    driver = Gear(
                        id=gear_id,
                        teeth=z1,
                        stage=level,
                        is_driver=True,
                        axis=driver_axis,
                        torque=driver_torque,
                        min_module=max(
                            (driver_torque / self.tau) ** (1/3),
                            (driver_torque / self.sigma) ** (1/3)
                        )
                    )
                    driven = Gear(
                        id=gear_id + 1,
                        teeth=z2,
                        stage=level,
                        is_driver=False,
                        axis=current_axis + 1,
                        torque=driven_torque,
                        min_module=max(
                            (driven_torque / self.tau) ** (1/3),
                            (driven_torque / self.sigma) ** (1/3)
                        )
                    )
                    
                    stages.append(GearStage(
                        level=level,
                        ratio=actual_ratio,
                        driver=driver,
                        driven=driven,
                        link_type=link_type,
                        interstage_link='N/A' if level == 1 else inter_link
                    ))
                    
                    prev_driven = driven
                    gear_id += 2
                    current_axis += 1
                    current_torque = driven_torque
                
                # 验证实际总速比
                product_actual = math.prod(actual_ratios)
                if not (lower <= product_actual <= upper):
                    valid = False
                    
                if valid:
                    solutions.append(stages)
                    global_axis_id = current_axis
                    if len(solutions) >= self.max_solutions:
                        break
            except:
                continue
                
        return solutions

# ==================== 输出模块 ====================
def export_to_excel(solutions: List[List[GearStage]], file_name: str):
    """增强型导出功能"""
    data = []
    for sol_idx, solution in enumerate(solutions, 1):
        for stage in solution:
            data.append({
                '方案编号': sol_idx,
                '传动级': stage.level,
                '本级类型': '双联' if stage.link_type == 'twin' else '普通',
                '级间连接': {
                    'twin': '双联',
                    'mesh': '普通',
                    'N/A': '无'
                }[stage.interstage_link],
                '速比': stage.ratio,
                '主动轮': str(stage.driver),
                '从动轮': str(stage.driven),
                '主动齿数': stage.driver.teeth,
                '从动齿数': stage.driven.teeth,
                '驱动轴': stage.driver.axis,
                '从动轴': stage.driven.axis,
                '主动轮扭矩(N·mm)': stage.driver.torque,
                '从动轮扭矩(N·mm)': stage.driven.torque,
                '主动轮最小模数(mm)': stage.driver.min_module,
                '从动轮最小模数(mm)': stage.driven.min_module
            })
    
    try:
        df = pd.DataFrame(data)
        df.sort_values(['方案编号', '传动级'], inplace=True)
        df.to_excel(file_name, index=False)
        print(f"✅ 成功导出 {len(solutions)} 个方案到 {file_name}")
    except Exception as e:
        print(f"❌ 导出失败: {str(e)}")

# ==================== 主程序 ====================
def main():
    print("╔══════════════════════════════╗")
    print("║      齿轮箱智能设计系统 v1.5     ║")
    print("╚══════════════════════════════╝")
    
    try:
        params = {
            'max_solutions': int(input("▶ 最大方案数 (10-1000): ")),
            'target_ratio': float(input("▶ 目标总速比 (如18.0): ")),
            'tolerance_pct': float(input("▶ 允许误差百分比 (如5): ")),
            'min_stages': int(input("▶ 最小级数 (≥1): ")),
            'max_stages': int(input("▶ 最大级数 (≤5): ")),
            'z_min': int(input("▶ 最小齿数 (≥15): ")),
            'z_max': int(input("▶ 最大齿数 (≤150): ")),
            'T_input': float(input("▶ 输入扭矩 (N·m): ")),
            'tau': float(input("▶ 材料剪切强度 (MPa): ")),
            'sigma': float(input("▶ 材料拉伸强度 (MPa): ")),
        }
    except ValueError:
        print("❗ 输入格式错误！")
        return

    print("\n⚙ 正在生成设计方案...")
    start_time = time.time()
    designer = GearboxDesigner(**params)
    solutions = designer.design_gearbox()
    elapsed = time.time() - start_time
    
    print(f"\n✅ 计算完成！耗时 {elapsed:.2f}s")
    print(f"找到 {len(solutions)} 个有效方案")
    print("════════════════════════════════════")
    
    for idx, solution in enumerate(solutions, 1):
        total_ratio = math.prod(s.ratio for s in solution)
        error = abs(total_ratio/params['target_ratio']-1)*100
        print(f"\n🔷 方案 {idx} | 总速比: {total_ratio:.2f} | 误差: {error:.2f}%")
        print("-"*60)
        
        # 打印各级详细信息
        for stage in solution:
            print(f"  {stage.description()}")
        
        # 生成连接示意图
        print("\n  [扭矩传递示意图]")
        path = [f"输入轴({params['T_input']}N·m)"]
        current_torque = params['T_input']
        for stage in solution:
            path.append(f"{stage.driver}→")
            path.append(f"{stage.driven}({stage.driven.torque/1000:.1f}N·m)")
            current_torque = stage.driven.torque / 1000
        path.append("→输出轴")
        print("    " + " ".join(path))
        print("════════════════════════════════════")
    
    # 导出处理
    if solutions:
        if input("\n是否导出到Excel？(y/n): ").lower() == 'y':
            default_name = f"GearDesign_{params['target_ratio']}x.xlsx"
            file_name = input(f"文件名（默认: {default_name}）: ") or default_name
            if not file_name.endswith('.xlsx'):
                file_name += '.xlsx'
            export_to_excel(solutions, file_name)
    else:
        print("\n⚠️ 未找到有效方案，建议：\n  1. 扩大齿数范围\n  2. 增加误差容忍度\n  3. 调整传动级数")

if __name__ == "__main__":
    main()