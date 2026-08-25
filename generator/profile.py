# -*- coding: utf-8 -*-
"""
AI 学习 500 关风格/难度 —— 统计分布拟合（profile）
====================================================
从真实 levels.json 的 500 关统计各难度档位的生成参数分布，
供 generator3 复用，让产出贴近真实关卡风格。

使用方式：profile.get_style(hard_type) 或 profile.sample_mode(mode)
"""
import json
import random
from collections import Counter
from pathlib import Path

# 缓存分析结果
_CACHE = {}


def _load():
    p = Path(__file__).parent.parent / "levels.json"
    with open(p) as f:
        return json.load(f)["Levels"]


def analyze():
    """分析 500 关，返回按 HardType 分组的风格参数。"""
    if "data" in _CACHE:
        return _CACHE["data"]
    L = _load()
    res = {}
    for h in (0, 1, 3):
        lvls = [lv for lv in L if lv.get("HardType") == h]
        if not lvls:
            continue
        res[h] = {
            "count": len(lvls),
            "ncolors": [len(lv["TotalCarColorTypes"]) for lv in lvls],
            "total": [sum(lv["TotalCarCounts"]) for lv in lvls],
            "nfactory": [len(lv.get("Factorys", [])) for lv in lvls],
            "nbox": [len(lv.get("Boxs", [])) for lv in lvls],
            "nsub": sum(1 for lv in lvls if lv.get("SubLevels")),
            "nfreeze": sum(1 for lv in lvls if lv.get("FreezingCars")),
            # Factory 方向分布
            "fdir": dict(Counter(f["Dir"] for lv in lvls for f in lv.get("Factorys", []))),
        }
    _CACHE["data"] = res
    return res


def sample(mode="hard", seed=None):
    """按难度档位随机采样风格参数。
    mode: 'hard'(HardType=3 超难, 默认) / 'medium'(HardType=1) / 'normal'(HardType=0) / 'auto'(随机)"""
    rng = random.Random(seed)
    data = analyze()
    if mode == "hard":
        h = 3
    elif mode == "medium":
        h = 1
    elif mode == "normal":
        h = 0
    else:
        h = rng.choice([0, 1, 3])
    s = data.get(h, data[3])
    ncolors = s["ncolors"]
    total = s["total"]
    nfac = s["nfactory"]
    nbox = s["nbox"]
    # 随机采样
    n_color = rng.choice(ncolors)
    n_total = rng.choice(total)
    n_factory = rng.choice(nfac) if nfac else 0
    n_box = rng.choice(nbox) if nbox else 0
    return {
        "hard_type": h,
        "n_color": n_color,
        "n_total": n_total,
        "n_factory": n_factory,
        "n_box": n_box,
        "fdir": s.get("fdir", {}),
    }


def get_style(hard_type=3):
    """返回某难度档位的参数摘要。"""
    return analyze().get(hard_type)


if __name__ == "__main__":
    a = analyze()
    for h, s in a.items():
        print(f"HardType={h} ({s['count']}关): 颜色数{s['ncolors']} 总量均{sum(s['total'])/len(s['total']):.0f} "
              f"Factory均{sum(s['nfactory'])/len(s['nfactory']):.1f} Box均{sum(s['nbox'])/len(s['nbox']):.1f} "
              f"方向{s['fdir']}")
