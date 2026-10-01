#!/usr/bin/env python3
"""Simple cross-platform GUI for the AnyPS5 relinker.

The GUI intentionally uses only Python's standard library (Tkinter), so it can
wrap an existing AnyPS5 relinker build without adding another C++ dependency.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


APP_TITLE = "AnyPS5 - Game Porting Assistant"


def project_root() -> Path:
    # A PyInstaller one-file build runs from a temporary extraction directory.
    # Resolve bundled resources relative to the actual GUI executable instead.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def find_relinker() -> Path | None:
    root = project_root()
    names = ("relinker.exe", "relinker") if os.name == "nt" else ("relinker", "relinker.exe")
    candidates = [
        root / name
        for name in names
    ]
    candidates += [
        root / "build" / "core" / "relinker" / name
        for name in names
    ]
    candidates += [
        root / "build" / name
        for name in names
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    build_root = root / "build"
    if build_root.is_dir():
        for name in names:
            try:
                found = next(build_root.rglob(name))
            except StopIteration:
                continue
            if found.is_file():
                return found
    return None


def default_output(input_path: Path, target: str) -> Path:
    suffix = ".exe" if target == "Windows" else ""
    return input_path.with_name(input_path.stem + "_native" + suffix)


def build_command(
    relinker: Path,
    input_path: Path,
    output_path: Path,
    target: str,
    to_intel: bool,
    skip_syscall: bool,
    skip_modules: bool,
    lazy_binding: bool,
    registry: bool,
    unused_filter: str,
    rpath: str,
    windows_diagnostics: bool,
    windows_gui: bool,
) -> list[str]:
    command = [str(relinker)]
    if target == "Windows":
        command.append("--windows")
        if windows_diagnostics:
            command.append("--windows-diagnostics")
        if windows_gui:
            command.append("--windows-gui")
    if to_intel:
        command.append("--to-intel")
    if skip_syscall:
        command.append("--skip-syscall-check")
    if skip_modules:
        command.append("--skip-sce-module")
    if lazy_binding:
        command.append("--lazy-binding")
    if registry:
        command.append("--registry")
    if unused_filter:
        command.append(f"unused-filter={unused_filter}")
    if rpath.strip():
        command.extend(["--rpath", rpath.strip()])
    command.extend([str(input_path), str(output_path)])
    return command


class AnyPS5Gui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x720")
        self.minsize(820, 620)

        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None

        self.relinker_var = tk.StringVar()
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.target_var = tk.StringVar(value="Windows" if os.name == "nt" else "Linux")
        self.to_intel_var = tk.BooleanVar(value=False)
        self.skip_syscall_var = tk.BooleanVar(value=False)
        self.skip_modules_var = tk.BooleanVar(value=False)
        self.lazy_binding_var = tk.BooleanVar(value=False)
        self.registry_var = tk.BooleanVar(value=False)
        self.windows_diagnostics_var = tk.BooleanVar(value=False)
        self.windows_gui_var = tk.BooleanVar(value=False)
        self.filter_var = tk.StringVar(value="")
        self.rpath_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.command_var = tk.StringVar(value="")

        self._build_style()
        self._build_ui()
        self._detect_relinker()

        self.after(100, self._drain_queue)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("TkDefaultFont", 10))
        style.configure("Section.TLabelframe.Label", font=("TkDefaultFont", 10, "bold"))
        style.configure("Primary.TButton", padding=(16, 8))
        style.configure("Status.TLabel", padding=(8, 6))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="AnyPS5", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Port a PS5 ELF into a native Linux or Windows executable without typing relinker commands.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        files = ttk.LabelFrame(outer, text="1. Files", style="Section.TLabelframe", padding=12)
        files.pack(fill="x", pady=(0, 10))
        self._path_row(files, "Relinker", self.relinker_var, self.browse_relinker, row=0)
        self._path_row(files, "PS5 ELF", self.input_var, self.browse_input, row=1)
        self._path_row(files, "Output", self.output_var, self.browse_output, row=2)

        target = ttk.LabelFrame(outer, text="2. Target", style="Section.TLabelframe", padding=12)
        target.pack(fill="x", pady=(0, 10))
        row = ttk.Frame(target)
        row.pack(fill="x")
        ttk.Label(row, text="Target OS:", width=12).pack(side="left")
        target_combo = ttk.Combobox(
            row,
            textvariable=self.target_var,
            values=("Windows", "Linux"),
            state="readonly",
            width=16,
        )
        target_combo.pack(side="left")
        target_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_output())
        ttk.Checkbutton(
            row,
            text="Intel CPU: enable AMD→x86-64 conversion (--to-intel)",
            variable=self.to_intel_var,
            command=self._refresh_command,
        ).pack(side="left", padx=(16, 0))

        advanced_toggle = ttk.Checkbutton(
            outer,
            text="Show advanced options",
            variable=self.show_advanced_var,
            command=self._toggle_advanced,
        )
        advanced_toggle.pack(anchor="w", pady=(0, 4))

        advanced = ttk.LabelFrame(outer, text="Advanced (optional)", style="Section.TLabelframe", padding=10)
        advanced.pack(fill="x", pady=(0, 10))

        grid = ttk.Frame(advanced)
        grid.pack(fill="x")
        ttk.Checkbutton(grid, text="Skip syscall check", variable=self.skip_syscall_var, command=self._refresh_command).grid(row=0, column=0, sticky="w", padx=(0, 16), pady=2)
        ttk.Checkbutton(grid, text="Skip sce_module/sce_modules", variable=self.skip_modules_var, command=self._refresh_command).grid(row=0, column=1, sticky="w", padx=(0, 16), pady=2)
        ttk.Checkbutton(grid, text="Lazy binding", variable=self.lazy_binding_var, command=self._refresh_command).grid(row=0, column=2, sticky="w", pady=2)
        ttk.Checkbutton(grid, text="Write registry JSON", variable=self.registry_var, command=self._refresh_command).grid(row=1, column=0, sticky="w", pady=2)
        self.windows_diagnostics_check = ttk.Checkbutton(
            grid, text="Windows diagnostics", variable=self.windows_diagnostics_var, command=self._refresh_command
        )
        self.windows_diagnostics_check.grid(row=1, column=1, sticky="w", pady=2)
        self.windows_gui_check = ttk.Checkbutton(
            grid, text="Windows GUI subsystem", variable=self.windows_gui_var, command=self._refresh_command
        )
        self.windows_gui_check.grid(row=1, column=2, sticky="w", pady=2)

        fields = ttk.Frame(advanced)
        fields.pack(fill="x", pady=(8, 0))
        ttk.Label(fields, text="Unused-filter:").grid(row=0, column=0, sticky="w")
        filter_combo = ttk.Combobox(fields, textvariable=self.filter_var, values=("", "0", "1", "2"), state="readonly", width=8)
        filter_combo.grid(row=0, column=1, padx=(6, 18), sticky="w")
        filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_command())
        ttk.Label(fields, text="RPATH:").grid(row=0, column=2, sticky="w")
        rpath = ttk.Entry(fields, textvariable=self.rpath_var)
        rpath.grid(row=0, column=3, padx=(6, 0), sticky="ew")
        rpath.bind("<KeyRelease>", lambda _e: self._refresh_command())
        fields.columnconfigure(3, weight=1)

        self.advanced_frame = advanced
        self.advanced_frame.pack_forget()

        self.command_frame = ttk.LabelFrame(outer, text="Command preview", padding=8)
        self.command_frame.pack(fill="x", pady=(0, 10))
        ttk.Entry(self.command_frame, textvariable=self.command_var, state="readonly").pack(fill="x")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Label(bottom, textvariable=self.status_var, style="Status.TLabel").pack(side="left", fill="x", expand=True)

        self.open_folder_button = ttk.Button(bottom, text="Open Folder", command=self.open_output_folder)
        self.open_folder_button.pack(side="right", padx=(8, 0))
        self.stop_button = ttk.Button(bottom, text="Stop", command=self.stop_process, state="disabled")
        self.stop_button.pack(side="right", padx=(8, 0))
        self.run_button = ttk.Button(bottom, text="Convert & Run", style="Primary.TButton", command=lambda: self.start_process(True))
        self.run_button.pack(side="right", padx=(8, 0))
        self.convert_button = ttk.Button(bottom, text="Convert", style="Primary.TButton", command=lambda: self.start_process(False))
        self.convert_button.pack(side="right")

        log_frame = ttk.LabelFrame(outer, text="Output", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log = ScrolledText(log_frame, height=10, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

        self.input_var.trace_add("write", lambda *_: self._input_changed())
        self.relinker_var.trace_add("write", lambda *_: self._refresh_command())

    def _toggle_advanced(self) -> None:
        if self.show_advanced_var.get():
            self.advanced_frame.pack(fill="x", pady=(0, 10), before=self.command_frame)
        else:
            self.advanced_frame.pack_forget()
        self._refresh_command()

    def _runtime_status(self, output_path: Path) -> str:
        missing = []
        if not (output_path.parent / "libs").is_dir():
            missing.append("libs/")
        if not (output_path.parent / "app0").is_dir():
            missing.append("app0/")
        return (
            "Runtime layout detected: libs/ + app0/"
            if not missing
            else "Runtime layout incomplete: " + ", ".join(missing) + " missing."
        )

    def _path_row(self, parent: ttk.Widget, label: str, variable: tk.StringVar, browse, row: int) -> None:
        ttk.Label(parent, text=label + ":", width=12).grid(row=row, column=0, sticky="w", pady=5)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=5)
        ttk.Button(parent, text="Browse...", command=browse).grid(row=row, column=2, pady=5)
        parent.columnconfigure(1, weight=1)

    def _detect_relinker(self) -> None:
        detected = find_relinker()
        if detected:
            self.relinker_var.set(str(detected))
            self._log(f"Found relinker: {detected}")
        else:
            self._log("Relinker not found automatically. Build AnyPS5 first, then use Browse...")

    def browse_relinker(self) -> None:
        path = filedialog.askopenfilename(
            title="Select AnyPS5 relinker",
            filetypes=(("Relinker executable", "relinker*"), ("All files", "*.*")),
        )
        if path:
            self.relinker_var.set(path)

    def browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select PS5 ELF executable",
            filetypes=(("ELF executables", "*.elf;*.bin;*.*"), ("All files", "*.*")),
        )
        if path:
            self.input_var.set(path)

    def browse_output(self) -> None:
        current = Path(self.output_var.get()) if self.output_var.get() else None
        initial_dir = str(current.parent) if current and current.parent.exists() else ""
        suffix = ".exe" if self.target_var.get() == "Windows" else ""
        path = filedialog.asksaveasfilename(
            title="Choose output executable",
            initialdir=initial_dir,
            initialfile=(current.name if current else "game_native" + suffix),
            defaultextension=suffix,
            filetypes=(("Executable", "*" + suffix if suffix else "*"), ("All files", "*.*")),
        )
        if path:
            self.output_var.set(path)

    def _input_changed(self) -> None:
        self._refresh_output()
        self._refresh_command()

    def _refresh_output(self) -> None:
        input_path = Path(self.input_var.get()) if self.input_var.get().strip() else None
        output_path = Path(self.output_var.get()) if self.output_var.get().strip() else None
        if input_path and input_path.exists():
            default = default_output(input_path, self.target_var.get())
            if output_path is None or output_path.parent == input_path.parent and (
                output_path.name.startswith(input_path.stem + "_native")
            ):
                self.output_var.set(str(default))
        self._update_windows_options()
        self._refresh_command()

    def _update_windows_options(self) -> None:
        state = tk.NORMAL if self.target_var.get() == "Windows" else tk.DISABLED
        self.windows_diagnostics_check.configure(state=state)
        self.windows_gui_check.configure(state=state)
        if state == tk.DISABLED:
            self.windows_diagnostics_var.set(False)
            self.windows_gui_var.set(False)

    def _refresh_command(self) -> None:
        relinker = Path(self.relinker_var.get().strip()) if self.relinker_var.get().strip() else Path("relinker")
        input_path = Path(self.input_var.get().strip()) if self.input_var.get().strip() else Path("input.elf")
        output_path = Path(self.output_var.get().strip()) if self.output_var.get().strip() else default_output(input_path, self.target_var.get())
        command = build_command(
            relinker,
            input_path,
            output_path,
            self.target_var.get(),
            self.to_intel_var.get(),
            self.skip_syscall_var.get(),
            self.skip_modules_var.get(),
            self.lazy_binding_var.get(),
            self.registry_var.get(),
            self.filter_var.get(),
            self.rpath_var.get(),
            self.windows_diagnostics_var.get() if self.target_var.get() == "Windows" else False,
            self.windows_gui_var.get() if self.target_var.get() == "Windows" else False,
        )
        self.command_var.set(subprocess.list2cmdline(command))

    def start_process(self, launch_after: bool = False) -> None:
        if self.process is not None:
            return

        relinker = Path(self.relinker_var.get().strip())
        input_path = Path(self.input_var.get().strip())
        output_path = Path(self.output_var.get().strip())

        if not relinker.is_file():
            messagebox.showerror("AnyPS5", "Relinker executable was not found. Build AnyPS5 or select relinker manually.")
            return
        if not input_path.is_file():
            messagebox.showerror("AnyPS5", "Please select a valid PS5 ELF executable.")
            return
        if not output_path.name:
            messagebox.showerror("AnyPS5", "Please choose an output executable.")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = build_command(
            relinker,
            input_path,
            output_path,
            self.target_var.get(),
            self.to_intel_var.get(),
            self.skip_syscall_var.get(),
            self.skip_modules_var.get(),
            self.lazy_binding_var.get(),
            self.registry_var.get(),
            self.filter_var.get(),
            self.rpath_var.get(),
            self.windows_diagnostics_var.get() if self.target_var.get() == "Windows" else False,
            self.windows_gui_var.get() if self.target_var.get() == "Windows" else False,
        )

        self._clear_log()
        self._log("$ " + " ".join(self._quote(part) for part in command))
        self.status_var.set("Converting...")
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        thread = threading.Thread(target=self._worker, args=(command, output_path, launch_after), daemon=True)
        thread.start()

    @staticmethod
    def _quote(value: str) -> str:
        if any(ch.isspace() for ch in value) or '"' in value:
            return subprocess.list2cmdline([value])
        return value

    def _worker(self, command: list[str], output_path: Path, launch_after: bool) -> None:
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(output_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.queue.put(("log", line.rstrip()))
            code = self.process.wait()
            self.queue.put(("finished", (code, output_path, launch_after)))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def stop_process(self) -> None:
        process = self.process
        if process is None:
            return
        try:
            process.terminate()
        except OSError:
            pass

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "finished":
                    code, output_path, launch_after = payload
                    self.process = None
                    self.convert_button.configure(state="normal")
                    self.run_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    if code == 0:
                        self.status_var.set("Conversion completed")
                        self._log(f"SUCCESS: {output_path}")
                        runtime = self._runtime_status(output_path)
                        self._log(runtime)
                        if launch_after:
                            if (output_path.parent / "libs").is_dir() and (output_path.parent / "app0").is_dir():
                                self._launch(output_path)
                            else:
                                messagebox.showwarning(
                                    "AnyPS5",
                                    "Conversion completed, but the runtime folders are incomplete.\n\n"
                                    f"{runtime}\n\n"
                                    f"Executable:\n{output_path}\n\n"
                                    "Add the required runtime files, then use Open Folder.",
                                )
                        else:
                            messagebox.showinfo(
                                "AnyPS5",
                                "Conversion completed.\n\n"
                                f"Executable:\n{output_path}\n\n"
                                f"{runtime}",
                            )
                    else:
                        self.status_var.set(f"Failed (exit code {code})")
                        messagebox.showerror(
                            "AnyPS5",
                            f"Conversion failed with exit code {code}.\n\nSee the Output panel for details.",
                        )
                elif kind == "error":
                    self.process = None
                    self.run_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.status_var.set("Failed")
                    messagebox.showerror("AnyPS5", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def open_output_folder(self) -> None:
        path = Path(self.output_var.get().strip()) if self.output_var.get().strip() else None
        folder = path.parent if path and path.parent.exists() else Path.cwd()
        try:
            if os.name == "nt":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("AnyPS5", f"Could not open the output folder.\n\n{exc}")

    def _launch(self, output_path: Path) -> None:
        if not output_path.is_file():
            messagebox.showerror("AnyPS5", f"Output executable does not exist:\n{output_path}")
            return
        try:
            if os.name != "nt":
                output_path.chmod(output_path.stat().st_mode | 0o111)
            subprocess.Popen([str(output_path)], cwd=str(output_path.parent))
            self._log(f"LAUNCHED: {output_path}")
            self.status_var.set("Game launched")
        except Exception as exc:
            messagebox.showerror("AnyPS5", f"Could not launch the converted game.\n\n{exc}")

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _close(self) -> None:
        if self.process is not None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.destroy()


def main() -> None:
    app = AnyPS5Gui()
    app.mainloop()


if __name__ == "__main__":
    main()
