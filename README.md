# Pomodoro Timer

A feature-rich Pomodoro timer desktop application built with PyQt6, featuring bundled audio assets and native Linux AppImage support. Designed for Wayland on Fedora Linux and compatible with other Linux distributions.

## Quick Start (AppImage)

The easiest way to use the application is via the pre-compiled AppImage, which includes all dependencies and default audio assets.

1. Download the latest `PomodoroTimer-x86_64.AppImage` from the [Releases](https://github.com/mtf-samee/Pomodoro_Timer/releases) page.
2. Make the file executable:
   ```bash
   chmod +x PomodoroTimer-x86_64.AppImage
   ```
3. Run the application:
   ```bash
   ./PomodoroTimer-x86_64.AppImage
   ```

## Building and Running from Source

If you prefer to run the script directly, install the required dependencies for your distribution.

### 1. Install Dependencies

**Fedora Linux:**
```bash
sudo dnf install python3-pyqt6 libnotify -y
```

**Ubuntu / Debian / Linux Mint:**
```bash
sudo apt install python3-pyqt6 libnotify-bin qt6-wayland -y
```

**Arch Linux:**
```bash
sudo pacman -S python-pyqt6 libnotify qt6-wayland
```

**openSUSE:**
```bash
sudo zypper install python3-PyQt6 libnotify-tools libQt6WaylandClient5 -y
```

### 2. Run the Application
```bash
python3 pomodro_timer.py
```

## Packaging the AppImage

To build the AppImage locally, ensure PyInstaller is installed and the `appimagetool` binary is available in your project directory.

1. Clean previous build artifacts:
   ```bash
   rm -rf build dist PomodoroTimer-x86_64.AppImage
   ```
2. Compile with PyInstaller. The `--add-data` flag bundles the local `assets` directory containing the audio files into the temporary execution path:
   ```bash
   pyinstaller --onedir --noconsole --name=PomodoroTimer --add-data "assets:assets" pomodro_timer.py
   ```
3. Copy compiled files to the AppDir:
   ```bash
   cp -r dist/PomodoroTimer/* AppDir/usr/bin/
   ```
4. Generate the AppImage:
   ```bash
   ./appimagetool-x86_64.AppImage AppDir PomodoroTimer-x86_64.AppImage
   ```

## Features

- **Bundled Audio Assets:** Includes a default audio asset packaged directly within the application and AppImage. Fallback logic automatically resolves FUSE extraction paths.
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
