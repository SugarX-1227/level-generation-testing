# -*- coding: utf-8 -*-
"""
非静态（Box 藏蛙 / Factory 刷蛙）可解性模拟器
================================================
复刻机制（反编译还原）：
- Box 藏蛙：BoxEntity，青蛙移动/落位经过其旁时 BoxController.bnv(Activate) 触发，
  用 RandomCarManager.om() 按 TotalCarCounts 配额刷出一只青蛙（开箱出蛙）。
- Factory 刷蛙：FactoryController.btk() 按 IncludeCarCount 刷蛙，颜色由 om() 按配额。
- 开出的青蛙落向荷花区参与三消（btf 落位 + cgp 任意3同色消除 + bsl/bsi 判定）。
- 核心保证：ol() 等式 => ΣTotalCarCounts = 静态Cars + ΣFactory刷入 + Box数 + 真正空格。
  配额每色=3倍数 => 可凑3连。

本模拟器用 random_car.RandomCarManager 复刻 om()，模拟"Box/Factory 开箱刷蛙 -> 落位 -> 消除"，
统计级判断：在 om() 的凑3连逻辑下，能否把所有青蛙消光（可解）。

返回 {solvable, reason, remaining, parked, eliminated_groups, max_parked}
"""
from __future__ import annotations
from typing import List, Optional, Tuple, Set, Dict
from collections import defaultdict
from rules import Board, CellType, COLOR_WHITE, ENTRY_ROW
from random_car import RandomCarManager


class DynamicSim:
    def __init__(self, board: Board, color_types: list, color_counts: list,
                 space_probs=None, space_guarantee=None, seed=0, max_moves=600):
        self.b = board
        self.max_moves = max_moves
        self.rng_main = __import__("random").Random(seed)
        # 颜色映射：color index (from color_types) -> CarColorType int
        # color_types 已是 int 索引(0..7)，直接映射
        self.rm = RandomCarManager(space_probs=space_probs, space_guarantee=space_guarantee,
                                   total_color_types=color_types, total_counts=color_counts,
                                   seed=seed)
        self.parked: List[Tuple[int, int]] = []   # (frog_id, color)
        self.placed_ids: Set[int] = set()
        self.eliminated_ids: Set[int] = set()
        self.eliminated_groups = 0
        self._frog_id = 1000
        self._max_parked = 0

    # ---- 统计 Box/Factory 开箱出蛙的总配额（ol() 保证）----
    def remaining_quota(self, color):
        return self.rm.ced.get(color, 0)

    def movable_static(self):
        """棋盘上初始静态青蛙(id<1000, 未被落位/消除)。"""
        return [f for f in self.b.frogs if f.id < 1000
                and f.id not in self.placed_ids and f.id not in self.eliminated_ids]

    def blocked(self, x, y, cleared=None):
        if not self.b.in_bounds(x, y):
            return True
        if cleared and (x, y) in cleared:
            return False
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
        def h(p): return abs(p[0]-goal[0]) + abs(p[1]-goal[1])
        open_list = [(h(start), 0, start)]
        g = {start: 0}; came = {}; seen = set()
        while open_list:
            open_list.sort(key=lambda t: t[0])
            _, gc, cur = open_list.pop(0)
            if cur == goal:
                path = [cur]
                while cur in came:
                    cur = came[cur]; path.append(cur)
                path.reverse(); return path[1:]
            if cur in seen: continue
            seen.add(cur)
            x, y = cur
            for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
                nxt = (x+dx, y+dy)
                if self.blocked(*nxt, cleared) or nxt in seen: continue
                ng = gc+1
                if nxt not in g or ng < g[nxt]:
                    g[nxt] = ng; came[nxt] = cur
                    open_list.append((ng+h(nxt), ng, nxt))
        return None

    def reachable_entry(self, frog, cleared=None):
        cands = [(x, ENTRY_ROW) for x in range(self.b.w) if not self.blocked(x, ENTRY_ROW, cleared)]
        best = None
        for c in cands:
            if c == (frog.x, frog.y): continue
            p = self.a_star((frog.x, frog.y), c, cleared)
            if p is not None and (best is None or len(p) < len(best)):
                best = p
        return best

    def choose_slot(self, color):
        if not self.parked: return 0
        for i in range(len(self.parked)-1, -1, -1):
            if self.parked[i][1] == color: return i+1
        return len(self.parked)

    def try_eliminate(self):
        groups = defaultdict(list)
        for idx, (fid, c) in enumerate(self.parked):
            if c != COLOR_WHITE: groups[c].append(idx)
        for c, idxs in groups.items():
            if len(idxs) >= 3:
                rem = sorted(idxs, reverse=True)
                for i in rem[:3]:
                    self.eliminated_ids.add(self.parked[i][0])
                    del self.parked[i]
                self.eliminated_groups += 1
                return True
        return False

    def is_lose(self):
        return len(self.parked) >= 7 and not self.try_eliminate()

    def is_win(self):
        return (len(self.movable_static()) == 0 and len(self.parked) == 0
                and all(v <= 0 for v in self.rm.ced.values()))

    def _spawn_with_om(self, cell):
        """用 om() 刷一只青蛙（复刻 Box/Factory 开箱）。返回 Frog 或 None。"""
        # om() 输出颜色索引(枚举值 int)；需映射到颜色名对应索引
        col = self.rm.om()
        if col == COLOR_WHITE:
            return None
        frog = type("Frog", (), {})()
        frog.id = self._frog_id; self._frog_id += 1
        frog.color = col; frog.x = cell[0]; frog.y = cell[1]
        frog.state = "idle"
        self.b.frogs.append(frog)
        return frog

    def simulate(self):
        cleared = set()
        moves = 0
        # 初始：把静态青蛙排队（先处理它们）
        while moves < self.max_moves and not self.is_win():
            if self.is_lose():
                return {"solvable": False, "reason": "lose", "steps": moves,
                        "remaining": len(self.movable_static()), "parked": len(self.parked),
                        "eliminated_groups": self.eliminated_groups, "max_parked": self._max_parked}
            movable = self.movable_static()
            chosen = None
            if movable:
                # 优先选能凑3连的
                def score(f):
                    s = 0
                    if sum(1 for (_, c) in self.parked if c == f.color) + 1 >= 3: s += 100
                    return s
                movable.sort(key=lambda f: (score(f), -(abs(f.y-ENTRY_ROW))), reverse=True)
                for f in movable:
                    if self.reachable_entry(f, cleared) is not None:
                        chosen = f; break
            # 若无静态可动，看看有没有 Box/Factory 能开箱出一只蛙
            if chosen is None:
                spawned = self._try_spawn_from_dynamic(cleared)
                if spawned is None:
                    # 开不出新蛙且静态全卡 -> 判负或需更多步
                    if not movable:
                        return {"solvable": False, "reason": "stuck", "steps": moves,
                                "remaining": len(self.movable_static()), "parked": len(self.parked),
                                "eliminated_groups": self.eliminated_groups, "max_parked": self._max_parked}
                else:
                    chosen = spawned
            if chosen is None:
                return {"solvable": False, "reason": "no_move", "steps": moves,
                        "remaining": len(self.movable_static()), "parked": len(self.parked),
                        "eliminated_groups": self.eliminated_groups, "max_parked": self._max_parked}
            # 落位
            slot = self.choose_slot(chosen.color)
            if slot >= len(self.parked): self.parked.append((chosen.id, chosen.color))
            else: self.parked.insert(slot, (chosen.id, chosen.color))
            self.placed_ids.add(chosen.id)
            cleared.add((chosen.x, chosen.y))
            self._max_parked = max(self._max_parked, len(self.parked))
            moves += 1
            self.try_eliminate()
        if self.is_win():
            return {"solvable": True, "reason": "solved", "steps": moves, "remaining": 0,
                    "parked": 0, "eliminated_groups": self.eliminated_groups, "max_parked": 0}
        return {"solvable": False, "reason": "timeout", "steps": moves,
                "remaining": len(self.movable_static()), "parked": len(self.parked),
                "eliminated_groups": self.eliminated_groups, "max_parked": self._max_parked}

    def _try_spawn_from_dynamic(self, cleared):
        """尝试从 Box/Factory 刷一只蛙（模拟开箱）。返回 Frog 或 None。"""
        # 找棋盘上 Box/Factory 实体格
        dyn_cells = []
        for y in range(self.b.h):
            for x in range(self.b.w):
                c = self.b.get_cell(x, y)
                if c in (CellType.BOX, CellType.FACTORY):
                    dyn_cells.append((x, y))
        # 找一个还能刷且配额有余的（简单策略：刷一个，颜色由 om() 定）
        for cell in dyn_cells:
            if self.remaining_quota_any():
                frog = self._spawn_with_om(cell)
                if frog is not None:
                    return frog
        return None

    def remaining_quota_any(self):
        return sum(self.rm.ced.values()) > 0 or len(self.movable_static()) > 0
