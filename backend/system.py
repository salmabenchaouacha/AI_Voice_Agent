"""Intégration système (Windows / macOS / Linux)."""
import platform
import re
import subprocess
import webbrowser

OS = platform.system()  # "Windows", "Darwin", "Linux"

APPS = {
    ("chrome", "navigateur"): {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
    ("calculatrice", "calculator"): {"Windows": "calc", "Darwin": "Calculator", "Linux": "gnome-calculator"},
    ("bloc-notes", "bloc notes", "notepad"): {"Windows": "notepad", "Darwin": "TextEdit", "Linux": "gedit"},
    ("vscode", "vs code", "visual studio code"): {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    ("terminal",): {"Windows": "wt", "Darwin": "Terminal", "Linux": "gnome-terminal"},
    ("spotify",): {"Windows": "spotify", "Darwin": "Spotify", "Linux": "spotify"},
    ("explorateur", "fichiers"): {"Windows": "explorer", "Darwin": "Finder", "Linux": "nautilus"},
}
SITES = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "google": "https://www.google.com",
}


def _launch(cmd: str, label: str) -> str:
    if not re.fullmatch(r"[\w .+-]+", cmd):          # évite toute injection via la transcription
        return f"Je n'arrive pas à ouvrir {label}."
    try:
        if OS == "Windows":
            ok = subprocess.run(f'start "" "{cmd}"', shell=True, capture_output=True).returncode == 0
        elif OS == "Darwin":
            ok = subprocess.run(["open", "-a", cmd], capture_output=True).returncode == 0
        else:
            subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ok = True
    except OSError:
        ok = False
    return f"J'ouvre {label}." if ok else f"Je n'arrive pas à ouvrir {label}."


def open_target(name: str) -> str:
    name = name.strip()
    for site, url in SITES.items():
        if site in name:
            webbrowser.open(url)
            return f"J'ouvre {site}."
    for keys, cmds in APPS.items():
        if any(k in name for k in keys):
            return _launch(cmds[OS], keys[0])
    return _launch(name, name)


def volume(delta: int) -> None:
    """delta : +1 monter, -1 baisser, 0 couper/rétablir le son."""
    if OS == "Windows":
        import pyautogui
        key = "volumemute" if delta == 0 else "volumeup" if delta > 0 else "volumedown"
        pyautogui.press(key, presses=1 if delta == 0 else 5)
    elif OS == "Darwin":
        script = ("set volume output muted true" if delta == 0 else
                  f"set volume output volume ((output volume of (get volume settings)) + {10 * delta})")
        subprocess.run(["osascript", "-e", script])
    else:
        args = (["set-sink-mute", "@DEFAULT_SINK@", "toggle"] if delta == 0 else
                ["set-sink-volume", "@DEFAULT_SINK@", f"{'+' if delta > 0 else '-'}10%"])
        subprocess.run(["pactl", *args])