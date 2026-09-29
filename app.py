"""Small Windows companion window for Codex account limits."""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path


APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CodexQuotaFloat"
POSITION_FILE = APP_DIR / "position.json"
BG = "#10151f"
CARD = "#1b2330"
TEXT = "#f5f7fb"
MUTED = "#94a3b8"
CYAN = "#55d6d1"
AMBER = "#f5bd65"
WIDTH, HEIGHT = 354, 340


def codex_window_open():
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    found = False

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        nonlocal found
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return True
        try:
            path = ctypes.create_unicode_buffer(1024)
            length = wintypes.DWORD(len(path))
            if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
                found = "OpenAI.Codex_" in path.value and path.value.lower().endswith("chatgpt.exe")
        finally:
            kernel32.CloseHandle(handle)
        return not found

    user32.EnumWindows(visit, 0)
    return found


def codex_executable():
    path = shutil.which("codex")
    if path:
        return path
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    matches = list(root.glob("*/codex.exe"))
    if not matches:
        raise RuntimeError("未找到 Codex CLI。请先启动一次 Codex 桌面版。")
    return str(max(matches, key=lambda item: item.stat().st_mtime))


def read_limits():
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [codex_executable(), "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        bufsize=1,
        creationflags=flags,
    )
    incoming = queue.Queue()

    def reader():
        for line in proc.stdout:
            try:
                incoming.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    threading.Thread(target=reader, daemon=True).start()

    def send(data):
        proc.stdin.write(json.dumps(data) + "\n")
        proc.stdin.flush()

    def response(request_id, deadline):
        while time.monotonic() < deadline:
            try:
                message = incoming.get(timeout=min(0.5, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                if proc.poll() is not None:
                    raise RuntimeError("Codex 数据服务已退出。")
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"].get("message", "读取用量失败"))
                return message.get("result") or {}
        raise TimeoutError("读取用量超时。")

    try:
        deadline = time.monotonic() + 25
        send({"method": "initialize", "id": 1, "params": {"clientInfo": {
            "name": "codex_quota_float", "title": "Codex 额度速览", "version": "1.0.0"}}})
        response(1, deadline)
        send({"method": "initialized", "params": {}})
        send({"method": "account/rateLimits/read", "id": 2})
        return response(2, deadline)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def extract_snapshot(result):
    buckets = result.get("rateLimitsByLimitId") or {}
    if not buckets and result.get("rateLimits"):
        buckets = {"codex": result["rateLimits"]}
    windows = [window for bucket in buckets.values() for window in
               (bucket.get("primary"), bucket.get("secondary")) if window]
    primary = next((w for w in windows if w.get("windowDurationMins") == 300), None)
    secondary = next((w for w in windows if w.get("windowDurationMins") == 10080), None)
    reset_credits = result.get("rateLimitResetCredits") or {}
    return primary, secondary, reset_credits.get("availableCount")


def remaining(window):
    if not window or window.get("usedPercent") is None:
        return None
    return max(0, min(100, 100 - float(window["usedPercent"])))


def countdown(window):
    if not window or window.get("resetsAt") is None:
        return "重置时间未知"
    seconds = max(0, int(window["resetsAt"] - time.time()))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}天 {hours}小时后重置"
    if hours:
        return f"{hours}小时 {minutes}分钟后重置"
    return f"{minutes}分钟后重置"


class QuotaFloat:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Codex 额度速览")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        self.root.geometry(self.load_position())
        self.root.withdraw()
        self.was_open = False
        self.dismissed = False
        self.refreshing = False
        self.last_refresh = 0
        self.snapshot = (None, None, None)
        self.messages = queue.Queue()
        self.drag_origin = None
        self.build()
        self.root.after(200, self.tick)

    def load_position(self):
        try:
            position = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
            x, y = int(position["x"]), int(position["y"])
        except (OSError, ValueError, KeyError):
            x, y = self.root.winfo_screenwidth() - WIDTH - 28, 70
        return f"{WIDTH}x{HEIGHT}+{max(0, x)}+{max(0, y)}"

    def save_position(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        POSITION_FILE.write_text(json.dumps({"x": self.root.winfo_x(), "y": self.root.winfo_y()}), encoding="utf-8")

    def label(self, parent, text, size=10, color=TEXT, weight="normal", **kwargs):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color,
                        font=("Microsoft YaHei UI", size, weight), **kwargs)

    def build(self):
        header = tk.Frame(self.root, bg=BG, height=46)
        header.pack(fill="x", padx=16, pady=(9, 2))
        header.pack_propagate(False)
        title = self.label(header, "◉  CODEX  额度速览", 12, TEXT, "bold")
        title.pack(side="left", pady=8)
        close = self.label(header, "×", 17, MUTED, cursor="hand2")
        close.pack(side="right", padx=(8, 0), pady=3)
        close.bind("<Button-1>", self.dismiss)
        for widget in (header, title):
            widget.bind("<ButtonPress-1>", self.drag_start)
            widget.bind("<B1-Motion>", self.drag_move)
            widget.bind("<ButtonRelease-1>", lambda _: self.save_position())

        self.cards = []
        for caption, color in (("5 小时额度", CYAN), ("一周额度", AMBER)):
            card = tk.Frame(self.root, bg=CARD, height=86)
            card.pack(fill="x", padx=14, pady=(0, 7))
            card.pack_propagate(False)
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=13, pady=(9, 0))
            self.label(row, caption, 10, MUTED).pack(side="left")
            percent = self.label(row, "--%", 17, color, "bold")
            percent.pack(side="right")
            bar = tk.Canvas(card, bg=CARD, highlightthickness=0, height=7)
            bar.pack(fill="x", padx=13, pady=(6, 0))
            detail = self.label(card, "等待读取", 9, MUTED, anchor="w")
            detail.pack(fill="x", padx=13, pady=(3, 0))
            self.cards.append((percent, bar, detail, color))
            bar.bind("<Configure>", lambda _, index=len(self.cards)-1: self.draw_bar(index))

        lower = tk.Frame(self.root, bg=CARD, height=42)
        lower.pack(fill="x", padx=14, pady=(0, 6))
        lower.pack_propagate(False)
        self.label(lower, "可用重置卡", 10, MUTED).pack(side="left", padx=13)
        self.credits = self.label(lower, "-- 次", 15, TEXT, "bold")
        self.credits.pack(side="right", padx=13)
        for widget in lower.winfo_children():
            widget.pack_configure(pady=7)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=16)
        self.status = self.label(footer, "打开 Codex 后读取额度", 8, MUTED, anchor="w")
        self.status.pack(side="left")
        refresh = self.label(footer, "↻ 刷新", 9, CYAN, cursor="hand2")
        refresh.pack(side="right")
        refresh.bind("<Button-1>", lambda _: self.refresh())
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="立即刷新", command=self.refresh)
        menu.add_command(label="退出悬浮窗", command=self.root.destroy)
        self.root.bind("<Button-3>", lambda event: menu.tk_popup(event.x_root, event.y_root))

    def drag_start(self, event):
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag_move(self, event):
        if self.drag_origin:
            self.root.geometry(f"+{event.x_root-self.drag_origin[0]}+{event.y_root-self.drag_origin[1]}")

    def dismiss(self, _):
        self.dismissed = True
        self.root.withdraw()

    def draw_bar(self, index):
        _, bar, _, color = self.cards[index]
        bar.delete("all")
        width = max(1, bar.winfo_width())
        bar.create_rectangle(0, 0, width, 7, fill="#344052", outline="")
        value = remaining(self.snapshot[index])
        if value is not None:
            bar.create_rectangle(0, 0, width * value / 100, 7, fill=color, outline="")

    def refresh(self):
        if self.refreshing or not self.was_open:
            return
        self.refreshing = True
        self.status.configure(text="正在读取额度…", fg=MUTED)

        def worker():
            try:
                self.messages.put((True, extract_snapshot(read_limits())))
            except Exception as exc:
                self.messages.put((False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def tick(self):
        is_open = codex_window_open()
        if is_open and not self.was_open:
            self.dismissed = False
            self.root.deiconify()
            self.root.lift()
        elif not is_open and self.was_open:
            self.root.withdraw()
        self.was_open = is_open
        if is_open and not self.dismissed and time.monotonic() - self.last_refresh >= 60:
            self.refresh()
        try:
            while True:
                success, value = self.messages.get_nowait()
                self.refreshing = False
                self.last_refresh = time.monotonic()
                if success:
                    self.snapshot = value
                    count = value[2]
                    self.credits.configure(text="-- 次" if count is None else f"{count} 次")
                    self.status.configure(text="更新于 " + datetime.now().strftime("%H:%M:%S"), fg=MUTED)
                else:
                    self.status.configure(text=str(value)[:39], fg=AMBER)
        except queue.Empty:
            pass
        for index, (percent, _, detail, _) in enumerate(self.cards):
            window = self.snapshot[index]
            value = remaining(window)
            percent.configure(text="--%" if value is None else f"{value:g}%")
            detail.configure(text=countdown(window))
            self.draw_bar(index)
        self.root.after(1000, self.tick)


def main():
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\CodexQuotaFloat")
    if ctypes.windll.kernel32.GetLastError() == 183:
        return
    try:
        QuotaFloat().root.mainloop()
    finally:
        ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
