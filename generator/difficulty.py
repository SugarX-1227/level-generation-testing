# -*- coding: utf-8 -*-
"""
难度梯度参数 —— 第4步（对齐真实 500 关 HardType 分布）
====================================================
从真实 500 关统计分析：
  HardType=0(普通): 颜色数 2-8 均值6.4, 总量均值53, 进阶少(SubLevel15% Lock8%)
  HardType=1(困难): 颜色数 5-8 均值7.3, 总量均值59, 进阶多(SubLevel26%)
  HardType=3(超难): 颜色数 5-8 均值7.4, 总量均值59.8, 进阶最多(SubLevel29% Lock11%)

定义各难度档位的生成参数（本工具使用静态青蛙关 + 可选进阶元素）。
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DifficultySpec:
    tid: int              # 档位 id
    hard_type: int        # 对应的 LevelConfig.HardType
    name: str
    min_colors: int       # 最少颜色数
    max_colors: int       # 最多颜色数
    frog_per_color: int   # 每色青蛙数（须3倍数）
    slot_width_range: tuple  # (min,max) 槽宽
    slot_height_range: tuple  # (min,max) 槽高
    max_total_frogs: int  # 每关青蛙总量上限
    allow_boxes: bool     # 是否放 Box（进阶障碍）
    allow_factory: bool   # 是否放 Factory（青蛙来源）
    allow_sublevel: bool  # 是否放 SubLevel
    allow_gridentity: bool  # 是否放 GridLock/Key
    allow_freezing: bool  # 是否放 FreezingCar


DIFFICULTY: List[DifficultySpec] = [
    DifficultySpec(tid=1, hard_type=0, name="极简(教学)",
                   min_colors=3, max_colors=3, frog_per_color=3,
                   slot_width_range=(3, 4), slot_height_range=(1, 1),
                   max_total_frogs=9, allow_boxes=False, allow_factory=False,
                   allow_sublevel=False, allow_gridentity=False, allow_freezing=False),
    DifficultySpec(tid=2, hard_type=0, name="普通",
                   min_colors=4, max_colors=6, frog_per_color=3,
                   slot_width_range=(3, 5), slot_height_range=(2, 4),
                   max_total_frogs=36, allow_boxes=True, allow_factory=False,
                   allow_sublevel=False, allow_gridentity=False, allow_freezing=False),
    DifficultySpec(tid=3, hard_type=1, name="困难",
                   min_colors=6, max_colors=7, frog_per_color=3,
                   slot_width_range=(4, 5), slot_height_range=(3, 5),
                   max_total_frogs=54, allow_boxes=True, allow_factory=False,
                   allow_sublevel=False, allow_gridentity=False, allow_freezing=False),
    DifficultySpec(tid=4, hard_type=3, name="超难",
                   min_colors=7, max_colors=8, frog_per_color=3,
                   slot_width_range=(4, 5), slot_height_range=(4, 6),
                   max_total_frogs=72, allow_boxes=True, allow_factory=False,
                   allow_sublevel=False, allow_gridentity=False, allow_freezing=False),
]


def get_difficulty(tid: int) -> DifficultySpec:
    for d in DIFFICULTY:
        if d.tid == tid:
            return d
    return DIFFICULTY[1]  # 默认"普通"
