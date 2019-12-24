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
from PyQt5 import QtWidgets

# This loads your .ui file so that PyQt can populate your plugin with the
# elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'guided_offline_editing_dialog_base.ui'
), resource_suffix='')


class GuidedOfflineEditingPluginDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        """Constructor."""
        super(GuidedOfflineEditingPluginDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.pg_project_model = None
        self.offline_layer_model = None
        self.pg_project_selection_model = None

    def disable_download_check_box(self):
        """Disable download check box and show hint."""
        self.downloadCheckBox.setChecked(False)
        self.downloadCheckBox.setEnabled(False)
        self.setGisDataHomeLabel.show()

    def enable_download_check_box(self):
        """Enable download check box and hide hint."""
        self.setGisDataHomeLabel.hide()
        self.downloadCheckBox.setEnabled(True)
        self.downloadCheckBox.setChecked(False)

    def initialize_extent_group_box(self, original_extent, current_extent,
                                    output_crs, canvas):
        self.pgProjectDownloadExtent.setOriginalExtent(original_extent,
                                                       output_crs)
        self.pgProjectDownloadExtent.setCurrentExtent(current_extent,
                                                      output_crs)
        self.pgProjectDownloadExtent.setOutputCrs(output_crs)
        self.pgProjectDownloadExtent.setMapCanvas(canvas)

    def pg_project_selection_model(self):
        """Return the selection model from the project list."""
        return self.pgProjectList.selectionModel()

    def refresh_pg_project_list(self):
        self.pgProjectList.setModel(self.pg_project_model.model)
        self.pg_project_selection_model = self.pgProjectList.selectionModel()
        self.pg_project_selection_model.selectionChanged.connect(
            self.update_go_button_state
        )

    def refresh_offline_layer_list(self):
        self.offlineLayerList.setModel(self.offline_layer_model.model)

    def select_project_at_index(self, index):
        """Select the project at given index in project list."""
        self.pgProjectList.setCurrentIndex(index)

    def selected_extent(self):
        """Return a 2-uple ``(rect, crs_id)`` where ``rect`` is the selected
        extent from where data should be downloaded, and ``crs_id`` is the
        EPSG identifier of this rectangle's CRS."""
        extent = self.pgProjectDownloadExtent.outputExtent()
        if extent.area() == 0.0:
            return None, None
        else:
            return extent, self.pgProjectDownloadExtent.outputCrs().authid()

    def selected_pg_project(self):
        """Return the selected project name or ``None`` if no project is
        selected."""
        selected_rows = self.pg_project_selection_model.selectedRows()
        if selected_rows:
            return self.pg_project_model.project_at_index(selected_rows[0])
        else:
            return None

    def set_db_title(self, db_title):
        """Set the DB Title label."""
        self.dbTitleLabel.setText(db_title)

    def set_offline_layer_model(self, model):
        """Link to the given ``OfflineLayerListModel`` instance."""
        self.offline_layer_model = model

    def set_pg_project_model(self, model):
        """Link to the given ``PostgresPorjectListModel`` instance."""
        self.pg_project_model = model

    def update_extent_group_box_state(self):
        """Set the extent group box enable or disable depending on UI state."""
        if self.downloadCheckBox.isChecked():
            self.pgProjectDownloadExtent.setEnabled(True)
        else:
            self.pgProjectDownloadExtent.setEnabled(False)

    def update_go_button_state(self):
        """Set the download button enable or disable depending on UI state."""
        if not self.selected_pg_project():
            self.goButton.setEnabled(False)
        else:
            self.goButton.setEnabled(True)

    def update_upload_button_state(self):
        """Set the upload button enable or disable depending on UI state."""
        if self.offline_layer_model.is_empty():
            self.uploadButton.setEnabled(False)
        else:
            self.uploadButton.setEnabled(True)

    def update_widgets(self, project_index_to_select=None,
                       tab_index_to_show=0):
        """Update some widgets state."""
        if project_index_to_select is not None:
            self.select_project_at_index(project_index_to_select)
        self.tabWidget.setCurrentIndex(tab_index_to_show)
        if (project_index_to_select is None
                and self.downloadCheckBox.isChecked()):
            self.downloadCheckBox.setChecked(False)
        elif (project_index_to_select is not None
              and tab_index_to_show == 0
              and not self.downloadCheckBox.isChecked()):
            self.downloadCheckBox.setChecked(True)
        self.update_extent_group_box_state()
        self.update_go_button_state()
        self.update_upload_button_state()
