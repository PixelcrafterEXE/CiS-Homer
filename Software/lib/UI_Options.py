from __future__ import annotations
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
        self.columnconfigure(1, weight=1)


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
