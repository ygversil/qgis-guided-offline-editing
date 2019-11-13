# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GuidedOfflineEditingPlugin layer_list.py
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

from PyQt5.QtCore import QObject, QStringListModel, Qt, pyqtSignal
from qgis.core import QgsProject

from .db_manager import PostgresProjectDownloader


_IS_OFFLINE_EDITABLE = 'isOfflineEditable'


class PostgresProjectListModel(QObject):
    """Qt list model representing available projects saved in PostgreSQL."""

    model_changed = pyqtSignal()

    def __init__(self, host, port, dbname, schema, authcfg, sslmode, *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.host = host
        self.port = port
        self.dbname = dbname
        self.schema = schema
        self.authcfg = authcfg
        self.sslmode = sslmode
        self.model = QStringListModel()

    def refresh_data(self):
        """Refresh the list of projects saved in PostgreSQL."""
        fetch_projects = PostgresProjectDownloader(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            schema=self.schema,
            authcfg=self.authcfg,
            sslmode=self.sslmode,
        )
        self.model.setStringList(list(fetch_projects()))
        self.model_changed.emit()

    def project_at_index(self, index):
        """Return the name of project at given index."""
        return self.model.data(index, Qt.DisplayRole)


class OfflineLayerListModel(QObject):
    """Represents offline layers in a QGIS project."""

    model_changed = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = QStringListModel()

    def refresh_data(self):
        """Refresh the offline layers dict from QGIS project legend."""
        proj = QgsProject.instance()
        offline_layers = (layer for layer_id, layer in proj.mapLayers().items()
                          if layer.customProperty(_IS_OFFLINE_EDITABLE))
        self.model.setStringList(
            layer.name() for layer in offline_layers
        )
        self.model_changed.emit()
