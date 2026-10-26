from __future__ import annotations

import threading

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from poc_convert import run_poc


class PocScreen(BoxLayout):
    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=8, spacing=8, **kwargs)
        self.result_label = Label(
            text="Tap RUN to start PoC", size_hint_y=None, height=40
        )
        self.log_view = TextInput(text="", readonly=True, font_size=13)
        self.run_button = Button(
            text="RUN", size_hint_y=None, height=48, on_release=self._start
        )
        self.add_widget(self.result_label)
        self.add_widget(self.run_button)
        self.add_widget(self.log_view)

    def _append(self, line: str) -> None:
        def _do() -> None:
            self.log_view.text += line + "\n"
            self.log_view.cursor = (0, len(self.log_view.text))

        from kivy.clock import Clock

        Clock.schedule_once(lambda _dt: _do())

    def _start(self, *_args) -> None:
        self.run_button.disabled = True
        self.result_label.text = "Running..."
        self.log_view.text = ""

        def worker() -> None:
            ok = run_poc(log=self._append)

            def _finish(_dt: object) -> None:
                self.result_label.text = f"RESULT: {'PASS' if ok else 'FAIL'}"
                self.run_button.disabled = False

            from kivy.clock import Clock

            Clock.schedule_once(_finish)

        threading.Thread(target=worker, daemon=True).start()


class PocApp(App):
    def build(self):  # noqa: ANN201
        return PocScreen()


if __name__ == "__main__":
    PocApp().run()
