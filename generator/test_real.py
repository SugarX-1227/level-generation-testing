# -*- coding: utf-8 -*-
"""
用真实 levels.json 关卡验证模拟器是否复刻游戏规则。
如果模拟器对真实已知"可玩"的关卡判定为可解，说明规则还原正确。
"""
import json
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from rules import Board, CellType, color_of_name, DIR_DOWN
from solver import Solver


def load_level(levels, lv_num):
    for lv in levels:
        if lv["LV"] == lv_num:
            return lv
    return None


def build_board(lv):
    b = Board()
    grid = lv["Grid"]
    b.w = grid["Width"]
    b.h = grid["Height"]
    # 先填满 Wall
    for y in range(b.h):
        for x in range(b.w):
            b.set_cell(x, y, CellType.WALL)
    # 再建荷花区（先清空 slots）
    b.setup_fixed_parks()
    # 依据关卡实际 Parks/PayParks 覆盖
    for p in sorted(lv.get("Parks", []), key=lambda q: q["CellX"]):
        b.set_cell(p["CellX"], p["CellY"], CellType.PARK)
    for p in sorted(lv.get("PayParks", []), key=lambda q: q["CellX"]):
        b.set_cell(p["CellX"], p["CellY"], CellType.PAYPARK)
    # 重建 parking_slots 为 关卡实际顺序（先 x0..6 行y=0 pay，再 x0..6 行y=1 park —— 见数据）
    # 数据中 PayParks 在 y=0, Parks 在 y=1
    b.parking_slots = []
    for p in sorted(lv.get("PayParks", []), key=lambda q: q["CellX"]):
        b.parking_slots.append(type("S", (), {"x": p["CellX"], "y": p["CellY"], "kind": "paypark", "index": len(b.parking_slots), "occupied": False})())
    for p in sorted(lv.get("Parks", []), key=lambda q: q["CellX"]):
        b.parking_slots.append(type("S", (), {"x": p["CellX"], "y": p["CellY"], "kind": "park", "index": len(b.parking_slots), "occupied": False})())
    # 覆盖其他元素（Emptys->EMPTY, Boxs->BOX, SubLevels/Lock/Freeze 视作阻塞）
    for e in lv.get("Emptys", []):
        b.set_cell(e["CellX"], e["CellY"], CellType.EMPTY)
    for bx in lv.get("Boxs", []):
        b.set_cell(bx["CellX"], bx["CellY"], CellType.BOX)
    for s in lv.get("SubLevels", []):
        b.set_cell(s["CellX"], s["CellY"], CellType.SUBLEVEL)
    for g in lv.get("GridLocks", []):
        b.set_cell(g["CellX"], g["CellY"], CellType.GRIDLOCK)
    for k in lv.get("GridKeys", []):
        b.set_cell(k["CellX"], k["CellY"], CellType.GRIDKEY)
    for fc in lv.get("FreezingCars", []):
        b.set_cell(fc["CellX"], fc["CellY"], CellType.FREEZINGCAR)
    for ld in lv.get("LockDoors", []):
        b.set_cell(ld["CellX"], ld["CellY"], CellType.LOCKDOOR)
    # Cars -> 青蛙（静态）
    for c in lv.get("Cars", []):
        col = color_of_name(c["ColorType"]) if c["ColorType"] else 999
        b.add_frog(col, c["CellX"], c["CellY"])
        b.set_cell(c["CellX"], c["CellY"], CellType.CAR)
    return b


def main():
    data = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "levels.json"))
    levels = data["Levels"]
    lv_nums = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1]
    for n in lv_nums:
        lv = load_level(levels, n)
        if not lv:
            print(f"LV {n}: not found")
            continue
        b = build_board(lv)
        s = Solver(b)
        ok, reason = s.solvable()
        print(f"LV {n}: cars={len(lv.get('Cars',[]))} colors={lv.get('TotalCarColorTypes')} -> solvable={ok} reason={reason} nodes={s.nodes}")


if __name__ == "__main__":
    main()
