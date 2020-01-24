<p align="center">
  <img width="380" height="180" src="https://user-images.githubusercontent.com/490097/72409396-8055b780-371a-11ea-80f1-3d5915ac9116.png" />
</p>

Mindustry Notifier
=======================================
This will create Windows notifications when boss waves appear 
in [Mindustry](https://github.com/Anuken/Mindustry).

The motivation for creating this was so I could leave the game running in 
the background while doing other things and be alerted when boss waves 
appeared.

The notifier detects boss waves by checking for the red health bar in the 
top left corner of the game window. Because of this, Mindustry needs to be 
running in window or borderless window mode. The game window can be in the 
background behind other windows or off the side of the screen, but it cannot 
be minimized.


## Download
- [v1.103](https://github.com/ritsu/mindustry-notifier/releases/tag/1.103) for Mindustry build 103 (released Jan 24, 2020)
- [v1.0](https://github.com/ritsu/mindustry-notifier/releases/tag/1.0) for Mindustry build 102 (released Dec 29, 2019)

## Requirements
- Windows 7 or higher
- Python 3.6 or higher
- Pillow, install with `pip install Pillow`
- pywin32, install with `pip install pywin32`


## Usage
Run **notifier.py**, either by associating .py files with Python in 
Windows and double clicking the file, or opening a command line window 
and running:
```
python notifier.py
```
You should now recieve Windows notifications whenever boss waves appear in 
Mindustry as long as both the notifier and the game are running, and the 
game is not minimized or in fullscreen mode.

Close the notifier through the system tray icon menu. You can also close 
it by killing the command line window, but that may cause the notifier 
icon to linger in the system tray until you hover over it.


## Options
The options are mainly for debugging or observation. To see the list of options, type:
```
python notifier.py -h
```
This will bring up the following:

    usage: notifier.py [-h] [-v] [-i [INTERVAL]]

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         log status to console at every interval, even if
                            nothing has changed
      -i [INTERVAL], --interval [INTERVAL]
                            seconds between status updates in verbose mode
                            (default 5)

## Troubleshooting
**Notifications aren't being triggered**!

If Windows notifications aren't being triggered, Focus Assist is 
probably turned on, which silences all Windows notifications. Windows 
automatically enables this feature when it detects that you're 
gaming. To enable the notifications, you'll have to 
[turn off Focus Assist](https://support.microsoft.com/en-us/help/4026996/windows-10-turn-focus-assist-on-or-off).

Another issue might be that there's another window with the name 
"Mindustry" open. The notifier identifies the Mindustry 
game window by its title. If there's another window titled "Mindustry" 
(for example, an open folder in explorer), the notifier may mistake 
that for the game and get confused.
