# Pomodoro Timer

A configurable multi-stage interval timer built with PyQt6. Designed for Wayland on Fedora Linux.

## Requirements

```bash
sudo dnf install python3-pyqt6 libnotify

Usage
python3 study_timer.py

Features
Custom stage sequences, durations, and audio alerts.

Configurable rounds and infinite loop mode.

System notifications (via libnotify).

Persistent JSON configuration stored in ~/.config/study_timer/config.json.

Keyboard shortcuts for rapid control (Space to toggle, S to skip, R to reset).
