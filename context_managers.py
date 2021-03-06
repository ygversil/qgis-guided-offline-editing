# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GuidedOfflineEditingPlugin project_context_manager.py
                                 A QGIS plugin
 Extend the built-in Offline Editing Plugin providing automated processes
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-06-08
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Yann Voté
        email                : ygversil@lilo.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from contextlib import contextmanager

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from qgis.core import QgsProject, QgsSettings

from .utils import log_exception, log_message


@contextmanager
def busy_refreshing(iface, refresh_func=None):
    """Context manager that shows busy cursor on startup and ensures that
    normal cursor is back on exit. Also ``refresh_func`` is called on exit."""
    try:
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        yield
        if refresh_func is not None:
            refresh_func()
    except Exception as exc:
        log_exception(exc, level='Critical', feedback=True, iface=iface)
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


@contextmanager
def qgis_group_settings(iface, group_prefix):
    """Context manager returning a ``QgsSettings`` instance ready to read
    settings within the `group_prefix`` group.

    It ensures that the group is ended on exit.
    """
    s = QgsSettings()
    s.beginGroup(group_prefix)
    try:
        yield s
    except Exception as exc:
        log_exception(exc, level='Warning', feedback=True, iface=iface)
    finally:
        s.endGroup()


@contextmanager
def removing(iface, path):
    """Context manager that ensure given path is deleted on exit."""
    try:
        yield
    except Exception as exc:
        log_exception(exc, level='Critical', feedback=True, iface=iface)
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def temporary_connect_signal_slot(iface, signal, slot):
    """Context manager that connects the given PyQt signal to given slot on
    enter and ensure it is disconnected on exit.
    """
    try:
        signal.connect(slot)
        yield
    except Exception as exc:
        log_exception(exc, level='Critical', feedback=True, iface=iface)
    finally:
        signal.disconnect(slot)


@contextmanager
def transactional_project(iface, src_url=None, dest_url=None,
                          dont_resolve_layers=True):
    """Context manager returning a ``QgsProject`` instance and saves it on exit
    if no error occured.

    If ``src_url`` is ``None``, the returned project is the current one (the
    one loaded int QGIS interface). Else, the project found at ``src_url`` is
    returned.

    The project is saved to its original location if ``dest_url`` is ``None``,
    else it is saved to ``dest_url``.

    Implementation detail: after saving the project with ``proj.write()`` (thus
    updating the project file on disk), when the user clicks on the Save icon
    in QGIS UI, a warning is shown indicating that the file has been modified
    after it has been opened by QGIS. Workaround: the project is reloaded with
    ``proj.clear()`` and ``proj.read()``.
    """
    try:
        if src_url:
            proj = QgsProject()
            if dont_resolve_layers:
                proj.read(src_url, QgsProject.FlagDontResolveLayers)
            else:
                proj.read(src_url)
        else:
            proj = QgsProject.instance()
        yield proj
    except Exception as exc:
        log_exception(exc, level='Critical', feedback=True, iface=iface)
    finally:
        if not dest_url:
            project_saved = proj.write()
            dest_url = proj.fileName()
        else:
            project_saved = proj.write(dest_url)
        if not project_saved:
            log_message('Project has not been saved after transaction.',
                        level='Warning', feedback=True, iface=iface)
        # XXX: better way to avoid warning if the user click save ?
        proj.clear()
        proj.read(dest_url)
