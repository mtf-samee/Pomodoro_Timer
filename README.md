# Pomodoro Timer

A configurable multi-stage interval timer built with PyQt6. Designed for Wayland on Fedora Linux.

## Requirements

```bash
sudo dnf install python3-pyqt6 libnotify -y
```

## Usage

```bash
python3 pomodro_timer.py
```

## Features

- **Interactive Timeline:** Drag the live progress bar to immediately seek/adjust the time remaining for the current stage.
- **CLI / Shortcut Toggling:** Running the launch command again will seamlessly toggle the backgrounded system tray instance rather than opening duplicates.
- **System Tray & Background Mode:** Minimize the timer to the system tray. The tray icon tooltip displays the live countdown and current stage.
- **Auto/Manual Advance:** Choose whether the next stage starts automatically or waits for you to press Space.
- **Advanced Audio Management:** Set global or per-stage audio files via file browsers. Adjust volume individually per stage.
- **Custom Stage Sequences:** Create unlimited stages with text-based duration parsing (e.g., `40m`, `1h 30m`, `90s`).
- **Persistent JSON Configuration:** Presets, sounds, and settings are saved automatically to `~/.config/study_timer/config.json`.
- **Native Notifications:** Wayland alerts via `libnotify` ensure you never miss a transition, even if the app is hidden.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Space`  | Start / Pause / Resume / Next (if manual advance) |
| `S`      | Skip Current Stage |
| `R`      | Reset Session |
| `E`      | Open Editor / Remake Timer |
| `F`      | Toggle Fullscreen |
| `M`      | Minimize to System Tray |
| `Q`      | Quit the Application completely |
| `Esc`    | Exit Fullscreen |
| `Enter`  | Save & Apply (inside configuration editors) |
