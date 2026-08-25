# -*- coding: utf-8 -*-
"""
GUI 驱动 AutoTest 跑真实闭环（第2步·实跑）
==========================================
前提：已授权 辅助功能 + 屏幕录制。
原理：AutoTest 是 Unity 应用，内部 InputField/Button 不是 macOS AX 控件，
      无法用 System Events 遍历；改用它自带的「局外自动测试」界面坐标点击。
策略：
  1) 激活 + 前置 AutoTest 窗口（CGWindowList 拿到 onscreen 窗口 bounds）。
  2) 用屏幕录制截图（视觉定位）或已知比例坐标，定位 3 个输入框 + 按钮。
  3) 用 CGEvent 点击输入框 -> 键盘输入 关卡范围 -> 点击「自动测试关卡」。
  4) 读 persistentDataPath/GameLog.txt 解析结果。
"""
import os
import re
import subprocess
import json
import time
from pathlib import Path

PERSIST = Path.home() / "Library" / "Application Support" / "com.DefaultCompany.Frog-Match"
GAMELOG = PERSIST / "GameLog.txt"


def run_swift(src: str) -> str:
    """写临时 swift 并运行，返回 stdout。"""
    p = Path("/tmp") / f"_dsh_{abs(hash(src))}.swift"
    p.write_text(src)
    r = subprocess.run(["swift", str(p)], capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def get_window_bounds() -> tuple:
    """返回 (x, y, w, h) 的主窗口 bounds，找不到返回 None。含 optionAll 兜底 + 重试。"""
    swift = '''
import CoreGraphics
import Foundation
for opt in [CGWindowListOption.optionOnScreenOnly, CGWindowListOption.optionAll] {
  let list = CGWindowListCopyWindowInfo(opt, kCGNullWindowID) as! [[String:Any]]
  for w in list {
    if let owner = w[kCGWindowOwnerName as String] as? String, owner == "Frog Match",
       let name = w[kCGWindowName as String] as? String, name == "Frog Match" {
      let alpha = w[kCGWindowAlpha as String] as? Double ?? 0
      if alpha > 0.5 {
        let b = w[kCGWindowBounds as String] as? [String:Any] ?? [:]
        print("\\(b["X"] ?? 0) \\(b["Y"] ?? 0) \\(b["Width"] ?? 0) \\(b["Height"] ?? 0)")
        exit(0)
      }
    }
  }
}
'''
    for _ in range(3):
        out = run_swift(swift)
        if out:
            parts = out.split()
            if len(parts) >= 4:
                try:
                    return tuple(int(x) for x in parts[:4])
                except ValueError:
                    pass
        time.sleep(0.5)
    return None


def activate():
    subprocess.run(["osascript", "-e", 'tell application "Frog Match" to activate'],
                   capture_output=True, timeout=15)


def click(x, y):
    """用 CGEvent 点击屏幕坐标。"""
    swift = f'''
import CoreGraphics
import Foundation
let p = CGPoint(x: {x}, y: {y})
let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left)
move?.post(tap: .cghidEventTap)
usleep(60000)
let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: p, mouseButton: .left)
down?.post(tap: .cghidEventTap)
usleep(60000)
let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: p, mouseButton: .left)
up?.post(tap: .cghidEventTap)
print("clicked")
'''
    run_swift(swift)


def type_text(text: str):
    """用 CGEvent 键盘输入文本（需已聚焦输入框）。"""
    # 用 pbcopy + Cmd+V 粘贴最可靠
    subprocess.run(["pbcopy"], input=text.encode(), capture_output=True)
    # Cmd+V
    swift = '''
import CoreGraphics
import Foundation
let src = CGEventSource(stateID: .hidSystemState)
let cmd = CGKeyCode(55) // Command
let v = CGKeyCode(9)   // V
let down = CGEvent(keyboardEventSource: src, virtualKey: v, keyDown: true)
down?.flags = .maskCommand
down?.post(tap: .cghidEventTap)
usleep(60000)
let up = CGEvent(keyboardEventSource: src, virtualKey: v, keyDown: false)
up?.flags = .maskCommand
up?.post(tap: .cghidEventTap)
print("typed")
'''
    run_swift(swift)


def read_results():
    if not GAMELOG.exists():
        return []
    txt = GAMELOG.read_text(encoding="utf-8", errors="replace")
    results = []
    for m in re.finditer(
        r"关卡id:(\d+)\s+是否胜利:(\w+)\s+结束剩余CarEntity数量:(\d+)\s+操作次数:(\d+)", txt
    ):
        results.append({"level": int(m.group(1)), "win": m.group(2) == "True",
                        "remaining": int(m.group(3)), "moves": int(m.group(4))})
    return results


def main():
    import sys
    start = sys.argv[1] if len(sys.argv) > 1 else "1"
    end = sys.argv[2] if len(sys.argv) > 2 else "10"
    count = sys.argv[3] if len(sys.argv) > 3 else "1"
    activate()
    time.sleep(1.5)
    bounds = get_window_bounds()
    print("窗口 bounds:", bounds)
    if not bounds:
        print("未找到 AutoTest 主窗口")
        return
    x, y, w, h = bounds
    # CGWindowList 报告的 X 在 Unity 重启后有时漂移(如 1429)，但窗口实际固定在屏幕左上。
    # 强制用已知的窗口原点(0,33) + 尺寸(1470,923)，避免坐标错位。
    x, y, w, h = 0, 33, 1470, 923
    # 精确坐标(由窗口截图视觉定位 + 折算到屏幕坐标): 窗口在(0,33,1470,923)
    # 输入框行屏幕y ≈ 872; 开始框≈410, 结束框≈631, 次数框≈863, 按钮≈1176
    fy = y + h * 0.909   # 872 (输入框行)
    box1 = (x + w * 0.279, fy)
    box2 = (x + w * 0.429, fy)
    box3 = (x + w * 0.587, fy)
    btn = (x + w * 0.800, fy)
    print(f"坐标: box1={box1} box2={box2} box3={box3} btn={btn}")
    # 依次点击填入（每框先 pbcopy 对应值 → Ctrl+A → Cmd+V）
    for name, pos, val in [("开始", box1, start), ("结束", box2, end), ("次数", box3, count)]:
        click(*pos)
        time.sleep(0.3)
        # pbcopy 该框的值
        subprocess.run(["pbcopy"], input=val.encode(), capture_output=True)
        # Ctrl+A 全选
        run_swift('''
import CoreGraphics
import Foundation
let src = CGEventSource(stateID: .hidSystemState)
let a = CGKeyCode(0)
let down = CGEvent(keyboardEventSource: src, virtualKey: a, keyDown: true)
down?.flags = .maskCommand
down?.post(tap: .cghidEventTap)
usleep(50000)
let up = CGEvent(keyboardEventSource: src, virtualKey: a, keyDown: false)
up?.flags = .maskCommand
up?.post(tap: .cghidEventTap)
''')
        # Cmd+V 粘贴
        run_swift('''
import CoreGraphics
import Foundation
let src = CGEventSource(stateID: .hidSystemState)
let v = CGKeyCode(9)
let down = CGEvent(keyboardEventSource: src, virtualKey: v, keyDown: true)
down?.flags = .maskCommand
down?.post(tap: .cghidEventTap)
usleep(50000)
let up = CGEvent(keyboardEventSource: src, virtualKey: v, keyDown: false)
up?.flags = .maskCommand
up?.post(tap: .cghidEventTap)
''')
        time.sleep(0.2)
    click(*btn)
    print("已点击自动测试，等待结果...")
    time.sleep(18)
    res = read_results()
    print("结果:", json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
