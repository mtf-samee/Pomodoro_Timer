# Pomodoro Timer

A feature-rich Pomodoro timer desktop application built with PyQt6. Designed for Wayland on Fedora Linux and compatible with other Linux distributions.

## Requirements

### Fedora Linux
```bash
sudo dnf install python3-pyqt6 libnotify -y
```

### Ubuntu / Debian / Linux Mint
```bash
sudo apt install python3-pyqt6 libnotify-bin qt6-wayland -y
```

### Arch Linux
```bash
sudo pacman -S python-pyqt6 libnotify qt6-wayland
```

### openSUSE
```bash
sudo zypper install python3-PyQt6 libnotify-tools libQt6WaylandClient5 -y
```

## Usage

Start the application by running the Python script:

```bash
python3 pomodro_timer.py
```

## Features

- **CLI / Shortcut Toggling:** Running the command again toggles the backgrounded tray instance.
- **System Tray Integration:** Run in the background with live tray status.
- **Draggable Interactive Progress Bar:** Click or drag directly on the progress bar to scrub time.
- **Auto & Manual Advance:** Automatically or manually switch between work and break sessions.
- **Advanced Audio Management:** Sound notifications for session completions.
- **Single-Instance Enforcement:** File locking prevents multiple simultaneous instances.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Space`  | Start / Pause Timer |
| `R`      | Reset Timer |
| `M`      | Minimize to System Tray |
| `Q`      | Quit Application |
| `Enter`  | Save configuration / Edit Timer |
