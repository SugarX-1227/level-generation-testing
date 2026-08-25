# -*- coding: utf-8 -*-
"""
关卡生成器 v2 —— 「槽式/行列模板」，贴近真实关卡风格 + 可解性自校验

仿真实 LV1 等关卡：
- 用 Wall 围出若干「槽」（竖井），青蛙按颜色成行/成列整齐堆叠。
- 青蛙只能向下（或按需）掉落到荷花区（entry_row=2）。
- 每种颜色数量 = 3 的倍数（可全消）。
- 用 Solver 精确校验可解性，生成即保证「存在一条全消路径且不判负」。

模板：一个主槽，宽 wslot（可取 3~5），高 hslot；青蛙按行填充，每行同色。
"""
import json
import random
from rules import Board, CellType, COLOR_NAMES
from autotest_sim import solvable as at_solvable  # 用 AutoTest 风格判定（与真实测试对齐）


def gen_board(rng, width=7, height=11, colors=None, frogs_per_color=3,
              slot_width=None, slot_height=None, seed=None):
    """生成『槽式』棋盘：Wall 围出竖井，青蛙成行堆叠。返回 (Board, color_counts)。"""
    if seed is not None:
        rng = random.Random(seed)
    if colors is None:
        pool = [0, 1, 2, 3, 4, 5, 6, 7]
        ncolor = rng.randint(3, 4)
        colors = pool[:ncolor]

    # 主槽尺寸
    ncolors = len(colors)
    slot_width = slot_width or rng.randint(3, min(width - 2, 5))
    # 槽高：至少容纳颜色数与每色数量（需放 total_needed 只）
    cnt_per_color = frogs_per_color if frogs_per_color % 3 == 0 else 3
    total_needed = ncolors * cnt_per_color
    # 需要的行数 = ceil(total_needed / slot_width)
    import math
    need_rows = math.ceil(total_needed / slot_width)
    slot_height = slot_height or max(1, need_rows)
    slot_height = max(slot_height, need_rows)
    slot_height = min(slot_height, height - 4)  # 不超过棋盘可用高度

    # 屏宽/高
    b = Board()
    for y in range(height):
        for x in range(width):
            b.set_cell(x, y, CellType.WALL)
    b.setup_fixed_parks()

    # 槽底位于 entry_row 上方：槽格 y in [4, 4+slot_height-1]
    slot_left = (width - slot_width) // 2
    slot_bottom = 4
    # 下落通道：y in [2, slot_bottom-1] 全屏 Empty（通往荷花，不能堵死）
    for y in range(2, slot_bottom):
        for x in range(width):
            b.set_cell(x, y, CellType.EMPTY)
    # 槽内先设为 Empty（可放青蛙）
    for x in range(slot_left, slot_left + slot_width):
        for y in range(slot_bottom, slot_bottom + slot_height):
            b.set_cell(x, y, CellType.EMPTY)

    # 放置青蛙：统一顺序填充（槽内空格按"下->上、左->右"，每色连续填 cnt 只）。
    # 若槽容量不足以放下所有青蛙，则直接失败（上层重试）。
    color_counts = {}
    placed = []
    total_needed = 0
    per_color = []
    for color in colors:
        cnt = frogs_per_color if frogs_per_color % 3 == 0 else 3
        per_color.append(cnt)
        color_counts[color] = cnt
        total_needed += cnt
    # 构建槽内空格序列（优先从下往上、左到右，便于青蛙落向荷花）
    cells = []
    for y in range(slot_bottom, slot_bottom + slot_height):
        for x in range(slot_left, slot_left + slot_width):
            if b.get_cell(x, y) == CellType.EMPTY:
                cells.append((x, y))
    if len(cells) < total_needed:
        # 容量不足 -> 返回空，上层判定失败
        b.frogs = []
        return b, {}
    # 顺序填充
    idx = 0
    for ci, color in enumerate(colors):
        cnt = per_color[ci]
        for k in range(cnt):
            (xx, yy) = cells[idx]
            idx += 1
            frog = b.add_frog(color, xx, yy)
            b.set_cell(xx, yy, CellType.CAR)
            placed.append(frog)
    return b, color_counts


def build_level(lv, board, color_counts, type_name=None):
    width, height = board.w, board.h
    entity = {
        "LV": lv, "HardType": 0,
        "Grid": {"Width": width, "Height": height, "CellSize": 64.0},
        "Parks": [], "PayParks": [], "Cars": [], "Entities": [], "Emptys": [],
        "Factorys": [], "Boxs": [], "LockDoors": [], "SubLevels": [],
        "GridLocks": [], "GridKeys": [], "FreezingCars": [],
    }
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
    tct = list(color_counts.keys())
    entity["TotalCarColorTypes"] = [COLOR_NAMES[c] for c in tct]
    entity["TotalCarCounts"] = [color_counts[c] for c in tct]
    entity["AwardCoin"] = 0
    entity["AwardItem1"] = 0
    entity["AwardItem2"] = 0
    entity["AwardItem3"] = 0
    entity["AwardItem4"] = 0
    return entity


def _ge(typ, x, y, color=None):
    return {"Type": typ, "CellX": x, "CellY": y, "ColorType": color, "Dir": None,
            "IncludeCarCount": 0, "Floor": 0, "SubLevelSizeX": 0, "SubLevelSizeY": 0,
            "FreezingLayers": 0}


def generate(count, seed=None, start_lv=1, colors=None, frogs_per_color=3,
             slot_width=None, slot_height=None, verbose=False, difficulty=None,
             ncolor_range=None, max_total=None):
    """生成关卡。difficulty: DifficultySpec(见 difficulty.py) 控制难度梯度。"""
    from difficulty import get_difficulty
    rng = random.Random(seed)
    diff = get_difficulty(difficulty) if difficulty is not None else None
    levels = []
    made = 0
    lv = start_lv
    attempts = 0
    while made < count and attempts < count * 20:
        attempts += 1
        # 按难度档位取参数（若未显式传入）
        use_colors = colors
        use_fpc = frogs_per_color
        use_sw = slot_width
        use_sh = slot_height
        if diff is not None:
            ncol = rng.randint(diff.min_colors, diff.max_colors)
            use_colors = list(range(ncol))
            use_fpc = diff.frog_per_color
            use_sw = rng.randint(*diff.slot_width_range)
            use_sh = rng.randint(*diff.slot_height_range)
        elif ncolor_range is not None:
            ncol = rng.randint(*ncolor_range)
            use_colors = list(range(ncol))
        b, color_counts = gen_board(rng, colors=use_colors, frogs_per_color=use_fpc,
                                    slot_width=use_sw, slot_height=use_sh, seed=None)
        if not b.frogs:
            continue
        if max_total is not None and sum(color_counts.values()) > max_total:
            continue
        # AutoTest 风格可解性校验
        r = at_solvable(b)
        ok = r["solvable"]
        if verbose:
            print(f"  LV{lv} frogs={len(b.frogs)} colors={color_counts} solvable={ok} ({r['reason']})")
        if not ok:
            continue
        lvl = build_level(lv, b, color_counts)
        if diff is not None:
            lvl["HardType"] = diff.hard_type
        levels.append(lvl)
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
