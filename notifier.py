import asyncio
import argparse
import time
from datetime import datetime
from os import path
from enum import Enum
from PIL import Image
from ctypes import windll
import win32gui
import win32ui
import win32api
import win32con
import winerror


class GameState(Enum):
    NOT_FOUND = 1
    SCREENSHOT_FAIL = 2
    MINIMIZED = 3
    BOSS_WAVE = 4
    OTHER = 5


GAME_STATE_TEXT = {
    GameState.NOT_FOUND: [
        "Mindustry not found.",
        "",
    ],
    GameState.SCREENSHOT_FAIL: [
        "Failed to read bitmap.",
        "Unable to read pixel data from the Mindustry game window. Boss wave notifications will be unavailable.",
    ],
    GameState.MINIMIZED: [
        "Mindustry is minimized.",
        "Boss waves cannot be detected if the game window is minimized.",
    ],
    GameState.BOSS_WAVE: [
        "Boss wave detected.",
        "A boss wave has been detected in your Mindustry game.",
    ],
    GameState.OTHER: [
        "Mindustry is active.",
        ""
    ],
}


class Notifier:
    """ Notify user when boss waves occur in Mindustry """

    CHECK_STATE_INTERVAL = 0.5
    CHECK_MESSAGE_INTERVAL = 0.1
    SCREENSHOT_X1 = 20
    SCREENSHOT_X2 = 30
    SCREENSHOT_Y1 = 145
    SCREENSHOT_Y2 = 175

    def __init__(self, **kwargs):
        self.windows_notifier = WindowsNotifier()
        self.last_state = None
        self.last_status = 0
        self.last_boss = 0
        self.verbose = kwargs.get("verbose", False)
        self.interval = kwargs.get("interval")
        self.log("Notifier started.", True)

    def log(self, msg, state_change=False):
        if state_change or (self.verbose and (time.time() - self.last_status) > self.interval):
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t{msg}")
            self.last_status = time.time()

    @staticmethod
    def is_boss_pixel(pixel):
        """ Checks if pixel matches luminance of red boss health bar """
        lum_pixel = 0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]
        lum_boss = 93.425
        err = 1.0
        return abs(lum_pixel - lum_boss) < err

    @staticmethod
    def game_state():
        """ Return GameState Enum """
        # Get handle for Mindustry window
        win_hd = win32gui.FindWindow(None, "Mindustry")
        if win_hd == 0:
            return GameState.NOT_FOUND
        
        if win32gui.IsIconic(win_hd):
            return GameState.MINIMIZED

        # Create device context
        win_dc = win32gui.GetWindowDC(win_hd)
        img_dc = win32ui.CreateDCFromHandle(win_dc)

        # Create memory based device context
        mem_dc = img_dc.CreateCompatibleDC()

        # Create bitmap object
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(img_dc, Notifier.SCREENSHOT_X2, Notifier.SCREENSHOT_Y2)
        mem_dc.SelectObject(bitmap)
        
        result = windll.user32.PrintWindow(win_hd, mem_dc.GetSafeHdc(), 1)
        bitmap_info = bitmap.GetInfo()
        bitmap_str = bitmap.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (bitmap_info["bmWidth"], bitmap_info["bmHeight"]), 
                               bitmap_str, "raw", "BGRX", 0, 1)
        img_cropped = img.crop((Notifier.SCREENSHOT_X1, Notifier.SCREENSHOT_Y1, 
                                Notifier.SCREENSHOT_X2, Notifier.SCREENSHOT_Y2))

        # Check for boss
        state = GameState.BOSS_WAVE 
        width = Notifier.SCREENSHOT_X2 - Notifier.SCREENSHOT_X1
        height = Notifier.SCREENSHOT_Y2 - Notifier.SCREENSHOT_Y1
        for i in range(1, width):
            for j in range(1, height):
                pixel = img_cropped.getpixel((i, j))
                if not Notifier.is_boss_pixel(pixel):
                    state = GameState.OTHER
                    break
            else:
                continue   # only executed of no break encountered
            break
        
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        img_dc.DeleteDC()
        win32gui.ReleaseDC(win_hd, win_dc)

        if result != 1:
            return GameState.SCREENSHOT_FAIL
        
        return state
    
    def notify(self, title, msg):
        self.windows_notifier.show_notification(title, msg)

    async def monitor(self):
        while self.windows_notifier.alive:
            state = Notifier.game_state()
            if state != self.last_state:
                # Avoid false positives when health bar of an individual boss depletes in the middle of a wave.
                if state == GameState.BOSS_WAVE and (time.time() - self.last_boss) > 120:
                    self.notify(GAME_STATE_TEXT[state][0], GAME_STATE_TEXT[state][1])
                    self.log(" ".join([GAME_STATE_TEXT[state][0], "Notification sent."]), True)
                    self.last_boss = time.time()
                elif state in [GameState.SCREENSHOT_FAIL, GameState.MINIMIZED]:
                    self.notify(GAME_STATE_TEXT[state][0], GAME_STATE_TEXT[state][1])
                    self.log(" ".join([GAME_STATE_TEXT[state][0], "Notification sent."]), True)
                else:
                    self.log(GAME_STATE_TEXT[state][0], True)
                self.windows_notifier.game_state = state
                self.windows_notifier.update_icon()
            else:
                self.log(GAME_STATE_TEXT[state][0])

            self.last_state = state
            await self.message_aware_sleep()

    @staticmethod
    async def message_aware_sleep():
        """ This is probably a terrible idea """
        for _ in range(int(Notifier.CHECK_STATE_INTERVAL / Notifier.CHECK_MESSAGE_INTERVAL)):
            win32gui.PumpWaitingMessages()
            await asyncio.sleep(Notifier.CHECK_MESSAGE_INTERVAL)
        

class WindowsNotifier:
    def __init__(self):
        self.alive = True
        # Register the window class
        message_map = {
            win32con.WM_DESTROY: self.on_destroy,
            win32con.WM_COMMAND: self.on_command,
            win32con.WM_USER + 20: self.on_taskbar_notify,
        }
        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "MindustryNotifierTaskbar"
        wc.lpfnWndProc = message_map

        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        wc.hCursor = win32api.LoadCursor( 0, win32con.IDC_ARROW )
        wc.hbrBackground = win32con.COLOR_WINDOW

        try:
            class_atom = win32gui.RegisterClass(wc)
        except win32gui.error as err:
            if err.winerror != winerror.ERROR_CLASS_ALREADY_EXISTS:
                raise

        # Create the window
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(class_atom, "Taskbar", style, 0, 0, win32con.CW_USEDEFAULT,
                                          win32con.CW_USEDEFAULT, 0, 0, hinst, None)
        win32gui.UpdateWindow(self.hwnd)

        # Icon
        icon_path = path.realpath("notifier.ico")
        icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        try:
            self.hicon = win32gui.LoadImage(hinst, icon_path, win32con.IMAGE_ICON, 0, 0, icon_flags)
        except err:
            self.hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        # Taskbar icon
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        nid = (self.hwnd, 0, flags, win32con.WM_USER + 20, self.hicon, "Mindustry Notifier")
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except win32gui.error:
            # Windows usually recovers from this, so notify and continue
            print("Failed to create taskbar icon. Possibly explorer has crashed or has not yet started.")

    def on_destroy(self, hwnd, msg, wparam, lparam):
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32api.PostQuitMessage(0)
    
    def on_taskbar_notify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_RBUTTONUP:
            menu = win32gui.CreatePopupMenu()
            # win32gui.AppendMenu(menu, win32con.MF_STRING, 1023, "Show Status")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1024, "Show Mindustry Game")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1025, "Exit Notifier")
            pos = win32gui.GetCursorPos()
            win32gui.SetForegroundWindow(self.hwnd)
            win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, self.hwnd, None)
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        return 1

    def on_command(self, hwnd, msg, wparam, lparam):
        wid = win32api.LOWORD(wparam)
        if wid == 1024:
            WindowsNotifier.show_game_window()
        elif wid == 1025:
            win32gui.DestroyWindow(self.hwnd)
            win32gui.UnregisterClass(self.wc.lpszClassName, None)
            self.alive = False
        else:

    def show_notification(self, title, msg):
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, (self.hwnd, 0, win32gui.NIF_INFO, win32con.WM_USER + 20, 
                                  self.hicon, "Balloon Tooltip", msg, 200, title, win32gui.NIIF_ICON_MASK))
            print(f"Unknown command: {wid}")

    @staticmethod
    def show_game_window():
        win_hd = win32gui.FindWindow(None, "Mindustry")
        if win_hd != 0:
            win32gui.ShowWindow(win_hd, win32con.SW_SHOWNORMAL)
            win32gui.SetForegroundWindow(win_hd)
            win32gui.UpdateWindow(win_hd)


def main(kwargs):
    notifier = Notifier(**kwargs)
    loop = asyncio.get_event_loop()
    future = loop.create_task(notifier.monitor())
    loop.run_until_complete(future)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="log status to console at every interval, even if nothing has changed")
    parser.add_argument("-i", "--interval", type=int, nargs="?", default=5, 
                        help="seconds between status updates in verbose mode (default 5)")

    main(vars(parser.parse_args()))
