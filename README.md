Mindustry Notifier
=======================================
Creates Windows notifications to alert the player when boss waves occur 
in [Mindustry](https://github.com/Anuken/Mindustry).

Boss waves are detected by checking for the red health bar that appears 
in the top left corner of the game window.

Mindustry needs to be running in window or borderless 
window mode for this to work. The game window needs to be open (not 
mimimized), although it can be behind other windows.


## Requirements
- Windows 7 or higher
- Python 3.6 or higher
- Pillow, install with `pip install Pillow`
- pywin32, install with `pip install pywin32`


## Usage
Run **notifier.py**, either by associating .py files with Python in 
Windows and double-clicking the file, or opening a command line window 
and running:
```
python notifier.py
```
Quit by right-clicking the system tray icon or closing the command line 
window.


## Options
Command line options are available via the command line:
```
python notifier.py -h
```
This will bring up the following:

    usage: notifier.py [-h] [-v | -q] [-i [INTERVAL]]

    optional arguments:
    -h, --help            show this help message and exit
    -v, --verbose         log status to console at every interval, even if nothing has changed
    -q, --quiet           only log critical statuses to console (windows notifications will be sent)
    -i [INTERVAL], --interval [INTERVAL]
                            seconds between status log updates in verbose mode


## Troubleshooting
**Notifications aren't being triggered**!

If Windows notifications aren't being triggered, Focus Assist is 
probably turned on, which silences all Windows notifications. Windows 
tends to automatically enable this feature when it detects that you're 
gaming. To enable the notifications, you'll have to 
[turn off Focus Assist](https://support.microsoft.com/en-us/help/4026996/windows-10-turn-focus-assist-on-or-off)

Another issue might be that there's another window with the name 
"Mindustry" open. The notifier identifies the Mindustry 
game window by its title. If there's another window titled "Mindustry" 
(for example, an open folder in explorer), the notifier may mistake 
that for the game and get confused. 

