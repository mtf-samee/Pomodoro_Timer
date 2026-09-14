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

- **System Tray & Background Mode:** Minimize the timer to the system tray. The tray icon tooltip displays the live countdown and current stage.
- **Visual Progress Bar:** Real-time progress tracking for the current stage.
- **Auto/Manual Advance:** Choose whether the next stage starts automatically or waits for you to press Space (ideal for un-timed physical breaks).
- **Advanced Audio Management:** Set global or per-stage audio files via file browsers. Adjust volume individually per stage.
- **Dynamic Audio Test:** Preview stage sounds smoothly with a morphing Test/Stop button in the editor.
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
| `Esc`    | Exit Fullscreen |
