# -*- coding: utf-8 -*-
"""对照测试v2：验证搜索式模拟器的判别力。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from rules import Board, CellType
from solver import Solver


def make_board(color_counts, wall_cols=None):
    b = Board()
    for y in range(b.h):
        for x in range(b.w): b.set_cell(x, y, CellType.WALL)
    b.setup_fixed_parks()   # 在 fill 之后设置荷花区，避免被覆盖
    for y in range(2, b.h):
        for x in range(1, 6): b.set_cell(x, y, CellType.EMPTY)
    fid = 0
    for color, cnt in color_counts.items():
        for k in range(cnt):
            x = 1 + (fid % 5); y = 4 + (fid // 5)
            if wall_cols and x in wall_cols:
                pass
            b.add_frog(color, x, y); b.set_cell(x, y, CellType.CAR); fid += 1
    return b


def run(name, b):
    s = Solver(b)
    ok, reason = s.solvable()
    print(f"[{name}] solvable={ok} reason={reason} nodes={s.nodes}")


# 可解：3红+3蓝+3绿（每种3只恰好消1次）
run("可解-每种3只", make_board({0:3, 1:3, 2:3}))
# 某色2只(凑不齐3) -> 该色无法消，不可解
run("不可解-绿2只", make_board({0:3, 1:3, 2:2}))
# 某色5只(非3倍数) -> 余2只消不掉，不可解
run("不可解-红5只", make_board({0:5, 1:3}))
# 可解：多色都3的倍数
run("可解-4色各3", make_board({0:3, 1:3, 2:3, 3:3}))
