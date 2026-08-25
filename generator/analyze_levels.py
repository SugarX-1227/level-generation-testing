# -*- coding: utf-8 -*-
"""
前 500 关结构分析 —— 本脚本复现 《500关结构分析报告.md》 里的全部统计。
用法: python3 analyze_levels.py path/to/levels.json
"""
import json, sys, statistics as st
from collections import Counter, defaultdict, deque

ARR = ('Cars','Entities','Emptys','Factorys','Boxs','SubLevels','GridLocks',
       'GridKeys','FreezingCars','LockDoors','Parks','PayParks')
DIR_VEC = {'Down':(0,-1),'Up':(0,1),'Left':(-1,0),'Right':(1,0)}


def cellmap(l):
    d = {}
    for k in ARR:
        for e in l.get(k, []) or []:
            d.setdefault((e['CellX'], e['CellY']), k)
    return d


def sec_basic(L):
    print('== 1. 棋盘与三层结构 ==')
    print('  尺寸分布:', Counter((l['Grid']['Width'], l['Grid']['Height']) for l in L).most_common())
    ok = {'y0=PayPark':0, 'y1=Park':0, 'y2全Empty':0, '元素只在y>=3':0}
    for l in L:
        if sorted((e['CellX'],e['CellY']) for e in l['PayParks']) == [(x,0) for x in range(7)]:
            ok['y0=PayPark'] += 1
        if sorted((e['CellX'],e['CellY']) for e in l['Parks']) == [(x,1) for x in range(7)]:
            ok['y1=Park'] += 1
        d = cellmap(l)
        if all(d.get((x,2)) == 'Emptys' for x in range(7)):
            ok['y2全Empty'] += 1
        others = [e for k in ('Cars','Entities','Factorys','Boxs','SubLevels',
                              'GridLocks','GridKeys','FreezingCars') for e in l.get(k,[]) or []]
        if all(e['CellY'] >= 3 for e in others):
            ok['元素只在y>=3'] += 1
    for k, v in ok.items():
        print(f'  {k}: {v}/{len(L)}')


def sec_conservation(L):
    print('\n== 2. 青蛙来源守恒等式 ==')
    hits = 0
    for l in L:
        W, H = l['Grid']['Width'], l['Grid']['Height']
        undec = W*H - sum(len(l.get(k,[]) or []) for k in ARR)
        pred = (undec + len(l['Cars']) + len(l['Boxs'])
                + sum(f['IncludeCarCount'] for f in l['Factorys'])
                + len(l['FreezingCars'])
                + sum(s['SubLevelSizeX']*s['SubLevelSizeY']+1 for s in l['SubLevels']))
        if sum(l['TotalCarCounts']) == pred:
            hits += 1
    print(f'  ΣTotalCarCounts == 未声明格 + Cars + Box + ΣFac.Inc + Freeze + Σ(SubW*SubH+1)')
    print(f'  命中: {hits}/{len(L)}')
    allc = [c for l in L for c in l['TotalCarCounts']]
    print('  单色数量取值域:', sorted(set(allc)), ' 全为3的倍数:', all(c%3==0 for c in allc))
    tot = [sum(l['TotalCarCounts']) for l in L]
    print(f'  总量 min={min(tot)} max={max(tot)} 均值={st.mean(tot):.1f} 全为3的倍数={all(t%3==0 for t in tot)}')
    print('  颜色种类数分布:', Counter(len(l['TotalCarColorTypes']) for l in L).most_common())
    print('  颜色使用频次:', Counter(c for l in L for c in l['TotalCarColorTypes']).most_common())


def sec_connectivity(L):
    print('\n== 3. 连通性 ==')
    def run(block):
        full = 0
        for l in L:
            d = cellmap(l)
            W, H = l['Grid']['Width'], l['Grid']['Height']
            seen = {(x,2) for x in range(W)}
            q = deque(seen)
            while q:
                x, y = q.popleft()
                for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
                    n = (x+dx, y+dy)
                    if not (0 <= n[0] < W and 0 <= n[1] < H) or n in seen:
                        continue
                    if d.get(n) == 'Entities' or (block and d.get(n) in block):
                        continue
                    seen.add(n); q.append(n)
            srcs = [(x,y) for y in range(3,H) for x in range(W) if (x,y) not in d]
            if all(c in seen for c in srcs):
                full += 1
        return full
    print(f'  只 Wall 阻塞           -> 全部青蛙源可达 y=2: {run(None)}/{len(L)}')
    print(f'  Wall+Box 阻塞          -> {run({"Boxs"})}/{len(L)}')
    print(f'  Wall+全部实体 阻塞      -> {run({"Boxs","Factorys","SubLevels","GridLocks","FreezingCars"})}/{len(L)}')
    oob = wall = ok = other = 0
    for l in L:
        d = cellmap(l); W, H = l['Grid']['Width'], l['Grid']['Height']
        for f in l['Factorys']:
            vx, vy = DIR_VEC[f.get('Dir') or 'Down']
            n = (f['CellX']+vx, f['CellY']+vy)
            if not (0 <= n[0] < W and 0 <= n[1] < H): oob += 1
            elif d.get(n) == 'Entities': wall += 1
            elif n not in d: ok += 1
            else: other += 1
    print(f'  工厂出口格: 青蛙源{ok} 其他实体{other} 越界{oob} 是墙{wall}')


def sec_factory(L):
    print('\n== 4. 工厂方向与位置 ==')
    F = [f for l in L for f in l['Factorys']]
    print('  Dir 分布:', Counter(f['Dir'] for f in F).most_common())
    for d in ('Down','Up','Left','Right'):
        sub = [f for f in F if f['Dir'] == d]
        if not sub: continue
        print(f'   {d:6s} n={len(sub):4d} CellX={Counter(f["CellX"] for f in sub).most_common(3)}'
              f' CellY峰={Counter(f["CellY"] for f in sub).most_common(2)}')
    print('  IncludeCarCount:', Counter(f['IncludeCarCount'] for f in F).most_common(8))
    print('  每关工厂数:', Counter(len(l['Factorys']) for l in L).most_common())


def sec_progression(L):
    print('\n== 5. 元素投放节奏 ==')
    els = ['Cars','Factorys','Boxs','SubLevels','GridLocks','GridKeys','FreezingCars','LockDoors']
    for e in els:
        f = [l['LV'] for l in L if l.get(e)]
        print(f'  {e:14s} 首次LV{f[0] if f else "-":>4} 共{len(f):3d}关 末LV{f[-1] if f else "-"}')
    print()
    print('  段        ' + ''.join(f'{e[:8]:>10s}' for e in els) + '   色数  总量  Hard')
    for s in range(0, len(L), 50):
        seg = L[s:s+50]
        row = f'  {s+1:3d}-{s+50:3d} '
        for e in els:
            row += f'{100*sum(1 for l in seg if l.get(e))/len(seg):9.0f}%'
        row += (f'  {st.mean([len(l["TotalCarColorTypes"]) for l in seg]):5.1f}'
                f' {st.mean([sum(l["TotalCarCounts"]) for l in seg]):5.1f}'
                f' {st.mean([l["HardType"] for l in seg]):5.2f}')
        print(row)


def sec_composition(L):
    print('\n== 6. 玩法区 56 格构成 ==')
    def comp(levels, label):
        acc = defaultdict(list)
        for l in levels:
            d = cellmap(l)
            play = [(x,y) for y in range(3,11) for x in range(7)]
            acc['Wall'].append(sum(1 for c in play if d.get(c)=='Entities'))
            acc['青蛙源'].append(sum(1 for c in play if c not in d))
            acc['Box'].append(sum(1 for c in play if d.get(c)=='Boxs'))
            acc['Factory'].append(sum(1 for c in play if d.get(c)=='Factorys'))
        print(f'  [{label}]')
        for k, v in acc.items():
            print(f'    {k:8s} 均{st.mean(v):5.1f} 中位{st.median(v):4.0f} 范围{min(v)}-{max(v)}')
    comp(L, f'全{len(L)}关')
    comp(L[-50:], f'最后50关')
    print('  Wall 占玩法区比例 按段:')
    for s in range(0, len(L), 50):
        seg = L[s:s+50]
        v = [sum(1 for c in [(x,y) for y in range(3,11) for x in range(7)]
                 if cellmap(l).get(c)=='Entities') for l in seg]
        print(f'    {s+1:3d}-{s+50:3d}: {st.mean(v):5.1f}/56 = {100*st.mean(v)/56:.0f}%')


def sec_misc(L):
    print('\n== 7. 杂项 ==')
    okp = tot = 0
    for l in L:
        if not l['GridLocks']: continue
        tot += 1
        if Counter(e['ColorType'] for e in l['GridLocks']) == Counter(e['ColorType'] for e in l['GridKeys']):
            okp += 1
    print(f'  GridLock/GridKey 逐色配平: {okp}/{tot}')
    print('  FreezingLayers:', Counter(e['FreezingLayers'] for l in L for e in l['FreezingCars']).most_common())
    print('  SubLevel Floor:', Counter(s['Floor'] for l in L for s in l['SubLevels']).most_common())
    print('  SubLevel 尺寸:', Counter((s['SubLevelSizeX'],s['SubLevelSizeY']) for l in L for s in l['SubLevels']).most_common(5))
    for k in ('Boxs','Factorys','SubLevels','FreezingCars'):
        v = Counter(e.get('ColorType') for l in L for e in l.get(k,[]) or [])
        print(f'  {k} ColorType:', v.most_common())
    print('  含 SpaceProbabilityConfigs 字段的关:', sum(1 for l in L if 'SpaceProbabilityConfigs' in l))


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'levels.json'
    L = json.load(open(path))['Levels']
    print(f'关卡数: {len(L)}\n')
    for fn in (sec_basic, sec_conservation, sec_connectivity,
               sec_factory, sec_progression, sec_composition, sec_misc):
        fn(L)
