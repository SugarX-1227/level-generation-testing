# -*- coding: utf-8 -*-
"""
精确可解性模拟器 v2 —— 带回溯搜索

复刻规则（反编译还原）：
- 荷花队列 = Park 槽（dpi，容量=7，即 500 关每关 7 个 Park）。青蛙落位进 Park 序列 dvc。
- 停车位置 ParkingSlotManager.btf：新青蛙优先落在"最近一只同色青蛙后面"(slot = 同色位置+1)；无同色则队尾。
- 消除 CarEliminationManager.cgp/cgt：荷花序列中"任意 3 只同色"即消掉这 3 只（动态、每落1只检查一次）。
- 胜利 ParkingManager.bsi：场上青蛙全消 且 各列表空。
- 判负 ParkingManager.bsl：荷花序列占满(>=7) 且 无连续3同色(bsg)。

可解性 = 是否存在一条操作序列（依次选择可达青蛙落位），使最终全消且从不判负。
用回溯搜索（DFS + 剪枝）枚举，而不是贪心。
"""
from __future__ import annotations
from typing import List, Optional, Tuple
from collections import defaultdict
from rules import Board, CellType, COLOR_WHITE, PARK_ROW, PAYPARK_ROW, ENTRY_ROW


class SimState:
    """一次落位决策的可变状态：棋盘剩余青蛙 + 荷花序列。"""
    def __init__(self, board: Board):
        self.board = board
        # 荷花序列（dvc）: 用 list 存已落位的青蛙(按槽序) —— 但消除会移除。
        # 用 list 存 (frog_id, color)
        self.lotus: List[Tuple[int, int]] = []
        # 记录棋盘上仍待移动的青蛙(非 eliminated)
        self.remaining = [f for f in board.frogs if f.state != "eliminated"]
        # 已移走青蛙的格子（这些格被腾空，供后续通行）—— 不修改原始 board
        self.cleared: Set[Tuple[int, int]] = set()

    def copy(self) -> "SimState":
        s = SimState.__new__(SimState)
        s.board = self.board
        s.lotus = list(self.lotus)
        s.remaining = list(self.remaining)
        s.cleared = set(self.cleared)
        return s


class Solver:
    def __init__(self, board: Board, max_depth: int = 40, max_nodes: int = 200000):
        self.b = board
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.nodes = 0

    # ---- A* (复刻 CarController.bqn) ----
    def blocked(self, x, y, cleared=None):
        if not self.b.in_bounds(x, y):
            return True
        if cleared and (x, y) in cleared:
            return False  # 被移走的青蛙，格已空
        if self.b.frog_at(x, y) is not None and (x, y) not in (cleared or set()):
            return True  # 有静态青蛙挡路
        c = self.b.get_cell(x, y)
        return c in (CellType.WALL, CellType.CAR, CellType.BOX, CellType.GRIDLOCK,
                     CellType.GRIDKEY, CellType.SUBLEVEL, CellType.FREEZINGCAR, CellType.LOCKDOOR)

    def a_star(self, start, goal, cleared=None):
        if start == goal:
            return []
        cleared = cleared or set()
        def h(p):
            return abs(p[0]-goal[0]) + abs(p[1]-goal[1])
        open_list = [(h(start), 0, start)]
        g = {start: 0}
        came = {}
        seen = set()
        while open_list:
            open_list.sort(key=lambda t: t[0])
            _, gc, cur = open_list.pop(0)
            if cur == goal:
                path = [cur]
                while cur in came:
                    cur = came[cur]
                    path.append(cur)
                path.reverse()
                return path[1:]
            if cur in seen:
                continue
            seen.add(cur)
            x, y = cur
            for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
                nxt = (x+dx, y+dy)
                if self.blocked(*nxt, cleared) or nxt in seen:
                    continue
                ng = gc + 1
                if nxt not in g or ng < g[nxt]:
                    g[nxt] = ng
                    came[nxt] = cur
                    open_list.append((ng+h(nxt), ng, nxt))
        return None

    def reachable(self, frog, cleared=None):
        """青蛙能到达的荷花区关键行目标。返回路径或 None。"""
        b = self.b
        cands = []
        for x in range(b.w):
            if not self.blocked(x, ENTRY_ROW, cleared):
                cands.append((x, ENTRY_ROW))
        best = None
        for c in cands:
            if c == (frog.x, frog.y):
                continue
            p = self.a_star((frog.x, frog.y), c, cleared)
            if p is not None:
                if best is None or len(p) < len(best):
                    best = p
        return best

    # ---- 停车位置 (btf) ----
    def choose_slot(self, lotus, color):
        """返回插入槽 index。lotus = [(frog_id, color), ...] 已落位序列。"""
        if len(lotus) == 0:
            return 0
        # 从后往前找最近同色，停到同色位置+1
        for i in range(len(lotus)-1, -1, -1):
            if lotus[i][1] == color:
                return i+1
        return len(lotus)

    # ---- 消除检测 (cgp): 任意3同色，消掉那3只 ----
    def try_eliminate(self, lotus):
        """返回 (new_lotus, eliminated_count)。任意3同色则消。"""
        groups = defaultdict(list)
        for idx, (fid, col) in enumerate(lotus):
            if col != COLOR_WHITE:
                groups[col].append(idx)
        # 找任何一个有>=3同色的组
        for col, idxs in groups.items():
            if len(idxs) >= 3:
                rem = sorted(idxs, reverse=True)
                for i in rem[:3]:
                    del lotus[i]
                return lotus, 3
        return lotus, 0

    def dfs(self, state: SimState, depth: int):
        """回溯搜索。返回 True 表示可解。"""
        self.nodes += 1
        if self.nodes > self.max_nodes:
            return None  # 超节点上限，不确定
        # 胜利：棋盘无青蛙 且 荷花序列也清空
        if len(state.remaining) == 0 and len(state.lotus) == 0:
            return True
        if depth > self.max_depth:
            return None

        # 对每只可移动青蛙尝试落位
        moved = False
        for frog in state.remaining:
            path = self.reachable(frog, state.cleared)
            if path is None:
                continue
            moved = True
            # 落位
            slot = self.choose_slot(state.lotus, frog.color)
            # 插入到 slot（保持序列顺序）
            inserted = False
            new_lotus = list(state.lotus)
            if slot >= len(new_lotus):
                new_lotus.append((frog.id, frog.color))
            else:
                new_lotus.insert(slot, (frog.id, frog.color))
            # 消除
            new_lotus, elim = self.try_eliminate(new_lotus)
            # 判负：荷花序列占满 且 无3同色
            if len(new_lotus) >= 7 and elim == 0:
                continue  # 判负，此分支不可
            # 构造新状态
            ns = state.copy()
            ns.lotus = new_lotus
            ns.remaining = [f for f in ns.remaining if f is not frog]
            # 记录该格已腾空（供后续青蛙通行），不修改原始 board
            ns.cleared.add((frog.x, frog.y))
            res = self.dfs(ns, depth+1)
            if res is True:
                return True
            if res is None:
                return None
        if not moved:
            # 无可移动青蛙且还有剩余 -> 不可解
            return False
        return False

    def solvable(self) -> Tuple[bool, Optional[str]]:
        init = SimState(self.b)
        r = self.dfs(init, 0)
        if r is True:
            return True, "solved"
        if r is None:
            return False, "unknown(limit)"
        return False, "stuck"
