"""Make SQLite/SpatiaLite connection open & close thread-safe during tests.

On Python 3.13 the selenium live-server tests intermittently crash with
``double free or corruption`` / ``Segmentation fault``. The live server (both
the WSGI ``StaticLiveServerTestCase`` and the Daphne/ASGI
``ChannelsLiveServerTestCase``) serves requests from several threads, so SQLite
connections are opened and closed concurrently. Two things make that fatal:

1. Django's SpatiaLite backend builds ``lib_spatialite_paths`` with
   ``ctypes.util.find_library("spatialite")`` on *every* new connection, and on
   Linux that forks an ``ldconfig`` subprocess. Forking in a multi-threaded
   process while another thread is inside ``malloc``/``free`` (a SQLite
   ``close``) corrupts the C heap.
2. ``close_old_connections()`` / ``connections.close_all()`` run from several
   threads at once (channels' ``DatabaseSyncToAsync`` and the live-server
   thread teardown), closing connections concurrently with other threads
   opening them.

This module memoizes ``find_library`` (so the subprocess fork happens at most
once, while still single-threaded) and serializes connection open/close with a
single process-wide lock. It is imported only from the test settings, so it does
not affect production. The patch is inherited by the forked Daphne child.
"""

import ctypes.util
import functools
import threading

_applied = False
_conn_lock = threading.RLock()


def make_sqlite_threadsafe():
    global _applied
    if _applied:
        return
    _applied = True

    # 1) Memoize find_library so the SpatiaLite backend stops forking an
    #    ldconfig subprocess on every new connection. Pre-warm the cache now,
    #    while we are still single-threaded, so no fork happens once the
    #    live-server threads are running.
    cached_find_library = functools.lru_cache(maxsize=None)(ctypes.util.find_library)
    ctypes.util.find_library = cached_find_library
    try:
        from django.contrib.gis.db.backends.spatialite import base as spatialite_base

        spatialite_base.find_library = cached_find_library
        cached_find_library("spatialite")
    except Exception:
        # GIS backend not importable in this context; the lock below still helps.
        pass

    # 2) Serialize connection open and close so the SQLite C layer is never
    #    opening on one thread while closing on another.
    from django.db.backends.base.base import BaseDatabaseWrapper

    _orig_connect = BaseDatabaseWrapper.connect
    _orig_close = BaseDatabaseWrapper._close

    @functools.wraps(_orig_connect)
    def connect(self):
        with _conn_lock:
            return _orig_connect(self)

    @functools.wraps(_orig_close)
    def _close(self):
        with _conn_lock:
            return _orig_close(self)

    BaseDatabaseWrapper.connect = connect
    BaseDatabaseWrapper._close = _close
