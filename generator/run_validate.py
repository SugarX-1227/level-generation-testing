# -*- coding: utf-8 -*-
"""
AutoTest 实跑验证脚本 —— 第2步闭环工具
=========================================
机制（反编译确认，Windows 版 Assembly-CSharp.dll）：
- AutoTest 读关卡的**外部文件**：`Application.persistentDataPath/levels.json`（file 存在时优先，否则用内嵌资源）。
  源码：`bxk.StaticResources.bgz()` —— `if (File.Exists(ResourceDefine.cvf)) deo = ResourceManager.ber(cvf); else deo = ResourceManager.bek(cve);`
  其中 `ResourceDefine.cvf = Path.Combine(persistentDataPath, a.bld())`，反射求值 `a.bld() = "levels.json"`。
- 概率配置同理：`levels_probability.csv`（`a.blf()`）。
- 运行结果写入 `persistentDataPath/GameLog.txt`（`ReCarMatch.Framework.Log.GameLog`，`File.AppendAllText`）。

本脚本：
  run_validate.py <生成的 levels.json 路径> [startLv] [endLv]
  —— 拷贝关卡到 persistentDataPath，并解析 GameLog.txt 里的结果。

依赖 GUI 手动触发：AutoTest 需要在界面输入"开始关卡id/结束关卡id/次数"并点"自动测试关卡"。
（macOS 上若能授予辅助功能权限，可进一步用 cliclick/osascript 自动点击；否则需人工点一次。）
"""
import json
import os
import re
import sys
import shutil
from pathlib import Path

# AutoTest persistentDataPath (macOS)
PERSIST = Path.home() / "Library" / "Application Support" / "com.DefaultCompany.Frog-Match"
LEVEL_FILE = "levels.json"
PROB_FILE = "levels_probability.csv"
GAMELOG = "GameLog.txt"


def install_levels(src_path: str) -> Path:
    """拷贝生成的 levels.json 到 AutoTest persistentDataPath。"""
    PERSIST.mkdir(parents=True, exist_ok=True)
    dst = PERSIST / LEVEL_FILE
    shutil.copyfile(src_path, dst)
    print(f"[install] 已写入 {dst} ({dst.stat().st_size} bytes)")
    return dst


def parse_gamelog(txt: str):
    """从 GameLog.txt 解析单关结果 + 汇总。"""
    results = []
    for m in re.finditer(
        r"关卡id:(\d+)\s+是否胜利:(\w+)\s+结束剩余CarEntity数量:(\d+)\s+操作次数:(\d+)", txt
    ):
        results.append({
            "level": int(m.group(1)),
            "win": m.group(2) == "True",
            "remaining": int(m.group(3)),
            "moves": int(m.group(4)),
        })
    return results


def read_results() -> list:
    p = PERSIST / GAMELOG
    if not p.exists():
        print("[read] GameLog.txt 不存在")
        return []
    txt = p.read_text(encoding="utf-8", errors="replace")
    return parse_gamelog(txt)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 run_validate.py <levels.json> [startLv endLv]")
        sys.exit(1)
    src = sys.argv[1]
    install_levels(src)
    print(f"[read] 当前持久目录: {PERSIST}")
    print("[hint] 请在 AutoTest 界面输入 关卡范围 并点『自动测试关卡』，然后再次运行本脚本查看结果。")
    # 展示已有结果
    res = read_results()
    if res:
        print("\n[结果] GameLog.txt 已解析：")
        for r in res:
            print(f"  关卡id:{r['level']} 胜利:{r['win']} 剩余:{r['remaining']} 步数:{r['moves']}")
    else:
        print("[结果] GameLog.txt 暂无自动测试结果")


if __name__ == "__main__":
    main()
