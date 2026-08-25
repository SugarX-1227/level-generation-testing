# -*- coding: utf-8 -*-
"""
RandomCarManager 复刻 —— 第3步核心：Factory/Box 刷青蛙的颜色分配算法
================================================================
反编译来源：ReCarMatch.Framework.RandomCarManager（_OUT_AUTOTEST）
om()=刷一只青蛙选颜色的入口：on()(保底) -> oo()(概率) -> os()(剩余随机)
op()=选色核心：优先选「已停>=2且还有配额」的颜色（凑3连防堵死）。
"""
from __future__ import annotations
import random
from collections import defaultdict
from rules import COLOR_WHITE

__all__ = ["RandomCarManager"]


class RandomCarManager:
    def __init__(self, space_probs=None, space_guarantee=None,
                 total_color_types=None, total_counts=None, seed=None):
        """
        space_probs: {space_int(bool): prob}  -> SpaceProbabilityConfigs 解析结果
        space_guarantee: {space_int: count}   -> SpaceGuaranteeConfigs
        total_color_types: list[int]          -> TotalCarColorTypes 索引
        total_counts: list[int]               -> TotalCarCounts
        """
        self.cdz = space_probs or {}          # space -> {restrict: prob}
        self.cea = space_guarantee or {}      # space -> {restrict: count}
        self.rng = random.Random(seed)
        # ceb: 颜色配额总量
        self.ceb = {}
        if total_color_types and total_counts:
            for c, n in zip(total_color_types, total_counts):
                if c != COLOR_WHITE:
                    self.ceb[c] = self.ceb.get(c, 0) + n
        # cec: 静态/场外已用的颜色计数
        self.cec = defaultdict(int)
        self.ced = {}   # 剩余可用配额（ol() 计算）
        self._rebuild()

    def _rebuild(self):
        """ol(): 计算剩余可用配额 ced。简化为 总量-已用。"""
        self.ced = {}
        for c, total in self.ceb.items():
            used = self.cec.get(c, 0)
            rem = total - used
            if rem > 0:
                self.ced[c] = rem

    # ---- 外部状态注入 ----
    def set_parked_colors(self, colors: list):
        """当前已停荷花上的颜色（oq()）。影响 op() 选择。"""
        self._oq = list(colors)

    def set_queue_colors(self, colors: list):
        """当前网格上未消的青蛙颜色（or()）。"""
        self._oq_extra = list(colors)

    # ---- ow()/ov(): 剩余空车位 ----
    def rem_space(self, slot_total, parked, moving, queue):
        return max(0, slot_total - parked - moving - queue)

    # ---- op(): 选色核心(防堵死/促消除) ----
    def _op(self):
        """复刻 op()：优先选「已停>=2 且有配额」的颜色。"""
        source = self._oq if hasattr(self, "_oq") else []
        # source 按颜色计数降序
        cnt = defaultdict(int)
        for c in source:
            if c != COLOR_WHITE:
                cnt[c] += 1
        ordered = sorted(cnt.items(), key=lambda kv: kv[1], reverse=True)
        chosen = None
        # 第一优先：已停>=2 且有配额
        for c, n in ordered:
            if n >= 2 and self.ced.get(c, 0) > 0:
                chosen = c
                break
        if chosen is None:
            # 第二优先：已停>=1 且有配额（含队列）
            extra = self._oq_extra if hasattr(self, "_oq_extra") else []
            ecnt = defaultdict(int)
            for c in extra:
                if c != COLOR_WHITE:
                    ecnt[c] += 1
            for c, n in ordered:
                total = n + ecnt.get(c, 0)
                if total >= 2 and self.ced.get(c, 0) > 0:
                    chosen = c
                    break
        if chosen is not None:
            self.ced[chosen] -= 1
            return chosen
        # 无合适 -> 随机从剩余配额抽
        if self.ced:
            total_rem = sum(self.ced.values())
            if total_rem > 0:
                r = self.rng.randrange(total_rem)
                acc = 0
                for c, n in self.ced.items():
                    acc += n
                    if r < acc:
                        self.ced[c] -= 1
                        return c
        return COLOR_WHITE

    # ---- om(): 刷一只青蛙的颜色 ----
    def om(self):
        """复刻 om()。返回颜色索引，White 表示无合适颜色。"""
        # on(): 保底（space_guarantee）
        space = getattr(self, "_space", None)
        if space is not None and space in self.cea:
            counts = self.cea[space]
            for restrict, cnt in counts.items():
                if cnt > 0:
                    col = self._op()
                    if col != COLOR_WHITE:
                        counts[restrict] = cnt - 1
                        return col
        # oo(): 概率（space_prob）
        if space is not None and space in self.cdz:
            probs = self.cdz[space]
            for restrict, p in probs.items():
                if self.rng.randrange(100) < p:
                    col = self._op()
                    if col != COLOR_WHITE:
                        return col
        # os(): 剩余随机
        if self.ced:
            return self._op()
        return COLOR_WHITE
