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
    def __init__(
        self,
        parent,
        label: str,
        min_val: float = 0,
        max_val: float = 100,
        initial: float | None = None,
        accuracy: int = 1,
        command: Callable[[float], None] | None = None,
        visibility: Callable[[], bool] | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.persistent = persistent
        self.config_key = f"slider_{label.replace(' ', '_')}"
        self.min_val = min_val
        self.max_val = max_val
        self.accuracy = max(1, accuracy)
        self.command = command
        
        # Calculate increments based on range
        range_val = max_val - min_val
        self.base_increment = 10 ** int(len(str(int(range_val))) - 1) if range_val >= 10 else 1
        
        # Set initial value
        if initial is None:
            initial = (min_val + max_val) / 2
        if self.persistent:
            initial = getCFGKey(self.config_key, initial)
        self.value = tk.DoubleVar(value=max(min_val, min(max_val, initial)))
        
        # Layout: Label on top, controls below
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)
        
        # Label
        label_widget = tkk.Label(self, text=label, font=("", 10, "bold"))
        label_widget.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        # Controls frame
        controls_frame = tkk.Frame(self)
        controls_frame.grid(row=1, column=0, sticky="ew")
        controls_frame.columnconfigure(1, weight=1)  # Slider column expands
        
        # Decrement buttons frame (left side)
        dec_frame = tkk.Frame(controls_frame)
        dec_frame.grid(row=0, column=0, padx=(0, 5))
        
        # Create decrement buttons (right to left: -, --, ---, ...)
        for i in range(self.accuracy, 0, -1):
            increment = self.base_increment * (10 ** (i - 1))
            btn_text = "−" * i
            btn = tkk.Button(
                dec_frame,
                text=btn_text,
                command=lambda inc=increment: self._adjust_value(-inc),
                bootstyle="secondary",
                width=3 + i
            )
            btn.pack(side="right", padx=2)
        
        # Slider canvas
        self.canvas = tk.Canvas(controls_frame, height=60, bg="white", highlightthickness=0)
        self.canvas.grid(row=0, column=1, sticky="ew")
        
        # Increment buttons frame (right side)
        inc_frame = tkk.Frame(controls_frame)
        inc_frame.grid(row=0, column=2, padx=(5, 0))
        
        # Create increment buttons (left to right: +, ++, +++, ...)
        for i in range(1, self.accuracy + 1):
            increment = self.base_increment * (10 ** (i - 1))
            btn_text = "+" * i
            btn = tkk.Button(
                inc_frame,
                text=btn_text,
                command=lambda inc=increment: self._adjust_value(inc),
                bootstyle="secondary",
                width=3 + i
            )
            btn.pack(side="left", padx=2)
        
        # Initialize slider elements
        self.track_id = None
        self.handle_id = None
        self.teardrop_id = None
        self.text_id = None
        self.dragging = False
        
        # Bind events
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Initial draw (will be triggered by Configure event)
        self.canvas.after(10, self._draw_slider)
    
    def _adjust_value(self, delta: float) -> None:
        """Adjust value by delta and update"""
        new_val = max(self.min_val, min(self.max_val, self.value.get() + delta))
        self.value.set(new_val)
        self._draw_slider()
        self._fire_command()
        if self.persistent:
            setCFGKey(self.config_key, new_val)
    
    def _fire_command(self) -> None:
        """Fire the command callback if set"""
        if self.command:
            self.command(self.value.get())
    
    def _get_handle_x(self) -> float:
        """Calculate handle x position based on current value"""
        width = self.canvas.winfo_width()
        padding = 30
        track_width = width - 2 * padding
        
        ratio = (self.value.get() - self.min_val) / (self.max_val - self.min_val)
        return padding + ratio * track_width
    
    def _value_from_x(self, x: float) -> float:
        """Calculate value from x position"""
        width = self.canvas.winfo_width()
        padding = 30
        track_width = width - 2 * padding
        
        ratio = max(0, min(1, (x - padding) / track_width))
        return self.min_val + ratio * (self.max_val - self.min_val)
    
    def _draw_slider(self) -> None:
        """Draw the slider track, handle, and teardrop"""
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return
        
        self.canvas.delete("all")
        
        padding = 30
        track_y = height - 20
        track_height = 6
        handle_radius = 12
        
        # Draw track
        self.canvas.create_rectangle(
            padding, track_y - track_height // 2,
            width - padding, track_y + track_height // 2,
            fill="#d0d0d0", outline="#a0a0a0", width=1
        )
        
        # Get handle position
        handle_x = self._get_handle_x()
        
        # Draw filled portion of track
        self.canvas.create_rectangle(
            padding, track_y - track_height // 2,
            handle_x, track_y + track_height // 2,
            fill="#2196F3", outline=""
        )
        
        # Draw teardrop
        teardrop_top = 10
        teardrop_bottom = track_y - handle_radius - 5
        teardrop_width = 50
        teardrop_height = teardrop_bottom - teardrop_top
        
        # Teardrop shape (rounded top, pointed bottom)
        points = [
            handle_x, teardrop_bottom,  # Point at bottom
            handle_x - teardrop_width // 2, teardrop_top + teardrop_height // 2,
            handle_x - teardrop_width // 2, teardrop_top + 10,
            handle_x - teardrop_width // 3, teardrop_top,
            handle_x + teardrop_width // 3, teardrop_top,
            handle_x + teardrop_width // 2, teardrop_top + 10,
            handle_x + teardrop_width // 2, teardrop_top + teardrop_height // 2,
        ]
        
        self.canvas.create_polygon(
            points,
            fill="#2196F3", outline="#1976D2", width=2, smooth=True
        )
        
        # Draw value text in teardrop
        value_text = f"{self.value.get():.1f}" if isinstance(self.value.get(), float) else f"{int(self.value.get())}"
        self.canvas.create_text(
            handle_x, teardrop_top + 15,
            text=value_text,
            fill="white",
            font=("", 11, "bold")
        )
        
        # Draw handle (large circle for touch)
        self.canvas.create_oval(
            handle_x - handle_radius, track_y - handle_radius,
            handle_x + handle_radius, track_y + handle_radius,
            fill="white", outline="#2196F3", width=3
        )
        
        # Draw small center dot
        self.canvas.create_oval(
            handle_x - 3, track_y - 3,
            handle_x + 3, track_y + 3,
            fill="#2196F3", outline=""
        )
    
    def _on_resize(self, event) -> None:
        """Handle canvas resize"""
        self._draw_slider()
    
    def _on_click(self, event) -> None:
        """Handle mouse click on slider"""
        self.dragging = True
        new_val = self._value_from_x(event.x)
        self.value.set(new_val)
        self._draw_slider()
        self._fire_command()
    
    def _on_drag(self, event) -> None:
        """Handle mouse drag"""
        if self.dragging:
            new_val = self._value_from_x(event.x)
            self.value.set(new_val)
            self._draw_slider()
            # Don't fire command on every drag event to avoid spam
    
    def _on_release(self, event) -> None:
        """Handle mouse release"""
        if self.dragging:
            self.dragging = False
            self._fire_command()
            if self.persistent:
                setCFGKey(self.config_key, self.value.get())


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