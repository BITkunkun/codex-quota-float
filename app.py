"""A two-line Codex quota indicator that follows the desktop pet."""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path

import uiautomation as auto


BG = "#111924"
BORDER = "#344252"
TRACK = "#3c4a5a"
TEXT = "#eaf2f7"
CYAN = "#5de1da"
AMBER = "#ffc874"
KEY = "#010203"
WIDTH, HEIGHT = 236, 72
REFRESH_SECONDS = 60
user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]


def pet_window_handles():
    """Find the transparent Codex pet host, excluding the main app window."""
    handles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or not user32.GetWindowLongPtrW(hwnd, -20) & 0x20:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel32.OpenProcess(0x1000, False, pid.value)
        if not process:
            return True
        try:
            path = ctypes.create_unicode_buffer(1024)
            length = wintypes.DWORD(len(path))
            if kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                if "OpenAI.Codex_" in path.value and path.value.lower().endswith("chatgpt.exe"):
                    handles.append(hwnd)
        finally:
            kernel32.CloseHandle(process)
        return True

    user32.EnumWindows(visit, 0)
    return handles


def find_pet():
    for hwnd in pet_window_handles():
        try:
            root = auto.ControlFromHandle(hwnd)
            images = []
            for control, _ in auto.WalkControl(root, maxDepth=40):
                if control.ControlTypeName == "ImageControl":
                    rect = control.BoundingRectangle
                    width, height = rect.right - rect.left, rect.bottom - rect.top
                    if width >= 60 and height >= 60 and not control.IsOffscreen:
                        images.append((width * height, control))
            if images:
                return hwnd, max(images, key=lambda item: item[0])[1]
        except Exception:
            continue
    return None, None


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
    proc = subprocess.Popen(
        [codex_executable(), "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
            "name": "codex_quota_float", "title": "Codex 额度速览", "version": "2.0.0"}}})
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
    five_hours = next((w for w in windows if w.get("windowDurationMins") == 300), None)
    week = next((w for w in windows if w.get("windowDurationMins") == 10080), None)
    cards = (result.get("rateLimitResetCredits") or {}).get("availableCount")
    return five_hours, week, cards


def remaining(window):
    if not window or window.get("usedPercent") is None:
        return None
    return max(0, min(100, 100 - float(window["usedPercent"])))


def countdown(window):
    if not window or window.get("resetsAt") is None:
        return "未知"
    seconds = max(0, int(window["resetsAt"] - time.time()))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}天 {hours}小时"
    if hours:
        return f"{hours}小时 {minutes}分钟"
    return f"{minutes}分钟"


def position_above_pet(rect):
    virtual_x = user32.GetSystemMetrics(76)
    virtual_y = user32.GetSystemMetrics(77)
    virtual_right = virtual_x + user32.GetSystemMetrics(78)
    virtual_bottom = virtual_y + user32.GetSystemMetrics(79)
    x = (rect.left + rect.right - WIDTH) // 2
    x = min(max(x, virtual_x + 6), virtual_right - WIDTH - 6)
    y = rect.top - HEIGHT - 10
    if y < virtual_y + 6:
        y = min(rect.bottom + 10, virtual_bottom - HEIGHT - 6)
    return int(x), int(y)


class QuotaFloat:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Codex 额度速览")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", KEY)
        self.root.configure(bg=KEY)
        self.root.geometry(f"{WIDTH}x{HEIGHT}+0+0")
        self.root.withdraw()
        self.canvas = tk.Canvas(self.root, width=WIDTH, height=HEIGHT, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<Button-3>", self.show_menu)
        self.menu = tk.Menu(self.root, tearoff=False)
        self.pet_hwnd = None
        self.pet_image = None
        self.next_search = 0
        self.refreshing = False
        self.last_refresh = 0
        self.messages = queue.Queue()
        self.snapshot = (None, None, None)
        self.visible = False
        self.draw()
        self.root.after(100, self.tick)

    def rounded_box(self, x1, y1, x2, y2, radius, color):
        c = self.canvas
        c.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=color, outline="")
        c.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=color, outline="")
        for x in (x1, x2 - 2 * radius):
            for y in (y1, y2 - 2 * radius):
                c.create_oval(x, y, x + 2 * radius, y + 2 * radius, fill=color, outline="")

    def draw(self):
        c = self.canvas
        c.delete("all")
        self.rounded_box(0, 0, WIDTH, HEIGHT, 15, BORDER)
        self.rounded_box(1, 1, WIDTH - 1, HEIGHT - 1, 14, BG)
        for index, (label, color, y) in enumerate((("5小时", CYAN, 21), ("一周", AMBER, 51))):
            value = remaining(self.snapshot[index])
            c.create_text(14, y, text=label, anchor="w", fill=TEXT,
                          font=("Microsoft YaHei UI", 9))
            c.create_line(63, y, 171, y, fill=TRACK, width=5, capstyle="round")
            if value is not None and value > 0:
                c.create_line(63, y, 63 + 108 * value / 100, y,
                              fill=color, width=5, capstyle="round")
            text = "--" if value is None else f"{value:g}%"
            c.create_text(221, y, text=text, anchor="e", fill=color,
                          font=("Microsoft YaHei UI", 9, "bold"))

    def show_menu(self, event):
        self.menu.delete(0, "end")
        self.menu.add_command(label=f"5小时额度重置：{countdown(self.snapshot[0])}", state="disabled")
        self.menu.add_command(label=f"一周额度重置：{countdown(self.snapshot[1])}", state="disabled")
        cards = self.snapshot[2]
        self.menu.add_command(label=f"可用重置卡：{'--' if cards is None else cards} 次", state="disabled")
        self.menu.add_separator()
        self.menu.add_command(label="立即刷新", command=self.refresh)
        self.menu.add_command(label="退出悬浮窗", command=self.root.destroy)
        self.menu.tk_popup(event.x_root, event.y_root)

    def refresh(self):
        if self.refreshing or not self.visible:
            return
        self.refreshing = True

        def worker():
            try:
                self.messages.put((True, extract_snapshot(read_limits())))
            except Exception as exc:
                self.messages.put((False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def pet_rect(self):
        if self.pet_image is not None and user32.IsWindowVisible(self.pet_hwnd):
            try:
                rect = self.pet_image.BoundingRectangle
                if not self.pet_image.IsOffscreen and rect.right - rect.left >= 60:
                    return rect
            except Exception:
                pass
        self.pet_hwnd = self.pet_image = None
        if time.monotonic() < self.next_search:
            return None
        self.next_search = time.monotonic() + 1.5
        self.pet_hwnd, self.pet_image = find_pet()
        if self.pet_image is not None:
            return self.pet_image.BoundingRectangle
        return None

    def tick(self):
        rect = self.pet_rect()
        if rect is None:
            if self.visible:
                self.root.withdraw()
                self.visible = False
        else:
            x, y = position_above_pet(rect)
            if not self.visible:
                self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
                self.root.deiconify()
                self.root.lift()
                self.visible = True
            elif (self.root.winfo_x(), self.root.winfo_y()) != (x, y):
                self.root.geometry(f"+{x}+{y}")
                self.root.lift()
        if self.visible and time.monotonic() - self.last_refresh >= REFRESH_SECONDS:
            self.refresh()
        try:
            while True:
                success, value = self.messages.get_nowait()
                self.refreshing = False
                self.last_refresh = time.monotonic()
                if success:
                    self.snapshot = value
                    self.draw()
        except queue.Empty:
            pass
        self.root.after(120, self.tick)


def main():
    user32.SetProcessDPIAware()
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    mutex = kernel32.CreateMutexW(None, False, "Local\\CodexQuotaFloat")
    if kernel32.GetLastError() == 183:
        return
    try:
        QuotaFloat().root.mainloop()
    finally:
        kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
