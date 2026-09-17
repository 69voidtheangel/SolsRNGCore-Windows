from __future__ import annotations
import os
import queue
import threading

import sys
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from solsrng_core.antiafk import AntiAFKController, WindowError
from solsrng_core.config import (
    BIOMES,
    EVENT_BIOMES,
    NORMAL_BIOMES,
    RARE_LIST,
    AppConfig,
    WebhookProfile,
    load_config,
    save_config,
)
from solsrng_core.discord import DiscordWebhook
from solsrng_core.automation.ui import AutomationPage
from solsrng_core.logwatcher import SoberBiomeWatcher
from solsrng_core.platform.windows.environment import detect_environment
from .themes import THEMES

ROOT = Path(__file__).resolve().parents[3]
LOGO = ROOT / "assets" / "solsrng_core_logo.svg"


class _PriorityGate:
    """
    Shared execution gate for Anti-AFK and Automation.

    Anti-AFK is the highest-priority task.

    Automation waits whenever Anti-AFK is already running
    or waiting for its turn.

    An automation item that already owns the gate is allowed
    to finish its complete cycle safely. Anti-AFK gets the
    next available turn before another automation attempt.
    """

    def __init__(self):
        self._condition = threading.Condition()
        self._active = False
        self._afk_waiting = False

    def enter_afk(self):
        with self._condition:
            self._afk_waiting = True

            while self._active:
                self._condition.wait()

            self._afk_waiting = False
            self._active = True

    def enter_automation(self):
        with self._condition:
            while (
                self._active
                or self._afk_waiting
            ):
                self._condition.wait()

            self._active = True

    def leave(self):
        with self._condition:
            self._active = False
            self._condition.notify_all()


class _AntiAFKSignals(QObject):
    log_message = Signal(str)


class _BiomeWatcherSignals(QObject):
    log_message = Signal(str)
    biome_appeared = Signal(str)
    biome_ended = Signal(str)


class SidebarButton(QPushButton):
    def __init__(self, text: str, page: int):
        super().__init__(text)
        self.page = page
        self.setCheckable(True)
        self.setProperty("navButton", True)


class _DiscordWorker:
    def __init__(self, log_emit):
        self._log_emit = log_emit
        self._queue = queue.Queue(maxsize=32)
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="SolsRNG-DiscordWorker",
            daemon=True,
        )
        self._thread.start()

    def submit(self, profile, method_name, biome=None):
        try:
            self._queue.put_nowait(
                (profile, method_name, biome)
            )
            return True
        except queue.Full:
            self._log_emit(
                "Discord queue full; notification dropped"
            )
            return False

    def _run(self):
        while not self._stop.is_set():
            try:
                profile, method_name, biome = self._queue.get(
                    timeout=0.5
                )
            except queue.Empty:
                continue

            try:
                webhook = DiscordWebhook(profile)

                if method_name == "send_biome_appeared":
                    result = webhook.send_biome_appeared(biome)

                elif method_name == "send_biome_ended":
                    result = webhook.send_biome_ended(biome)

                elif method_name == "send_unknown_biome":
                    result = webhook.send_unknown_biome(biome)

                else:
                    self._log_emit(
                        f"Unknown Discord method: {method_name}"
                    )
                    continue

                status = (
                    "sent"
                    if result.ok
                    else f"failed: {result.error or result.status or 'unknown error'}"
                )

                suffix = f" {biome}" if biome else ""

                self._log_emit(
                    f"Discord {method_name}{suffix}: {status}"
                )

            except Exception as exc:
                self._log_emit(
                    f"Discord worker error: {exc}"
                )
            finally:
                self._queue.task_done()

    def stop(self):
        self._stop.set()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Background threads never write directly into QPlainTextEdit.
        # Messages are buffered and rendered by the Qt thread.
        self._log_queue = queue.Queue(maxsize=300)
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setInterval(100)
        self._log_flush_timer.timeout.connect(self._flush_log_queue)
        self._log_flush_timer.start()

        self.config: AppConfig = load_config()
        self.afk: AntiAFKController | None = None
        self._priority_gate = _PriorityGate()

        self._biome_signals = _BiomeWatcherSignals(self)
        self._antiafk_signals = _AntiAFKSignals(self)
        self._antiafk_signals.log_message.connect(self.log)
        self._discord_worker = _DiscordWorker(self._biome_signals.log_message.emit)
        self._biome_signals.log_message.connect(
            self.log
        )
        self._biome_signals.biome_appeared.connect(
            self._biome_detected
        )
        self._biome_signals.biome_ended.connect(
            self._biome_ended
        )

        self.biome_watcher = SoberBiomeWatcher(
            self._biome_signals.biome_appeared.emit,
            self._biome_signals.log_message.emit,
            biome_ended_callback=self._biome_signals.biome_ended.emit,
        )
        self._loading = True
        self._buttons: list[SidebarButton] = []
        self._loaded_profile_index = 0

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self._autosave)

        self.setWindowTitle("Sol's RNG Core")
        self.setWindowIcon(QIcon(str(LOGO)))
        self.resize(1120, 760)
        self.setMinimumSize(980, 680)

        self._build()
        self._apply_theme(self.config.theme, autosave=False)
        self._loading = False

        # Start external/background services only after the window has
        # entered the Qt event loop. This prevents network I/O or log
        # watcher callbacks from blocking GUI construction.
        QTimer.singleShot(0, self._start_background_services)

    # ---------- background startup ----------

    def _start_background_services(self):
        try:
            self.biome_watcher.start()
        except Exception as exc:
            self.log(f"Biome watcher startup error: {exc}")

        threading.Thread(
            target=self._discord_started_background,
            name="SolsRNG-Discord-Startup",
            daemon=True,
        ).start()

    def _discord_started_background(self):
        try:
            self._broadcast_discord_event("send_started")
        except Exception as exc:
            self._biome_signals.log_message.emit(
                f"Discord startup notification error: {exc}"
            )

    # ---------- window / layout ----------

    def _build(self):
        outer = QWidget()
        root = QHBoxLayout(outer)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        root.addWidget(self._sidebar(), 0)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._dashboard_page())
        self.pages.addWidget(self._discord_page())
        self.pages.addWidget(self._biomes_page())
        self.pages.addWidget(self._settings_page())
        self.automation_page = AutomationPage(
            self,
            priority_gate=self._priority_gate,
        )
        self.pages.addWidget(self.automation_page)
        root.addWidget(self.pages, 1)

        self.setCentralWidget(outer)
        self._set_page(0)

    def _sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidebar")
        panel.setFixedWidth(220)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(8)

        brand = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(
            QPixmap(str(LOGO)).scaled(
                46,
                46,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        brand.addWidget(icon)

        text = QLabel(
            "<b>Sol's RNG Core</b><br>"
            "<span class='muted'>Detect • Notify • Automate</span>"
        )
        text.setTextFormat(Qt.TextFormat.RichText)
        brand.addWidget(text)
        layout.addLayout(brand)

        status = QLabel("●  Core online")
        status.setObjectName("statusPill")
        layout.addWidget(status)
        layout.addSpacing(12)

        names = [
            "◈  Dashboard",
            "◎  Discord",
            "✦  Biomes",
            "⚙  Settings",
            "⚡  Automation",
        ]
        for index, name in enumerate(names):
            button = SidebarButton(name, index)
            button.clicked.connect(
                lambda _checked=False, i=index: self._set_page(i)
            )
            self._buttons.append(button)
            layout.addWidget(button)

        layout.addStretch()

        footer = QLabel(
            "Moonlit edition\n"
            "Profile settings save automatically."
        )
        footer.setObjectName("sidebarFooter")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        return panel

    def _set_page(self, index: int):
        if index < 0 or index >= self.pages.count():
            return
        if not self._loading:
            self._collect()
            self._save_now()
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self._buttons):
            button.setChecked(i == index)

    def _brand_header(self, title: str, subtitle: str) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 4)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return box

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("cardTitle")
            layout.addWidget(label)
        return frame, layout

    # ---------- dashboard ----------

    def _dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.addWidget(
            self._brand_header(
                "Dashboard",
                "Keep the game focused, automate Anti-AFK, and test your selected Discord profile.",
            )
        )

        top = QHBoxLayout()
        top.setSpacing(14)

        afk_card, afk_layout = self._card("Anti-AFK")
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status"))
        self.afk_status = QLabel("STOPPED")
        self.afk_status.setObjectName("statusValue")
        status_row.addWidget(self.afk_status)
        status_row.addStretch()
        afk_layout.addLayout(status_row)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(8)

        for label, fn, row, col in [
            ("Start", self.start_afk, 0, 0),
            ("Stop", self.stop_afk, 0, 1),
        ]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            buttons.addWidget(b, row, col)
        afk_layout.addLayout(buttons)
        top.addWidget(afk_card, 1)

        profile_card, profile_layout = self._card("Selected Discord Profile")

        profile_layout.addWidget(
            QLabel("Test Webhook Target")
        )

        self.dashboard_profile_combo = QComboBox()
        self.dashboard_profile_combo.setToolTip(
            "Choose which configured Discord server/profile receives the test."
        )
        self.dashboard_profile_combo.currentIndexChanged.connect(
            self._dashboard_profile_changed
        )
        profile_layout.addWidget(
            self.dashboard_profile_combo
        )

        dashboard_automation_button = QPushButton(
            "Open Automation"
        )
        dashboard_automation_button.setToolTip(
            "Configure the Sol's RNG item automation."
        )
        dashboard_automation_button.clicked.connect(
            lambda: self._set_page(4)
        )
        profile_layout.addWidget(
            dashboard_automation_button
        )

        self.dashboard_profile = QLabel("Main Server")
        self.dashboard_profile.setObjectName("metricValue")
        profile_layout.addWidget(
            self.dashboard_profile
        )

        self.dashboard_webhook = QLabel(
            "Webhook not configured"
        )
        self.dashboard_webhook.setWordWrap(True)
        profile_layout.addWidget(
            self.dashboard_webhook
        )

        test = QPushButton(
            "Send Test Webhook"
        )
        test.setToolTip(
            "Send a test only to the selected Discord profile."
        )
        test.clicked.connect(
            self.test_webhook
        )

        save = QPushButton(
            "Save Everything"
        )
        save.clicked.connect(
            self.save_all
        )

        profile_layout.addWidget(test)
        profile_layout.addWidget(save)

        top.addWidget(
            profile_card,
            1,
        )
        layout.addLayout(top)

        log_card, log_layout = self._card("Activity")
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(100)
        self.log_box.setUndoRedoEnabled(False)
        self.log_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        log_layout.addWidget(self.log_box)
        layout.addWidget(log_card, 1)
        return page

    # ---------- discord ----------

    def _discord_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.addWidget(
            self._brand_header(
                "Discord",
                "Each profile has its own webhook, Roblox private-server link, notification rules, images, and biome roles. All enabled profiles run simultaneously.",
            )
        )

        profile_card, profile_layout = self._card("Webhook Profiles")
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile"))
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        profile_row.addWidget(self.profile_combo, 1)

        for label, fn in [
            ("+ Add", self._add_profile),
            ("Rename", self._rename_profile),
            ("Remove", self._remove_profile),
        ]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            profile_row.addWidget(b)

        profile_layout.addLayout(profile_row)
        layout.addWidget(profile_card)

        details_card, details_layout = self._card("Profile Settings")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.webhook_enabled = QCheckBox("Enabled")
        self.webhook_url = QLineEdit()
        self.webhook_url.setPlaceholderText("https://discord.com/api/webhooks/...")
        self.private_server = QLineEdit()
        self.private_server.setPlaceholderText("Optional Roblox private-server URL")
        self.image_dir = QLineEdit()
        self.image_dir.setPlaceholderText("library/biomes")
        self.rare_fallback = QCheckBox("Rare biome end: role ping, or @everyone when no role is set")

        self.webhook_url.textChanged.connect(
            lambda value: self._profile_field_changed("url", value)
        )
        self.private_server.textChanged.connect(
            lambda value: self._profile_field_changed(
                "roblox_private_server_url", value
            )
        )
        self.image_dir.textChanged.connect(
            lambda value: self._profile_field_changed(
                "biome_image_dir", value
            )
        )
        self.webhook_enabled.toggled.connect(
            lambda value: self._profile_field_changed("enabled", value)
        )
        self.rare_fallback.toggled.connect(
            lambda value: self._profile_field_changed(
                "rare_everyone_fallback", value
            )
        )

        grid.addWidget(self.webhook_enabled, 0, 0)
        grid.addWidget(self.webhook_url, 0, 1, 1, 2)
        grid.addWidget(QLabel("Roblox private server"), 1, 0)
        grid.addWidget(self.private_server, 1, 1, 1, 2)
        grid.addWidget(QLabel("Biome images"), 2, 0)
        grid.addWidget(self.image_dir, 2, 1)
        grid.addWidget(self.rare_fallback, 2, 2)

        details_layout.addLayout(grid)
        layout.addWidget(details_card)

        roles_card, roles_layout = self._card("Per-Biome Roles")
        hint = QLabel(
            "One Discord role per biome. Put the numeric role ID in the middle column. "
            "There is no random role mode."
        )
        hint.setObjectName("cardHint")
        hint.setWordWrap(True)
        roles_layout.addWidget(hint)

        self.roles_table = QTableWidget(len(BIOMES), 3)
        self.roles_table.setObjectName("rolesTable")
        self.roles_table.setHorizontalHeaderLabels([
            "Biome",
            "Discord Role ID",
            "Notify",
        ])
        self.roles_table.setAlternatingRowColors(True)
        self.roles_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.roles_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.roles_table.verticalHeader().setVisible(False)
        self.roles_table.horizontalHeader().setStretchLastSection(False)
        self.roles_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.roles_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.roles_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.roles_table.itemChanged.connect(self._roles_changed)
        roles_layout.addWidget(self.roles_table, 1)

        controls = QHBoxLayout()
        for label, biomes in [
            ("Enable Normal", NORMAL_BIOMES),
            ("Enable Events", EVENT_BIOMES),
            ("Enable Rare", RARE_LIST),
            ("Enable All", BIOMES),
        ]:
            b = QPushButton(label)
            b.clicked.connect(
                lambda _checked=False, names=biomes: self._set_biomes(names)
            )
            controls.addWidget(b)
        controls.addStretch()
        save = QPushButton("Save Profile")
        save.clicked.connect(self.save_all)
        controls.addWidget(save)
        roles_layout.addLayout(controls)

        layout.addWidget(roles_card, 1)

        self._refresh_profiles()
        return page

    def _refresh_profiles(self):
        if not hasattr(self, "profile_combo") or not self.config.profiles:
            return

        index = max(
            0,
            min(
                self.config.active_profile,
                len(self.config.profiles) - 1,
            ),
        )

        self.profile_combo.blockSignals(True)
        try:
            self.profile_combo.clear()

            for profile in self.config.profiles:
                self.profile_combo.addItem(profile.name)

            self.profile_combo.setCurrentIndex(index)
        finally:
            self.profile_combo.blockSignals(False)

        self.config.active_profile = index
        self._loaded_profile_index = index
        self._load_profile_fields()

    def _current_profile(self) -> WebhookProfile:
        index = max(
            0,
            min(
                self._loaded_profile_index,
                len(self.config.profiles) - 1,
            ),
        )

        self._loaded_profile_index = index
        return self.config.profiles[index]

    def _load_profile_fields(self):
        if not hasattr(self, "profile_combo"):
            return

        index = self._loaded_profile_index

        if index < 0 or index >= len(self.config.profiles):
            return

        profile = self.config.profiles[index]

        self._loading = True

        widgets = [
            self.webhook_enabled,
            self.webhook_url,
            self.private_server,
            self.image_dir,
            self.rare_fallback,
            self.roles_table,
        ]

        try:
            for widget in widgets:
                widget.blockSignals(True)

            self.webhook_enabled.setChecked(bool(profile.enabled))
            self.webhook_url.setText(str(profile.url or ""))
            self.private_server.setText(
                str(profile.roblox_private_server_url or "")
            )
            self.image_dir.setText(
                str(profile.biome_image_dir or "library/biomes")
            )
            self.rare_fallback.setChecked(
                bool(profile.rare_everyone_fallback)
            )

            notify = set(profile.notify_biomes)

            self.roles_table.setRowCount(len(BIOMES))

            for row, biome in enumerate(BIOMES):
                biome_item = QTableWidgetItem(biome)
                biome_item.setFlags(
                    biome_item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                )
                self.roles_table.setItem(row, 0, biome_item)

                role_item = QTableWidgetItem(
                    profile.biome_roles.get(biome, "")
                )
                role_item.setData(
                    Qt.ItemDataRole.UserRole,
                    "role ID",
                )
                role_item.setToolTip(
                    "Paste the numeric Discord role ID"
                )
                self.roles_table.setItem(row, 1, role_item)

                notify_item = QTableWidgetItem()
                notify_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                notify_item.setCheckState(
                    Qt.CheckState.Checked
                    if biome in notify
                    else Qt.CheckState.Unchecked
                )
                self.roles_table.setItem(row, 2, notify_item)

        finally:
            for widget in widgets:
                widget.blockSignals(False)

            self._loading = False

        self._update_dashboard_profile()

    def _profile_field_changed(self, field: str, value):
        if self._loading:
            return

        index = self._loaded_profile_index

        if index < 0 or index >= len(self.config.profiles):
            return

        setattr(self.config.profiles[index], field, value)
        self.schedule_save()

    def _save_profile_fields(self, profile=None):
        if profile is None:
            profile = self._current_profile()

        profile.enabled = self.webhook_enabled.isChecked()
        profile.url = self.webhook_url.text().strip()
        profile.roblox_private_server_url = (
            self.private_server.text().strip()
        )
        profile.biome_image_dir = (
            self.image_dir.text().strip()
            or "library/biomes"
        )
        profile.rare_everyone_fallback = (
            self.rare_fallback.isChecked()
        )

        profile.notify_biomes = []
        profile.biome_roles = {
            biome: ""
            for biome in BIOMES
        }

        for row, biome in enumerate(BIOMES):
            role_item = self.roles_table.item(row, 1)
            notify_item = self.roles_table.item(row, 2)

            if role_item is not None:
                profile.biome_roles[biome] = (
                    role_item.text().strip()
                )

            if (
                notify_item is not None
                and notify_item.checkState()
                == Qt.CheckState.Checked
            ):
                profile.notify_biomes.append(biome)

    def _profile_changed(self, index: int):
        if self._loading or index < 0:
            return

        if index >= len(self.config.profiles):
            return

        old_index = self._loaded_profile_index

        if 0 <= old_index < len(self.config.profiles):
            self._save_profile_fields(
                self.config.profiles[old_index]
            )

        self.config.active_profile = index
        self._loaded_profile_index = index

        self._load_profile_fields()
        self._save_now()

    def _add_profile(self):
        # Save the current profile before creating another
        self._save_profile_fields()

        number = len(self.config.profiles) + 1

        new_profile = WebhookProfile(
            name=f"Server {number}",
            enabled=False,
            url="",
            roblox_private_server_url="",
            biome_image_dir="library/biomes",
        )

        self.config.profiles.append(new_profile)
        self.config.active_profile = len(self.config.profiles) - 1

        self._refresh_profiles()
        self._load_profile_fields()
        self._save_now()

    def _remove_profile(self):
        if len(self.config.profiles) <= 1:
            QMessageBox.information(
                self,
                "Webhook Profiles",
                "Keep at least one profile.",
            )
            return
        self._save_profile_fields()
        index = self.profile_combo.currentIndex()
        self.config.profiles.pop(index)
        self.config.active_profile = max(
            0,
            min(index, len(self.config.profiles) - 1),
        )
        self._refresh_profiles()
        self._save_now()

    def _rename_profile(self):
        profile = self._current_profile()
        name, ok = QInputDialog.getText(
            self,
            "Rename Profile",
            "Profile name:",
            text=profile.name,
        )
        if ok and name.strip():
            profile.name = name.strip()
            self._refresh_profiles()
            self.profile_combo.setCurrentIndex(self.config.active_profile)
            self._save_now()

    def _roles_changed(self, _item: QTableWidgetItem):
        if not self._loading:
            self._save_profile_fields()
            self.schedule_save()

    def _set_biomes(self, names: list[str]):
        for row, biome in enumerate(BIOMES):
            item = self.roles_table.item(row, 2)
            if item is None:
                continue
            item.setCheckState(
                Qt.CheckState.Checked
                if biome in names
                else Qt.CheckState.Unchecked
            )
        self._save_profile_fields()
        self._save_now()

    # ---------- biomes ----------

    def _biomes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.addWidget(
            self._brand_header(
                "Biome Notifications",
                "Control which events the selected Discord profile receives. All enabled profiles run simultaneously.",
            )
        )

        card, card_layout = self._card("Selected Profile Biomes")
        self.biome_list = QListWidget()
        self._biome_items: dict[str, QListWidgetItem] = {}

        groups = [
            ("NORMAL", NORMAL_BIOMES),
            ("EVENT", EVENT_BIOMES),
            ("RARE", RARE_LIST),
        ]
        selected = set(self._current_profile().notify_biomes)

        for heading, names in groups:
            header = QListWidgetItem(f"━━ {heading} BIOMES ━━")
            header.setFlags(
                header.flags()
                & ~Qt.ItemFlag.ItemIsSelectable
                & ~Qt.ItemFlag.ItemIsEnabled
            )
            self.biome_list.addItem(header)
            for biome in names:
                item = QListWidgetItem(biome)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if biome in selected
                    else Qt.CheckState.Unchecked
                )
                self.biome_list.addItem(item)
                self._biome_items[biome] = item

        self.biome_list.itemChanged.connect(self._biome_list_changed)
        card_layout.addWidget(self.biome_list)
        layout.addWidget(card, 1)

        hint = QLabel(
            "Role IDs are edited from Discord → Per-Biome Roles. "
            "Changes here are saved automatically to the selected profile."
        )
        hint.setObjectName("cardHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return page

    def _biome_list_changed(self, _item: QListWidgetItem):
        if self._loading:
            return
        profile = self._current_profile()
        profile.notify_biomes = [
            biome
            for biome, item in self._biome_items.items()
            if item.checkState() == Qt.CheckState.Checked
        ]
        self.schedule_save()

    # ---------- settings ----------

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            self._brand_header(
                "Settings",
                "Anti-AFK, input backend, theme, and Linux session details.",
            )
        )

        afk_card, afk_layout = self._card(
            "Anti-AFK"
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.afk_enabled = QCheckBox()
        self.afk_enabled.setChecked(
            bool(self.config.anti_afk.enabled)
        )

        self.interval = QDoubleSpinBox()
        self.interval.setRange(
            1.0,
            86400.0,
        )
        self.interval.setDecimals(1)
        self.interval.setSingleStep(1.0)
        self.interval.setSuffix(" s")
        self.interval.setValue(
            float(
                self.config.anti_afk.interval_seconds
            )
        )

        self.afk_method = QComboBox()

        kde_wayland = (
            os.environ.get("XDG_CURRENT_DESKTOP", "").strip().lower() == "kde"
            and os.environ.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
        )

        self.afk_method.addItem(
            "Press Space",
            "space",
        )

        self.afk_method.addItem(
            "Alt+Tab + Space",
            "alt_tab",
        )

        current_method = str(
            self.config.anti_afk.method
        ).strip().lower()


        method_index = (
            self.afk_method.findData(
                current_method
            )
        )

        if method_index >= 0:
            self.afk_method.setCurrentIndex(
                method_index
            )

        self.afk_backend = QComboBox()
        self.afk_backend.addItem(
            "Automatic",
            "auto",
        )
        self.afk_backend.addItem(
            "Windows — native SendInput",
            "windows",
        )

        current_backend = str(
            getattr(
                self.config.anti_afk,
                "backend",
                "auto",
            )
        ).strip().lower()

        backend_index = (
            self.afk_backend.findData(
                current_backend
            )
        )

        if backend_index >= 0:
            self.afk_backend.setCurrentIndex(
                backend_index
            )

        self.theme = QComboBox()

        for theme_name in THEMES:
            self.theme.addItem(
                str(theme_name).title(),
                theme_name,
            )

        current_theme = str(
            self.config.theme
        )

        theme_index = self.theme.findData(
            current_theme
        )

        if theme_index >= 0:
            self.theme.setCurrentIndex(
                theme_index
            )

        grid.addWidget(
            QLabel("Enable Anti-AFK"),
            0,
            0,
        )
        grid.addWidget(
            self.afk_enabled,
            0,
            1,
        )

        grid.addWidget(
            QLabel("Anti-AFK method"),
            1,
            0,
        )
        grid.addWidget(
            self.afk_method,
            1,
            1,
        )

        grid.addWidget(
            QLabel("Input backend"),
            2,
            0,
        )
        grid.addWidget(
            self.afk_backend,
            2,
            1,
        )

        grid.addWidget(
            QLabel("Anti-AFK interval"),
            3,
            0,
        )
        grid.addWidget(
            self.interval,
            3,
            1,
        )

        grid.addWidget(
            QLabel("Theme"),
            4,
            0,
        )
        grid.addWidget(
            self.theme,
            4,
            1,
        )

        afk_layout.addLayout(grid)

        backend_hint = QLabel(
            "Automatic mode: KDE Wayland uses wdotool for Sober "
            "focus/restore and ydotool for keyboard input. "
            "X11/XWayland keeps the legacy input path."
        )
        backend_hint.setObjectName(
            "cardHint"
        )
        backend_hint.setWordWrap(True)
        afk_layout.addWidget(
            backend_hint
        )

        environment = detect_environment()

        distro = environment.distribution
        session = environment.session
        commands = environment.commands

        environment_card, environment_layout = self._card(
            "Windows Environment"
        )

        distro_version = (
            f" {distro.version}"
            if distro.version
            else ""
        )

        environment_text = QLabel(
            "\n".join(
                [
                    f"Platform: {distro.name}{distro_version}",
                    f"Desktop: {session.desktop}",
                    f"Display server: {session.display_server}",
                    f"Session type: {session.session_type}",
                    "Native input: Windows SendInput",
                    "Window control: Win32 user32",
                ]
            )
        )

        environment_text.setObjectName(
            "cardHint"
        )
        environment_layout.addWidget(
            environment_text
        )

        button_row = QHBoxLayout()

        save = QPushButton(
            "Save All Settings"
        )
        save.clicked.connect(
            self.save_all
        )

        refresh = QPushButton(
            "Refresh Environment"
        )

        def refresh_environment():
            current_index = (
                self.pages.currentIndex()
            )

            self.pages.removeWidget(page)

            replacement = self._settings_page()

            self.pages.insertWidget(
                current_index,
                replacement,
            )

            self.pages.setCurrentIndex(
                current_index
            )

        refresh.clicked.connect(
            refresh_environment
        )

        button_row.addWidget(
            save
        )
        button_row.addWidget(
            refresh
        )
        button_row.addStretch()

        layout.addWidget(
            afk_card
        )
        layout.addWidget(
            environment_card
        )
        layout.addStretch()
        layout.addLayout(
            button_row
        )

        self.afk_backend.currentIndexChanged.connect(
            lambda _index: self._save_afk_backend_choice()
        )

        return page

    def _theme_changed(self, name: str):
        self._apply_theme(name)
        self.schedule_save()

    def _apply_theme(self, name: str, autosave: bool = True):
        QApplication.instance().setStyleSheet(
            THEMES.get(name, THEMES["midnight"])
        )
        self.config.theme = name
        if autosave:
            self.schedule_save()

    # ---------- persistence ----------

    def _collect(self):
        # Profile data is saved only when switching profiles or pressing Save.
        if hasattr(self, "afk_enabled"):
            self.config.anti_afk.enabled = (
                self.afk_enabled.isChecked()
            )

        if hasattr(self, "interval"):
            self.config.anti_afk.interval_seconds = (
                self.interval.value()
            )

        if hasattr(self, "afk_method"):
            method = self.afk_method.currentData()

            if method not in {"space", "alt_tab"}:
                method = "space"

            self.config.anti_afk.method = method

        if hasattr(self, "afk_backend"):
            backend = self.afk_backend.currentData()

            if backend not in {
                "auto",
                "windows",
            }:
                backend = "auto"

            self.config.anti_afk.backend = backend

    def schedule_save(self):
        if not self._loading:
            self.save_timer.start()

    def _autosave(self):
        self._collect()
        self._save_now()

    def _save_now(self):
        try:
            save_config(self.config)
            self._update_dashboard_profile()
        except Exception as exc:
            self.log(f"Save failed: {exc}")

    def save_all(self):
        self._save_profile_fields()
        self._collect()
        self._save_now()
        self.log("All settings saved")

    # ---------- Anti-AFK ----------

    def _new_afk(self):
        backend = "auto"

        if hasattr(self, "afk_backend"):
            backend = str(
                self.afk_backend.currentData()
                or "auto"
            )

        return AntiAFKController(
            interval_seconds=float(
                self.interval.value()
            ),
            method=str(
                self.afk_method.currentData()
                or "space"
            ),
            log=self.log,
            backend_preference=backend,
            priority_gate=self._priority_gate,
        )

    def start_afk(self):
        if not self.config.anti_afk.enabled:
            self.afk_status.setText("DISABLED")
            self.log("Anti-AFK is disabled in Settings")
            return

        try:
            self.save_all()
            self.afk = self._new_afk()
            self.afk.start()
            self.afk_status.setText("RUNNING")

            # The main Dashboard Start button also starts
            # Automation when Enable Automation is ON.
            if hasattr(self, "automation_page"):
                try:
                    self.automation_page.start_from_main()
                except Exception as exc:
                    self.log(
                        f"Automation start error: {exc}"
                    )
        except WindowError as exc:
            QMessageBox.warning(self, "Anti-AFK", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Anti-AFK", str(exc))

    def stop_afk(self):
        # Main-page Stop also stops Automation.
        if hasattr(self, "automation_page"):
            try:
                stop_fn = getattr(self.automation_page, "stop", None)
                if not callable(stop_fn):
                    stop_fn = getattr(self.automation_page, "_stop", None)
                if callable(stop_fn):
                    stop_fn()
            except Exception as exc:
                self.log(f"Automation stop error: {exc}")

        if self.afk:
            self.afk.stop()
            self.afk = None
        self.afk_status.setText("STOPPED")

    def swap_game(self):
        try:
            self.save_all()
            if not self.afk:
                self.afk = self._new_afk()
            self.afk.swap_to_game()
        except Exception as exc:
            QMessageBox.warning(self, "Swap to Game", str(exc))

    def restore_window(self):
        if self.afk:
            self.afk.restore_previous_window()

    # ---------- Sober biome detection ----------

    def _biome_detected(self, biome: str):
        biome = str(biome).strip().upper()

        self._biome_signals.log_message.emit(
            f"Sober detected biome: {biome}"
        )

        queued = 0

        unknown_biome = biome not in BIOMES

        for profile in self.config.profiles:
            if not profile.enabled:
                continue

            if not profile.url.strip():
                continue

            if unknown_biome:
                # Unknown biomes always use the backup embed.
                # They do not require notify_biomes membership
                # and never use role/@everyone behavior.
                action = "send_unknown_biome"
            else:
                if biome not in profile.notify_biomes:
                    continue

                action = "send_biome_appeared"

            if self._discord_worker.submit(
                profile,
                action,
                biome,
            ):
                queued += 1

        if unknown_biome:
            message = (
                f"Unknown biome detected: {biome} • "
                f"backup Discord notification queued "
                f"({queued} profiles)"
            )
        else:
            message = (
                f"Discord notification queued: {biome} "
                f"({queued} profiles)"
            )

        self._biome_signals.log_message.emit(message)

    def _broadcast_discord_event(
        self,
        method_name: str,
        *,
        biome: str | None = None,
        duration: str | None = None,
    ):
        """Queue non-biome Discord lifecycle events safely."""

        if method_name in {
            "send_biome_appeared",
            "send_biome_ended",
        }:
            if biome is None:
                return

            if method_name == "send_biome_appeared":
                action = "send_biome_appeared"
            else:
                action = "send_biome_ended"

            for profile in self.config.profiles:
                if not profile.enabled:
                    continue

                if not profile.url.strip():
                    continue

                if biome not in profile.notify_biomes:
                    continue

                self._discord_worker.submit(
                    profile,
                    action,
                    biome,
                )

            return

        # Lifecycle events can still use the existing worker thread,
        # but never run a requests.post() call in the Qt thread.
        for profile in self.config.profiles:
            if not profile.enabled:
                continue

            if not profile.url.strip():
                continue

            self._discord_worker.submit(
                profile,
                method_name,
                biome or "",
            )

    def _discord_started(self):
        self._broadcast_discord_event("send_started")

    def _discord_stopped(self):
        self._broadcast_discord_event("send_stopped")

    def _discord_biome_ended(
        self,
        biome: str,
        *,
        duration: str | None = None,
    ):
        self._broadcast_discord_event(
            "send_biome_ended",
            biome=biome,
            duration=duration,
        )

    def _biome_ended(self, biome: str):
        biome = str(biome).strip().upper()

        self._biome_signals.log_message.emit(
            f"Sober biome ended: {biome}"
        )

        queued = 0

        for profile in self.config.profiles:
            if not profile.enabled:
                continue

            if not profile.url.strip():
                continue

            if biome not in profile.notify_biomes:
                continue

            if self._discord_worker.submit(
                profile,
                "send_biome_ended",
                biome,
            ):
                queued += 1

        self._biome_signals.log_message.emit(
            f"Discord end notification queued: {biome} "
            f"({queued} profiles)"
        )

    # ---------- Discord / misc ----------

    def test_webhook(self):
        """Send a test only to the currently selected webhook profile."""

        try:
            self._save_profile_fields()
        except Exception:
            pass

        try:
            self._save_now()
        except Exception:
            pass

        try:
            profile = self._current_profile()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Webhook Test",
                f"Unable to read the selected profile: {exc}",
            )
            return

        if not profile.url.strip():
            QMessageBox.warning(
                self,
                "Webhook Test",
                (
                    f'Profile "{profile.name}" has no webhook URL.\n\n'
                    "Add a Discord webhook URL to this profile first."
                ),
            )
            return

        self.log(
            f'[Profile: {profile.name}] Sending test webhook...'
        )

        def send_test():
            try:
                result = DiscordWebhook(profile).test()

                if result.ok:
                    message = (
                        f'[Profile: {profile.name}] '
                        "Test webhook sent successfully."
                    )
                else:
                    message = (
                        f'[Profile: {profile.name}] '
                        "Test webhook failed: "
                        f'{result.error or result.status or "unknown error"}'
                    )

            except Exception as exc:
                message = (
                    f'[Profile: {profile.name}] '
                    f"Test webhook error: {exc}"
                )

            try:
                self._biome_signals.log_message.emit(message)
            except Exception:
                self.log(message)

        threading.Thread(
            target=send_test,
            name="SolsRNG-Webhook-Test",
            daemon=True,
        ).start()

    def _dashboard_profile_changed(self, index: int):
        if getattr(self, "_loading", False):
            return

        if index < 0 or index >= len(self.config.profiles):
            return

        self._save_profile_fields()

        self.config.active_profile = index
        self._loaded_profile_index = index

        if hasattr(self, "profile_combo"):
            self.profile_combo.blockSignals(True)
            try:
                self.profile_combo.setCurrentIndex(index)
            finally:
                self.profile_combo.blockSignals(False)

        self._load_profile_fields()
        self._update_dashboard_profile()
        self.schedule_save()

    def _update_dashboard_profile(self):
        if not hasattr(
            self,
            "dashboard_profile",
        ):
            return

        if not self.config.profiles:
            self.dashboard_profile.setText(
                "No Discord profiles"
            )

            self.dashboard_webhook.setText(
                "Webhook not configured"
            )

            if hasattr(
                self,
                "dashboard_profile_combo",
            ):
                self.dashboard_profile_combo.blockSignals(
                    True
                )

                try:
                    self.dashboard_profile_combo.clear()
                finally:
                    self.dashboard_profile_combo.blockSignals(
                        False
                    )

            return

        active_index = max(
            0,
            min(
                self.config.active_profile,
                len(self.config.profiles) - 1,
            ),
        )

        profile = self.config.profiles[
            active_index
        ]

        if hasattr(
            self,
            "dashboard_profile_combo",
        ):
            self.dashboard_profile_combo.blockSignals(
                True
            )

            try:
                self.dashboard_profile_combo.clear()

                for item_index, item_profile in enumerate(
                    self.config.profiles
                ):
                    self.dashboard_profile_combo.addItem(
                        item_profile.name,
                        item_index,
                    )

                self.dashboard_profile_combo.setCurrentIndex(
                    active_index
                )
            finally:
                self.dashboard_profile_combo.blockSignals(
                    False
                )

        self.dashboard_profile.setText(
            profile.name
        )

        if profile.enabled and profile.url.strip():
            self.dashboard_webhook.setText(
                "Webhook configured • Enabled"
            )
        elif profile.url.strip():
            self.dashboard_webhook.setText(
                "Webhook configured • Disabled"
            )
        else:
            self.dashboard_webhook.setText(
                "Webhook not configured"
            )

    def log(self, text: str):
        text = str(text)

        # Never touch Qt widgets from worker threads.
        try:
            self._log_queue.put_nowait(text)
        except queue.Full:
            # Drop oldest message and keep the newest one.
            try:
                self._log_queue.get_nowait()
            except queue.Empty:
                pass

            try:
                self._log_queue.put_nowait(text)
            except queue.Full:
                pass

    def _flush_log_queue(self):
        if not hasattr(self, "log_box"):
            return

        messages = []

        # Only render a small batch per GUI tick.
        for _ in range(20):
            try:
                messages.append(
                    self._log_queue.get_nowait()
                )
            except queue.Empty:
                break

        if not messages:
            return

        self.log_box.appendPlainText(
            "\n".join(messages)
        )

        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(
            scrollbar.maximum()
        )

    def closeEvent(self, event):
        if hasattr(self, "automation_page"):
            try:
                self.automation_page.shutdown()
            except Exception as exc:
                self.log(
                    f"Automation shutdown error: {exc}"
                )


        try:
            try:
                if self.afk:
                    self.afk.stop()
            except Exception as exc:
                self.log(
                    f"Anti-AFK shutdown error: {exc}"
                )

            try:
                self.biome_watcher.stop()
            except Exception as exc:
                self.log(
                    f"Biome watcher shutdown error: {exc}"
                )

            try:
                self._discord_worker.stop()
            except Exception:
                pass

            try:
                self.save_timer.stop()
            except Exception as exc:
                self.log(
                    f"Save timer shutdown error: {exc}"
                )

            try:
                self._collect()
                self._save_now()
            except Exception as exc:
                self.log(
                    f"Final save error: {exc}"
                )

        finally:
            event.accept()


def run() -> int:
    app = QApplication(sys.argv)


    app.setWindowIcon(QIcon(str(LOGO)))
    win = MainWindow()
    win.show()
    return app.exec()
