# -*- coding: utf-8 -*-
"""
关卡生成器 —— 生成「基础静态青蛙」关卡，并用模拟器精确校验可解性。

生成策略（保守可靠，保证可解）：
1. 固定骨架：Grid 7x11；y=0 PayPark、y=1 Park（荷叶区）；LV 递增。
2. 棋盘布局：用障碍(Wall) 围出可达区，空出若干 Empty 供青蛙与路径通行。
3. 青蛙：放置若干只静态青蛙，**每种颜色数量 = 3 的倍数**（保证可从荷花区消除）。
4. 保证可达性：青蛙与荷叶区之间保持 A* 可达路径。
5. 用 Solver 精确校验：确保「存在一条操作序列使全场青蛙全消、不判负」。
6. 输出 levels.json 格式（与现有 500 关一致）。

约简：首版不生成 Factory/Box/SubLevel/GridLock/GridKey/FreezingCar 进阶元素，
只做最稳固的静态青蛙关卡 —— 这是用户选择的首版范围。
"""
import json
import random
from rules import Board, CellType, COLOR_NAMES, color_of_name
from solver import Solver


def color_balance(count_per_color_color_names):
    """每种颜色 count 只（count 为 3 的倍数）。"""
    return count_per_color_color_names


def gen_board(random, width=7, height=11,
              colors=None, frogs_per_color=3,
              obstacle_density=0.15, seed=None):
    """生成一个棋盘：布局 + 静态青蛙。返回 (Board, color_counts)。"""
    rng = random.Random(seed) if seed else random
    if colors is None:
        # 默认 6~8 种颜色里挑 3~4 种（保守）
        pool = [0, 1, 2, 3, 4, 5, 6, 7]
        ncolor = rng.randint(3, 4)
        colors = pool[:ncolor]

    b = Board()
    # 全填 Wall
    for y in range(height):
        for x in range(width):
            b.set_cell(x, y, CellType.WALL)
    b.setup_fixed_parks()

    # 可达区：让青蛙能到 entry_row(y=2)。设计一个"漏斗"式通道。
    # 活动区 y in [2, height-1]，x in [0, width-1]，大部分空，放少量障碍。
    for y in range(2, height):
        for x in range(width):
            b.set_cell(x, y, CellType.EMPTY)

    # 放少量障碍（Wall），但保证不堵死通往 entry_row 的路径
    # 为避免堵死，只在 y>=4 放障碍，y=2,3 保持全空（通往荷花的咽喉）
    obstacles_cells = []
    for y in range(4, height):
        for x in range(width):
            if rng.random() < obstacle_density:
                obstacles_cells.append((x, y))
    for (x, y) in obstacles_cells:
        if b.in_bounds(x, y) and (x, y) not in b.slot_by_cell:
            b.set_cell(x, y, CellType.WALL)

    # 放置青蛙：每种颜色 frogs_per_color 只（3的倍数），放在 y>=4 且非障碍格
    color_counts = {c: frogs_per_color for c in colors}
    placed = []
    for c, cnt in color_counts.items():
        for _ in range(cnt):
            # 找可放置的空格（Empty 且不在荷叶区，非障碍）
            placed_ok = False
            attempts = 0
            while not placed_ok and attempts < 200:
                attempts += 1
                x = rng.randint(0, width - 1)
                y = rng.randint(4, height - 1)
                if b.get_cell(x, y) == CellType.EMPTY:
                    frog = b.add_frog(c, x, y)
                    b.set_cell(x, y, CellType.CAR)
                    placed.append(frog)
                    placed_ok = True
            if not placed_ok:
                # 放不下则不再加（保证每种3只的完整性可能受影响，稍后校验过滤）
                break
    return b, color_counts


def build_level(lv, board, color_counts):
    """把 Board 转成 levels.json 的一个 Level 条目。"""
    width, height = board.w, board.h
    entity = {
        "LV": lv,
        "HardType": 0,
        "Grid": {"Width": width, "Height": height, "CellSize": 64.0},
        "Parks": [],
        "PayParks": [],
        "Cars": [],
        "Entities": [],
        "Emptys": [],
        "Factorys": [],
        "Boxs": [],
        "LockDoors": [],
        "SubLevels": [],
        "GridLocks": [],
        "GridKeys": [],
        "FreezingCars": [],
    }
    # Parks/PayParks
    for y in range(height):
        for x in range(width):
            c = board.get_cell(x, y)
            if c == CellType.PARK:
                entity["Parks"].append(_ge("Park", x, y))
            elif c == CellType.PAYPARK:
                entity["PayParks"].append(_ge("PayPark", x, y))
            elif c == CellType.WALL:
                entity["Entities"].append(_ge("Wall", x, y))
            elif c == CellType.EMPTY:
                entity["Emptys"].append(_ge("Empty", x, y))
            elif c == CellType.CAR:
                f = board.frog_at(x, y)
                col = COLOR_NAMES.get(f.color, "White") if f else "White"
                entity["Cars"].append(_ge("Car", x, y, color=col))
    # TotalCarColorTypes / TotalCarCounts
    tct = list(color_counts.keys())
    tcc = [color_counts[c] for c in tct]
    entity["TotalCarColorTypes"] = [COLOR_NAMES[c] for c in tct]
    entity["TotalCarCounts"] = tcc
    entity["AwardCoin"] = 0
    entity["AwardItem1"] = 0
    entity["AwardItem2"] = 0
    entity["AwardItem3"] = 0
    entity["AwardItem4"] = 0
    return entity


def _ge(typ, x, y, color=None):
    return {
        "Type": typ,
        "CellX": x,
        "CellY": y,
        "ColorType": color,
        "Dir": None,
        "IncludeCarCount": 0,
        "Floor": 0,
        "SubLevelSizeX": 0,
        "SubLevelSizeY": 0,
        "FreezingLayers": 0,
    }


def generate(count, seed=None, start_lv=1, colors=None, frogs_per_color=3,
             obstacle_density=0.15, verbose=False):
    rng = random.Random(seed)
    levels = []
    made = 0
    lv = start_lv
    while made < count:
        b, color_counts = gen_board(rng, colors=colors,
                                    frogs_per_color=frogs_per_color,
                                    obstacle_density=obstacle_density,
                                    seed=None)
        # 校验可解性
        if not (b.frogs and len(b.frogs) % 3 == 0):
            # 青蛙数不是3的倍数 -> 不可能全消，跳过
            continue
        s = Solver(b)
        ok, reason = s.solvable()
        if verbose:
            print(f"  LV{lv} frogs={len(b.frogs)} solvable={ok} ({reason}) nodes={s.nodes}")
        if not ok:
            continue
        levels.append(build_level(lv, b, color_counts))
        made += 1
        lv += 1
    return {"Levels": levels}


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20260822
    data = generate(n, seed=seed, verbose=True)
    out = json.dumps(data, ensure_ascii=False, indent=2)
    open("generated_levels.json", "w").write(out)
    print(f"generated {len(data['Levels'])} levels -> generated_levels.json")
