## 2026-08-20 - Task: 解除 LevelJsonEditor 的飞书下载隔离并验证启动
### What was done
- 递归移除 `LevelJsonEditor.app` 的 `com.apple.quarantine` 扩展属性，保留其他系统属性。
- 启动应用并确认程序进程正常运行。
### Testing
- `xattr -l LevelJsonEditor.app` 仅显示 `com.apple.provenance`，不再包含 `com.apple.quarantine`。
- 递归检查应用包，未发现残留的 `com.apple.quarantine`。
- `open -n LevelJsonEditor.app` 成功，`level-json-editor` 进程持续运行。
### Notes
- `LevelJsonEditor.app`：仅移除应用包及其内容的飞书下载隔离元数据，未修改程序内容。
- `progress.md`：新增本次处理与验证记录。
- 回滚：执行 `xattr -w com.apple.quarantine '0087;6a869b69;Feishu;' LevelJsonEditor.app` 可在应用包根目录恢复原隔离标记；原始交付点为 `LevelJsonEditor-macOS-arm64-debug.zip`。

## 2026-08-20 - Task: 解除 AutoTest 的飞书下载隔离并验证启动
### What was done
- 递归移除 `AutoTest.app` 的 `com.apple.quarantine` 扩展属性，保留其他系统属性。
- 启动应用并确认 Unity 主进程正常运行。
### Testing
- `xattr -l AutoTest.app` 仅显示 `com.apple.provenance`，不再包含 `com.apple.quarantine`。
- 递归检查应用包，未发现残留的 `com.apple.quarantine`。
- `open -n AutoTest.app` 成功，`Frog Match` 主进程持续运行，最近系统日志无启动错误。
### Notes
- `AutoTest.app`：仅移除应用包及其内容的飞书下载隔离元数据，未修改程序内容。
- `progress.md`：追加本次处理与验证记录。
- 回滚：执行 `xattr -w com.apple.quarantine '0087;6a870d0a;Feishu;' AutoTest.app` 可在应用包根目录恢复原隔离标记；原始交付点为 `AutoTest.zip`。

## 2026-08-22 - Task: 处理替换后的 AutoTest 飞书隔离并验证启动
### What was done
- 递归移除替换后 `AutoTest.app` 的 `com.apple.quarantine` 扩展属性，保留其他系统属性。
- 启动新版应用并确认 Unity 主进程正常运行。
### Testing
- `xattr -l AutoTest.app` 仅显示 `com.apple.provenance`，不再包含 `com.apple.quarantine`。
- 递归检查应用包，未发现残留的 `com.apple.quarantine`。
- `open -n AutoTest.app` 成功，`Frog Match` 主进程持续运行，最近系统日志无启动错误。
### Notes
- `AutoTest.app`：仅移除应用包及其内容的飞书下载隔离元数据，未修改程序内容。
- `progress.md`：追加新版 AutoTest 的处理与验证记录。
- 回滚：执行 `xattr -w com.apple.quarantine '0087;6a891731;Feishu;' AutoTest.app` 可在应用包根目录恢复本次隔离标记；原始交付点为当前 `AutoTest.zip`。

## 2026-08-22 - Task: 处理新替换的 AutoTest 飞书隔离并验证启动
### What was done
- 递归移除当前 `AutoTest.app` 的 `com.apple.quarantine` 扩展属性，保留其他系统属性。
- 启动当前版本并确认 Unity 主进程正常运行。
### Testing
- `xattr -l AutoTest.app` 仅显示 `com.apple.provenance`，不再包含 `com.apple.quarantine`。
- 递归检查应用包，未发现残留的 `com.apple.quarantine`。
- `open -n AutoTest.app` 成功，`Frog Match` 主进程持续运行，最近系统日志无启动错误。
### Notes
- `AutoTest.app`：仅移除应用包及其内容的飞书下载隔离元数据，未修改程序内容。
- `progress.md`：追加本次新版 AutoTest 的处理与验证记录。
- 回滚：执行 `xattr -w com.apple.quarantine '0087;6a893aff;Feishu;' AutoTest.app` 可在应用包根目录恢复本次隔离标记；原始交付点为当前 `AutoTest.zip`。

## 2026-08-25 - Task: 将项目源码与资料上传至私有 GitHub 仓库
### What was done
- 为项目建立 Git 版本管理和私有 GitHub 仓库。
- 按要求只纳入生成器源码、关卡数据、文档和截图，排除 Mac/Windows 软件包、本地反编译工具和视频。
### Testing
- 上传前检查 Git 跟踪清单，确认未包含 `AutoTest`、`LevelJsonEditor`、`_OUT_AUTOTEST` 和 `_tools`。
- 检查纳入文件的单文件大小和常见密钥特征，确认可推送。
- 推送后通过 GitHub CLI 确认仓库可见性为 `PRIVATE` 且本地分支已跟踪远端。
### Notes
- `.gitignore`：新增本地缓存、软件交付包、反编译工具和视频的排除规则。
- `progress.md`：追加本次 GitHub 上传范围、验证与回滚点。
- 回滚：在 GitHub 删除 `SugarX-1227/level-generation-testing` 私有仓库，并在本地删除 `.git` 和 `.gitignore`；已提交内容也可以首次提交作为回滚点。

## 2026-08-24 - Task: ReCarMatch 关卡生成器四步深化（识图+反编译+生成器）
### 背景
用户目标：第一阶段生成「可玩的基础关卡」，期望程序辅助批量产出。依据关卡制作文档 + 已有的 500 关 + AutoTest 测试工具。

### What was done（四步）
1. **识图还原**：会话支持图像输入后，直接读取 AutoTest 截图 + 游戏画面关键帧，确认玩法（青蛙跳荷叶三消，7x11 棋盘，底部 7 Park + 7 PayPark 荷叶区）。
2. **反编译还原游戏规则**（Mac/Windows 版 `Assembly-CSharp.dll`，ilspycmd）：
   - 完整关卡 schema（`LevelData`/`GridEntityData` 及 10 字段）；枚举 `GridEntityType`/`CarColorType`(`White=999`)/`DirectionsType`/`LevelHardType`。
   - 玩法闭环：青蛙 A* 寻路到 `entry_row=2` → `ParkingSlotManager.btf` 落位（优先紧贴同色）→ `CarEliminationManager` 任意3同色消除 → `bsl` 判负（荷花占满且无3连）→ `bsi` 胜利（全消）。
   - 澄清误解：`Space(1~7)` 是剩余空车位数，用于调控刷蛙颜色概率，**不是**格子→元素映射；格子元素由关卡 JSON 布局数组直接写死。
3. **Windows 版深度挖掘**：`_OUT_AUTOTEST` 的 `resources.assets` 提取出**完整关卡 JSON（与桌面500关一致）+ `levels_probability` 概率 CSV**（默认表 Space7=0/6=0.1/5=0.3/4=0.3/3=0.4/2=0.5/1=0.5，id=43 特殊含保底 Space=3 Count=2）。
4. **生成器实现**：`generator/` 目录。`autotest_sim.py`(复刻AutoTest走棋, 与真实GameLog对齐: LV1/2步数9/9一致)，`generator2.py`(槽式生成, 自动校验可解, 支持难度档位)，`difficulty.py`(4档难度)，`random_car.py`(复刻RandomCarManager颜色分配)。

### 关键突破（第2步实跑链路）
- 反编译确认 AutoTest 读外部 `persistentDataPath/levels.json`（`File.Exists(cvf)` 优先），概率 CSV `levels_probability.csv`。
- 通过 C# 反射求值出文件名：`a.bld()="levels.json"`，`a.blf()="levels_probability.csv"`（persistentDataPath = `~/Library/Application Support/com.DefaultCompany.Frog-Match/`）。
- AutoTest 结果写入 `GameLog.txt`（`File.AppendAllText`），可用 `run_validate.py` 脚本化抓取。

### Testing
- 判别力对照测试：可解/不可解正确区分（每种3只→可解；绿2只/红5只→不可解）。
- 生成器独立复核：多批关卡在模拟器下全部可解，颜色/总量/字段校验通过。
- 难度梯度各档位:极简(3色9只)/普通(4-6色12-18)/困难(6-7色18-21,H=1)/超难(7-8色21-24,H=3)，全部可解无截断。
- 生成的 `levels.json` 已写入 `persistentDataPath`；与真实 500 关结构/类型完全一致。

### Notes
- **AutoTest 实跑闭环已完全打通**：用户授权「辅助功能」+「屏幕录制」给 Terminal 后，用 `drive_autotest.py`（CGEvent + pbcopy 坐标点击 Unity 界面）一键完成：激活窗口→填开始/结束/次数→点「自动测试关卡」→读 `GameLog.txt`。
- **真实验证结果**：AutoTest 判定生成的关卡（LV1-15）**全部胜利**（剩余0，9-12步内），与模拟器预测步数一致。
- **⚠️ 关键机制（解决"LV11-15 读取关卡失败"的根因）**：`DummyLevelProvider.uc()` 有 `if (fjc) return;`——关卡数据只在 AutoTest 进程启动后**首次加载一次**（`fiz` 缓存）。首次测试时文件是 10 关，缓存了 10 关；之后改成 15 关但缓存未更新，LV11-15 报"读取关卡失败"。**每次改 `levels.json` 后必须重启 AutoTest，新关卡才会被读入。** 重启后全部 15 关通过。
- 预期流程对齐：①程序生成基础关→②人工微调→③调试参数入库。当前已完成①（生成器+可解性自校验）且**经 AutoTest 真实验证 LV1-15 全胜**。
- 反编译分析全文见 `反编译分析_ReCarMatch玩法与生成器.md`；用法见 `generator/README.md`。
