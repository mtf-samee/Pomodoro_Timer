#!/usr/bin/env python3
import sys
import os
import json
import time
import re
import shutil
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QDialog, 
                             QListWidget, QListWidgetItem, QLineEdit, 
                             QFileDialog, QMessageBox, QCheckBox, QInputDialog, QComboBox)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QUrl
from PyQt6.QtGui import QShortcut, QKeySequence, QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

CONFIG_DIR = os.path.expanduser("~/.config/study_timer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
BACKUP_FILE = os.path.join(CONFIG_DIR, "config.json.bak")

def parse_duration(text):
    text = text.lower().strip()
    if not text:
        return 0
    total_seconds = 0
    matches = re.findall(r'(\d+)\s*([hms])', text)
    if not matches:
        try:
            return int(text)
        except ValueError:
            return 0
    for val, unit in matches:
        if unit == 'h': total_seconds += int(val) * 3600
        elif unit == 'm': total_seconds += int(val) * 60
        elif unit == 's': total_seconds += int(val)
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
            "sound_dir": os.path.expanduser("~/Music"),
            "use_common_sound": False,
            "common_sound_file": "",
            "presets": {
                "Default": {
                    "rounds": 1,
                    "infinite": False,
                    "stages": [{"name": "WORK", "duration": 1500, "sound": ""}]
                }
            },
            "current_preset": "Default"
        }
        self.load()

    def load(self):
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
        if not os.path.exists(CONFIG_FILE):
            self.save()
            return
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                self.config.update(data)
                if self.config["current_preset"] not in self.config["presets"]:
                    self.config["current_preset"] = list(self.config["presets"].keys())[0]
        except Exception as e:
            print(f"Error loading config: {e}. Attempting backup recovery.")
            if os.path.exists(BACKUP_FILE):
                try:
                    with open(BACKUP_FILE, 'r') as f:
                        self.config.update(json.load(f))
                except Exception:
                    pass

    def save(self):
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
        if os.path.exists(CONFIG_FILE):
            shutil.copy(CONFIG_FILE, BACKUP_FILE)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_current_preset(self):
        return self.config["presets"][self.config["current_preset"]]

class AudioManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

    def play(self, sound_file):
        if not sound_file:
            return
        path = os.path.join(self.config.config["sound_dir"], sound_file)
        if not os.path.exists(path):
            print(f"Sound file not found: {path}")
            return
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def stop(self):
        self.player.stop()

class NotificationManager:
    @staticmethod
    def send(title, message):
        try:
            subprocess.Popen(['notify-send', '-a', 'Study Timer', title, message])
        except FileNotFoundError:
            pass

class TimerEngine(QObject):
    tick_signal = pyqtSignal(int)
    stage_changed_signal = pyqtSignal(int, int)
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
        self.target_time = 0
        self.total_elapsed = 0
        self.stages = []
        self.rounds = 1
        self.infinite = False
        
        self.load_preset()

    def load_preset(self):
        preset = self.config_manager.get_current_preset()
        self.stages = preset["stages"]
        self.rounds = preset["rounds"]
        self.infinite = preset["infinite"]
        self.reset()

    def start(self):
        if not self.stages: return
        if self.state == "STOPPED":
            self.remaining = self.stages[self.stage_idx]["duration"]
        if self.state != "RUNNING":
            self.target_time = time.monotonic() + self.remaining
            self.state = "RUNNING"
            self.timer.start(100)

    def pause(self):
        if self.state == "RUNNING":
            self.remaining = self.target_time - time.monotonic()
            self.state = "PAUSED"
            self.timer.stop()

    def reset(self):
        self.state = "STOPPED"
        self.timer.stop()
        self.stage_idx = 0
        self.round_idx = 1
        self.total_elapsed = 0
        if self.stages:
            self.remaining = self.stages[0]["duration"]
        else:
            self.remaining = 0
        self.tick_signal.emit(self.remaining)
        self.stage_changed_signal.emit(self.stage_idx, self.round_idx)

    def skip(self):
        if self.state == "STOPPED":
            return
        self.next_stage(skipped=True)

    def update(self):
        if self.state != "RUNNING": return
        now = time.monotonic()
        rem = int(self.target_time - now)
        if rem <= 0:
            self.total_elapsed += self.stages[self.stage_idx]["duration"]
            self.next_stage(skipped=False)
        else:
            if rem != int(self.remaining):
                self.remaining = rem
                self.tick_signal.emit(rem)

    def next_stage(self, skipped=False):
        if not skipped:
            current_stage = self.stages[self.stage_idx]
            sound = self.config_manager.config["common_sound_file"] if self.config_manager.config["use_common_sound"] else current_stage["sound"]
            self.audio.play(sound)
            NotificationManager.send("Stage Complete", current_stage["name"])

        self.stage_idx += 1
        
        if self.stage_idx >= len(self.stages):
            self.stage_idx = 0
            self.round_idx += 1
            if not self.infinite and self.round_idx > self.rounds:
                self.state = "STOPPED"
                self.timer.stop()
                NotificationManager.send("Timer Complete", "All rounds finished.")
                self.completed_signal.emit(self.total_elapsed)
                return

        self.remaining = self.stages[self.stage_idx]["duration"]
        self.target_time = time.monotonic() + self.remaining
        if not skipped:
            NotificationManager.send("Stage Started", self.stages[self.stage_idx]["name"])
            
        if self.state == "PAUSED":
            self.tick_signal.emit(self.remaining)
            
        self.stage_changed_signal.emit(self.stage_idx, self.round_idx)

class EditorDialog(QDialog):
    def __init__(self, config_manager, audio_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.audio = audio_manager
        self.setWindowTitle("Edit Timer Configuration")
        self.setMinimumSize(500, 500)
        self.stages = [s.copy() for s in self.config.get_current_preset()["stages"]]
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
        self.edit_sound = QLineEdit()
        
        btn_apply = QPushButton("Apply to Stage")
        btn_apply.clicked.connect(self.apply_stage_edit)
        
        btn_test_sound = QPushButton("Test Sound")
        btn_test_sound.clicked.connect(lambda: self.audio.play(self.edit_sound.text()))

        s_layout = QVBoxLayout()
        s_layout.addWidget(QLabel("Stage Name:"))
        s_layout.addWidget(self.edit_name)
        s_layout.addWidget(QLabel("Duration:"))
        s_layout.addWidget(self.edit_duration)
        s_layout.addWidget(QLabel("Sound File (in sound dir):"))
        
        snd_hbox = QHBoxLayout()
        snd_hbox.addWidget(self.edit_sound)
        snd_hbox.addWidget(btn_test_sound)
        s_layout.addLayout(snd_hbox)
        s_layout.addWidget(btn_apply)
        layout.addLayout(s_layout)

        layout.addWidget(QLabel("--- Global Settings ---"))
        g_layout = QHBoxLayout()
        self.edit_rounds = QLineEdit(str(self.config.get_current_preset()["rounds"]))
        self.chk_infinite = QCheckBox("Infinite Rounds")
        self.chk_infinite.setChecked(self.config.get_current_preset()["infinite"])
        g_layout.addWidget(QLabel("Rounds:"))
        g_layout.addWidget(self.edit_rounds)
        g_layout.addWidget(self.chk_infinite)
        layout.addLayout(g_layout)

        dir_layout = QHBoxLayout()
        self.edit_sound_dir = QLineEdit(self.config.config["sound_dir"])
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.browse_dir)
        dir_layout.addWidget(QLabel("Sound Dir:"))
        dir_layout.addWidget(self.edit_sound_dir)
        dir_layout.addWidget(btn_browse)
        layout.addLayout(dir_layout)

        com_layout = QHBoxLayout()
        self.chk_common = QCheckBox("Use Common Sound")
        self.chk_common.setChecked(self.config.config["use_common_sound"])
        self.edit_common = QLineEdit(self.config.config["common_sound_file"])
        btn_test_common = QPushButton("Test Common")
        btn_test_common.clicked.connect(lambda: self.audio.play(self.edit_common.text()))
        com_layout.addWidget(self.chk_common)
        com_layout.addWidget(self.edit_common)
        com_layout.addWidget(btn_test_common)
        layout.addLayout(com_layout)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save & Apply")
        btn_save.clicked.connect(self.save_config)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def change_preset(self, preset_name):
        if not preset_name or preset_name not in self.config.config["presets"]: return
        preset = self.config.config["presets"][preset_name]
        self.stages = [s.copy() for s in preset["stages"]]
        self.edit_rounds.setText(str(preset["rounds"]))
        self.chk_infinite.setChecked(preset["infinite"])
        self.refresh_list()

    def new_preset(self):
        text, ok = QInputDialog.getText(self, "New Preset", "Preset Name:")
        if ok and text:
            self.config.config["presets"][text] = {
                "rounds": 1,
                "infinite": False,
                "stages": [{"name": "NEW STAGE", "duration": 300, "sound": ""}]
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
            self.list_widget.addItem(f"{s['name']} - {format_duration(s['duration'])}")

    def load_selected_stage(self):
        idx = self.list_widget.currentRow()
        if idx < 0: return
        stage = self.stages[idx]
        self.edit_name.setText(stage["name"])
        self.edit_duration.setText(format_duration(stage["duration"]))
        self.edit_sound.setText(stage["sound"])

    def apply_stage_edit(self):
        idx = self.list_widget.currentRow()
        if idx < 0: return
        dur = parse_duration(self.edit_duration.text())
        if dur <= 0:
            QMessageBox.warning(self, "Error", "Invalid duration.")
            return
        self.stages[idx]["name"] = self.edit_name.text()
        self.stages[idx]["duration"] = dur
        self.stages[idx]["sound"] = self.edit_sound.text()
        self.refresh_list()
        self.list_widget.setCurrentRow(idx)

    def add_stage(self):
        self.stages.append({"name": "NEW", "duration": 300, "sound": ""})
        self.refresh_list()
        self.list_widget.setCurrentRow(len(self.stages)-1)

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
            self.stages[idx], self.stages[idx-1] = self.stages[idx-1], self.stages[idx]
            self.refresh_list()
            self.list_widget.setCurrentRow(idx-1)

    def move_down(self):
        idx = self.list_widget.currentRow()
        if idx >= 0 and idx < len(self.stages)-1:
            self.stages[idx], self.stages[idx+1] = self.stages[idx+1], self.stages[idx]
            self.refresh_list()
            self.list_widget.setCurrentRow(idx+1)

    def duplicate_stage(self):
        idx = self.list_widget.currentRow()
        if idx >= 0:
            self.stages.insert(idx+1, self.stages[idx].copy())
            self.refresh_list()
            self.list_widget.setCurrentRow(idx+1)

    def browse_dir(self):
        dir = QFileDialog.getExistingDirectory(self, "Select Sound Directory")
        if dir: self.edit_sound_dir.setText(dir)

    def save_config(self):
        preset_name = self.preset_combo.currentText()
        try:
            r = int(self.edit_rounds.text())
            if r <= 0: raise ValueError
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
        preset["stages"] = self.stages
        
        self.config.save()
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.audio = AudioManager(self.config)
        self.engine = TimerEngine(self.config, self.audio)
        self.engine.tick_signal.connect(self.update_time_display)
        self.engine.stage_changed_signal.connect(self.update_stage_display)
        self.engine.completed_signal.connect(self.show_completion)

        self.setup_ui()
        self.setup_shortcuts()
        self.engine.reset()

    def setup_ui(self):
        self.setWindowTitle("Study Timer")
        self.resize(600, 400)
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

        self.lbl_round = QLabel("Round: 1 / 1")
        self.lbl_round.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font_round = QFont()
        font_round.setPointSize(16)
        self.lbl_round.setFont(font_round)

        self.lbl_next = QLabel("Next: ---")
        self.lbl_next.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_stage)
        layout.addWidget(self.lbl_time)
        layout.addWidget(self.lbl_round)
        layout.addWidget(self.lbl_next)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start/Pause")
        self.btn_start.clicked.connect(self.toggle_timer)
        self.btn_reset = QPushButton("Reset Session")
        self.btn_reset.clicked.connect(self.engine.reset)
        self.btn_skip = QPushButton("Skip Stage")
        self.btn_skip.clicked.connect(self.engine.skip)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_skip)
        layout.addLayout(btn_layout)

        self.btn_edit = QPushButton("Remake / Edit Timer")
        self.btn_edit.clicked.connect(self.open_editor)
        layout.addWidget(self.btn_edit)

    def setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self.toggle_timer)
        QShortcut(QKeySequence(Qt.Key.Key_R), self).activated.connect(self.engine.reset)
        QShortcut(QKeySequence(Qt.Key.Key_S), self).activated.connect(self.engine.skip)
        QShortcut(QKeySequence(Qt.Key.Key_E), self).activated.connect(self.open_editor)
        QShortcut(QKeySequence(Qt.Key.Key_F), self).activated.connect(self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.showNormal)

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

    def open_editor(self):
        self.engine.pause()
        dlg = EditorDialog(self.config, self.audio, self)
        if dlg.exec():
            self.engine.load_preset()

    def update_time_display(self, seconds):
        self.lbl_time.setText(format_duration(seconds))

    def update_stage_display(self, stage_idx, round_idx):
        if not self.engine.stages: return
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

    def show_completion(self, elapsed):
        self.lbl_stage.setText("TIMER COMPLETE")
        self.lbl_time.setText("00:00")
        self.lbl_round.setText(f"Total time: {format_duration(elapsed)}")
        self.lbl_next.setText("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Study Timer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
