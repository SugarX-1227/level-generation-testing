# -*- coding: utf-8 -*-
"""
AutoTest 风格可解性模拟器 —— 复刻 UIGameLevelAutoTestTool.AutoTestCarSelector 的走棋决策
========================================================================
反编译还原（Windows 版 Assembly-CSharp.dll）：

- dft() 主选择器：dfu() 取"可动青蛙"（dx且!moving&&!parking&&!eliminating&&idle）后 shuffle，
  然后按权重优先级 dfx(220)->dzx(1) 依次尝试 dfv() 选取最高优先级的那只。
- 落位 ehl()：ParkingSlotManager.btf 选槽 -> 插入 dvb/dvc -> 清场 -> 触发连锁。
- 消除 enf()：dvb 中"任意 3 只同色（非moving非eliminating）"即消掉这 3 只。
- 判定 ehi()：bsi() 胜 -> bsl() 判负 -> 步数上限 -> ehj() 可走 + dft 选车 -> ehl 落位，循环。

本模拟器复刻核心决策（聚焦静态青蛙关；Factory/Box/Key/SubLevel/LockDoor/Freezing 的连锁
在本版本列为「未建模触发现象」，仅保留其存在性作为阻塞/约束）。对存在这些进阶元素的关，
本判定为近似；对纯静态青蛙关为本判定精确。

返回: {solvable, reason, steps, remaining, eliminated_groups}
"""
from __future__ import annotations
from typing import List, Optional, Tuple, Set, Dict
import random
from rules import Board, CellType, COLOR_WHITE, ENTRY_ROW


class AutoTestSim:
    """复刻 AutoTest 走棋决策的可解性判定器。"""

    def __init__(self, board: Board, max_moves: int = 400, seed: int = 0):
        self.b = board
        self.max_moves = max_moves
        self.rng = random.Random(seed)
        self.moves = 0
        self.eliminated_groups = 0
        # 荷花序列 dvb —— 用 (frog_id, color) 列表
        self.parked: List[Tuple[int, int]] = []
        # 用内部集合跟踪，不修改原始 frog.state（避免污染棋盘）
        self.placed_ids: Set[int] = set()   # 已落位的青蛙
        self.eliminated_ids: Set[int] = set()  # 已消除的青蛙

    # ---------- 数据查询 ----------
    def movable_frogs(self):
        """dfu(): 可动青蛙 = 未被落位/消除的青蛙。返回 list[Frog]。"""
        out = []
        for f in self.b.frogs:
            if f.id in self.placed_ids or f.id in self.eliminated_ids:
                continue
            out.append(f)
        return out

    def park_count(self):
        """dvb.Count —— 已停稳数量（lily 序列长度）。"""
        return len(self.parked)

    def color_count_in_park(self, color):
        """eae(color): dvb 中该颜色已停数量（非moving非eliminating）。"""
        return sum(1 for (_, c) in self.parked if c == color)

    def park_colors_present(self):
        """eab(): dvb 中出现的颜色集合。"""
        s = set()
        for (_, c) in self.parked:
            s.add(c)
        return s

    def colors_with_2_in_park(self):
        """eaf(): dvb 中计数>=2 的颜色。"""
        from collections import Counter
        cnt = Counter(c for (_, c) in self.parked if c != COLOR_WHITE)
        return {c for c, n in cnt.items() if n >= 2}

    # ---------- 可达性（A*，复刻 CarController.bqn） ----------
    def blocked(self, x, y, cleared=None):
        if not self.b.in_bounds(x, y):
            return True
        if cleared and (x, y) in cleared:
            return False
        # 该格有青蛙且未被落位/消除 -> 阻塞
        f = self.b.frog_at(x, y)
        if f is not None and f.id not in self.placed_ids and f.id not in self.eliminated_ids:
            return True
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

    def reachable_entry(self, frog, cleared=None):
        """青蛙可达 entry_row 的空格（落入荷花区）。返回路径或 None。"""
        cands = []
        for x in range(self.b.w):
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

    # ---------- 停车位置（复刻 ParkingSlotManager.btf） ----------
    def choose_slot(self, color):
        """返回插入槽 index。"""
        if not self.parked:
            return 0
        for i in range(len(self.parked)-1, -1, -1):
            if self.parked[i][1] == color:
                return i+1
        return len(self.parked)

    # ---------- 消除（复刻 enf: 任意3同色非moving非eliminating） ----------
    def try_eliminate(self):
        """若 parked 中存在任意 3 只同色，则移除它们。返回是否发生。"""
        from collections import defaultdict
        groups = defaultdict(list)
        for idx, (fid, c) in enumerate(self.parked):
            if c != COLOR_WHITE:
                groups[c].append(idx)
        for c, idxs in groups.items():
            if len(idxs) >= 3:
                rem = sorted(idxs, reverse=True)
                for i in rem[:3]:
                    fid = self.parked[i][0]
                    self.eliminated_ids.add(fid)
                    del self.parked[i]
                self.eliminated_groups += 1
                return True
        return False

    # ---------- 判负 / 胜利（bsl / bsi） ----------
    def is_lose(self):
        return len(self.parked) >= 7 and not self.try_eliminate()

    def is_win(self):
        return (len(self.movable_frogs()) == 0 and self.park_count() == 0)

    # ---------- 主走棋循环（复刻 ehi） ----------
    def simulate(self):
        cleared = set()
        moves = 0
        while moves < self.max_moves and not self.is_win():
            # 判负
            if self.is_lose():
                return {"solvable": False, "reason": "lose", "steps": moves,
                        "remaining": len(self.movable_frogs()), "parked": self.park_count(),
                        "eliminated_groups": self.eliminated_groups}
            # 选一只可动青蛙（复刻 dft 的高层策略：优先选"落位后能凑3同色"的）
            chosen = None
            movable = self.movable_frogs()
            if not movable:
                # 无青蛙可动但未胜利 —— 若 queue/场上有残留则卡住
                return {"solvable": False, "reason": "no_movable", "steps": moves,
                        "remaining": len(movable), "parked": self.park_count(),
                        "eliminated_groups": self.eliminated_groups}
            # 排序：优先"落位后使某色凑到>=3"（对应 dzz: eae(color)+1>=3）及"距荷近"
            def score(f):
                s = 0
                if self.color_count_in_park(f.color) + 1 >= 3:
                    s += 100
                return s
            movable.sort(key=lambda f: (score(f), -(abs(f.y-ENTRY_ROW))), reverse=True)
            chosen = movable[0]
            # 检查可达
            path = self.reachable_entry(chosen, cleared)
            if path is None:
                # 这只不可达，尝试其他只
                chosen = None
                for f in movable:
                    if self.reachable_entry(f, cleared) is not None:
                        chosen = f
                        break
                if chosen is None:
                    return {"solvable": False, "reason": "blocked", "steps": moves,
                            "remaining": len(movable), "parked": self.park_count(),
                            "eliminated_groups": self.eliminated_groups}
            # 落位（复刻 ehl）
            slot = self.choose_slot(chosen.color)
            if slot >= len(self.parked):
                self.parked.append((chosen.id, chosen.color))
            else:
                self.parked.insert(slot, (chosen.id, chosen.color))
            self.placed_ids.add(chosen.id)
            cleared.add((chosen.x, chosen.y))
            moves += 1
            # 消除检查
            self.try_eliminate()
        if self.is_win():
            return {"solvable": True, "reason": "solved", "steps": moves,
                    "remaining": 0, "parked": 0, "eliminated_groups": self.eliminated_groups}
        return {"solvable": False, "reason": "timeout", "steps": moves,
                "remaining": len(self.movable_frogs()), "parked": self.park_count(),
                "eliminated_groups": self.eliminated_groups}


def solvable(board: Board, **kw) -> Dict:
    sim = AutoTestSim(board, **kw)
    return sim.simulate()
