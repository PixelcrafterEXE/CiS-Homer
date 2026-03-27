"""
On-screen keyboard (onboard) integration for X11.

Provides automatic show/hide of the ``onboard`` on-screen keyboard
whenever an editable widget gains or loses focus.

Widgets tagged with ``_numeric_keyboard = True`` as an instance
attribute trigger the compact ``Numpad`` layout instead of the default
``Phone`` (QWERTY) layout.  ``tk.Spinbox`` instances are always treated
as numeric.

Layout switching is done live via ``gsettings``; onboard reloads the
layout automatically without restarting.  Show/hide is controlled
through its D-Bus interface (``org.onboard.Onboard``).  Both calls use
``subprocess.Popen`` (fire-and-forget) so failures are silent and never
block the UI thread.

Usage
-----
Add ``KeyboardMixin`` to the ``tkinter.Tk`` subclass MRO and call
``self._setup_keyboard()`` once, **after** the widget tree is fully
built::

    class UI(tkk.Tk, KeyboardMixin, ...):
        def buildUI(self):
            ...

        def __init__(self):
            super().__init__()
            self.buildUI()
            self._setup_keyboard()   # ← binds to ALL current & future widgets
"""

from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from typing import Optional


# ---------------------------------------------------------------------------
# Widget type filter
# ---------------------------------------------------------------------------

# Class-name substrings that mark a widget as a text-input target.
# Tkinter/ttkbootstrap internal names include the 'T' prefix for themed
# variants, e.g. "TEntry", "TCombobox", "TSpinbox".
_EDITABLE_TYPES: frozenset[str] = frozenset(
    {"Entry", "Combobox", "Spinbox", "Text"}
)


def _is_editable(widget: tk.Widget) -> bool:
    """Return True if *widget* should trigger the on-screen keyboard."""
    wtype = type(widget).__name__
    if not any(t in wtype for t in _EDITABLE_TYPES):
        return False
    # Readonly Comboboxes (i.e. plain dropdowns) don't need the keyboard.
    if "Combobox" in wtype:
        try:
            return str(widget.cget("state")) != "readonly"
        except Exception:
            pass
    return True


def _is_numeric(widget: tk.Widget) -> bool:
    """Return True if *widget* should use the numpad layout."""
    return isinstance(widget, tk.Spinbox) or bool(
        getattr(widget, "_numeric_keyboard", False)
    )


# ---------------------------------------------------------------------------
# onboard controller
# ---------------------------------------------------------------------------

class _OnboardController:
    """
    Singleton that drives the ``onboard`` on-screen keyboard via D-Bus
    and ``gsettings``.

    All external calls are fire-and-forget: errors (e.g. onboard not
    installed, no D-Bus session) are caught and silently discarded so
    the application continues to function without a keyboard.
    """

    _instance: Optional["_OnboardController"] = None

    _LAYOUT_QWERTY  = "Phone"
    _LAYOUT_NUMPAD  = "Numpad"

    # D-Bus destination / object path / interface for onboard
    _DBUS_DEST   = "org.onboard.Onboard"
    _DBUS_PATH   = "/org/onboard/Onboard/Keyboard"
    _DBUS_IFACE  = "org.onboard.Onboard.Keyboard"

    @classmethod
    def get(cls) -> "_OnboardController":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._hide_timer: Optional[threading.Timer] = None
        self._current_layout: str = self._LAYOUT_QWERTY

    # ── Public API ────────────────────────────────────────────────────────────

    def show(self, numpad: bool = False) -> None:
        """Show the keyboard immediately; cancel any pending hide."""
        if self._hide_timer is not None:
            self._hide_timer.cancel()
            self._hide_timer = None

        target = self._LAYOUT_NUMPAD if numpad else self._LAYOUT_QWERTY
        if target != self._current_layout:
            self._set_layout(target)
            self._current_layout = target

        self._dbus("Show")

    def hide(self, delay: float = 0.15) -> None:
        """
        Hide the keyboard after *delay* seconds.

        The small delay prevents the keyboard from vanishing before a
        tap on one of its keys registers.
        """
        if self._hide_timer is not None:
            self._hide_timer.cancel()
        t = threading.Timer(delay, self._do_hide)
        t.daemon = True
        t.start()
        self._hide_timer = t

    # ── Internals ─────────────────────────────────────────────────────────────

    def _do_hide(self) -> None:
        self._hide_timer = None
        self._dbus("Hide")

    @staticmethod
    def _dbus(method: str) -> None:
        """Send a D-Bus call to onboard (fire-and-forget)."""
        try:
            subprocess.Popen(
                [
                    "dbus-send", "--session",
                    f"--dest={_OnboardController._DBUS_DEST}",
                    "--type=method_call",
                    _OnboardController._DBUS_PATH,
                    f"{_OnboardController._DBUS_IFACE}.{method}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass  # dbus-send not available

    @staticmethod
    def _set_layout(layout: str) -> None:
        """Switch the onboard layout via gsettings (onboard auto-reloads)."""
        try:
            subprocess.Popen(
                ["gsettings", "set", "org.onboard", "layout", layout],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pass  # gsettings not available


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class KeyboardMixin:
    """
    Mixin for the root ``tkinter.Tk`` window.

    Call ``_setup_keyboard()`` once after the UI is fully built.  The
    mixin registers application-level ``<FocusIn>`` / ``<FocusOut>``
    bindings that apply to every widget—including widgets added later by
    dynamic UI rebuilds—so it only needs to be called once.
    """

    def _setup_keyboard(self) -> None:
        """Register global focus handlers for the on-screen keyboard."""
        # ``bind_all`` attaches to the Tk application level, so every
        # widget in the hierarchy—present and future—delivers the event.
        self.bind_all(  # type: ignore[attr-defined]
            "<FocusIn>", self._on_focus_in_kb, add="+"
        )
        self.bind_all(  # type: ignore[attr-defined]
            "<FocusOut>", self._on_focus_out_kb, add="+"
        )

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_focus_in_kb(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        widget = event.widget
        if not isinstance(widget, tk.Widget):
            return
        if _is_editable(widget):
            _OnboardController.get().show(numpad=_is_numeric(widget))

    def _on_focus_out_kb(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        widget = event.widget
        if not isinstance(widget, tk.Widget):
            return
        if _is_editable(widget):
            _OnboardController.get().hide()
