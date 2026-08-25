# ReCarMatch 关卡生成器（四步深化）

基于对 AutoTest（Mac/Windows 版）程序集反编译还原的游戏规则，完成四步深化。
**核心目标：生成"策划认可可玩"的关卡，可解性判定与真实 AutoTest 对齐。**

## 四步成果
1. **复刻 AutoTest 走棋策略 → 可解性模拟器**（`autotest_sim.py`）
   - 经反编译还原 `UIGameLevelAutoTestTool.AutoTestCarSelector.dft` 的加权优先级走棋 + `ehl` 落位 + `enf` 消除 + `bsl/bsi` 判定。
   - 与真实 AutoTest 的 `GameLog.txt` 结果**对齐校准**（LV1/2 步数 9/9 完全一致）。
   - 判别力经对照测试验证（可解/不可解正确区分）。
2. **对接 AutoTest 实跑验证闭环**（`run_validate.py`）
   - 反编译确认 AutoTest **读外部** `persistentDataPath/levels.json`（`File.Exists(cvf)` 优先），概率 CSV 同理（`levels_probability.csv`）。
   - 反射求值出文件名 `a.bld()="levels.json"` / `a.blf()="levels_probability.csv"`。
   - 结果写入 `GameLog.txt`（`File.AppendAllText`），脚本化抓取。
   - ⚠️ 触发"自动测试"需 macOS 辅助功能权限（GUI 点击），无法自助；其余全自动。
3. **扩展进阶元素基础**（`random_car.py`）
   - 复刻 `RandomCarManager.om()` 颜色分配算法（保底→概率→剩余随机，`op()` 优先凑3连防堵死）。
   - Factory/Box 刷青蛙的运行时随机颜色建模基础。
4. **难度梯度**（`difficulty.py` + `generator2.py` 参数化）
   - 从真实 500 关 HardType 统计提取参数：极简(3色)/普通(4-6色)/困难(6-7色 HardType=1)/超难(7-8色 HardType=3)。
   - 生成器按档位控制颜色数/总量/槽尺寸/`HardType`。

## 文件
- `rules.py`          —— 数据模型 + 常量（GridConfig/GridEntityType/CarColorType）
- `solver.py`         —— 可解性模拟器（DFS带回溯，复刻 btf/cgp/bsl/bsi）
- `autotest_sim.py`   —— **AutoTest 风格模拟器（默认判定器）**，与真实测试对齐，不污染棋盘
- `random_car.py`     —— `RandomCarManager` 颜色分配算法复刻（第3步）
- `difficulty.py`     —— 难度梯度档位定义（第4步）
- `generator2.py`     —— 槽式关卡生成器（主产），生成→校验→输出，支持难度档位
- `generator.py`      —— 早期散点版（保留参考）
- `run_validate.py`   —— AutoTest 实跑验证脚本（写 levels.json + 读 GameLog.tsv）
- `test_control.py`   —— 判别力对照测试
- `test_real.py`      —— 真实关卡验证 / 构建棋盘
- `generated_levels.json` —— 生成的示例关卡

## 玩法规则（反编译还原）
- 棋盘 7x11；y=0 PayPark / y=1 Park（荷花区，7+7 格），entry_row=2 触发落位。
- 青蛙 A* 寻路 → `btf` 落位（优先紧贴同色）→ `enf/cgp` 任意3同色消除 → `bsl` 判负（占满且无3连）→ `bsi` 胜利（全消）。
- 静态青蛙每种颜色数量须为 3 的倍数。

## 用法
```bash
# 生成 20 关（默认难度）
python3 generator2.py 20 20260822
# 生成指定难度档位（1极简/2普通/3困难/4超难）
python3 -c "import sys,os;sys.path.insert(0,'.');from generator2 import generate;import json;json.dump(generate(20,seed=1,difficulty=3),open('generated_levels.json','w'),indent=2,ensure_ascii=False)"
# 判别力对照 / 真实关卡验证
python3 test_control.py
python3 test_real.py ../levels.json 1,2,4
# AutoTest 实跑：写关卡到 persistentDataPath + 读结果
python3 run_validate.py generator/generated_levels.json
```

## AutoTest 实跑验证闭环（第2步，已跑通）
前置：授权「辅助功能」+「屏幕录制」给 Terminal（运行 Harness 的宿主 App）。
```bash
# 一键：激活 AutoTest -> 填 开始/结束/次数 -> 点「自动测试关卡」-> 读 GameLog.txt 结果
# 参数: <start> <end>
python3 drive_autotest.py 1 20
```
**已验证结果**：AutoTest 真实判定生成的关卡（LV1-15）**全部胜利**（剩余0、9-12步内），与模拟器预测一致。

**⚠️ 重要机制（易踩坑）**：`DummyLevelProvider.uc()` 里 `if (fjc) return;`——**关卡数据只在 AutoTest 进程启动后首次加载一次**（`fiz` 字典缓存）。所以**每次改动 `levels.json` 后必须重启 AutoTest**，新关卡才会被读到（否则新加的关(如 LV11+)会报"读取关卡失败"）。
**正确批量工作流**：先把整批关卡写好 → 重启 AutoTest → 一次测完整批。

## 限制与下一步
- 本版生成**静态青蛙**关（可解性精确保证），覆盖游戏里最小但最可控的子集；AutoTest 实跑 LV1-15 全胜验证。
- Factory/Box 关（92% 真实关）依赖运行时随机刷色，可解性靠游戏内置保底——本版仅提供 `random_car.py` 的建模基础。
- 改关卡文件后**必须重启 AutoTest** 才生效（`uc()` 单次加载缓存）。
- AutoTest 实跑需**辅助功能 + 屏幕录制**权限（已演示如何授权）。
