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
import traceback

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from qgis.core import Qgis, QgsProject, QgsMessageLog


@contextmanager
def busy_refreshing(refresh_func):
    """Context manager that shows busy cursor on startup and ensures that
    normal cursor is back on exit. Also ``refresh_func`` is called on exit."""
    try:
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        yield
        refresh_func()
    except Exception as exc:
        QgsMessageLog.logMessage('GuidedOfflineEditing: {}'.format(str(exc)),
                                 'Extensions',
                                 level=Qgis.Critical)
        QgsMessageLog.logMessage(
            'GuidedOfflineEditing: {}'.format(traceback.format_exc()),
            'Extensions',
            level=Qgis.Critical)
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


@contextmanager
def removing(path):
    """Context manager that ensure given path is deleted on exit."""
    try:
        yield
    except Exception as exc:
        QgsMessageLog.logMessage('GuidedOfflineEditing: {}'.format(str(exc)),
                                 'Extensions',
                                 level=Qgis.Critical)
        QgsMessageLog.logMessage(
            'GuidedOfflineEditing: {}'.format(traceback.format_exc()),
            'Extensions',
            level=Qgis.Critical)
    finally:
        path.unlink(missing_ok=True)


@contextmanager
def transactional_project(dest_url=None):
    """Context manager returning a ``QgsProject`` instance and saves it on exit
    if no error occured.

    The project is saved to its original location if ``dest_path`` is ``None``,
    else it is saved to ``dest_path``.

    Implementation detail: after saving the project with ``proj.write()`` (thus
    updating the project file on disk), when the user clicks on the Save icon
    in QGIS UI, a warning is shown indicating that the file has been modified
    after it has been opened by QGIS. Workaround: the project is reloaded with
    ``proj.clear()`` and ``proj.read()``.
    """
    try:
        proj = QgsProject.instance()
        yield proj
    except Exception as exc:
        QgsMessageLog.logMessage('GuidedOfflineEditing: {}'.format(str(exc)),
                                 'Extensions',
                                 level=Qgis.Critical)
        QgsMessageLog.logMessage(
            'GuidedOfflineEditing: {}'.format(traceback.format_exc()),
            'Extensions',
            level=Qgis.Critical)
    finally:
        if not dest_url:
            project_saved = proj.write()
        else:
            project_saved = proj.write(dest_url)
        if not project_saved:
            QgsMessageLog.logMessage('GuidedOfflineEditing: project has not '
                                     'been saved after transaction.',
                                     'Extensions',
                                     level=Qgis.Warning)
            QgsMessageLog.logMessage(
                'GuidedOfflineEditing: {}'.format(traceback.format_exc()),
                'Extensions',
                level=Qgis.Warning)
        # XXX: better way to avoid warning if the user click save ?
        proj.clear()
        if not dest_url:
            proj.read(proj.fileName())
        else:
            proj.read(dest_url)
