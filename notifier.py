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
    MIN_BOSS_INTERVAL = 120
    SCREENSHOT_X1 = 20
    SCREENSHOT_X2 = 25
    SCREENSHOT_Y1 = 145
    SCREENSHOT_Y2 = 175

    def __init__(self, **kwargs):
        self.windows_notifier = WindowsNotifier()
        self.prev_state = None
        self.status_time = 0
        # Always send notification for first boss wave, even if it happens immediately after starting game
        self.active_time_without_boss = Notifier.MIN_BOSS_INTERVAL
        self.verbose = kwargs.get("verbose", False)
        self.interval = kwargs.get("interval")
        self.log("Notifier started.", True)

    def log(self, msg, state_change=False):
        if state_change or (self.verbose and (time.time() - self.status_time) > self.interval):
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t{msg}")
            self.status_time = time.time()

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
        try:
            mem_dc.DeleteDC()
            img_dc.DeleteDC()
        except Exception as err:
            print(f"Error trying to delete context: {err}")
        win32gui.ReleaseDC(win_hd, win_dc)

        if result != 1:
            return GameState.SCREENSHOT_FAIL
        
        return state
    
    def notify(self, title, msg):
        self.windows_notifier.show_notification(title, msg)

    async def monitor(self):
        while self.windows_notifier.alive:
            state = Notifier.game_state()
            if state != self.prev_state:
                # Only alert on boss wave if minimum non-boss active time has passed
                if state == GameState.BOSS_WAVE and self.active_time_without_boss >= Notifier.MIN_BOSS_INTERVAL:
                    self.notify(GAME_STATE_TEXT[state][0], GAME_STATE_TEXT[state][1])
                    self.log(" ".join([GAME_STATE_TEXT[state][0], "Notification sent."]), True)
                elif state in [GameState.SCREENSHOT_FAIL, GameState.MINIMIZED]:
                    self.notify(GAME_STATE_TEXT[state][0], GAME_STATE_TEXT[state][1])
                    self.log(" ".join([GAME_STATE_TEXT[state][0], "Notification sent."]), True)
                else:
                    self.log(GAME_STATE_TEXT[state][0], True)
                self.windows_notifier.game_state = state
                self.windows_notifier.update_icon()
            else:
                self.log(GAME_STATE_TEXT[state][0])

            if state == GameState.BOSS_WAVE:
                self.active_time_without_boss = 0
            elif state == GameState.OTHER:
                self.active_time_without_boss += Notifier.CHECK_STATE_INTERVAL

            self.prev_state = state
            await self.message_aware_sleep(Notifier.CHECK_STATE_INTERVAL, Notifier.CHECK_MESSAGE_INTERVAL)

    @staticmethod
    async def message_aware_sleep(total_time, msg_time):
        """ Sleep for total_time, while calling PumpWaitingMessages() every msg_time """
        for _ in range(int(total_time / msg_time)):
            win32gui.PumpWaitingMessages()
            await asyncio.sleep(msg_time)
        

class WindowsNotifier:
    def __init__(self):
        self.alive = True

        # Icons based on game state
        icon_normal = path.realpath("notifyon.ico")
        icon_gray = path.realpath("notifyoff.ico")

        # Menu text color based on game state
        menu_gray = win32con.MF_STRING | win32con.MF_GRAYED
        menu_normal = win32con.MF_STRING
        self.menu_mindustry_flags = {
            GameState.NOT_FOUND: menu_gray,
            GameState.SCREENSHOT_FAIL: menu_normal,
            GameState.MINIMIZED: menu_normal,
            GameState.BOSS_WAVE: menu_normal,
            GameState.OTHER: menu_normal,
        }
        self.game_state = GameState.OTHER

        self.icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        self.nid_flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP

        # Register the window class
        message_map = {
            win32con.WM_DESTROY: self.on_destroy,
            win32con.WM_COMMAND: self.on_command,
            win32con.WM_USER + 20: self.on_taskbar_notify,
        }
        self.wc = win32gui.WNDCLASS()
        hinst = self.wc.hInstance = win32api.GetModuleHandle(None)
        self.wc.lpszClassName = "MindustryNotifierTaskbar"
        self.wc.lpfnWndProc = message_map

        self.wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        self.wc.hCursor = win32api.LoadCursor( 0, win32con.IDC_ARROW )
        self.wc.hbrBackground = win32con.COLOR_WINDOW

        try:
            class_atom = win32gui.RegisterClass(self.wc)
        except win32gui.error as err:
            if err.winerror != winerror.ERROR_CLASS_ALREADY_EXISTS:
                raise

        # Create the window
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(class_atom, "Taskbar", style, 0, 0, win32con.CW_USEDEFAULT,
                                          win32con.CW_USEDEFAULT, 0, 0, hinst, None)
        win32gui.UpdateWindow(self.hwnd)

        # Create icons
        try:
            self.hicon_normal = win32gui.LoadImage(hinst, icon_normal, win32con.IMAGE_ICON, 0, 0, self.icon_flags)
        except Exception as err:
            self.hicon_normal = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        try:
            self.hicon_gray = win32gui.LoadImage(hinst, icon_gray, win32con.IMAGE_ICON, 0, 0, self.icon_flags)
        except Exception as err:
            self.hicon_gray = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        self.hicons = {
            GameState.NOT_FOUND: self.hicon_gray,
            GameState.SCREENSHOT_FAIL: self.hicon_gray,
            GameState.MINIMIZED: self.hicon_gray,
            GameState.BOSS_WAVE: self.hicon_normal,
            GameState.OTHER: self.hicon_normal,
        }
        nid = (self.hwnd, 0, self.nid_flags, win32con.WM_USER + 20, self.hicons[self.game_state], "Mindustry Notifier")
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except win32gui.error:
            print("Failed to create taskbar icon. Possibly explorer has crashed or has not yet started.")

    def show_notification(self, title, msg):
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, (self.hwnd, 0, win32gui.NIF_INFO, win32con.WM_USER + 20,
                                  self.hicon_normal, "Balloon Tooltip", msg, 200, title, win32gui.NIIF_ICON_MASK))

    def update_icon(self):
        icon_text = "\n".join(["Mindustry Notifier", GAME_STATE_TEXT[self.game_state][0].replace("Mindustry", "Game")])
        nid = (self.hwnd, 0, self.nid_flags, win32con.WM_USER + 20, self.hicons[self.game_state], icon_text)
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        except win32gui.error:
            print("Failed to create taskbar icon. Possibly explorer has crashed or has not yet started.")

    def on_destroy(self, hwnd, msg, wparam, lparam):
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32api.PostQuitMessage(0)
    
    def on_taskbar_notify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_RBUTTONUP:
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, self.menu_mindustry_flags[self.game_state], 1024, "Show Mindustry Game")
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
