# -*- coding: utf-8 -*-
"""
ReCarMatch 关卡可解性模拟器 —— 精确复刻反编译还原的规则
=========================================================
数据来源：对 AutoTest(_OUT_AUTOTEST) 程序集 ilspy 反编译还原。

核心规则（对应游戏类）：
- 棋盘 GridConfig: 7x11, CellSize=64；dg/world->cell 坐标变换；dc 边界检查。
- GridEntityType: Empty/Wall/Car/Park/PayPark/Factory/Box/LockDoor/SubLevel/GridLock/GridKey/FreezingCar
- CarColorType: Red=0 Blue=1 Green=2 Yellow=3 Purple=4 Orange=5 Cyan=6 Pink=7 Brown=8 Black=9 White=999
- 青蛙进入荷花区: CarController.bqk —— 当 frog 的 cell.y == 2（荷花区上方关键行）或 IsInPayPark 时进入停车流程。
- 停车位置: ParkingSlotManager.btf —— 新青蛙优先落在"最近一只同色青蛙后面"(slot = 该同色位置+1)；无同色则追加队尾。
- 消除: CarEliminationManager.cgp —— 已停稳的青蛙中"任意 3 只同色"即触发消除（不要求连续）。
  * 注意: 实际消除用 cgp(任意3同色)；ParkingManager.bsf(连续3同色) 用于判负判定 bsl() 和潜在消除检测 ox()。
- 判负: ParkingManager.bsl —— 荷花序列 dvc.Count >= 槽位总数 dpi.Count 且 !bsg()(无连续3同色) -> 败。
- 胜利: ParkingManager.bsi —— 场上青蛙 dpp==0 且 dvb/dvc/dvd/dve 全空 且 队列 btb()==0。
- 静态青蛙移动: CarController.bqn A*（4邻，bqq=目标格被占判定）。

本模块为『静态 Cars 布局』精确模拟。Factory/Box 刷入运行时随机颜色，先不在本版本纳入精确模拟。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Dict, Tuple, Optional, Set

# ---- 常量 ----
COLOR_RED, COLOR_BLUE, COLOR_GREEN, COLOR_YELLOW = 0, 1, 2, 3
COLOR_PURPLE, COLOR_ORANGE, COLOR_CYAN, COLOR_PINK = 4, 5, 6, 7
COLOR_BROWN, COLOR_BLACK, COLOR_WHITE = 8, 9, 999
COLOR_NAMES = {
    0: "Red", 1: "Blue", 2: "Green", 3: "Yellow",
    4: "Purple", 5: "Orange", 6: "Cyan", 7: "Pink",
    8: "Brown", 9: "Black", 999: "White",
}

# 实体类型
ENT_EMPTY, ENT_WALL, ENT_CAR, ENT_PARK = "Empty", "Wall", "Car", "Park"
ENT_PAYPARK, ENT_FACTORY, ENT_BOX, ENT_LOCKDOOR = "PayPark", "Factory", "Box", "LockDoor"
ENT_SUBLEVEL, ENT_GRIDLOCK, ENT_GRIDKEY, ENT_FREEZINGCAR = "SubLevel", "GridLock", "GridKey", "FreezingCar"

# 方向
DIR_DOWN, DIR_UP, DIR_RIGHT, DIR_LEFT = "Down", "Up", "Right", "Left"

GRID_W, GRID_H = 7, 11
PARK_ROW, PAYPARK_ROW = 1, 0   # Park 在 y=1, PayPark 在 y=0
# 到达荷叶区触发停车的关键行
ENTRY_ROW = 2


class CellType(IntEnum):
    EMPTY = 0
    WALL = 1
    PARK = 2      # 荷花槽（可停）
    PAYPARK = 3   # 付费荷花槽（可停）
    CAR = 4
    # 以下静态布局常见，本版本模拟可存在但不参与青蛙
    BOX = 5
    FACTORY = 6
    SUBLEVEL = 7
    GRIDLOCK = 8
    GRIDKEY = 9
    FREEZINGCAR = 10
    LOCKDOOR = 11


@dataclass
class Frog:
    """一只青蛙（CarEntity 的简化）"""
    color: int
    x: int
    y: int
    id: int
    state: str = "idle"   # idle / moving / parked / parked_queue / eliminated
    slot: int = -1        # parked 时的荷花槽索引


@dataclass
class ParkingSlot:
    """荷花槽位（Park 或 PayPark）"""
    x: int
    y: int
    kind: str             # "park" / "paypark"
    index: int
    occupied: bool = False


class Board:
    """棋盘布局 + 静态青蛙，复刻 GridConfig.dc / dg 语义"""

    def __init__(self, width: int = GRID_W, height: int = GRID_H):
        self.w = width
        self.h = height
        # grid[y][x] = CellType
        self.cells: List[List[CellType]] = [
            [CellType.EMPTY for _ in range(width)] for _ in range(height)
        ]
        self.frogs: List[Frog] = []
        self.parking_slots: List[ParkingSlot] = []  # 有序荷花槽
        self.slot_by_cell: Dict[Tuple[int, int], int] = {}
        self._frog_id = 0

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def set_cell(self, x: int, y: int, t: CellType):
        self.cells[y][x] = t

    def get_cell(self, x: int, y: int) -> CellType:
        return self.cells[y][x]

    def add_frog(self, color: int, x: int, y: int) -> Frog:
        f = Frog(color=color, x=x, y=y, id=self._frog_id)
        self._frog_id += 1
        self.frogs.append(f)
        return f

    def add_parking_slot(self, x: int, y: int, kind: str):
        idx = len(self.parking_slots)
        slot = ParkingSlot(x=x, y=y, kind=kind, index=idx)
        self.parking_slots.append(slot)
        self.slot_by_cell[(x, y)] = idx
        self.set_cell(x, y, CellType.PARK if kind == "park" else CellType.PAYPARK)

    def setup_fixed_parks(self):
        """按游戏默认：y=0 一排 PayPark(7)，y=1 一排 Park(7)。幂等。"""
        self.parking_slots = []
        self.slot_by_cell = {}
        for x in range(self.w):
            self.add_parking_slot(x, PAYPARK_ROW, "paypark")
        for x in range(self.w):
            self.add_parking_slot(x, PARK_ROW, "park")

    def occupied(self, x: int, y: int) -> bool:
        """该格是否被阻塞（WALL/静态CAR/BOX 等 Blocking=true 的实体）。
        复刻 GridEntityManager.fd(a) —— Blocking 判定。"""
        c = self.cells[y][x]
        if c == CellType.WALL or c == CellType.CAR or c == CellType.BOX:
            return True
        # PARK/PAYPARK 不阻塞
        return False

    def frog_at(self, x: int, y: int) -> Optional[Frog]:
        for f in self.frogs:
            if f.state != "eliminated" and f.x == x and f.y == y and f.state in ("idle", "moving"):
                return f
        return None


def color_of_name(name: str) -> int:
    n = name.strip()
    for k, v in COLOR_NAMES.items():
        if v.lower() == n.lower():
            return k
    raise ValueError(f"unknown color: {name}")
