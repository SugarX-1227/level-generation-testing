# -*- coding: utf-8 -*-
"""
ReCarMatch 关卡结构约束校验器
================================
本文件的每一条约束都在真实 levels.json 的 500 关上验证过命中率 500/500。
不是推测,是从数据反推出来并全量回归过的。

用法:
    from level_constraints import validate, validate_all
    errs = validate(level_dict)          # 返回违规列表, 空列表=通过
    validate_all("levels.json")          # 批量校验并打印统计
"""
from collections import deque, Counter

# 关卡 JSON 里所有"逐格实体"数组的键名
ENTITY_ARRAYS = (
    "Cars", "Entities", "Emptys", "Factorys", "Boxs", "SubLevels",
    "GridLocks", "GridKeys", "FreezingCars", "LockDoors", "Parks", "PayParks",
)

# 方向向量。注意 CellY 越大越靠上,Down 即 y 递减(流向荷花区)
DIR_VEC = {"Down": (0, -1), "Up": (0, 1), "Left": (-1, 0), "Right": (1, 0)}

GRID_W, GRID_H = 7, 11
PAYPARK_ROW, PARK_ROW, ENTRY_ROW = 0, 1, 2
PLAY_Y_MIN = 3          # 玩法元素只能出现在 y>=3


def cell_map(level):
    """返回 {(x,y): 数组名}。未出现在任何数组里的格子 = 青蛙源格。"""
    d = {}
    for key in ENTITY_ARRAYS:
        for e in level.get(key, []) or []:
            d[(e["CellX"], e["CellY"])] = key
    return d


def frog_source_cells(level):
    """青蛙源格 = 玩法区内未被任何数组声明的格子,每格产出 1 只青蛙。"""
    d = cell_map(level)
    w = level["Grid"]["Width"]
    h = level["Grid"]["Height"]
    return [(x, y) for y in range(h) for x in range(w) if (x, y) not in d]


def predicted_total_frogs(level):
    """
    青蛙总量守恒等式(500/500 验证通过):

        ΣTotalCarCounts
          = 未声明格数
          + 静态 Cars 数
          + Box 数                              (每个 Box 恰好 1 只)
          + Σ Factory.IncludeCarCount           (工厂按字段刷)
          + FreezingCars 数                     (每个冰冻蛙 1 只)
          + Σ (SubLevelSizeX * SubLevelSizeY + 1)   (子关卡:覆盖面积 + 自身格)

    注意: DS 代码里用的是
        ΣTotalCarCounts - 静态Cars == Σ工厂刷入 + ΣBox数 + 真正空格数
    这条在 500 关上只命中 3/500,是错的。
    """
    w, h = level["Grid"]["Width"], level["Grid"]["Height"]
    # 注意: 用"声明条目总数"而非"不重复格子数"。SubLevel 是 Floor=1 的覆盖层,
    # 可以和 Floor=0 的 Box 占同一格(实测 22 关 / 24 处如此),两条都要计入。
    undeclared = w * h - sum(len(level.get(k, []) or []) for k in ENTITY_ARRAYS)
    return (
        undeclared
        + len(level.get("Cars", []) or [])
        + len(level.get("Boxs", []) or [])
        + sum(f["IncludeCarCount"] for f in (level.get("Factorys", []) or []))
        + len(level.get("FreezingCars", []) or [])
        + sum(s["SubLevelSizeX"] * s["SubLevelSizeY"] + 1
              for s in (level.get("SubLevels", []) or []))
    )


def _reachable_from_entry(level):
    """从 y=2 整行出发,只穿越非 Wall 格的 BFS 可达集。"""
    d = cell_map(level)
    w, h = level["Grid"]["Width"], level["Grid"]["Height"]
    seen = {(x, ENTRY_ROW) for x in range(w)}
    q = deque(seen)
    while q:
        x, y = q.popleft()
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            n = (x + dx, y + dy)
            if not (0 <= n[0] < w and 0 <= n[1] < h) or n in seen:
                continue
            if d.get(n) == "Entities":      # Wall 是唯一永久阻塞物
                continue
            seen.add(n)
            q.append(n)
    return seen


def validate(level):
    """校验单关。返回违规描述列表,空列表表示全部通过。"""
    errs = []
    lv = level.get("LV", "?")
    g = level.get("Grid", {})
    w, h = g.get("Width"), g.get("Height")

    # C1 棋盘尺寸
    if (w, h) != (GRID_W, GRID_H):
        errs.append(f"C1 棋盘尺寸 {w}x{h},真实 500 关恒为 {GRID_W}x{GRID_H}")
        return errs

    d = cell_map(level)

    # C2 荷花区三行固定
    payparks = sorted((e["CellX"], e["CellY"]) for e in level.get("PayParks", []) or [])
    parks = sorted((e["CellX"], e["CellY"]) for e in level.get("Parks", []) or [])
    if payparks != [(x, PAYPARK_ROW) for x in range(w)]:
        errs.append("C2a y=0 必须是 7 个 PayPark 铺满")
    if parks != [(x, PARK_ROW) for x in range(w)]:
        errs.append("C2b y=1 必须是 7 个 Park 铺满")

    # C3 y=2 入口行必须整行 Empty(437/500 是恰好 7 个;全部 500 关该行都为 Empty)
    entry = [(x, ENTRY_ROW) for x in range(w)]
    if any(d.get(c) != "Emptys" for c in entry):
        errs.append("C3 y=2 入口行必须整行声明为 Emptys(通往荷花的咽喉)")

    # C4 玩法元素不得侵入 y<3
    for key in ("Cars", "Entities", "Factorys", "Boxs", "SubLevels",
                "GridLocks", "GridKeys", "FreezingCars", "LockDoors"):
        for e in level.get(key, []) or []:
            if e["CellY"] < PLAY_Y_MIN:
                errs.append(f"C4 {key} 出现在 y={e['CellY']},玩法元素只能在 y>=3")
                break

    # C5 青蛙总量守恒
    declared = sum(level.get("TotalCarCounts", []) or [])
    pred = predicted_total_frogs(level)
    if declared != pred:
        errs.append(f"C5 守恒等式不成立: ΣTotalCarCounts={declared} 但布局推算={pred}")

    # C6 每色数量为 3 的倍数(否则该色永远消不完)
    for c, n in zip(level.get("TotalCarColorTypes", []) or [],
                    level.get("TotalCarCounts", []) or []):
        if n % 3 != 0:
            errs.append(f"C6 颜色 {c} 数量 {n} 不是 3 的倍数")

    # C7 颜色种类数 2-8,且单色数量落在真实取值域
    ncol = len(level.get("TotalCarColorTypes", []) or [])
    if not (2 <= ncol <= 8):
        errs.append(f"C7a 颜色种类数 {ncol},真实范围 2-8")
    for n in level.get("TotalCarCounts", []) or []:
        if n not in (3, 6, 9, 12, 15):
            errs.append(f"C7b 单色数量 {n} 超出真实取值域 {{3,6,9,12,15}}")

    # C8 全部青蛙源格必须能通过非 Wall 路径到达 y=2
    reach = _reachable_from_entry(level)
    srcs = [(x, y) for y in range(PLAY_Y_MIN, h) for x in range(w) if (x, y) not in d]
    unreach = [c for c in srcs if c not in reach]
    if unreach:
        errs.append(f"C8 有 {len(unreach)} 个青蛙源格无法到达 y=2(Wall 围死): {unreach[:5]}")

    # C9 工厂出口格必须在界内且不是 Wall
    for f in level.get("Factorys", []) or []:
        dr = f.get("Dir") or "Down"          # 反序列化默认 Down
        vx, vy = DIR_VEC[dr]
        n = (f["CellX"] + vx, f["CellY"] + vy)
        if not (0 <= n[0] < w and 0 <= n[1] < h):
            errs.append(f"C9a 工厂 ({f['CellX']},{f['CellY']}) Dir={dr} 出口越界")
        elif d.get(n) == "Entities":
            errs.append(f"C9b 工厂 ({f['CellX']},{f['CellY']}) Dir={dr} 出口是 Wall")

    # C10 GridLock 与 GridKey 必须逐色配平
    lk = Counter(e["ColorType"] for e in (level.get("GridLocks", []) or []))
    ky = Counter(e["ColorType"] for e in (level.get("GridKeys", []) or []))
    if lk != ky:
        errs.append(f"C10 锁/钥匙颜色不配平: 锁={dict(lk)} 钥匙={dict(ky)}")

    # C11 Box/Factory/SubLevel/FreezingCar 不得写颜色(真实数据 0 例外)
    for key in ("Boxs", "Factorys", "SubLevels", "FreezingCars"):
        for e in level.get(key, []) or []:
            if e.get("ColorType"):
                errs.append(f"C11 {key} 不应携带 ColorType,实测 500 关无一例外")
                break

    return errs


def validate_all(path, limit=None):
    import json
    levels = json.load(open(path))["Levels"]
    if limit:
        levels = levels[:limit]
    bad = 0
    hist = Counter()
    for l in levels:
        errs = validate(l)
        if errs:
            bad += 1
            for e in errs:
                hist[e.split(" ")[0]] += 1
    print(f"{path}: {len(levels)} 关, 通过 {len(levels)-bad}, 违规 {bad}")
    for k, v in hist.most_common():
        print(f"   {k}: {v} 关违规")
    return bad
