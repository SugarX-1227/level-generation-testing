# ReCarMatch / Frog Match — 反编译还原分析（关卡生成评估用）

> 基于对 `AutoTest.app/Contents/Resources/Data/Managed/Assembly-CSharp.dll` 的反编译（ilspycmd 9.0）。
> 其中大量方法被混淆（`bxa`/`dpa` 等），本文采用「行为还原」而非逐行还原；关键语义用反编译确认 + 官方中文 `Header/Tooltip` 注释交叉验证。

---

## 1. 关卡数据结构（levels.json 权威 schema）

### `LevelData`（关卡文件每个条目）
```
LV, HardType(int),
Grid{Width, Height, CellSizeX, CellSizeY, CellSize},
Cars[], Entities[], Parks[], PayParks[], Emptys[], Factorys[],
Boxs[], LockDoors[], SubLevels[], GridLocks[], GridKeys[], FreezingCars[],
TotalCarColorTypes[], TotalCarCounts[],
AwardCoin, AwardItem1, AwardItem2, AwardItem3, AwardItem4,
SpaceProbabilityConfigs[], SpaceGuaranteeConfigs
```

### `GridEntityData`（每个格子元素，含 10 字段）
```
Type, CellX, CellY, ColorType, Dir, IncludeCarCount, Floor, SubLevelSizeX, SubLevelSizeY, FreezingLayers
```

### 枚举
- `GridEntityType`: `Empty, Wall, Car, Park, PayPark, Factory, Box, LockDoor, SubLevel, GridLock, GridKey, FreezingCar`
- `CarColorType`: `Red=0, Blue=1, Green=2, Yellow=3, Purple=4, Orange=5, Cyan=6, Pink=7, Brown=8, Black=9, White=999`（White=999 是"无颜色"默认值）
- `DirectionsType`: `Down, Up, Right, Left`
- `LevelHardType`: `Normal, Hard, VeryHard, SuperHard`（对应 HardType 0/1/2/3）

### 反序列化默认值（来自 `DummyLevelProvider.cr()/cs()`）
- `Type` 为空 → 默认 `Wall`
- `Grid.CellSize` 为 0 → 默认 64
- `ColorType` 为空 → 默认 `White`（不参与消除）
- `Dir` 为空 → 默认 `Down`

---

## 2. 玩法闭环（从控制器还原）

### 2.1 玩家操作：青蛙可移动性（`CarController.bqn` = A* 寻路）
- 棋盘坐标制：`Vector2Int(x, y)`，`x`=列，`y`=行，`y=0` 为底部荷叶区方向。
- 青蛙格子移动走**四方向**（Up/Down/Left/Right），用 **A\***（曼哈顿距离启发式 `bqo`）寻路。
- `bqq(a) = GridEntityManager.fd(a)`：目标格是否被占（`Blocking=true` 的实体挡路）。
- 关键：**青蛙到达 `y==2` 行（荷叶区上方第2行）或进入 PayPark 时，触发停车流程**（`bqk`，`dib.dg(...).y == 2`）。

### 2.2 停车位置算法（`ParkingSlotManager.btf` = 青蛙 → Park 槽）
- 槽位列 `dpi`（Park+Pays 位置列表），已停列 `dvb`。
- 若空 → 停 `slot[0]`；否则**从后往前**找最近一只**同色且未在消除**的青蛙，停到 `该同色位置+1`；无同色 → 停到队尾。
- 即：**同色青蛙优先紧贴放置**，从而自然累积成 3 连。
- `btg`（→ PayPark 槽 `dpj`）：一律追加到队尾。

### 2.3 消除判定（`CarEliminationManager.cgp` / `ParkingManager`)
- 对「已停稳」的青蛙序列，**收集任意 3 只同色**即触发消除。
  - `cgp`：遍历停靠列表，按颜色分组，某颜色数到 3 → 返回（**任意位置，不要求连续**）。
  - `bsf/bsh`：在序列中找**连续 3 只同色**（`dvc` 序列场景），也触发。
- 即：**无论"连续"还是"任意凑齐3只"，只要同类有 3 只就消**。两张判定并存，取其一即可。

### 2.4 胜利 / 判负（`ParkingManager.bsi` / `bsl`）—— 生成核心约束
- **胜利 `bsi`**：`GridEntityManager.dpp==0`（场上青蛙数=0）且 `dvb/dvc/dvd/dve` 全空，且 `ParkingQueueManager.btb()==0`（队列空）→ 所有青蛙消光。
- **判负 `bsl`**：`dvc.Count >= dpi.Count`（**荷叶序列占满**）且 `!bsg()`（**当前无三消可触发**）→ 败。
- 这正是策划说的「荷叶不能全部占满否则判负」。

---

## 3. 游戏内置生成器的实现方式（`DummyLevelProvider` + `RandomCarManager`）

### 3.1 概率配置的两个关键词（官方中文 Tooltip 原文）
`LevelConfig` 里这两个字段的注释，**直接定义了生成算法的调控入口**：
- `SpaceProbabilityConfigs`（配置项A）：**保底调控概率配置（按剩余车位配置，1-7）**
- `SpaceGuaranteeConfigs`（配置项B）：**必定保底次数配置**

### 3.2 `Space` = 剩余空车位数量（`RandomCarManager.ow()`）
```
ow() = dpi.Count(总槽位) - dvb(已停) - dve(移动中) - 队列数，取 max(0,...)
```
`Space` 范围 **1~7**。当 `ow() <= 3`（`ov()`）时，剩余空间紧张，颜色选择格外谨慎（防判负）。

### 3.3 刷青蛙颜色算法（`RandomCarManager.om()`）—— 生成器可直接复刻
工厂刷青蛙选颜色的入口 `om()`，优先级：
1. **`on()`**：查**保底配置**（`cea` = SpaceGuaranteeConfig）。若该 `Space` 的保底额度 >0，则用 `op()` 选色并扣额度 1。→ 保证某颜色达到目标数量。
2. **`oo()`**：查**概率配置**（`cdz` = SpaceProbabilityConfig）。`Random(0,100) < probability` 命中 → 用 `op()` 选色。
3. **`os()`**：都失败 → 从**剩余颜色配额 `ced`**（= `TotalCarCounts`/`TotalCarColorTypes` 减去已生成/已停）里随机抽一个。

### 3.4 `op()` = 防堵死 / 促消除的核心规则
- 取「当前已停荷花上的颜色计数」`oq()` 从多到少排序；
- **优先选「已有 ≥2 只且还有配额」的颜色**（凑齐 3 只就能消）；
- 若无，则选「已停 + 队列中合计 ≥2」的颜色；
- 目的：**始终朝"生成 3 只同色"倾斜，避免占满却消不掉**。

### 3.5 `ox()` = 是否存在潜在三消
- 检测「网格上未消的青蛙 + 已停青蛙」里是否有**连续 3 同色**；有 → `RestrictNoMatch` 相关逻辑生效。

---

## 4. 对「关卡生成」的直接结论

1. **"可玩/可解" = 能找到一个青蛙操作序列，让所有青蛙最终被消除（`bsi`=true），且全程不触发判负（`bsl`）。** 这是**可解性/状态空间问题**，不是"把青蛙摆好看"。
2. **生成引擎的最优做法是复刻 `RandomCarManager.om()` 的选色逻辑**：给定 `TotalCarColorTypes`/`TotalCarCounts` 后，游戏自己就能刷出"优先凑3连、防占满"的青蛙序列。生成器无需凭空发明颜色分配，只需设好这两个字段 + 概率/保底配置。
3. **棋盘布局（Space 1~7 → 元素类型）**与 `SpaceProbabilityConfig`/`SpaceGuaranteeConfig` 绑定，可离线用"剩余空位数"做约束生成。
4. **AutoTest 就是现成的可解性 oracle**：输入 `startLv~endLv` + `count`，逐关输出 `level:x round:1/1`、`是否胜利`、`结束剩余CarEntity数量`、`操作次数`，汇总 TSV 复制到剪贴板。
   - 缺点：结果只打在应用内 / 剪贴板，**不直接落盘**（需解决抓取，见方案）。

---

## 5. Windows 版（_OUT_AUTOTEST）额外发现 —— 关键

### 5.1 两个版本对比
- Mac 版（`AutoTest.app`）与 Windows 版（`_OUT_AUTOTEST/Frog Match.exe`）的程序集 **MD5 不同**（Mac `cb47...` / Win `89c1...`），是不同构建；但 `Levels`/`Grid`/`RandomCar` 等类型结构一致。
- Windows 版打包的**关卡数据 `resources.assets` 里内嵌的 500 关 JSON，与桌面 `levels.json` 完全一致**（`IDENTICAL: True`）。

### 5.2 从 `resources.assets` 提取出的「概率配置」`levels_probability`（权威数据）
这是一个 **CSV**（Unity TextAsset），**独立于关卡 JSON**。桌面 `levels.json` **不含** `SpaceProbabilityConfigs/Guarantee` 字段，这些字段的值**全部来自这个 CSV**。

CSV 列结构（含官方中文表头「剩余空格N的概率 / 是否防匹配」）：
```
id, Space7_概率, Space7_防匹配, Space6_概率, Space6_防匹配, ..., Space1_概率, Space1_防匹配, 保底空间, 保底防匹配, 保底次数
```
**实际数据：**
- 共 **48 关**配备了概率（id 1~48），关卡 49~500 无（default）。
- **默认表（46 关）**：`Space7=0, Space6=0.1, Space5=0.3, Space4=0.3, Space3=0.4, Space2=0.5, Space1=0.5`，全部 `RestrictNoMatch=true`。
- **id=43 特殊**：`Space1=0.6`，且配置保底 `Guarantee_Space=3, RestrictNoMatch=false, Count=2`。

### 5.3 ⭐ 澄清「Space→元素映射」的根本误解
- **`Space`(1~7) 不是"格子→元素类型"的映射**；它是**剩余空车位数的动态值**（`RandomCarManager.ow() = 总槽位 - 已停 - 移动中 - 队列`）。
- **`SpaceProbabilityConfig`/`SpaceGuaranteeConfig` 完全用于调控"刷青蛙颜色"的概率**（防止荷花占满却无法三消 → 判负），**与"格子放什么元素"无关**。
- **"格子放什么元素（Wall/Box/Factory/Empty/SubLevel...）由关卡 JSON 的布局数组直接写死**（`Entities`/`Boxs`/`Factorys` 等），不靠 `Space` 动态生成。

### 5.4 关卡编号映射（`ConfigManager.dqv`）
- 维护 `LevelOrderData`：`game_level_id → json_level_id`（`ma()`），**显示关卡号 ≠ JSON 的 `LV`**，两套编号通过 `level_order` 配置关联。CSV 的 `id` 用 `game_level_id`。

---

## 6. 生成器的真正挑战（据 Windows 版证据修正）
生成器要解决的不是"分配格子元素类型"（那已由 JSON 布局决定），而是：
1. **定布局**：哪些格子是 `Wall/Empty/Frog/Factory/Box/SubLevel/GridLock/GridKey/FreezingCar`，及各自坐标。
2. **定青蛙配比**：`TotalCarColorTypes` + `TotalCarCounts`（每种色数量应为 3 的倍数 → 可全消）。
3. **定刷车路径**：Factory 的 `Dir` 决定青蛙入场方向；`IncludeCarCount` 决定总量。
4. **保证可解性**：依赖 `levels_probability` 的 Space 概率 + 保底配置驱动 `RandomCarManager` 自动凑三连防占满；生成器可用离线模拟复刻此规则，验证"能否全消 + 是否判负"。

## 7. 待确认 / 需补的信息
- `SubLevel` 的布局规则（`Floor>0`、`SubLevelSizeX/Y` 判定）。
- `GridLock/GridKey`、`LockDoor`、`FreezingCar` 的触发细节（均已发现 `Controller`，但交互细节可后续补）。
- AutoTest 结果如何自动化抓取（日志重定向 / 剪贴板 / 需人工截图）。
