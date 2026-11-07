"""MetaMop - a small, offline-first metadata cleaner.

Copyright (C) 2026 BenFreedomWalker
Licensed under the GNU General Public License v3.0 or later.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ExifTags, UnidentifiedImageError

APP_NAME = "MetaMop"
VERSION = "0.1.0"
ISSUES_URL = "https://github.com/BenFreedomWalker/metamop/issues"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
EXIF_NAMES = ExifTags.TAGS


def readable(value: Any) -> str:
    """Turn metadata values into compact, readable text."""
    if isinstance(value, bytes):
        return f"<binary data: {len(value)} bytes>"
    if isinstance(value, (tuple, list)):
        return ", ".join(str(v) for v in value)
    return str(value)


def inspect_image(path: Path) -> list[tuple[str, str]]:
    """Return human-readable metadata found in an image."""
    rows: list[tuple[str, str]] = []
    with Image.open(path) as image:
        rows.append(("Format", str(image.format or "Unknown")))
        rows.append(("Dimensions", f"{image.width} × {image.height}"))
        rows.append(("Color mode", image.mode))
        if getattr(image, "n_frames", 1) > 1:
            rows.append(("Animation/pages", str(image.n_frames)))

        exif = image.getexif()
        for tag_id, value in exif.items():
            name = EXIF_NAMES.get(tag_id, f"EXIF tag {tag_id}")
            rows.append((f"EXIF · {name}", readable(value)))

        ignored = {"exif", "icc_profile", "transparency"}
        for key, value in image.info.items():
            if key.lower() in ignored or key.startswith("_"):
                continue
            if isinstance(value, bytes) and len(value) > 512:
                shown = f"<binary data: {len(value)} bytes>"
            else:
                shown = readable(value)
            rows.append((f"Image · {key}", shown))

    stat = path.stat()
    rows.extend([
        ("File size", f"{stat.st_size:,} bytes"),
        ("Modified", __import__("datetime").datetime.fromtimestamp(stat.st_mtime).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")),
    ])
    return rows


def unique_destination(folder: Path, filename: str) -> Path:
    """Avoid overwriting an earlier output or the source file."""
    target = folder / filename
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    number = 1
    while True:
        candidate = folder / f"{stem}_{number}{suffix}"
        if not candidate.exists():
            return candidate
        number += 1


EXIFTOOL_URL = "https://exiftool.org/"


def find_exiftool() -> str | None:
    """Find ExifTool on PATH or beside the application."""
    found = shutil.which("exiftool") or shutil.which("exiftool.exe")
    if found:
        return found
    candidates = [
        Path(__file__).resolve().with_name("exiftool.exe"),
        Path(__file__).resolve().with_name("exiftool"),
        Path(sys.executable).resolve().parent / "exiftool.exe",
        Path(sys.executable).resolve().parent / "exiftool",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def clean_image(source: Path, output_dir: Path | None = None) -> Path:
    """Remove image metadata with ExifTool without re-encoding image pixels."""
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported image type: {suffix or '(no extension)'}")

    exiftool = find_exiftool()
    if not exiftool:
        raise FileNotFoundError(
            "ExifTool was not found. Download the Windows executable from "
            "https://exiftool.org/, rename it to exiftool.exe, and place it "
            "beside metamop.py or add it to PATH."
        )

    destination_dir = output_dir if output_dir is not None else source.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(
        destination_dir, f"{source.stem}_metamop{source.suffix}"
    )

    # Keep ICC/color-space information and orientation so that colors and
    # automatically rotated photos continue to display correctly. ExifTool
    # edits metadata in the container; it does not decode/recompress pixels.
    command = [
        exiftool,
        "-all=",
        "-CommonIFD0=",
        "--icc_profile:all",
        "-tagsfromfile", "@",
        "-colorspacetags",
        "-orientation",
        "-o", str(destination),
        str(source),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0 or not destination.is_file():
        destination.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "ExifTool could not create the cleaned copy.")
    if destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise RuntimeError("ExifTool created an empty output file.")
    return destination


class MetaMopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {VERSION}")
        self.root.geometry("980x620")
        self.root.minsize(760, 480)
        self.files: list[Path] = []
        self.rows: dict[str, Path] = {}

        self._configure_style()
        self._build_menu()
        self._build_ui()
        self.root.after(100, self._set_initial_status)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista" if sys.platform == "win32" and "vista" in style.theme_names() else "clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=26)
        style.configure("Treeview.Heading", font=("", 9, "bold"))
        style.configure("Title.TLabel", font=("", 17, "bold"))
        style.configure("Muted.TLabel", foreground="#666666")

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About MetaMop", command=self._about)
        help_menu.add_command(label="Download ExifTool", command=self._open_exiftool)
        help_menu.add_command(label="Open issue tracker", command=self._open_issues)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        heading = ttk.Frame(outer)
        heading.pack(fill="x", pady=(0, 12))
        ttk.Label(heading, text="MetaMop", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            heading,
            text="Inspect image metadata and create clean copies — your originals stay untouched.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Add files…", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="Add folder…", command=self.add_folder).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Remove selected", command=self.remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Clear list", command=self.clear_list).pack(side="left", padx=(6, 0))

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, padding=(0, 0, 8, 0))
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        body.add(left, weight=3)
        body.add(right, weight=2)

        ttk.Label(left, text="Files").pack(anchor="w", pady=(0, 5))
        columns = ("name", "type", "size", "status")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="extended")
        for column, title, width in [
            ("name", "File", 220), ("type", "Type", 70),
            ("size", "Size", 85), ("status", "Status", 95),
        ]:
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=55, anchor="w")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._show_details)

        ttk.Label(right, text="Metadata").pack(anchor="w", pady=(0, 5))
        self.details = tk.Text(right, wrap="word", height=10, width=38, padx=9, pady=8,
                               relief="solid", borderwidth=1, font=("TkFixedFont", 9))
        detail_scroll = ttk.Scrollbar(right, orient="vertical", command=self.details.yview)
        self.details.configure(yscrollcommand=detail_scroll.set, state="disabled")
        self.details.pack(side="left", fill="both", expand=True)
        detail_scroll.pack(side="right", fill="y")

        bottom = ttk.LabelFrame(outer, text="Clean copies", padding=9)
        bottom.pack(fill="x", pady=(12, 0))
        output_row = ttk.Frame(bottom)
        output_row.pack(fill="x")
        ttk.Label(output_row, text="Output folder (optional):").pack(side="left")
        self.output_var = tk.StringVar(value="")
        ttk.Entry(output_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=7)
        ttk.Button(output_row, text="Browse…", command=self.choose_output).pack(side="left")
        action_row = ttk.Frame(bottom)
        action_row.pack(fill="x", pady=(8, 0))
        ttk.Button(action_row, text="Clean selected", command=self.clean_selected).pack(side="left")
        ttk.Button(action_row, text="Clean all", command=self.clean_all).pack(side="left", padx=(6, 0))
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(action_row, textvariable=self.status_var, style="Muted.TLabel").pack(side="right")

    def _set_initial_status(self) -> None:
        self.status_var.set("Ready · Offline · Originals are never changed")

    def add_files(self) -> None:
        chosen = filedialog.askopenfilenames(
            title="Add images",
            filetypes=[("Supported images", "*.jpg *.jpeg *.png *.webp *.tif *.tiff"),
                       ("All files", "*.*")],
        )
        self._add_paths(Path(item) for item in chosen)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose an image folder")
        if not folder:
            return
        paths = sorted(
            (p for p in Path(folder).rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED),
            key=lambda p: str(p).casefold(),
        )
        self._add_paths(paths)

    def _add_paths(self, paths: Any) -> None:
        added = 0
        added_items = []
        existing = set(self.files)
        for path in paths:
            path = Path(path)
            if path.suffix.lower() not in SUPPORTED or path in existing:
                continue
            self.files.append(path)
            existing.add(path)
            try:
                size = f"{path.stat().st_size / 1024:.1f} KB"
                status = "Ready"
            except OSError:
                size, status = "—", "Unavailable"
            item = self.tree.insert("", "end", values=(path.name, path.suffix[1:].upper(), size, status))
            self.rows[item] = path
            added_items.append(item)
            added += 1
        if added_items:
            self.tree.selection_set(*added_items)
            self.tree.focus(added_items[0])
            self.tree.see(added_items[0])
            self._show_details()
        self.status_var.set(f"Added {added} file(s) · {len(self.files)} in queue")

    def _show_details(self, _event: object = None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        path = self.rows.get(selected[0])
        if not path:
            return
        try:
            metadata = inspect_image(path)
            content = "\n".join(f"{key}\n  {value}" for key, value in metadata)
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            content = f"Could not read this image.\n\n{exc}"
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", content)
        self.details.configure(state="disabled")

    def remove_selected(self) -> None:
        for item in self.tree.selection():
            path = self.rows.pop(item, None)
            if path in self.files:
                self.files.remove(path)
            self.tree.delete(item)
        self.status_var.set(f"{len(self.files)} file(s) in queue")

    def clear_list(self) -> None:
        self.files.clear()
        self.rows.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.configure(state="disabled")
        self.status_var.set("Queue cleared")

    def choose_output(self) -> None:
        folder = filedialog.askdirectory(title="Choose output folder", initialdir=self.output_var.get())
        if folder:
            self.output_var.set(folder)

    def clean_selected(self) -> None:
        selected = [self.rows[item] for item in self.tree.selection() if item in self.rows]
        if not selected:
            messagebox.showinfo(APP_NAME, "Select one or more files first.")
            return
        self._clean_paths(selected)

    def clean_all(self) -> None:
        if not self.files:
            messagebox.showinfo(APP_NAME, "Add some images first.")
            return
        self._clean_paths(list(self.files))

    def _clean_paths(self, paths: list[Path]) -> None:
        output_text = self.output_var.get().strip()
        output = Path(output_text).expanduser() if output_text else None
        succeeded: list[tuple[Path, Path]] = []
        failures: list[str] = []
        for path in paths:
            try:
                destination = clean_image(path, output)
                succeeded.append((path, destination))
                before = path.stat().st_size
                after = destination.stat().st_size
                delta = after - before
                size_note = f"{after / 1024:.1f} KB ({delta:+,} bytes)"
                for item, row_path in self.rows.items():
                    if row_path == path:
                        values = list(self.tree.item(item, "values"))
                        values[3] = f"Cleaned · {size_note}"
                        self.tree.item(item, values=values)
                        break
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")

        self.status_var.set(f"Cleaned {len(succeeded)} · Failed {len(failures)}")
        if output is None:
            summary = f"Created {len(succeeded)} clean copy/copies beside their original files."
        else:
            summary = f"Created {len(succeeded)} clean copy/copies in:\n{output}"
        if succeeded:
            size_lines = []
            for original, destination in succeeded:
                change = destination.stat().st_size - original.stat().st_size
                size_lines.append(f"{destination.name}: {change:+,} bytes")
            if size_lines:
                summary += "\n\nSize change:\n" + "\n".join(size_lines[:8])
        if failures:
            summary += "\n\nCould not clean:\n" + "\n".join(failures[:8])
            if len(failures) > 8:
                summary += f"\n…and {len(failures) - 8} more."
            messagebox.showwarning(APP_NAME, summary)
        else:
            messagebox.showinfo(APP_NAME, summary)

    def _about(self) -> None:
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME} {VERSION}\n\nA lightweight, offline-first image metadata cleaner.\n\n"
            "Copyright © 2026 BenFreedomWalker\n"
            "Licensed under GNU GPL-3.0-or-later.\n"
            "No warranty is provided. See LICENSE for details.",
        )

    def _open_exiftool(self) -> None:
        import webbrowser
        webbrowser.open(EXIFTOOL_URL)

    def _open_issues(self) -> None:
        import webbrowser
        webbrowser.open(ISSUES_URL)


def main() -> None:
    root = tk.Tk()
    MetaMopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
