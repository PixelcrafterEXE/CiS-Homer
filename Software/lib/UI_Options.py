from __future__ import annotations
import math
import tkinter as tk
from typing import Callable, Sequence

import ttkbootstrap as tkk
from lib.Config import getCFGKey, setCFGKey


class Option(tkk.Frame):
    def __init__(self, parent, label: str | None = None, visibility: Callable[[], bool] | None = None) -> None:
        super().__init__(parent, padding=10)
        self.columnconfigure(0, weight=1)
        self._label = label
        self._visibility = visibility
        self._parent_container = None
        self._is_visible = False

    def add_to(self, parent) -> None:
        self._parent_container = parent
        self._is_visible = self._visibility() if self._visibility else True
        if self._is_visible:
            self.pack(in_=parent, fill="x", padx=8, pady=5)

    def check_visibility_change(self) -> bool:
        if not self._visibility:
            return False
        new_visible = self._visibility()
        if new_visible != self._is_visible:
            self._is_visible = new_visible
            return True
        return False

class OptionButton(Option):
    def __init__(self, parent, text: str, command: Callable | None = None, visibility: Callable[[], bool] | None = None) -> None:
        super().__init__(parent, visibility=visibility)
        button = tkk.Button(self, text=text, command=command, bootstyle="primary")
        button.grid(row=0, column=0, sticky="ew")

class OptionLabel(Option):
    def __init__(self, parent, text: str, foreground: str = "red", visibility: Callable[[], bool] | None = None) -> None:
        super().__init__(parent, visibility=visibility)
        label = tkk.Label(self, text=text, foreground=foreground)
        label.grid(row=0, column=0, sticky="w")

class OptionToggle(Option):
    def __init__(
        self,
        parent,
        label: str,
        initial: bool = False,
        command: Callable[[bool], None] | None = None,
        visibility: Callable[[], bool] | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.persistent = persistent
        self.config_key = f"toggle_{label.replace(' ', '_')}"
        if self.persistent:
            initial = getCFGKey(self.config_key, initial)
        self.value = tk.BooleanVar(value=initial)

        text = tkk.Label(self, text=label)
        text.grid(row=0, column=0, sticky="w")

        def _on_toggle() -> None:
            if self.persistent:
                setCFGKey(self.config_key, self.value.get())
            if command:
                command(self.value.get())

        toggle = tkk.Checkbutton(self, variable=self.value, command=_on_toggle, bootstyle="round-toggle")
        toggle.grid(row=0, column=1, sticky="e")

class OptionDropdown(Option):
    def __init__(
        self,
        parent,
        label: str,
        values: Sequence[str],
        initial: str | None = None,
        command: Callable[[str], None] | None = None,
        visibility: Callable[[], bool] | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.persistent = persistent
        self.config_key = f"dropdown_{label.replace(' ', '_')}"
        self.columnconfigure(0, weight=1, uniform="option_dropdown")
        self.columnconfigure(1, weight=1, uniform="option_dropdown")

        text = tkk.Label(self, text=label)
        text.grid(row=0, column=0, sticky="w", padx=(0, 10))

        selected = initial if initial is not None else (values[0] if values else "")
        if self.persistent:
            selected = getCFGKey(self.config_key, selected)
            
        self.value = tk.StringVar(value=selected)

        dropdown = tkk.Combobox(self, textvariable=self.value, values=list(values), state="readonly")
        dropdown.grid(row=0, column=1, sticky="ew")

        def _on_select(_event=None) -> None:
            if self.persistent:
                setCFGKey(self.config_key, self.value.get())
            if command:
                command(self.value.get())

        dropdown.bind("<<ComboboxSelected>>", _on_select)


class OptionSlider(Option):
    """Slider with ±step button pairs. accuracy sets the number of button pairs.
    Steps are descending powers of ten starting from the largest < (max-min)."""

    _PAD = 13  # approx half the ttk Scale sliderlength (handle travel margin)

    def __init__(
        self,
        parent,
        label: str,
        min_val: int = 0,
        max_val: int = 100,
        initial: int | None = None,
        accuracy: int = 1,
        show_minmax: bool = False,
        command: Callable[[int], None] | None = None,
        visibility: Callable[[], bool] | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.configure(padding=(6, 2))
        self.persistent = persistent
        self.config_key = f"slider_{label.replace(' ', '_')}"
        self._min, self._max = int(min_val), int(max_val)
        self._command = command

        span = self._max - self._min
        exp = max(0, math.floor(math.log10(span)) if span > 0 else 0)
        while 10 ** exp >= span and exp > 0:
            exp -= 1
        self._steps = [max(1, 10 ** (exp - i)) for i in range(max(1, int(accuracy)))]

        if initial is None:
            initial = self._min
        if self.persistent:
            initial = int(getCFGKey(self.config_key, initial))
        self.value = tk.IntVar(value=max(self._min, min(self._max, initial)))

        self.columnconfigure(1, weight=1)

        # Row 0: name label
        tkk.Label(self, text=label).grid(row=0, column=0, columnspan=3, sticky="w")

        # Row 1: value canvas spanning scale column (text tracks the slider dot)
        self._val_canvas = tk.Canvas(self, height=14, highlightthickness=0, bd=0)
        self._val_canvas.grid(row=1, column=1, sticky="ew")

        # Row 2: [dec buttons | scale | inc buttons]
        _DEC = ["\u2212", "\u2212\u2212", "\u2212\u2212\u2212", "\u2212\u2212\u2212\u2212", "\u2212\u2212\u2212\u2212\u2212"]
        _INC = ["+", "++", "+++", "++++", "+++++"]

        dec = tkk.Frame(self)
        dec.grid(row=2, column=0, sticky="e")
        for i, s in enumerate(reversed(self._steps)):
            tk.Button(dec, text=_DEC[min(i, 4)], command=lambda s=s: self._step(-s),
                      padx=2, pady=0, font=("TkFixedFont", 8),
                      relief="solid", bd=1).pack(side="right", padx=(1, 0))

        self._scale = tkk.Scale(self, from_=self._min, to=self._max, orient="horizontal",
                                variable=self.value, command=lambda _: self._on_change())
        self._scale.grid(row=2, column=1, sticky="ew", padx=0)

        inc = tkk.Frame(self)
        inc.grid(row=2, column=2, sticky="w")
        for i, s in enumerate(reversed(self._steps)):
            tk.Button(inc, text=_INC[min(i, 4)], command=lambda s=s: self._step(s),
                      padx=2, pady=0, font=("TkFixedFont", 8),
                      relief="solid", bd=1).pack(side="left", padx=(0, 1))

        if show_minmax:
            tkk.Label(self, text=str(self._min), font=("TkDefaultFont", 8)).grid(row=3, column=1, sticky="w")
            tkk.Label(self, text=str(self._max), font=("TkDefaultFont", 8)).grid(row=3, column=1, sticky="e")

        self._val_canvas.bind("<Configure>", lambda _: self._draw_val())
        self._val_canvas.after(50, self._draw_val)

    def _clamp(self, v: int) -> int:
        return max(self._min, min(self._max, v))

    def _slider_x(self) -> float:
        w = self._val_canvas.winfo_width()
        span = self._max - self._min
        ratio = (self.value.get() - self._min) / span if span else 0.5
        return self._PAD + ratio * max(0, w - 2 * self._PAD)

    def _draw_val(self) -> None:
        c = self._val_canvas
        c.delete("all")
        c.create_text(self._slider_x(), 7, text=str(round(self.value.get())),
                      font=("TkDefaultFont", 8), anchor="center")

    def _on_change(self) -> None:
        self._draw_val()
        self._fire_command()

    def _step(self, delta: int) -> None:
        self.value.set(self._clamp(self.value.get() + delta))
        self._draw_val()
        self._fire_command()

    def _fire_command(self) -> None:
        self.value.set(round(self.value.get()))
        if self.persistent:
            setCFGKey(self.config_key, self.value.get())
        if self._command:
            self._command(self.value.get())


class OptionSection(Option):
    def __init__(
        self,
        parent,
        label: str,
        visibility: Callable[[], bool] | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.persistent = persistent
        self.config_key = f"section_{label.replace(' ', '_')}"
        self.configure(padding=0)
        self._children: list[Option] = []
        self._is_expanded = getCFGKey(self.config_key, True) if self.persistent else True
        
        self._header_btn = tkk.Button(
            self, 
            text="", 
            command=self._toggle, 
            bootstyle="link",
        )
        self._header_btn.grid(row=0, column=0, sticky="w")
        
        self.content_frame = tkk.Frame(self)
        self.content_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0), padx=(10, 0))
        self.content_frame.columnconfigure(0, weight=1)
        self._apply_expand_state()

    def _apply_expand_state(self) -> None:
        if self._is_expanded:
            self._header_btn.configure(text=f"▼  {self._label}")
            self.content_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0), padx=(10, 0))
        else:
            self._header_btn.configure(text=f"▶  {self._label}")
            self.content_frame.grid_forget()

    def _toggle(self) -> None:
        self._is_expanded = not self._is_expanded
        if self.persistent:
            setCFGKey(self.config_key, self._is_expanded)
        self._apply_expand_state()

    def add_option(self, option: Option) -> None:
        self._children.append(option)
        option.add_to(self.content_frame)

    def check_visibility_change(self) -> bool:
        changed = super().check_visibility_change()
        
        children_changed = False
        for child in self._children:
            if child.check_visibility_change():
                children_changed = True
                
        if children_changed:
            for child in self._children:
                child.pack_forget()
            for child in self._children:
                if child._is_visible:
                    child.pack(in_=child._parent_container, fill="x", padx=8, pady=5)
        
        return changed