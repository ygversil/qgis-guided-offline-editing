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

import traceback

from qgis.core import Qgis, QgsMessageLog


def log_exception(err, level='Info', feedback=False, iface=None, duration=5):
    """Output the given exception in QGIS logs using the given level.

    If ``feedback`` is ``True``, then ``iface`` must reference a valid
    ``QgisInterface`` instance so that the message can be shown in the message
    bar in QGIS interface.
    """
    log_message(str(err), level=level, feedback=feedback, iface=iface,
                duration=duration)
    log_message(traceback.format_exc(), level=level)


def log_message(msg, level='Info', feedback=False, iface=None,
                duration=5):
    """Output the given message in QGIS logs using the given level.

    If ``feedback`` is ``True``, then ``iface`` must reference a valid
    ``QgisInterface`` instance so that the message can be shown in the message
    bar in QGIS interface.
    """
    level = getattr(Qgis, level)
    QgsMessageLog.logMessage(msg, 'GuidedOfflineEditing', level=level)
    if feedback:
        assert iface is not None
        iface.messageBar().pushMessage('GuidedOfflineEditing', msg,
                                       level=level, duration=duration)


def path_relative_to(path, parent):
    """Return a version of ``path`` (a filesystem path) relative to ``parent``,
    that is the relative sub-path of ``path`` without ``parent``.

    Return ``None`` if ``path`` is not a relative path to ``parent``.

    ``path`` and ``parent`` must be Python ``pathlib.Path`` objects.
    """
    try:
        return path.relative_to(parent)
    except ValueError:
        return None