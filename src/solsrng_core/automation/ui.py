from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .controller import (
    AutomationController,
    AutomationError,
)
from .models import (
    AutomationCoordinates,
    AutomationItem,
)
from .picker import CoordinatePicker
from .storage import (
    AutomationSettings,
    load_settings,
    save_settings,
)


class AutomationPage(QWidget):
    def __init__(self, parent=None, priority_gate=None):
        super().__init__(parent)

        self.priority_gate = priority_gate

        self.settings: AutomationSettings = (
            load_settings()
        )

        self.controller = AutomationController(
            backend=self.settings.backend,
            game_window_pattern=(
                self.settings.game_window_pattern
            ),
            priority_gate=self.priority_gate,
        )

        self._loading = False

        self._build()
        self._refresh_items()
        self._load_selected_item()

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(
            self._refresh_status
        )
        self.timer.start()

    # =========================================================
    # Widget helpers
    # =========================================================

    @staticmethod
    def _make_button(
        text: str,
        minimum_width: int = 120,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setMinimumHeight(36)
        button.setMinimumWidth(
            minimum_width
        )
        button.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        return button

    @staticmethod
    def _make_line_edit(
        text: str = "",
    ) -> QLineEdit:
        widget = QLineEdit(text)
        widget.setMinimumHeight(36)
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        return widget

    @staticmethod
    def _make_combo() -> QComboBox:
        widget = QComboBox()
        widget.setMinimumHeight(36)
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        return widget

    @staticmethod
    def _make_card(
        title: str,
    ):
        card = QGroupBox(title)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        layout.setSpacing(10)

        return card, layout

    @staticmethod
    def _hint(
        text: str,
    ) -> QLabel:
        label = QLabel(text)
        label.setObjectName(
            "cardHint"
        )
        label.setWordWrap(True)
        label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        return label

    # =========================================================
    # Build
    # =========================================================

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(
            QScrollArea.Shape.NoFrame
        )
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )
        layout.setSpacing(14)

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        title = QLabel(
            "Automation"
        )
        title.setObjectName(
            "pageTitle"
        )
        title.setMinimumHeight(42)

        layout.addWidget(title)

        subtitle = self._hint(
            "Target Roblox directly, run one-item tests, "
            "and schedule configured items independently."
        )
        layout.addWidget(subtitle)

        # -----------------------------------------------------
        # INPUT ACCESS
        # -----------------------------------------------------

        access_card, access_layout = self._make_card(
            "Input Access"
        )

        access_layout.addWidget(
            self._hint(
                "Automatic mode on KDE Wayland uses wdotool for window focus "
                "and ydotool for mouse/keyboard input. "
                "Authenticate before testing or starting automation."
            )
        )

        access_form = QFormLayout()
        access_form.setHorizontalSpacing(14)
        access_form.setVerticalSpacing(10)

        self.backend_combo = self._make_combo()

        self.backend_combo.addItem(
            "Automatic",
            "auto",
        )
        self.backend_combo.addItem(
            "ydotool — direct mouse/keyboard input",
            "ydotool",
        )
        self.backend_combo.addItem(
            "xdotool — X11 / XWayland fallback",
            "xdotool",
        )

        backend_index = (
            self.backend_combo.findData(
                self.settings.backend
            )
        )

        if backend_index >= 0:
            self.backend_combo.setCurrentIndex(
                backend_index
            )

        access_form.addRow(
            "Input backend",
            self.backend_combo,
        )

        access_layout.addLayout(
            access_form
        )

        access_row = QHBoxLayout()
        access_row.setSpacing(10)

        self.auth_status = QLabel(
            "NOT AUTHENTICATED"
        )
        self.auth_status.setObjectName(
            "statusValue"
        )
        self.auth_status.setMinimumHeight(36)
        self.auth_status.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )

        self.auth_button = self._make_button(
            "Authenticate Input Access",
            220,
        )
        self.auth_button.clicked.connect(
            self._authenticate
        )

        access_row.addWidget(
            self.auth_status,
            1,
        )
        access_row.addWidget(
            self.auth_button,
        )

        access_layout.addLayout(
            access_row
        )

        layout.addWidget(
            access_card
        )

        # -----------------------------------------------------
        # GAME WINDOW
        # -----------------------------------------------------

        window_card, window_layout = self._make_card(
            "Game Window"
        )

        window_layout.addWidget(
            self._hint(
                "The macro remembers the exact window that was "
                "active, focuses the matching Roblox/Sober window, "
                "runs the sequence, then restores the original window."
            )
        )

        window_form = QFormLayout()
        window_form.setHorizontalSpacing(14)
        window_form.setVerticalSpacing(10)

        self.game_window_pattern = self._make_line_edit(
            self.settings.game_window_pattern
        )
        self.game_window_pattern.setPlaceholderText(
            "Example: Sober"
        )

        window_form.addRow(
            "Window title / text",
            self.game_window_pattern,
        )

        window_layout.addLayout(
            window_form
        )

        window_buttons = QHBoxLayout()
        window_buttons.setSpacing(10)

        find_window = self._make_button(
            "Find Window",
            140,
        )
        find_window.clicked.connect(
            self._find_window
        )

        test_focus = self._make_button(
            "Test Focus",
            140,
        )
        test_focus.clicked.connect(
            self._test_focus
        )

        window_buttons.addWidget(
            find_window
        )
        window_buttons.addWidget(
            test_focus
        )
        window_buttons.addStretch()

        window_layout.addLayout(
            window_buttons
        )

        self.window_result = QLabel(
            "No window detected"
        )
        self.window_result.setObjectName(
            "cardHint"
        )
        self.window_result.setMinimumHeight(
            28
        )
        self.window_result.setWordWrap(True)

        window_layout.addWidget(
            self.window_result
        )

        layout.addWidget(
            window_card
        )

        # -----------------------------------------------------
        # SCHEDULER
        # -----------------------------------------------------

        scheduler_card, scheduler_layout = self._make_card(
            "Automation Scheduler"
        )

        scheduler_row = QHBoxLayout()
        scheduler_row.setSpacing(12)

        self.enabled = QCheckBox(
            "Enable Automation"
        )
        self.enabled.setMinimumHeight(36)
        self.enabled.setChecked(
            self.settings.enabled
        )
        self.enabled.toggled.connect(
            self._enabled_changed
        )

        self.status = QLabel(
            "STOPPED"
        )
        self.status.setObjectName(
            "statusValue"
        )
        self.status.setMinimumHeight(36)
        self.status.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignRight
        )

        scheduler_row.addWidget(
            self.enabled
        )
        scheduler_row.addStretch()
        scheduler_row.addWidget(
            self.status
        )

        scheduler_layout.addLayout(
            scheduler_row
        )

        scheduler_layout.addWidget(
            self._hint(
                "Each item has its own cooldown. "
                "Test Automation performs exactly one cycle "
                "and does not start the scheduler."
            )
        )

        layout.addWidget(
            scheduler_card
        )

        # -----------------------------------------------------
        # AUTOMATION ITEM
        # -----------------------------------------------------

        item_card, item_layout = self._make_card(
            "Automation Item"
        )

        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)

        self.item_combo = self._make_combo()
        self.item_combo.currentIndexChanged.connect(
            self._item_changed
        )

        add_item = self._make_button(
            "Add",
            90,
        )
        add_item.clicked.connect(
            self._add_item
        )

        remove_item = self._make_button(
            "Remove",
            100,
        )
        remove_item.clicked.connect(
            self._remove_item
        )

        selector_row.addWidget(
            self.item_combo,
            1,
        )
        selector_row.addWidget(
            add_item
        )
        selector_row.addWidget(
            remove_item
        )

        item_layout.addLayout(
            selector_row
        )

        item_form = QFormLayout()
        item_form.setHorizontalSpacing(14)
        item_form.setVerticalSpacing(10)

        self.item_name = self._make_line_edit()
        self.search_text = self._make_line_edit()

        self.cooldown = QDoubleSpinBox()
        self.cooldown.setMinimumHeight(36)
        self.cooldown.setRange(
            0.0,
            604800.0,
        )
        self.cooldown.setDecimals(1)
        self.cooldown.setSingleStep(1.0)
        self.cooldown.setSuffix(
            " s"
        )
        self.cooldown.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.item_enabled = QCheckBox(
            "Enabled in scheduler"
        )
        self.item_enabled.setMinimumHeight(
            36
        )

        item_form.addRow(
            "Item name",
            self.item_name,
        )
        item_form.addRow(
            "Search text",
            self.search_text,
        )
        item_form.addRow(
            "Cooldown",
            self.cooldown,
        )
        item_form.addRow(
            "",
            self.item_enabled,
        )

        item_layout.addLayout(
            item_form
        )

        save_item = self._make_button(
            "Save Item",
            130,
        )
        save_item.clicked.connect(
            self._save_item_button
        )

        item_layout.addWidget(
            save_item,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        layout.addWidget(
            item_card
        )

        # -----------------------------------------------------
        # RECORDED COORDINATES
        # -----------------------------------------------------

        coordinates_card, coordinates_layout = self._make_card(
            "Recorded Roblox Coordinates"
        )

        coordinates_layout.addWidget(
            self._hint(
                "Each target is selected by clicking the actual "
                "Roblox control. Close Inventory and Quantity are "
                "user-selected coordinates too."
            )
        )

        coordinates_grid = QGridLayout()
        coordinates_grid.setHorizontalSpacing(
            12
        )
        coordinates_grid.setVerticalSpacing(
            8
        )

        coordinates_grid.setColumnStretch(
            0,
            0,
        )
        coordinates_grid.setColumnStretch(
            1,
            1,
        )
        coordinates_grid.setColumnStretch(
            2,
            0,
        )

        definitions = [
            ("inventory", "Inventory"),
            ("items", "Items"),
            ("search_bar", "Search Bar"),
            ("first_slot", "First Slot"),
            ("quantity", "Quantity / One Item"),
            ("use_button", "Use Button"),
            ("close_inventory", "Close Inventory"),
        ]

        self.coordinate_buttons = {}

        for row, (
            attribute,
            label,
        ) in enumerate(
            definitions
        ):
            name = QLabel(label)
            name.setMinimumHeight(36)

            value = QLabel(
                "Not set"
            )
            value.setObjectName(
                "cardHint"
            )
            value.setMinimumHeight(36)
            value.setAlignment(
                Qt.AlignmentFlag.AlignVCenter
            )

            button = self._make_button(
                "Set",
                130,
            )
            button.clicked.connect(
                lambda _checked=False,
                attr=attribute,
                title=label: self._set_coordinate(
                    attr,
                    title,
                )
            )

            self.coordinate_buttons[
                attribute
            ] = button

            coordinates_grid.addWidget(
                name,
                row,
                0,
            )
            coordinates_grid.addWidget(
                value,
                row,
                1,
            )
            coordinates_grid.addWidget(
                button,
                row,
                2,
            )

            setattr(
                self,
                f"{attribute}_value",
                value,
            )

        coordinates_layout.addLayout(
            coordinates_grid
        )

        layout.addWidget(
            coordinates_card
        )

        # -----------------------------------------------------
        # RUN
        # -----------------------------------------------------

        run_card, run_layout = self._make_card(
            "Run"
        )

        run_layout.addWidget(
            self._hint(
                "Test Automation performs one complete item "
                "cycle. Start Automation enables the cooldown "
                "scheduler."
            )
        )

        run_grid = QGridLayout()
        run_grid.setHorizontalSpacing(
            10
        )
        run_grid.setVerticalSpacing(
            10
        )

        self.test_button = self._make_button(
            "▶  Test Automation",
            180,
        )
        self.test_button.clicked.connect(
            self._test_automation
        )

        self.start_button = self._make_button(
            "Start Automation",
            170,
        )
        self.start_button.clicked.connect(
            self._start
        )

        self.stop_button = self._make_button(
            "Stop",
            110,
        )
        self.stop_button.clicked.connect(
            self._stop
        )

        save_button = self._make_button(
            "Save",
            110,
        )
        save_button.clicked.connect(
            self._save_settings
        )

        run_grid.addWidget(
            self.test_button,
            0,
            0,
        )
        run_grid.addWidget(
            self.start_button,
            0,
            1,
        )
        run_grid.addWidget(
            self.stop_button,
            0,
            2,
        )
        run_grid.addWidget(
            save_button,
            0,
            3,
        )

        run_layout.addLayout(
            run_grid
        )

        self.activity = QLabel(
            "Ready."
        )
        self.activity.setObjectName(
            "cardHint"
        )
        self.activity.setMinimumHeight(
            28
        )
        self.activity.setWordWrap(True)

        run_layout.addWidget(
            self.activity
        )

        layout.addWidget(
            run_card
        )

        layout.addStretch(
            1
        )

        scroll.setWidget(
            content
        )

        outer.addWidget(
            scroll
        )

    # =========================================================
    # Authentication
    # =========================================================

    def _authenticate(self):
        self.controller.backend = (
            self.backend_combo.currentData()
        )

        self.settings.backend = (
            self.controller.backend
        )

        save_settings(
            self.settings
        )

        self.auth_button.setEnabled(
            False
        )
        self.auth_button.setText(
            "Authenticating..."
        )
        self.auth_status.setText(
            "AUTHENTICATING..."
        )

        self.controller.retry_authentication()

    # =========================================================
    # Status
    # =========================================================

    def _refresh_status(self):
        status = self.controller.status

        if status.authenticated:
            self.auth_status.setText(
                "READY"
            )
            self.auth_button.setText(
                "Input Access Ready"
            )
            self.auth_button.setEnabled(
                False
            )

        elif status.authenticating:
            self.auth_status.setText(
                "AUTHENTICATING..."
            )
            self.auth_button.setText(
                "Authenticating..."
            )
            self.auth_button.setEnabled(
                False
            )

        elif status.auth_error:
            self.auth_status.setText(
                f"FAILED: {status.auth_error}"
            )
            self.auth_button.setText(
                "Try Again"
            )
            self.auth_button.setEnabled(
                True
            )

        else:
            self.auth_status.setText(
                "NOT AUTHENTICATED"
            )
            self.auth_button.setText(
                "Authenticate Input Access"
            )
            self.auth_button.setEnabled(
                True
            )

        self.status.setText(
            status.message
        )

        if status.game_window:
            self.window_result.setText(
                f"Game: {status.game_window}"
            )

        if status.current_item:
            self.activity.setText(
                f"{status.message} • "
                f"{status.current_item}"
            )
        else:
            self.activity.setText(
                status.message
            )

    # =========================================================
    # Window targeting
    # =========================================================

    def _find_window(self):
        self._sync_window_pattern()

        try:
            window = (
                self.controller.find_game_window()
            )

            self.window_result.setText(
                f"✓ Found: {window.title}"
            )

        except Exception as exc:
            self.window_result.setText(
                f"✗ {exc}"
            )

    def _test_focus(self):
        self._sync_window_pattern()

        try:
            previous = (
                self.controller._get_active_window()
            )

            target = (
                self.controller.find_game_window()
            )

            self.controller._activate_window(
                target
            )

            self.window_result.setText(
                f"Focused: {target.title}"
            )

            QTimer.singleShot(
                700,
                lambda: self._restore_window(
                    previous
                ),
            )

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Window Focus",
                str(exc),
            )

    def _restore_window(
        self,
        window,
    ):
        try:
            self.controller._activate_window(
                window
            )

        except Exception as exc:
            self.window_result.setText(
                f"Restore failed: {exc}"
            )

    def _sync_window_pattern(self):
        pattern = (
            self.game_window_pattern
            .text()
            .strip()
        )

        if not pattern:
            pattern = "Sober"
            self.game_window_pattern.setText(
                pattern
            )

        self.settings.game_window_pattern = (
            pattern
        )

        self.controller.game_window_pattern = (
            pattern
        )

    # =========================================================
    # Items
    # =========================================================

    def _refresh_items(self):
        self._loading = True

        try:
            self.item_combo.clear()

            for item in self.settings.items:
                self.item_combo.addItem(
                    item.name
                )

        finally:
            self._loading = False

    def _item_changed(
        self,
        index: int,
    ):
        if self._loading:
            return

        if index < 0:
            return

        self._load_selected_item()

    def _load_selected_item(self):
        index = (
            self.item_combo.currentIndex()
        )

        if (
            index < 0
            or index >= len(
                self.settings.items
            )
        ):
            return

        item = self.settings.items[
            index
        ]

        self._loading = True

        try:
            self.item_name.setText(
                item.name
            )

            self.search_text.setText(
                item.search_text
            )

            self.cooldown.setValue(
                item.cooldown_seconds
            )

            self.item_enabled.setChecked(
                item.enabled
            )

        finally:
            self._loading = False

        # Coordinates are shared by all automation items.
        self._refresh_coordinate_labels(
            self.settings.coordinates
        )

    def _save_current_item(
        self,
    ) -> bool:
        index = (
            self.item_combo.currentIndex()
        )

        if (
            index < 0
            or index >= len(
                self.settings.items
            )
        ):
            return False

        name = (
            self.item_name
            .text()
            .strip()
        )

        search = (
            self.search_text
            .text()
            .strip()
        )

        if not name:
            QMessageBox.warning(
                self,
                "Automation",
                "Item name cannot be empty.",
            )
            return False

        if not search:
            QMessageBox.warning(
                self,
                "Automation",
                "Search text cannot be empty.",
            )
            return False

        item = self.settings.items[
            index
        ]

        item.name = name
        item.search_text = search
        item.cooldown_seconds = (
            self.cooldown.value()
        )
        item.enabled = (
            self.item_enabled.isChecked()
        )

        self.item_combo.setItemText(
            index,
            name,
        )

        return True

    def _save_item_button(self):
        if not self._save_current_item():
            return

        self._save_settings()

    def _add_item(self):
        name, ok = QInputDialog.getText(
            self,
            "Add Automation Item",
            "Item name:",
        )

        if not ok:
            return

        name = name.strip()

        if not name:
            return

        self.settings.items.append(
            AutomationItem(
                name=name,
                search_text=name,
                cooldown_seconds=60.0,
            )
        )

        self._refresh_items()

        self.item_combo.setCurrentIndex(
            len(self.settings.items) - 1
        )

        self._load_selected_item()
        self._save_settings()

    def _remove_item(self):
        index = (
            self.item_combo.currentIndex()
        )

        if (
            index < 0
            or index >= len(
                self.settings.items
            )
        ):
            return

        if len(self.settings.items) <= 1:
            QMessageBox.warning(
                self,
                "Automation",
                "Keep at least one automation item.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Remove Automation Item",
            (
                "Remove "
                f'"{self.settings.items[index].name}"?'
            ),
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        self.settings.items.pop(
            index
        )

        self._refresh_items()
        self._load_selected_item()
        self._save_settings()

    # =========================================================
    # Coordinates
    # =========================================================

    def _set_coordinate(
        self,
        attribute: str,
        label: str,
    ):
        index = (
            self.item_combo.currentIndex()
        )

        if (
            index < 0
            or index >= len(
                self.settings.items
            )
        ):
            return

        point = CoordinatePicker.capture(
            self,
            label,
        )

        if point is None:
            return

        # Coordinates belong to the Automation system itself,
        # not to an individual automation item.
        setattr(
            self.settings.coordinates,
            attribute,
            point,
        )

        # Keep every in-memory item synchronized immediately.
        self.settings._sync_item_coordinates()

        self._refresh_coordinate_labels(
            self.settings.coordinates
        )

        self._save_settings()

    def _refresh_coordinate_labels(
        self,
        coordinates: AutomationCoordinates,
    ):
        definitions = [
            ("inventory", "Inventory"),
            ("items", "Items"),
            ("search_bar", "Search Bar"),
            ("first_slot", "First Slot"),
            ("quantity", "Quantity / One Item"),
            ("use_button", "Use Button"),
            ("close_inventory", "Close Inventory"),
        ]

        for attribute, label in definitions:
            value = getattr(
                coordinates,
                attribute,
            )

            value_widget = getattr(
                self,
                f"{attribute}_value",
            )

            button = (
                self.coordinate_buttons[
                    attribute
                ]
            )

            if value is None:
                value_widget.setText(
                    "Not set"
                )
                button.setText(
                    "Set"
                )
            else:
                value_widget.setText(
                    f"{value[0]}, {value[1]}"
                )
                button.setText(
                    "Change"
                )

    # =========================================================
    # Main Dashboard Start integration
    # =========================================================

    def start_from_main(self):
        """
        Start Automation because the main Dashboard Start button
        was pressed.

        Automation only starts when Enable Automation is ON.
        Opening the application never starts Automation by itself.
        """
        if not self.settings.enabled:
            return

        if self.controller.status.running:
            return

        self._sync_window_pattern()

        if not self._save_current_item():
            return

        self._save_settings()

        if self.controller.status.authenticated:
            try:
                self._start(automatic=True)
            except Exception as exc:
                self._biome_log(
                    f"Automation startup from main Start failed: {exc}"
                )
            return

        # Input Access is not ready yet. Authenticate, then retry.
        try:
            self.controller.authenticate_async()
        except Exception as exc:
            self._biome_log(
                f"Automation authentication failed: {exc}"
            )
            return

        QTimer.singleShot(
            500,
            self._start_from_main_when_ready,
        )

    def _start_from_main_when_ready(self):
        if not self.settings.enabled:
            return

        if self.controller.status.running:
            return

        if self.controller.status.authenticating:
            QTimer.singleShot(
                500,
                self._start_from_main_when_ready,
            )
            return

        if not self.controller.status.authenticated:
            if self.controller.status.auth_error:
                self._biome_log(
                    "Automation Input Access failed: "
                    f"{self.controller.status.auth_error}"
                )
                return

            QTimer.singleShot(
                500,
                self._start_from_main_when_ready,
            )
            return

        try:
            self._start(automatic=True)
        except Exception as exc:
            self._biome_log(
                f"Automation startup from main Start failed: {exc}"
            )

    # =========================================================
    # Automatic startup
    # =========================================================

    def _auto_start_saved(self):
        if not self.settings.enabled:
            return

        if self.controller.status.running:
            return

        if self.controller.status.authenticating:
            QTimer.singleShot(
                500,
                self._auto_start_saved,
            )
            return

        if not self.controller.status.authenticated:
            try:
                self.controller.authenticate_async()
            except Exception as exc:
                self.settings.enabled = False
                self.enabled.setChecked(False)
                self._save_settings()
                self._biome_log(
                    f"Automatic Automation authentication failed: {exc}"
                )
                return

            QTimer.singleShot(
                500,
                self._auto_start_saved,
            )
            return

        try:
            self._start(
                automatic=True,
            )
        except Exception as exc:
            self._biome_log(
                f"Automatic Automation startup failed: {exc}"
            )

    def _biome_log(self, message: str):
        try:
            if hasattr(self.parent(), "log"):
                self.parent().log(message)
        except Exception:
            pass

    # =========================================================
    # Runtime
    # =========================================================

    def _enabled_changed(
        self,
        enabled: bool,
    ):
        self.settings.enabled = (
            enabled
        )

        if not enabled:
            self.controller.stop()

        self._save_settings()

    def _start(
        self,
        *,
        automatic: bool = False,
    ):
        self._sync_window_pattern()

        if not self._save_current_item():
            return

        self.settings.enabled = True
        self.enabled.setChecked(
            True
        )

        self._save_settings()

        if not self.controller.status.authenticated:
            if automatic:
                return

            QMessageBox.warning(
                self,
                "Automation",
                "Authenticate Input Access first.",
            )
            return

        try:
            self.controller.start()

        except AutomationError as exc:
            if automatic:
                self._biome_log(
                    f"Automation startup failed: {exc}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Automation",
                    str(exc),
                )

    def _test_automation(self):
        self._sync_window_pattern()

        if not self._save_current_item():
            return

        self._save_settings()

        index = (
            self.item_combo.currentIndex()
        )

        if (
            index < 0
            or index >= len(
                self.settings.items
            )
        ):
            QMessageBox.warning(
                self,
                "Test Automation",
                "Select an automation item first.",
            )
            return

        if not self.controller.status.authenticated:
            QMessageBox.warning(
                self,
                "Test Automation",
                "Authenticate Input Access first.",
            )
            return

        item = self.settings.items[
            index
        ]

        try:
            self.test_button.setEnabled(
                False
            )

            test_item = AutomationItem.from_dict(
                item.to_dict()
            )

            # Test Automation also uses the single shared
            # coordinate set.
            test_item.coordinates = (
                self.settings.coordinates.copy()
            )

            self.controller.test_item(
                test_item
            )

        except AutomationError as exc:
            QMessageBox.warning(
                self,
                "Test Automation",
                str(exc),
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Test Automation",
                str(exc),
            )

        finally:
            self.test_button.setEnabled(
                True
            )

    def _stop(self):
        self.controller.stop()

    def _save_settings(self):
        self._sync_window_pattern()

        self._save_current_item()

        self.settings.enabled = (
            self.enabled.isChecked()
        )

        self.settings.backend = (
            self.backend_combo.currentData()
            or "auto"
        )

        self.controller.backend = (
            self.settings.backend
        )

        self.controller.game_window_pattern = (
            self.settings.game_window_pattern
        )

        # Push the single shared coordinate set into the runtime
        # controller. Both Strange Controller and Biome Randomizer
        # consume this exact same object.
        self.controller.coordinates = (
            self.settings.coordinates.copy()
        )

        save_settings(
            self.settings
        )

        self.controller.items = [
            AutomationItem.from_dict(
                item.to_dict()
            )
            for item in self.settings.items
        ]

    def shutdown(self):
        try:
            self._save_settings()
        finally:
            self.controller.shutdown()
