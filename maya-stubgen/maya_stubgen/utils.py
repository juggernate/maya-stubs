import logging
import pathlib
import shutil
import sys
import time
from collections.abc import Iterator, Callable
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar, Optional

from typing_extensions import ParamSpec

from PySide2 import QtCore, QtWidgets

from . import _logging

logger = _logging.getLogger(__name__)

try:
    import maya  # pyright: ignore[reportUnusedImport]
except ModuleNotFoundError:
    _has_maya = False
else:
    _has_maya = True

__all__ = [
    "initialize_maya",
    "uninitialize_maya",
    "maya_standalone",
    "timed",
    "maya_version",
    "cache_dir",
    "remove_outdated_cache",
]

# List of plugins that contain commands that should have generated stubs
PLUGINS = ["invertShape.mll", "poseInterpolator.mll"]


def initialize_maya() -> None:
    if not _has_maya:
        return

    logger.info("Initializing Maya Standalone")

    # Initialize the QApplication properly to remove the Qt Logging message
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    QtWidgets.QApplication(sys.argv)

    try:
        import maya.standalone

        maya.standalone.initialize()
    except BaseException:
        logger.error("Failed to initialize Maya Standalone")
    else:
        for plugin in PLUGINS:
            try:
                import maya.cmds

                maya.cmds.loadPlugin(plugin)
            except BaseException:
                logger.warning("Couldn't load %s", plugin)

        # remove maya's handler
        logging.getLogger().handlers.pop()
        logger.success("Maya Standalone Initialized")


def uninitialize_maya() -> None:
    if not _has_maya:
        return

    logger.info("Uninitializing Maya Standalone")
    try:
        import maya.standalone

        maya.standalone.uninitialize()
    except BaseException:
        logger.error("Failed to uninitialize Maya Standalone")
    else:
        logger.success("Maya Standalone Uninitialized")
    finally:
        temp_maya_app_dir = Path() / "temp" / "maya_app_dir"

        shutil.rmtree(temp_maya_app_dir, ignore_errors=True)


@contextmanager
def maya_standalone() -> Iterator[None]:
    initialize_maya()
    yield
    uninitialize_maya()


_maya_version: Optional[str] = None


def maya_version() -> str:
    global _maya_version
    import maya.cmds

    if _maya_version is None:
        _maya_version = maya.cmds.about(majorVersion=True)

    return _maya_version


def remove_outdated_cache() -> None:
    """Deletes the existing cache directory if it was generated using another version of Maya."""
    version = maya_version()
    cache = cache_dir()
    if not cache.exists():
        # we have no cache, nothing to do
        return

    maya_version_file = cache / ".maya_version"
    if not maya_version_file.exists():
        cache_version = maya_version_file.read_text().strip()
        if cache_version == version:
            # cache is from current maya version, nothing to do
            return
        logger.warning(
            "Running against Maya %s, but cache was generated using Maya %s; removing existing cache",
            version,
            cache_version,
        )
    else:
        logger.warning("Cache from unknown Maya version found; removing existing cache")

    shutil.rmtree(cache)
    cache.mkdir(parents=True, exist_ok=True)
    maya_version_file.write_text(version)


def cache_dir() -> pathlib.Path:
    return Path().resolve() / ".cache"


P = ParamSpec("P")
T = TypeVar("T")


def timed(func: Callable[P, T]) -> Callable[P, T]:
    def wrap_func(*args: P.args, **kwargs: P.kwargs) -> T:
        t1 = time.perf_counter()
        result = func(*args, **kwargs)
        t2 = time.perf_counter()
        logger.info("Function %s executed in %ss", func.__name__, t2 - t1)
        return result

    return wrap_func
