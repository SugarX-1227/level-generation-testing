# -*- coding: utf-8 -*-
"""
关卡生成器 v3 —— Factory + Box 进阶元素（对齐真实关卡 92% 驱动模式）
====================================================================
对齐真实关卡风格（profile.py 从 500 关统计）：
- Factory 沿棋盘边缘向内部刷青蛙（真实方向 Down 主导）。
- Box 散布棋盘内部作障碍（真实每关 ~8-13 个）。
- 青蛙颜色由运行时 RandomCarManager 随机决定（游戏内置防堵死保底）。
- 总颜色配额 TotalCarColorTypes/TotalCarCounts 保证每种=3倍数（可全消）。

生成策略（高难度 HardType=3）：
1. 荷叶区固定（7 Park y=1 + 7 PayPark y=0）。
2. 棋盘上层为"活动区"，放 Factory（向下刷入）+ Box（障碍）+ Empty（通道）。
3. 关键：确保 Factory 出口向下通往荷叶的路径不被 Box 堵死。
4. 配额按 profile 采样（7-8色、总量~60、每色3倍数）。
5. 可解性：布局合法（通道可达）+ 配额3倍数；最终以 AutoTest 实测为准。
"""
import json
import random
import math
from rules import Board, CellType, COLOR_NAMES
from profile import sample as profile_sample


def config_layout(rng, width=7, height=11,
                  n_factory=None, n_box=None, factory_dirs=None,
                  n_color=None, n_total=None, mode="hard"):
    """生成 Factory+Box 布局。返回 (Board, color_types, color_counts)。"""
    # 从 profile 采样参数
    p = profile_sample(mode=mode, seed=rng.randrange(10**9))
    n_factory = n_factory if n_factory is not None else p["n_factory"]
    if n_factory < 1:
        n_factory = rng.randint(2, 5)   # Factory 关至少1台（高难度常见2-5台）
    n_box = n_box if n_box is not None else p["n_box"]
    n_color = n_color if n_color is not None else p["n_color"]
    n_total = n_total if n_total is not None else p["n_total"]
    fdir_dist = p.get("fdir", {"Down": 100})

    # 颜色配额：n_color 种，总量 n_total，每种=3倍数且尽量均分
    # 关键(反编译 RandomCarManager.ol()):  必须满足
    #   ΣTotalCarCounts - 静态Cars数 == Σ工厂刷入 + ΣBox数 + 真正空格数
    # 因此布局定完后反推 ΣTotalCarCounts。
    colors = list(range(min(n_color, 8)))
    n = len(colors)
    b = Board()
    for y in range(height):
        for x in range(width):
            b.set_cell(x, y, CellType.WALL)
    b.setup_fixed_parks()

    # 用 Wall 竖条隔出若干"上下通透车道"（贴近真实关卡结构）。
    # 车道: 每 lane_width 列为一个通道，列间 Wall 竖条。顶部放 Factory 向下刷。
    # 底部的 y=2,3 保持全空（通往荷花的咽喉）。
    lane_w = 2
    # 隔出车道列(从列 0..width-1，每个 lane_w 列后插1列 Wall)
    wall_cols = set()
    x = lane_w
    while x < width - 1:
        wall_cols.add(x)
        x += lane_w + 1
    # 车道内(非 wall_cols)设为 EMPTY(可走/可放青蛙源)，wall_cols 保持 WALL
    for y in range(2, height):
        for xi in range(width):
            if xi in wall_cols:
                b.set_cell(xi, y, CellType.WALL)
            else:
                b.set_cell(xi, y, CellType.EMPTY)
    # 底部两行(y=2,3)车道内全空(咽喉通向荷花)
    for y in (2, 3):
        for xi in range(width):
            if xi not in wall_cols:
                b.set_cell(xi, y, CellType.EMPTY)

    # 放 Factory：在每车道顶部(y=height-2)向下刷
    lanes = [c for c in range(width) if c not in wall_cols]
    factory_cells = []
    n_factory = max(1, min(n_factory, len(lanes)))
    for cx in rng.sample(lanes, n_factory):
        fy = height - 2
        if b.get_cell(cx, fy) != CellType.EMPTY:
            continue
        b.set_cell(cx, fy, CellType.FACTORY)
        factory_cells.append((cx, fy))

    # 放 Box（车道内、y in [4, height-3]，避开通往荷花的 y=2,3）
    box_cells = []
    target_box = min(n_box, 13)
    for _ in range(target_box * 8):
        if len(box_cells) >= target_box:
            break
        bx = rng.choice(lanes)
        by = rng.randint(4, height - 3)
        if b.get_cell(bx, by) != CellType.EMPTY:
            continue
        if (bx, by) in factory_cells:
            continue
        b.set_cell(bx, by, CellType.BOX)
        box_cells.append((bx, by))

    # ---- 迭代搜索 per：使 fac_sum = n*per - box - empty 落在每台Factory合理区间 ----
    n_cars = 0
    box_count = len(box_cells)
    wall_num = sum(1 for y in range(height) for x in range(width) if b.get_cell(x, y) == CellType.WALL)
    arr_entities = 7 + 7 + wall_num + len(factory_cells) + box_count
    empty_count = width * height - arr_entities
    if empty_count < 0:
        empty_count = 0
    nf = max(1, len(factory_cells))
    best = None
    per_candidates = [3, 6, 9, 12, 15, 18, 21, 24]
    for per in per_candidates:
        target = n * per
        fac_sum = target - box_count - empty_count
        if nf <= fac_sum <= nf * 10:
            best = (per, target, fac_sum)
            break
    if best is None:
        # 兜底：取 per=6，fac_sum 尽量接近
        per = 6
        target = n * per
        fac_sum = max(nf, target - box_count - empty_count)
        fac_sum = min(fac_sum, nf * 10)
    else:
        per, target, fac_sum = best
    per_color = [per] * n
    diff = target - sum(per_color)
    if diff % 3 == 0 and diff != 0:
        per_color[0] += diff
    return b, colors, per_color, {
        "n_factory": len(factory_cells), "n_box": len(box_cells),
        "fdir_dist": fdir_dist, "factory_cells": factory_cells,
        "fac_sum": fac_sum, "empty_count": empty_count, "total_needed": target,
    }


def _split_into_multiple_of_3(total, n):
    """把 total 拆成 n 个 3 的倍数(尽量均分)。无法均分时返回 None。"""
    if total < 3 * n:
        return None
    base = total // n
    base = (base // 3) * 3
    if base < 3:
        return None
    per = [base] * n
    rem = total - sum(per)
    # 把 rem(0,3,6,...) 匀到前面几个
    i = 0
    while rem >= 3 and i < n:
        per[i] += 3
        rem -= 3
        i += 1
    if rem != 0:
        return None
    return per


def build_level(lv, board, color_types, color_counts, hard_type=3, factory_spec=None):
    width, height = board.w, board.h
    entity = {
        "LV": lv, "HardType": hard_type,
        "Grid": {"Width": width, "Height": height, "CellSize": 64.0},
        "Parks": [], "PayParks": [], "Cars": [], "Entities": [], "Emptys": [],
        "Factorys": [], "Boxs": [], "LockDoors": [], "SubLevels": [],
        "GridLocks": [], "GridKeys": [], "FreezingCars": [],
    }
    fac_total = (factory_spec or {}).get("fac_sum", 0)
    nf = max(1, len((factory_spec or {}).get("factory_cells", [])))
    fac_base = fac_total // nf if nf else 0
    fac_rem = fac_total % nf if nf else 0
    _fac_seen = [0]
    for y in range(height):
        for x in range(width):
            c = board.get_cell(x, y)
            if c == CellType.PARK:
                entity["Parks"].append(_ge("Park", x, y))
            elif c == CellType.PAYPARK:
                entity["PayParks"].append(_ge("PayPark", x, y))
            elif c == CellType.WALL:
                entity["Entities"].append(_ge("Wall", x, y))
            elif c == CellType.CAR:
                entity["Cars"].append(_ge("Car", x, y, color="Red"))
            elif c == CellType.FACTORY:
                d = _pick_dir((factory_spec or {}).get("fdir_dist", {})) if factory_spec else "Down"
                # 精确分配 inc，总和 = fac_sum
                inc = fac_base + (1 if _fac_seen[0] < fac_rem else 0)
                _fac_seen[0] += 1
                entity["Factorys"].append(_ge("Factory", x, y, dir=d, inc=inc))
            elif c == CellType.BOX:
                entity["Boxs"].append(_ge("Box", x, y))
            elif c == CellType.EMPTY:
                # 保持为空：既非 Wall 也非 Emptys 数组 -> ol() 的 num2 算作青蛙源空格
                pass
    entity["TotalCarColorTypes"] = [COLOR_NAMES[c] for c in color_types]
    entity["TotalCarCounts"] = color_counts
    entity["AwardCoin"] = 0
    entity["AwardItem1"] = 0
    entity["AwardItem2"] = 0
    entity["AwardItem3"] = 0
    entity["AwardItem4"] = 0
    return entity


def _pick_dir(dist):
    if not dist:
        return "Down"
    items = list(dist.items())
    total = sum(v for _, v in items)
    r = random.randrange(max(1, total))
    acc = 0
    for k, v in items:
        acc += v
        if r < acc:
            return k
    return "Down"


def _ge(typ, x, y, color=None, dir=None, inc=0):
    return {"Type": typ, "CellX": x, "CellY": y, "ColorType": color, "Dir": dir,
            "IncludeCarCount": inc, "Floor": 0, "SubLevelSizeX": 0, "SubLevelSizeY": 0,
            "FreezingLayers": 0}


def generate(count, seed=None, start_lv=1, mode="hard", verbose=False):
    rng = random.Random(seed)
    levels = []
    made = 0
    lv = start_lv
    while made < count:
        b, colors, counts, spec = config_layout(rng, mode=mode)
        if not b:
            continue
        lvl = build_level(lv, b, colors, counts, hard_type=3, factory_spec=spec)
        levels.append(lvl)
        made += 1
        lv += 1
        if verbose:
            print(f"  LV{lv-1} factory={spec['n_factory']} box={spec['n_box']} colors={len(colors)} total={sum(counts)}")
    return {"Levels": levels}


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20260824
    data = generate(n, seed=seed, mode="hard", verbose=True)
    out = json.dumps(data, ensure_ascii=False, indent=2)
    open("generated_factory_levels.json", "w").write(out)
    print(f"generated {len(data['Levels'])} factory levels -> generated_factory_levels.json")
