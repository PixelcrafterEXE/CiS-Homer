import tkinter as tk
from typing import Callable, Sequence

import ttkbootstrap as tkk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from lib.Sensor import Sensor


class Option(tkk.Frame):
    def __init__(self, parent, label: str | None = None) -> None:
        super().__init__(parent, padding=10)
        self.columnconfigure(0, weight=1)
        self._label = label

    def add_to(self, parent) -> None:
        self.pack(in_=parent, fill="x", padx=8, pady=5)


class OptionButton(Option):
    def __init__(self, parent, text: str, command: Callable | None = None) -> None:
        super().__init__(parent)
        button = tkk.Button(self, text=text, command=command, bootstyle="primary")
        button.grid(row=0, column=0, sticky="ew")


class OptionToggle(Option):
    def __init__(
        self,
        parent,
        label: str,
        initial: bool = False,
        command: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__(parent, label)
        self.value = tk.BooleanVar(value=initial)

        text = tkk.Label(self, text=label)
        text.grid(row=0, column=0, sticky="w")

        def _on_toggle() -> None:
            if command:
                command(self.value.get())

        toggle = tkk.Checkbutton(self, variable=self.value, command=_on_toggle, bootstyle="switch")
        toggle.grid(row=0, column=1, sticky="e")


class OptionDropdown(Option):
    def __init__(
        self,
        parent,
        label: str,
        values: Sequence[str],
        initial: str | None = None,
        command: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, label)

        text = tkk.Label(self, text=label)
        text.grid(row=0, column=0, sticky="w", padx=(0, 10))

        selected = initial if initial is not None else (values[0] if values else "")
        self.value = tk.StringVar(value=selected)

        dropdown = tkk.Combobox(self, textvariable=self.value, values=list(values), state="readonly")
        dropdown.grid(row=0, column=1, sticky="ew")

        def _on_select(_event=None) -> None:
            if command:
                command(self.value.get())

        dropdown.bind("<<ComboboxSelected>>", _on_select)
        self.columnconfigure(1, weight=1)

class UI(tkk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._sensor: Sensor | None = None
        try:
            self._sensor = Sensor()
        except RuntimeError:
            pass
        self.buildUI()

    def _on_closing(self) -> None:
        if self._sensor is not None:
            self._sensor.stop()
        self.destroy()

    def buildUI(self) -> None:
        self.title("CiS HomeRPI")
        #self.attributes("-fullscreen", True)
        #todo: disable alt+tab, alt+f4, ctrl+alt+del, etc. to prevent user from exiting the app or switching to another app

        # Container roots for left and right panels 
        self._main = tkk.Frame(self)
        self._main.pack(fill="both", expand=True)
        self._main.columnconfigure(0, weight=4, uniform="group1")
        self._main.columnconfigure(1, weight=3, uniform="group1")
        self._main.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self) -> None:
        #todo: auto-rerun every few hundered ms
        if self._sensor is None:
            self._left_panel = tkk.Frame(self._main, padding=10)
            self._left_panel.grid(row=0, column=0, sticky="nsew")

            error_label = tkk.Label(self._left_panel, text="No sensor detected", foreground="red")
            error_label.pack(expand=True)
        else:
            self._left_panel = tkk.Frame(self._main, padding=10)
            self._left_panel.grid(row=0, column=0, sticky="nsew")

            figure = self._sensor.plotMesh()
            canvas = FigureCanvasTkAgg(figure, master=self._left_panel)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_right_panel(self) -> None:
        self._right_panel = tkk.Frame(self._main, padding=(0, 10, 10, 10))
        self._right_panel.grid(row=0, column=1, sticky="nsew")
        self._right_panel.rowconfigure(0, weight=1)
        self._right_panel.columnconfigure(0, weight=1)

        self._options_canvas = tk.Canvas(self._right_panel, highlightthickness=0)
        self._options_canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tkk.Scrollbar(self._right_panel, orient="vertical", command=self._options_canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._options_canvas.configure(yscrollcommand=scrollbar.set)

        self._options_container = tkk.Frame(self._options_canvas)
        window_id = self._options_canvas.create_window((0, 0), window=self._options_container, anchor="nw")

        self._options_container.bind(
            "<Configure>",
            lambda _event: self._options_canvas.configure(scrollregion=self._options_canvas.bbox("all")),
        )
        self._options_canvas.bind(
            "<Configure>",
            lambda event: self._options_canvas.itemconfigure(window_id, width=event.width),
        )

        self._options: list[Option] = []
        self._add_option(OptionButton(self._options_container, "Start Measurement"))
        self._add_option(OptionToggle(self._options_container, "Auto Save", initial=True))
        self._add_option(OptionDropdown(self._options_container, "Sample Rate", ["1 Hz", "5 Hz", "10 Hz"], "5 Hz"))

    def _add_option(self, option: Option) -> None:
        self._options.append(option)
        option.add_to(self._options_container)


    


