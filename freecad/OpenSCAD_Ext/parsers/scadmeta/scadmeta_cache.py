"""
TinyDB-backed cache for SCAD file metadata, with optional Watchdog monitoring.

Workflow
--------
1. ``ScadMetaCache.get(path)`` returns a cached ``ScadMeta`` dict if the file
   has not changed since it was last parsed (checked via mtime then SHA-256).
2. ``ScadMetaCache.put(path, meta_dict)`` stores a fresh result.
3. ``ScadMetaCache.watch_directory(dir)`` starts a Watchdog observer that
   automatically invalidates stale cache entries when SCAD files change on disk.

The cache is stored as a plain JSON file managed by TinyDB.  Its default
location is::

    <FreeCAD-user-data>/OpenSCAD_Ext/scad_meta_cache.json

On non-FreeCAD environments (unit tests, CLI tools) it falls back to::

    ~/.cache/openscad_ext/scad_meta_cache.json
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependencies – degrade gracefully if not installed
# ---------------------------------------------------------------------------

try:
    from tinydb import TinyDB, Query
    from tinydb.storages import JSONStorage
    from tinydb.middlewares import CachingMiddleware
    _TINYDB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TINYDB_AVAILABLE = False
    log.warning("tinydb not installed – SCAD metadata cache disabled.")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    _WATCHDOG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _WATCHDOG_AVAILABLE = False
    log.warning("watchdog not installed – automatic cache invalidation disabled.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_cache_path() -> str:
    """Return the platform-appropriate cache file path."""
    try:
        import FreeCAD  # type: ignore
        base = FreeCAD.getUserAppDataDir()
        return os.path.join(base, "OpenSCAD_Ext", "scad_meta_cache.json")
    except Exception:
        cache_dir = Path.home() / ".cache" / "openscad_ext"
        return str(cache_dir / "scad_meta_cache.json")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

if _WATCHDOG_AVAILABLE:
    class _ScadChangeHandler(FileSystemEventHandler):
        """Invalidates cache entries when SCAD files are modified or deleted."""

        def __init__(self, cache: "ScadMetaCache") -> None:
            super().__init__()
            self._cache = cache

        def _handle(self, path: str) -> None:
            if path.lower().endswith(".scad"):
                log.debug("watchdog: invalidating cache for %s", path)
                self._cache.invalidate(path)

        def on_modified(self, event: "FileSystemEvent") -> None:
            if not event.is_directory:
                self._handle(event.src_path)

        def on_deleted(self, event: "FileSystemEvent") -> None:
            if not event.is_directory:
                self._handle(event.src_path)

        def on_moved(self, event: "FileSystemEvent") -> None:
            if not event.is_directory:
                self._handle(event.src_path)


# ---------------------------------------------------------------------------
# Main cache class
# ---------------------------------------------------------------------------

class ScadMetaCache:
    """
    Persistent metadata cache for SCAD files.

    Parameters
    ----------
    cache_path:
        Path to the TinyDB JSON file.  Defaults to the FreeCAD user-data
        directory or ``~/.cache/openscad_ext/``.
    """

    def __init__(self, cache_path: Optional[str] = None) -> None:
        self._path = cache_path or _default_cache_path()
        self._lock = threading.Lock()
        self._db: Optional[object] = None
        self._table: Optional[object] = None
        self._observer: Optional[object] = None
        self._watched: set = set()

        if _TINYDB_AVAILABLE:
            self._open_db()

    # ------------------------------------------------------------------
    # Database lifecycle
    # ------------------------------------------------------------------

    def _open_db(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        try:
            self._db = TinyDB(
                self._path,
                storage=CachingMiddleware(JSONStorage),
            )
            self._table = self._db.table("scad_meta")
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to open TinyDB cache at %s: %s", self._path, exc)
            self._db = None
            self._table = None

    def close(self) -> None:
        """Flush cache to disk and stop watchdog observer."""
        if self._observer and _WATCHDOG_AVAILABLE:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._observer = None

        if self._db is not None:
            try:
                self._db.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._db = None

    # ------------------------------------------------------------------
    # Cache read / write
    # ------------------------------------------------------------------

    def get(self, path: str) -> Optional[Dict]:
        """
        Return the cached metadata dict for *path* if still valid, else ``None``.

        Validity is determined first by mtime (cheap), then confirmed by
        SHA-256 hash (only when mtime changed).
        """
        if self._table is None:
            return None

        path = os.path.abspath(path)

        with self._lock:
            Q = Query()
            record = self._table.get(Q.path == path)  # type: ignore[union-attr]

        if record is None:
            return None

        try:
            current_mtime = os.path.getmtime(path)
            cached_mtime = record.get("mtime", -1)

            if abs(current_mtime - cached_mtime) < 0.002:
                # mtime matches – trust the cache
                return record.get("meta")

            # mtime changed – confirm with hash
            if _sha256(path) == record.get("hash", ""):
                # content unchanged, update mtime
                with self._lock:
                    Q = Query()
                    self._table.update(  # type: ignore[union-attr]
                        {"mtime": current_mtime}, Q.path == path
                    )
                return record.get("meta")

        except OSError:
            pass

        return None

    def put(self, path: str, meta_dict: Dict) -> None:
        """Store *meta_dict* for *path* in the cache."""
        if self._table is None:
            return

        path = os.path.abspath(path)

        try:
            record = {
                "path": path,
                "mtime": os.path.getmtime(path),
                "hash": _sha256(path),
                "meta": meta_dict,
            }
            with self._lock:
                Q = Query()
                self._table.upsert(record, Q.path == path)  # type: ignore[union-attr]
                # Flush the caching middleware
                if hasattr(self._db, "storage") and hasattr(self._db.storage, "flush"):
                    self._db.storage.flush()  # type: ignore[union-attr]
        except Exception as exc:
            log.debug("Cache put failed for %s: %s", path, exc)

    def invalidate(self, path: str) -> None:
        """Remove the cache entry for *path*."""
        if self._table is None:
            return

        path = os.path.abspath(path)
        with self._lock:
            Q = Query()
            self._table.remove(Q.path == path)  # type: ignore[union-attr]

    def clear(self) -> None:
        """Remove all cached entries."""
        if self._table is None:
            return
        with self._lock:
            self._table.truncate()  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Watchdog directory monitoring
    # ------------------------------------------------------------------

    def watch_directory(self, directory: str, recursive: bool = False) -> None:
        """
        Start watching *directory* for SCAD file changes.

        When a watched file changes on disk its cache entry is automatically
        invalidated so the next call to :meth:`get` triggers a re-parse.
        Does nothing if watchdog is not installed.
        """
        if not _WATCHDOG_AVAILABLE:
            log.debug("watchdog not available – directory watching skipped.")
            return

        directory = os.path.abspath(directory)
        if directory in self._watched:
            return

        if self._observer is None:
            self._observer = Observer()
            self._observer.start()  # type: ignore[union-attr]

        handler = _ScadChangeHandler(self)
        self._observer.schedule(handler, directory, recursive=recursive)  # type: ignore[union-attr]
        self._watched.add(directory)
        log.debug("watchdog: watching %s", directory)

    def stop_watching(self, directory: str) -> None:
        """Stop watching a specific directory (best-effort)."""
        # Watchdog does not expose per-directory unschedule easily; clear all
        # and restart remaining watches.
        directory = os.path.abspath(directory)
        self._watched.discard(directory)


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised)
# ---------------------------------------------------------------------------

_cache_instance: Optional[ScadMetaCache] = None
_cache_lock = threading.Lock()


def get_cache() -> ScadMetaCache:
    """Return the module-level shared :class:`ScadMetaCache` instance."""
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = ScadMetaCache()
    return _cache_instance
