"""Compact three-part language selector for the Overlay header."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QHBoxLayout, QMenu, QSizePolicy, QToolButton, QWidget

from app.overlay.context_menu import LANGUAGE_OPTIONS, OVERLAY_THEMES, normalize_language_code


DEFAULT_TARGET_LANGUAGE = "zh-CN"


def normalize_target_language_code(
    value: object,
    *,
    fallback: str = DEFAULT_TARGET_LANGUAGE,
) -> str:
    """Return a supported concrete target language; ``auto`` is never valid."""

    candidate = str(value or "").strip()
    for code, _label, _compact in LANGUAGE_OPTIONS:
        if code == "auto":
            continue
        if candidate.lower() == code.lower():
            return code
    return fallback


def compact_language_label(value: object, *, target: bool = False) -> str:
    """Return the compact label used inside one segment of the header control."""

    code = (
        normalize_target_language_code(value)
        if target
        else normalize_language_code(value)
    )
    for option_code, _label, compact in LANGUAGE_OPTIONS:
        if option_code == code:
            if option_code == "auto":
                return "Auto"
            return compact
    return str(code)


class OverlayLanguageBar(QWidget):
    """Source selector + swap affordance + target selector.

    Source language supports automatic detection. Target language deliberately
    excludes ``auto``. The swap button is disabled while source is ``auto`` so
    the UI can never create an invalid automatic target language.
    """

    source_selected = Signal(str)
    target_selected = Signal(str)
    swap_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayLanguageBar")
        self._source_language = "auto"
        self._target_language = DEFAULT_TARGET_LANGUAGE
        self._palette = dict(OVERLAY_THEMES["dark"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.source_button = QToolButton(self)
        self.source_button.setObjectName("OverlaySourceLanguageButton")
        self.source_button.setToolTip("选择源语言")
        self.source_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.source_button.setAutoRaise(True)
        self.source_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.source_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.source_button.setMinimumWidth(50)
        self.source_button.setMaximumWidth(72)
        self.source_button.setFixedHeight(34)
        self.source_button.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.swap_button = QToolButton(self)
        self.swap_button.setObjectName("OverlayLanguageSwapButton")
        self.swap_button.setText("⇄")
        self.swap_button.setToolTip("互换源语言与目标语言")
        self.swap_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swap_button.setAutoRaise(True)
        self.swap_button.setFixedSize(32, 34)
        self.swap_button.clicked.connect(
            lambda _checked=False: self.swap_requested.emit()
        )

        self.target_button = QToolButton(self)
        self.target_button.setObjectName("OverlayTargetLanguageButton")
        self.target_button.setToolTip("选择目标语言")
        self.target_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.target_button.setAutoRaise(True)
        self.target_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.target_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.target_button.setMinimumWidth(50)
        self.target_button.setMaximumWidth(72)
        self.target_button.setFixedHeight(34)
        self.target_button.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        layout.addWidget(self.source_button)
        layout.addWidget(self.swap_button)
        layout.addWidget(self.target_button)

        self._source_menu = QMenu(self.source_button)
        self._source_menu.setObjectName("OverlaySourceLanguageMenu")
        self._source_group = QActionGroup(self)
        self._source_group.setExclusive(True)
        self._source_actions: dict[str, QAction] = {}
        for code, label, _compact in LANGUAGE_OPTIONS:
            action = QAction(label, self._source_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=code: self.source_selected.emit(selected)
            )
            self._source_group.addAction(action)
            self._source_menu.addAction(action)
            self._source_actions[code] = action
        self.source_button.setMenu(self._source_menu)

        self._target_menu = QMenu(self.target_button)
        self._target_menu.setObjectName("OverlayTargetLanguageMenu")
        self._target_group = QActionGroup(self)
        self._target_group.setExclusive(True)
        self._target_actions: dict[str, QAction] = {}
        for code, label, _compact in LANGUAGE_OPTIONS:
            if code == "auto":
                continue
            action = QAction(label, self._target_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=code: self.target_selected.emit(selected)
            )
            self._target_group.addAction(action)
            self._target_menu.addAction(action)
            self._target_actions[code] = action
        self.target_button.setMenu(self._target_menu)

        self.set_languages("auto", DEFAULT_TARGET_LANGUAGE)
        self.apply_palette(self._palette)

    @property
    def source_language(self) -> str:
        return self._source_language

    @property
    def target_language(self) -> str:
        return self._target_language

    @property
    def source_actions(self) -> dict[str, QAction]:
        return dict(self._source_actions)

    @property
    def target_actions(self) -> dict[str, QAction]:
        return dict(self._target_actions)

    def set_languages(self, source_language: object, target_language: object) -> tuple[str, str]:
        self._source_language = normalize_language_code(source_language)
        self._target_language = normalize_target_language_code(target_language)
        self.source_button.setText(compact_language_label(self._source_language))
        self.target_button.setText(
            compact_language_label(self._target_language, target=True)
        )
        self._sync_checks()
        concrete_source = self._source_language != "auto"
        self.swap_button.setEnabled(concrete_source)
        self.swap_button.setToolTip(
            "互换源语言与目标语言"
            if concrete_source
            else "自动检测不能作为目标语言，请先选择具体源语言"
        )
        return self._source_language, self._target_language

    def _sync_checks(self) -> None:
        for code, action in self._source_actions.items():
            blocked = action.blockSignals(True)
            action.setChecked(code == self._source_language)
            action.blockSignals(blocked)
        for code, action in self._target_actions.items():
            blocked = action.blockSignals(True)
            action.setChecked(code == self._target_language)
            action.blockSignals(blocked)

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = dict(palette)
        text = palette["text"]
        muted = palette["muted_text"]
        background = palette["menu_background"]
        border = palette["border"]
        hover = palette["hover"]
        accent = palette["accent"]
        self.setStyleSheet(
            f"""
            QWidget#OverlayLanguageBar {{
                background: transparent;
                border: none;
            }}
            QToolButton#OverlaySourceLanguageButton,
            QToolButton#OverlayLanguageSwapButton,
            QToolButton#OverlayTargetLanguageButton {{
                color: {text};
                background-color: {background};
                border: 1px solid {border};
                padding: 2px 6px;
                font-size: 13px;
            }}
            QToolButton#OverlaySourceLanguageButton {{
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QToolButton#OverlayLanguageSwapButton {{
                border-left: none;
                border-right: none;
                border-radius: 0px;
                padding: 0px 4px;
                font-size: 16px;
            }}
            QToolButton#OverlayTargetLanguageButton {{
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
            }}
            QToolButton#OverlaySourceLanguageButton::menu-indicator,
            QToolButton#OverlayTargetLanguageButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
            QToolButton#OverlaySourceLanguageButton:hover,
            QToolButton#OverlayLanguageSwapButton:hover:enabled,
            QToolButton#OverlayTargetLanguageButton:hover {{
                color: {text};
                background-color: {hover};
                border-color: {accent};
            }}
            QToolButton#OverlayLanguageSwapButton:disabled {{
                color: {muted};
                background-color: {background};
            }}
            QMenu#OverlaySourceLanguageMenu,
            QMenu#OverlayTargetLanguageMenu {{
                background-color: {background};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 6px 0px;
            }}
            QMenu#OverlaySourceLanguageMenu::item,
            QMenu#OverlayTargetLanguageMenu::item {{
                padding: 7px 24px;
                margin: 1px 4px;
                border-radius: 5px;
            }}
            QMenu#OverlaySourceLanguageMenu::item:selected,
            QMenu#OverlayTargetLanguageMenu::item:selected {{
                background-color: {hover};
                color: {text};
            }}
            """
        )


__all__ = [
    "DEFAULT_TARGET_LANGUAGE",
    "OverlayLanguageBar",
    "compact_language_label",
    "normalize_target_language_code",
]
