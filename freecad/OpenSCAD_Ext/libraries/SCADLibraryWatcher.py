"""
SCADLibraryWatcher.py

Watch the OpenSCAD library directory for file changes and trigger
incremental rescans. Designed to integrate with Qt via signals.
"""

import os
from PySide.QtCore import QObject, Signal, QThread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .scan_scad_library import scan_scad_library
from .ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


class _SCADWatchHandler(FileSystemEventHandler):
    """Internal watchdog handler to call scan on changes."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_created(self, event):
        if event.src_path.lower().endswith(".scad"):
            write_log("Info", f"New SCAD file detected: {event.src_path}")
            self.callback([event.src_path])

    def on_modified(self, event):
        if event.src_path.lower().endswith(".scad"):
            write_log("Info", f"SCAD file modified: {event.src_path}")
            self.callback([event.src_path])

    def on_deleted(self, event):
        if event.src_path.lower().endswith(".scad"):
            write_log("Info", f"SCAD file deleted: {event.src_path}")
            self.callback([event.src_path], deleted=True)


class SCADLibraryWatcher(QObject):
    """
    Qt-friendly SCAD library watcher.

    Emits signals when files are added, modified, or removed.
    """
    filesChanged = Signal(list)  # list of updated file paths
    filesDeleted = Signal(list)  # list of deleted file paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.library_path = ensure_openSCADPATH()
        self.observer = Observer()
        self.thread = QThread()
        self.handler = _SCADWatchHandler(self._on_files_changed)

    def start(self):
        """Start watching the library directory."""
        if not os.path.isdir(self.library_path):
            write_log("Error", f"OPENSCADPATH does not exist: {self.library_path}")
            return

        self.observer.schedule(self.handler, self.library_path, recursive=False)
        self.observer.start()
        write_log("Info", f"Started SCAD library watcher at {self.library_path}")

    def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join()
        write_log("Info", "Stopped SCAD library watcher")

    def _on_files_changed(self, paths: list[str], deleted: bool = False):
        """
        Internal callback from watchdog events.
        Calls scan_scad_library for modified/added files.
        """
        if deleted:
            # Emit deletion signal
            self.filesDeleted.emit(paths)
        else:
            # Incremental scan for changed files
            scan_scad_library(file_paths=paths)
            self.filesChanged.emit(paths)

