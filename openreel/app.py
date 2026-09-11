from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .config import Settings, get_secret, set_secret
from .pipeline import Pipeline


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OpenReel AI")
        self.geometry("900x650")
        self.minsize(760, 560)
        self.settings = Settings.load()
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self._build()
        self.after(100, self._poll)

    def _build(self):
        container = ttk.Frame(self, padding=24)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="OPENREEL AI", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(container, text="Describe a video. OpenReel plans and renders every shot.").pack(anchor="w", pady=(2, 18))
        self.prompt = tk.Text(container, height=12, wrap="word", font=("Segoe UI", 11))
        self.prompt.pack(fill="both", expand=True)

        options = ttk.Frame(container)
        options.pack(fill="x", pady=12)
        ttk.Label(options, text="Length").pack(side="left")
        self.duration = tk.IntVar(value=30)
        ttk.Spinbox(options, from_=15, to=120, increment=5, textvariable=self.duration, width=6).pack(side="left", padx=(8, 18))
        ttk.Label(options, text="seconds").pack(side="left", padx=(0, 18))
        ttk.Button(options, text="Settings", command=self._settings_dialog).pack(side="right")
        ttk.Button(options, text="Open output folder", command=self._open_output).pack(side="right", padx=8)

        self.progress = ttk.Progressbar(container, maximum=100)
        self.progress.pack(fill="x", pady=(2, 8))
        self.status = tk.StringVar(value="Ready")
        ttk.Label(container, textvariable=self.status).pack(anchor="w")
        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(16, 0))
        self.generate_button = ttk.Button(buttons, text="Generate MP4", command=self._generate)
        self.generate_button.pack(side="left")
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel_event.set, state="disabled")
        self.cancel_button.pack(side="left", padx=8)

    def _generate(self):
        prompt = self.prompt.get("1.0", "end").strip()
        duration = self.duration.get()
        if not prompt:
            messagebox.showwarning("Prompt required", "Describe the video you want to create.")
            return
        if duration < 15 or duration > 120:
            messagebox.showwarning("Invalid length", "Choose a length from 15 to 120 seconds.")
            return
        self.cancel_event.clear()
        self.generate_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.worker = threading.Thread(target=self._run, args=(prompt, duration), daemon=True)
        self.worker.start()

    def _run(self, prompt: str, duration: int):
        try:
            output = Pipeline(
                self.settings,
                self.cancel_event,
                lambda value, text: self.events.put(("progress", value, text)),
            ).run(prompt, duration)
            self.events.put(("done", output))
        except Exception as exc:  # GUI boundary: report provider/process errors
            self.events.put(("error", str(exc)))

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    self.progress["value"] = event[1] * 100
                    self.status.set(event[2])
                elif event[0] == "done":
                    self._idle()
                    messagebox.showinfo("Video complete", f"Saved to:\n{event[1]}")
                elif event[0] == "error":
                    self._idle()
                    messagebox.showerror("Generation stopped", event[1])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _idle(self):
        self.generate_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _open_output(self):
        path = Path(self.settings.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _settings_dialog(self):
        SettingsDialog(self, self.settings)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: App, settings: Settings):
        super().__init__(parent)
        self.parent, self.settings = parent, settings
        self.title("Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        self.values = {}
        fields = [
            ("Render mode", "render_mode", settings.render_mode),
            ("Video provider", "video_provider", settings.video_provider),
            ("Video model", "video_model", settings.video_model),
            ("HF endpoint", "hf_endpoint", settings.hf_endpoint),
            ("Planner base URL", "planner_base_url", settings.planner_base_url),
            ("Planner model", "planner_model", settings.planner_model),
            ("Output folder", "output_dir", settings.output_dir),
        ]
        for row, (label, key, value) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            variable = tk.StringVar(value=value)
            self.values[key] = variable
            if key == "render_mode":
                widget = ttk.Combobox(frame, textvariable=variable, values=("public_assets", "neural_provider"), state="readonly", width=54)
            elif key == "video_provider":
                widget = ttk.Combobox(frame, textvariable=variable, values=("replicate", "huggingface"), state="readonly", width=54)
            else:
                widget = ttk.Entry(frame, textvariable=variable, width=57)
            widget.grid(row=row, column=1, pady=5, padx=(12, 0))
        row = len(fields)
        self.secrets = {}
        for label, key in (
            ("Pexels key (optional/free)", "pexels_token"),
            ("Video provider token", "video_token"),
            ("Planner token (optional)", "planner_token"),
        ):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            if key in {"planner_token", "pexels_token"}:
                secret_name = key
            else:
                secret_name = f"{settings.video_provider}_token"
            variable = tk.StringVar(value=get_secret(secret_name))
            self.secrets[key] = variable
            ttk.Entry(frame, textvariable=variable, show="•", width=57).grid(row=row, column=1, pady=5, padx=(12, 0))
            row += 1
        controls = ttk.Frame(frame)
        controls.grid(row=row, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(controls, text="Cancel", command=self.destroy).pack(side="left")
        ttk.Button(controls, text="Save", command=self._save).pack(side="left", padx=(8, 0))

    def _save(self):
        for key, value in self.values.items():
            setattr(self.settings, key, value.get().strip())
        self.settings.save()
        set_secret(f"{self.settings.video_provider}_token", self.secrets["video_token"].get().strip())
        set_secret("planner_token", self.secrets["planner_token"].get().strip())
        set_secret("pexels_token", self.secrets["pexels_token"].get().strip())
        self.parent.settings = self.settings
        self.destroy()


def main():
    App().mainloop()
