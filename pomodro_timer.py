#!/usr/bin/env python3
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


def resource_path(relative_path):
  try:
    base_path = sys._MEIPASS
  except Exception:
    base_path = os.path.abspath(".")
  return os.path.join(base_path, relative_path)


CONFIG_DIR = os.path.expanduser("~/.config/study_timer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BACKUP_FILE = os.path.join(CONFIG_DIR, "config.json.bak")


def parse_duration(text):
  text = str(text).lower().strip()
  if not text:
    return 0
  total_seconds = 0
  matches = re.findall(r"(\d+)\s*([hms])", text)
  if not matches:
    try:
      return int(text)
    except ValueError:
      return 0
  for val, unit in matches:
    if unit == "h":
      total_seconds += int(val) * 3600
    elif unit == "m":
      total_seconds += int(val) * 60
    elif unit == "s":
      total_seconds += int(val)
  return total_seconds


def format_duration(seconds):
  h = seconds // 3600
  m = (seconds % 3600) // 60
  s = seconds % 60
  if h > 0:
    return f"{h:02}:{m:02}:{s:02}"
  return f"{m:02}:{s:02}"


class ConfigManager:

  def __init__(self):
    self.config = {
        "sound_dir": (
            resource_path("assets")
            if hasattr(sys, "_MEIPASS")
            else os.path.expanduser("~/Music")
        ),
        "use_common_sound": True,
        "common_sound_file": "timer.mp3",
        "presets": {
            "Default": {
                "rounds": 1,
                "infinite": False,
                "auto_advance": True,
                "stages": [{
                    "name": "WORK",
                    "duration": 1500,
                    "sound": "timer.mp3",
                    "volume": 1.0,
                }],
            }
        },
        "current_preset": "Default",
    }
    self.load()

  def load(self):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
      self.save()
      return

    try:
      with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        self.config.update(data)
        if self.config["current_preset"] not in self.config["presets"]:
          self.config["current_preset"] = list(
              self.config["presets"].keys()
          )[0]

        for preset in self.config["presets"].values():
          if "auto_advance" not in preset:
            preset["auto_advance"] = True
          for stage in preset["stages"]:
            if "volume" not in stage:
              stage["volume"] = 1.0

    except Exception:
      if os.path.exists(BACKUP_FILE):
        try:
          with open(BACKUP_FILE, "r") as f:
            self.config.update(json.load(f))
        except Exception:
          pass

  def save(self):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
      shutil.copy(CONFIG_FILE, BACKUP_FILE)
    with open(CONFIG_FILE, "w") as f:
      json.dump(self.config, f, indent=4)

  def get_current_preset(self):
    return self.config["presets"][self.config["current_preset"]]


class AudioManager:

  def __init__(self, config_manager):
    self.config = config_manager
    self.player = QMediaPlayer()
    self.audio_output = QAudioOutput()
    self.player.setAudioOutput(self.audio_output)

  def play(self, sound_file, volume=1.0):
    if not sound_file:
      sound_file = self.config.config.get("common_sound_file") or "timer.mp3"
    path = (
        sound_file
        if os.path.isabs(sound_file)
        else os.path.join(self.config.config["sound_dir"], sound_file)
    )
    if not os.path.exists(path):
      path = resource_path(os.path.join("assets", sound_file))
    if not os.path.exists(path):
      path = resource_path(os.path.join("assets", "timer.mp3"))
    if not os.path.exists(path):
      return

    self.audio_output.setVolume(volume)
    self.player.setSource(QUrl.fromLocalFile(path))
    self.player.play()

  def stop(self):
    self.player.stop()


class NotificationManager:

  @staticmethod
  def send(title, message):
    try:
      subprocess.Popen([
          "notify-send",
          "-a",
          "Pomodoro Timer",
          "-u",
          "normal",
          title,
          message,
      ])
    except FileNotFoundError:
      pass


class TimerEngine(QObject):
  tick_signal = pyqtSignal(int, int)
  stage_changed_signal = pyqtSignal(int, int)
  state_changed_signal = pyqtSignal(str)
  completed_signal = pyqtSignal(int)

  def __init__(self, config_manager, audio_manager):
    super().__init__()
    self.config_manager = config_manager
    self.audio = audio_manager
    self.timer = QTimer()
    self.timer.timeout.connect(self.update)

    self.state = "STOPPED"
    self.stage_idx = 0
    self.round_idx = 1
    self.remaining = 0
    self.current_stage_duration = 0
    self.target_time = 0
    self.total_elapsed = 0

    self.load_preset()

  def load_preset(self):
    preset = self.config_manager.get_current_preset()
    self.stages = preset["stages"]
    self.rounds = preset["rounds"]
    self.infinite = preset["infinite"]
    self.auto_advance = preset.get("auto_advance", True)
    self.reset()

  def set_state(self, new_state):
    self.state = new_state
    self.state_changed_signal.emit(self.state)

  def start(self):
    if not self.stages:
      return

    if self.state == "STOPPED" or self.state == "WAITING":
      self.current_stage_duration = self.stages[self.stage_idx]["duration"]
      if self.state == "STOPPED":
        self.remaining = self.current_stage_duration

    if self.state != "RUNNING":
      self.target_time = time.monotonic() + self.remaining
      self.set_state("RUNNING")
      self.timer.start(100)

  def pause(self):
    if self.state == "RUNNING":
      self.remaining = self.target_time - time.monotonic()
      self.set_state("PAUSED")
      self.timer.stop()

  def reset(self):
    self.set_state("STOPPED")
    self.timer.stop()
    self.stage_idx = 0
    self.round_idx = 1
    self.total_elapsed = 0
    if self.stages:
      self.current_stage_duration = self.stages[0]["duration"]
      self.remaining = self.current_stage_duration
    else:
      self.current_stage_duration = 0
      self.remaining = 0

    self.tick_signal.emit(self.remaining, self.current_stage_duration)
    self.stage_changed_signal.emit(self.stage_idx, self.round_idx)

  def seek(self, new_remaining):
    if self.state in ["STOPPED", "WAITING"]:
      return
    self.remaining = max(0, min(new_remaining, self.current_stage_duration))
    if self.state == "RUNNING":
      self.target_time = time.monotonic() + self.remaining
    self.tick_signal.emit(self.remaining, self.current_stage_duration)

  def skip(self):
    if self.state == "STOPPED":
      return
    self.next_stage(skipped=True)

  def update(self):
    if self.state != "RUNNING":
      return
    now = time.monotonic()
    rem = int(self.target_time - now)

    if rem <= 0:
      self.total_elapsed += self.stages[self.stage_idx]["duration"]
      self.next_stage(skipped=False)
    else:
      if rem != int(self.remaining):
        self.remaining = rem
        self.tick_signal.emit(rem, self.current_stage_duration)

  def next_stage(self, skipped=False):
    if not skipped:
      current_stage = self.stages[self.stage_idx]
      sound = (
          self.config_manager.config["common_sound_file"]
          if self.config_manager.config["use_common_sound"]
          else current_stage.get("sound", "")
      )
      vol = current_stage.get("volume", 1.0)
      self.audio.play(sound, vol)
      NotificationManager.send("Stage Complete", current_stage["name"])

    self.stage_idx += 1

    if self.stage_idx >= len(self.stages):
      self.stage_idx = 0
      self.round_idx += 1
      if not self.infinite and self.round_idx > self.rounds:
        self.set_state("STOPPED")
        self.timer.stop()
        NotificationManager.send("Timer Complete", "All rounds finished.")
        self.completed_signal.emit(self.total_elapsed)
        return

    self.current_stage_duration = self.stages[self.stage_idx]["duration"]
    self.remaining = self.current_stage_duration
    self.stage_changed_signal.emit(self.stage_idx, self.round_idx)
    self.tick_signal.emit(self.remaining, self.current_stage_duration)

    if not self.auto_advance and not skipped:
      self.set_state("WAITING")
      self.timer.stop()
    else:
      self.target_time = time.monotonic() + self.remaining
      if self.state == "PAUSED":
        pass
      else:
        self.set_state("RUNNING")
        if not skipped:
          NotificationManager.send(
              "Stage Started", self.stages[self.stage_idx]["name"]
          )


class EditorDialog(QDialog):

  def __init__(self, config_manager, audio_manager, parent=None):
    super().__init__(parent)
    self.config = config_manager
    self.audio = audio_manager
    self.setWindowTitle("Edit Timer Configuration")
    self.setMinimumSize(600, 600)
    self.stages = [s.copy() for s in self.config.get_current_preset()["stages"]]
    self.audio.player.playbackStateChanged.connect(
        self.on_playback_state_changed
    )
    self.setup_ui()
    self.refresh_list()

  def setup_ui(self):
    layout = QVBoxLayout(self)

    preset_layout = QHBoxLayout()
    preset_layout.addWidget(QLabel("Preset:"))
    self.preset_combo = QComboBox()
    self.preset_combo.addItems(self.config.config["presets"].keys())
    self.preset_combo.setCurrentText(self.config.config["current_preset"])
    self.preset_combo.currentTextChanged.connect(self.change_preset)
    preset_layout.addWidget(self.preset_combo)

    btn_new_preset = QPushButton("New")
    btn_new_preset.clicked.connect(self.new_preset)
    preset_layout.addWidget(btn_new_preset)

    btn_del_preset = QPushButton("Delete")
    btn_del_preset.clicked.connect(self.delete_preset)
    preset_layout.addWidget(btn_del_preset)

    layout.addLayout(preset_layout)

    hbox = QHBoxLayout()
    self.list_widget = QListWidget()
    self.list_widget.currentRowChanged.connect(self.load_selected_stage)
    hbox.addWidget(self.list_widget)

    vbox_btns = QVBoxLayout()
    btn_add = QPushButton("Add Stage")
    btn_add.clicked.connect(self.add_stage)
    btn_up = QPushButton("Move Up")
    btn_up.clicked.connect(self.move_up)
    btn_down = QPushButton("Move Down")
    btn_down.clicked.connect(self.move_down)
    btn_del = QPushButton("Delete Stage")
    btn_del.clicked.connect(self.delete_stage)
    btn_dup = QPushButton("Duplicate")
    btn_dup.clicked.connect(self.duplicate_stage)

    vbox_btns.addWidget(btn_add)
    vbox_btns.addWidget(btn_up)
    vbox_btns.addWidget(btn_down)
    vbox_btns.addWidget(btn_del)
    vbox_btns.addWidget(btn_dup)
    vbox_btns.addStretch()
    hbox.addLayout(vbox_btns)
    layout.addLayout(hbox)

    self.edit_name = QLineEdit()
    self.edit_duration = QLineEdit()
    self.edit_duration.setPlaceholderText("e.g. 40m, 90s, 1h 30m")

    vol_layout = QHBoxLayout()
    vol_layout.addWidget(QLabel("Stage Volume:"))
    self.vol_slider = QSlider(Qt.Orientation.Horizontal)
    self.vol_slider.setRange(0, 100)
    self.vol_slider.setValue(100)
    vol_layout.addWidget(self.vol_slider)

    snd_layout = QHBoxLayout()
    self.edit_sound = QLineEdit()
    self.edit_sound.setPlaceholderText("Sound File / Path")
    btn_browse_stage = QPushButton("Browse")
    btn_browse_stage.clicked.connect(self.browse_stage_sound)

    self.btn_test_sound = QPushButton("Test")
    self.btn_test_sound.clicked.connect(self.toggle_test_sound)

    snd_layout.addWidget(self.edit_sound)
    snd_layout.addWidget(btn_browse_stage)
    snd_layout.addWidget(self.btn_test_sound)

    btn_apply = QPushButton("Apply to Stage")
    btn_apply.clicked.connect(self.apply_stage_edit)

    s_layout = QVBoxLayout()
    s_layout.addWidget(QLabel("Stage Name:"))
    s_layout.addWidget(self.edit_name)
    s_layout.addWidget(QLabel("Duration:"))
    s_layout.addWidget(self.edit_duration)
    s_layout.addLayout(vol_layout)
    s_layout.addWidget(QLabel("Sound File (Overrides common if set):"))
    s_layout.addLayout(snd_layout)
    s_layout.addWidget(btn_apply)
    layout.addLayout(s_layout)

    layout.addWidget(QLabel("--- Global Preset Settings ---"))
    g_layout = QHBoxLayout()
    self.edit_rounds = QLineEdit(
        str(self.config.get_current_preset()["rounds"])
    )
    self.chk_infinite = QCheckBox("Infinite Rounds")
    self.chk_infinite.setChecked(self.config.get_current_preset()["infinite"])

    self.chk_auto = QCheckBox("Auto-start next stage")
    self.chk_auto.setChecked(
        self.config.get_current_preset().get("auto_advance", True)
    )

    g_layout.addWidget(QLabel("Rounds:"))
    g_layout.addWidget(self.edit_rounds)
    g_layout.addWidget(self.chk_infinite)
    g_layout.addWidget(self.chk_auto)
    layout.addLayout(g_layout)

    dir_layout = QHBoxLayout()
    self.edit_sound_dir = QLineEdit(self.config.config["sound_dir"])
    btn_browse_dir = QPushButton("Browse Dir")
    btn_browse_dir.clicked.connect(self.browse_dir)
    dir_layout.addWidget(QLabel("Base Sound Dir:"))
    dir_layout.addWidget(self.edit_sound_dir)
    dir_layout.addWidget(btn_browse_dir)
    layout.addLayout(dir_layout)

    com_layout = QHBoxLayout()
    self.chk_common = QCheckBox("Use Common Sound")
    self.chk_common.setChecked(self.config.config["use_common_sound"])
    self.edit_common = QLineEdit(self.config.config["common_sound_file"])
    btn_browse_com = QPushButton("Browse File")
    btn_browse_com.clicked.connect(self.browse_common)

    com_layout.addWidget(self.chk_common)
    com_layout.addWidget(self.edit_common)
    com_layout.addWidget(btn_browse_com)
    layout.addLayout(com_layout)

    btn_layout = QHBoxLayout()
    btn_save = QPushButton("Save & Apply")
    btn_save.clicked.connect(self.save_config)
    btn_cancel = QPushButton("Cancel")
    btn_cancel.clicked.connect(self.reject)
    btn_layout.addWidget(btn_save)
    btn_layout.addWidget(btn_cancel)
    layout.addLayout(btn_layout)

  def keyPressEvent(self, event):
    if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
      self.save_config()
    elif event.key() == Qt.Key.Key_Escape:
      self.reject()
    else:
      super().keyPressEvent(event)

  def browse_stage_sound(self):
    file, _ = QFileDialog.getOpenFileName(
        self,
        "Select Stage Sound",
        self.config.config["sound_dir"],
        "Audio Files (*.wav *.mp3 *.ogg *.flac)",
    )
    if file:
      self.edit_sound.setText(file)

  def browse_dir(self):
    d = QFileDialog.getExistingDirectory(
        self, "Select Sound Directory", self.config.config["sound_dir"]
    )
    if d:
      self.edit_sound_dir.setText(d)

  def browse_common(self):
    file, _ = QFileDialog.getOpenFileName(
        self,
        "Select Common Sound",
        self.config.config["sound_dir"],
        "Audio Files (*.wav *.mp3 *.ogg *.flac)",
    )
    if file:
      self.edit_common.setText(file)

  def toggle_test_sound(self):
    if (
        self.audio.player.playbackState()
        == QMediaPlayer.PlaybackState.PlayingState
    ):
      self.audio.stop()
    else:
      vol = self.vol_slider.value() / 100.0
      snd = self.edit_sound.text()
      if not snd and self.chk_common.isChecked():
        snd = self.edit_common.text()
      self.audio.play(snd, vol)

  def on_playback_state_changed(self, state):
    if state == QMediaPlayer.PlaybackState.PlayingState:
      self.btn_test_sound.setText("Stop")
    else:
      self.btn_test_sound.setText("Test")

  def change_preset(self, preset_name):
    if not preset_name or preset_name not in self.config.config["presets"]:
      return
    preset = self.config.config["presets"][preset_name]
    self.stages = [s.copy() for s in preset["stages"]]
    self.edit_rounds.setText(str(preset["rounds"]))
    self.chk_infinite.setChecked(preset["infinite"])
    self.chk_auto.setChecked(preset.get("auto_advance", True))
    self.refresh_list()

  def new_preset(self):
    text, ok = QInputDialog.getText(self, "New Preset", "Preset Name:")
    if ok and text:
      self.config.config["presets"][text] = {
          "rounds": 1,
          "infinite": False,
          "auto_advance": True,
          "stages": [{
              "name": "NEW STAGE",
              "duration": 300,
              "sound": "",
              "volume": 1.0,
          }],
      }
      self.preset_combo.addItem(text)
      self.preset_combo.setCurrentText(text)

  def delete_preset(self):
    name = self.preset_combo.currentText()
    if len(self.config.config["presets"]) <= 1:
      QMessageBox.warning(self, "Error", "Cannot delete the last preset.")
      return
    del self.config.config["presets"][name]
    self.preset_combo.removeItem(self.preset_combo.currentIndex())

  def refresh_list(self):
    self.list_widget.clear()
    for s in self.stages:
      self.list_widget.addItem(
          f"{s['name']} - {format_duration(s['duration'])}"
      )

  def load_selected_stage(self):
    idx = self.list_widget.currentRow()
    if idx < 0:
      return
    stage = self.stages[idx]
    self.edit_name.setText(stage["name"])
    self.edit_duration.setText(format_duration(stage["duration"]))
    self.edit_sound.setText(stage.get("sound", ""))
    self.vol_slider.setValue(int(stage.get("volume", 1.0) * 100))

  def apply_stage_edit(self):
    idx = self.list_widget.currentRow()
    if idx < 0:
      return
    dur = parse_duration(self.edit_duration.text())
    if dur <= 0:
      QMessageBox.warning(self, "Error", "Invalid duration.")
      return
    self.stages[idx]["name"] = self.edit_name.text()
    self.stages[idx]["duration"] = dur
    self.stages[idx]["sound"] = self.edit_sound.text()
    self.stages[idx]["volume"] = self.vol_slider.value() / 100.0
    self.refresh_list()
    self.list_widget.setCurrentRow(idx)

  def add_stage(self):
    self.stages.append({"name": "NEW", "duration": 300, "sound": "", "volume": 1.0})
    self.refresh_list()
    self.list_widget.setCurrentRow(len(self.stages) - 1)

  def delete_stage(self):
    if len(self.stages) <= 1:
      QMessageBox.warning(self, "Error", "Cannot delete the last stage.")
      return
    idx = self.list_widget.currentRow()
    if idx >= 0:
      self.stages.pop(idx)
      self.refresh_list()

  def move_up(self):
    idx = self.list_widget.currentRow()
    if idx > 0:
      self.stages[idx], self.stages[idx - 1] = (
          self.stages[idx - 1],
          self.stages[idx],
      )
      self.refresh_list()
      self.list_widget.setCurrentRow(idx - 1)

  def move_down(self):
    idx = self.list_widget.currentRow()
    if idx >= 0 and idx < len(self.stages) - 1:
      self.stages[idx], self.stages[idx + 1] = (
          self.stages[idx + 1],
          self.stages[idx],
      )
      self.refresh_list()
      self.list_widget.setCurrentRow(idx + 1)

  def duplicate_stage(self):
    idx = self.list_widget.currentRow()
    if idx >= 0:
      self.stages.insert(idx + 1, self.stages[idx].copy())
      self.refresh_list()
      self.list_widget.setCurrentRow(idx + 1)

  def save_config(self):
    preset_name = self.preset_combo.currentText()
    try:
      r = int(self.edit_rounds.text())
      if r <= 0:
        raise ValueError
    except ValueError:
      QMessageBox.warning(self, "Error", "Rounds must be a positive integer.")
      return

    self.config.config["sound_dir"] = self.edit_sound_dir.text()
    self.config.config["use_common_sound"] = self.chk_common.isChecked()
    self.config.config["common_sound_file"] = self.edit_common.text()
    self.config.config["current_preset"] = preset_name

    preset = self.config.config["presets"][preset_name]
    preset["rounds"] = r
    preset["infinite"] = self.chk_infinite.isChecked()
    preset["auto_advance"] = self.chk_auto.isChecked()
    preset["stages"] = self.stages

    self.config.save()
    self.accept()

  def closeEvent(self, event):
    self.audio.stop()
    try:
      self.audio.player.playbackStateChanged.disconnect(
          self.on_playback_state_changed
      )
    except TypeError:
      pass
    super().closeEvent(event)


class MainWindow(QMainWindow):

  def __init__(self):
    super().__init__()
    self.config = ConfigManager()
    self.audio = AudioManager(self.config)
    self.engine = TimerEngine(self.config, self.audio)
    self.engine.tick_signal.connect(self.update_time_display)
    self.engine.stage_changed_signal.connect(self.update_stage_display)
    self.engine.state_changed_signal.connect(self.update_state_display)
    self.engine.completed_signal.connect(self.show_completion)

    self.setWindowTitle("Pomodoro Timer")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_icon = os.path.join(script_dir, "pomodro_timer.png")
    if os.path.exists(local_icon):
      app_icon = QIcon(local_icon)
      self.setWindowIcon(app_icon)
      QApplication.instance().setWindowIcon(app_icon)

    self.resize(650, 450)
    self.setup_ui()
    self.setup_shortcuts()
    self.setup_tray()
    self.engine.reset()

  def setup_ui(self):
    central = QWidget()
    self.setCentralWidget(central)
    layout = QVBoxLayout(central)

    self.lbl_stage = QLabel("STAGE")
    self.lbl_stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font = QFont()
    font.setPointSize(36)
    font.setBold(True)
    self.lbl_stage.setFont(font)

    self.lbl_time = QLabel("00:00")
    self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font_time = QFont("Monospace")
    font_time.setPointSize(72)
    font_time.setBold(True)
    self.lbl_time.setFont(font_time)

    self.progress = QSlider(Qt.Orientation.Horizontal)
    self.progress.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.progress.setCursor(Qt.CursorShape.PointingHandCursor)
    self.progress.sliderPressed.connect(self.on_slider_pressed)
    self.progress.sliderReleased.connect(self.on_slider_released)
    self.progress.sliderMoved.connect(self.on_slider_moved)
    self.is_dragging = False

    self.lbl_round = QLabel("Round: 1 / 1")
    self.lbl_round.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font_round = QFont()
    font_round.setPointSize(16)
    self.lbl_round.setFont(font_round)

    self.lbl_next = QLabel("Next: ---")
    self.lbl_next.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(self.lbl_stage)
    layout.addWidget(self.progress)
    layout.addWidget(self.lbl_time)
    layout.addWidget(self.lbl_round)
    layout.addWidget(self.lbl_next)

    btn_layout = QHBoxLayout()

    self.btn_start = QPushButton("Start (Space)")
    self.btn_start.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_start.clicked.connect(self.toggle_timer)

    self.btn_reset = QPushButton("Reset Session (R)")
    self.btn_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_reset.clicked.connect(self.engine.reset)

    self.btn_skip = QPushButton("Skip Stage (S)")
    self.btn_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_skip.clicked.connect(self.engine.skip)

    btn_layout.addWidget(self.btn_start)
    btn_layout.addWidget(self.btn_reset)
    btn_layout.addWidget(self.btn_skip)
    layout.addLayout(btn_layout)

    self.btn_edit = QPushButton("Remake / Edit Timer (E)")
    self.btn_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_edit.clicked.connect(self.open_editor)
    layout.addWidget(self.btn_edit)

    self.btn_tray = QPushButton("Run in Background / Minimize (M)")
    self.btn_tray.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.btn_tray.clicked.connect(self.hide)
    layout.addWidget(self.btn_tray)

  def setup_shortcuts(self):
    QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.toggle_timer)
    QShortcut(QKeySequence(Qt.Key.Key_R), self, activated=self.engine.reset)
    QShortcut(QKeySequence(Qt.Key.Key_S), self, activated=self.engine.skip)
    QShortcut(QKeySequence(Qt.Key.Key_E), self, activated=self.open_editor)
    QShortcut(
        QKeySequence(Qt.Key.Key_F), self, activated=self.toggle_fullscreen
    )
    QShortcut(QKeySequence(Qt.Key.Key_M), self, activated=self.hide)
    QShortcut(
        QKeySequence(Qt.Key.Key_Q), self, activated=QApplication.instance().quit
    )
    QShortcut(
        QKeySequence(Qt.Key.Key_Escape), self, activated=self.exit_fullscreen
    )

  def setup_tray(self):
    QApplication.instance().setQuitOnLastWindowClosed(False)
    self.tray_icon = QSystemTrayIcon(self)
    self.tray_icon.setIcon(self.windowIcon())

    tray_menu = QMenu()
    restore_action = QAction("Show / Hide", self)
    restore_action.triggered.connect(self.toggle_window)
    quit_action = QAction("Quit Application", self)
    quit_action.triggered.connect(QApplication.instance().quit)

    tray_menu.addAction(restore_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)

    self.tray_icon.setContextMenu(tray_menu)
    self.tray_icon.activated.connect(self.tray_activated)
    self.tray_icon.show()

  def on_slider_pressed(self):
    self.is_dragging = True

  def on_slider_moved(self, value):
    total = self.engine.current_stage_duration
    rem = total - value
    self.lbl_time.setText(format_duration(rem))

  def on_slider_released(self):
    self.is_dragging = False
    total = self.engine.current_stage_duration
    new_remaining = total - self.progress.value()
    self.engine.seek(new_remaining)

  def toggle_timer(self):
    if self.engine.state == "RUNNING":
      self.engine.pause()
    else:
      self.engine.start()

  def toggle_fullscreen(self):
    if self.isFullScreen():
      self.showNormal()
    else:
      self.showFullScreen()

  def exit_fullscreen(self):
    if self.isFullScreen():
      self.showNormal()

  def toggle_window(self):
    if self.isHidden():
      self.showNormal()
      self.activateWindow()
    else:
      self.hide()

  def tray_activated(self, reason):
    if reason == QSystemTrayIcon.ActivationReason.Trigger:
      self.toggle_window()

  def open_editor(self):
    self.engine.pause()
    dlg = EditorDialog(self.config, self.audio, self)
    if dlg.exec():
      self.engine.load_preset()

  def update_time_display(self, remaining, total):
    time_str = format_duration(remaining)
    if not self.is_dragging:
      self.lbl_time.setText(time_str)
      self.progress.setRange(0, total)
      self.progress.setValue(total - remaining)

    stage_name = "Timer"
    if self.engine.stages and self.engine.stage_idx < len(self.engine.stages):
      stage_name = self.engine.stages[self.engine.stage_idx]["name"]

    tooltip = f"[{stage_name}] {time_str} left"
    if self.engine.state == "PAUSED":
      tooltip += " (Paused)"
    elif self.engine.state == "WAITING":
      tooltip += " (Waiting)"

    self.tray_icon.setToolTip(tooltip)

  def update_stage_display(self, stage_idx, round_idx):
    if not self.engine.stages:
      return
    stage = self.engine.stages[stage_idx]
    self.lbl_stage.setText(stage["name"])

    r_text = f"Round: {round_idx}"
    if not self.engine.infinite:
      r_text += f" / {self.engine.rounds}"
    else:
      r_text += " (Infinite)"
    self.lbl_round.setText(r_text)

    next_idx = stage_idx + 1
    if next_idx < len(self.engine.stages):
      self.lbl_next.setText(f"Next: {self.engine.stages[next_idx]['name']}")
    else:
      if not self.engine.infinite and round_idx >= self.engine.rounds:
        self.lbl_next.setText("Next: Finish")
      else:
        self.lbl_next.setText(f"Next: {self.engine.stages[0]['name']}")

  def update_state_display(self, state):
    if state == "RUNNING":
      self.btn_start.setText("Pause (Space)")
    elif state == "PAUSED":
      self.btn_start.setText("Resume (Space)")
    elif state == "WAITING":
      self.btn_start.setText("Start Next Stage (Space)")
    else:
      self.btn_start.setText("Start (Space)")

  def show_completion(self, elapsed):
    self.lbl_stage.setText("TIMER COMPLETE")
    self.lbl_time.setText("00:00")
    if not self.is_dragging:
      self.progress.setValue(self.progress.maximum())
    self.lbl_round.setText(f"Total time: {format_duration(elapsed)}")
    self.lbl_next.setText("")
    self.tray_icon.setToolTip("Timer Complete")


if __name__ == "__main__":
  os.makedirs(CONFIG_DIR, exist_ok=True)
  lock_file = os.path.join(CONFIG_DIR, "pomodoro_timer.lock")
  pid_file = os.path.join(CONFIG_DIR, "pomodoro_timer.pid")

  lock_fp = open(lock_file, "w")
  try:
    fcntl.lockf(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with open(pid_file, "w") as f:
      f.write(str(os.getpid()))
  except IOError:
    try:
      with open(pid_file, "r") as f:
        pid = int(f.read().strip())
      os.kill(pid, signal.SIGUSR1)
    except Exception:
      pass
    sys.exit(0)

  app = QApplication(sys.argv)
  app.setApplicationName("Pomodoro Timer")
  app.setDesktopFileName("pomodro-timer.desktop")
  window = MainWindow()

  def handle_toggle(signum, frame):
    QTimer.singleShot(0, window.toggle_window)

  signal.signal(signal.SIGUSR1, handle_toggle)

  wakeup_timer = QTimer()
  wakeup_timer.timeout.connect(lambda: None)
  wakeup_timer.start(100)

  window.show()
  sys.exit(app.exec())
