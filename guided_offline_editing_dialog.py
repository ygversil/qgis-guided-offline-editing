# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GuidedOfflineEditingPluginDialog
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

import os

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5 import QtWidgets

# This loads your .ui file so that PyQt can populate your plugin with the
# elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'guided_offline_editing_dialog_base.ui'
), resource_suffix='')


class GuidedOfflineEditingPluginDialog(QtWidgets.QDialog, FORM_CLASS):

    busy = pyqtSignal()
    idle = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(GuidedOfflineEditingPluginDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

    def refresh_layer_table(self, model):
        self.downloadLayerTable.setModel(model)
        self.downloadLayerTable.resizeColumnsToContents()
        self.downloadLayerTable.resizeRowsToContents()

    def selected_row_indices(self):
        """Yield each selected editable layer."""
        yield from (
            index.row()
            for index in self.downloadLayerTable.selectionModel()
            .selectedRows()
        )

    def setBusy(self):
        """Show busy interface: set waiting cursor and disable buttons."""
        self.downloadButton.setEnabled(False)
        self.uploadButton.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)

    def setIdle(self):
        """Show idle interface: set normal cursir and enable buttons."""
        self.downloadButton.setEnabled(True)
        self.uploadButton.setEnabled(True)
        QtWidgets.QApplication.restoreOverrideCursor()
