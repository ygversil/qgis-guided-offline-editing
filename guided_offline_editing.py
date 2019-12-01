# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GuidedOfflineEditingPlugin
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

import pathlib

from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsOfflineEditing,
    QgsRectangle,
    QgsSettings,
)

# Initialize Qt resources from file resources.py
from .resources import *  # noqa
# Import the code for the dialog
from .guided_offline_editing_dialog import GuidedOfflineEditingPluginDialog
from .guided_offline_editing_progress_dialog import (
    GuidedOfflineEditingPluginProgressDialog
)
from .model import OfflineLayerListModel, PostgresProjectListModel
from .context_managers import cleanup, transactional_project
from .db_manager import build_gpkg_project_url, build_pg_project_url
import os.path


# Shorter names for these functions
qgis_variable = QgsExpressionContextScope.variable
layer_scope = QgsExpressionContextUtils.layerScope
global_scope = QgsExpressionContextUtils.globalScope


class GuidedOfflineEditingPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            '{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Guided Offline Editing')
        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('GuidedOfflineEditingPlugin',
                                          message)

    def add_action(self,
                   icon_path,
                   text,
                   callback,
                   enabled_flag=True,
                   add_to_menu=True,
                   add_to_toolbar=True,
                   status_tip=None,
                   whats_this=None,
                   parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToDatabaseMenu(
                self.menu,
                action)
        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = (':/plugins/guided_offline_editing/icons/'
                     'guided_offline_editing_copy.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Guided Offline Editing'),
            callback=self.run,
            parent=self.iface.mainWindow())
        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginDatabaseMenu(
                self.tr(u'&Guided Offline Editing'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""
        # Create the dialog with elements (after translation) and keep
        # reference. Only create GUI ONCE in callback, so that it will only
        # load when the plugin is started
        if self.first_start is True:
            self.first_start = False
            self.dlg = GuidedOfflineEditingPluginDialog()
            self.progress_dlg = GuidedOfflineEditingPluginProgressDialog(
                parent=self.iface.mainWindow()
            )
        self.update_download_check_box()
        self.offliner = QgsOfflineEditing()
        s = QgsSettings()
        self.pg_host = s.value('Plugin-GuidedOfflineEditing/host', 'localhost')
        self.pg_port = s.value('Plugin-GuidedOfflineEditing/port', 5432)
        self.pg_authcfg = s.value('Plugin-GuidedOfflineEditing/authcfg',
                                  'authorg')
        self.pg_dbname = s.value('Plugin-GuidedOfflineEditing/dbname', 'orgdb')
        self.pg_schema = s.value('Plugin-GuidedOfflineEditing/schema', 'qgis')
        self.pg_sslmode = s.value('Plugin-GuidedOfflineEditing/sslmode',
                                  'disabled')
        self.pg_project_model = PostgresProjectListModel(
            host=self.pg_host,
            port=self.pg_port,
            dbname=self.pg_dbname,
            schema=self.pg_schema,
            authcfg=self.pg_authcfg,
            sslmode=self.pg_sslmode,
        )
        self.pg_project_model.refresh_data()
        self.offline_layer_model = OfflineLayerListModel()
        self.offline_layer_model.refresh_data()
        output_crs_id = s.value('Projections/projectDefaultCrs', 'EPSG:4326')
        output_crs = QgsCoordinateReferenceSystem(output_crs_id)
        original_extent = QgsRectangle(0.0, 0.0, 0.0, 0.0)
        current_extent = QgsRectangle(0.0, 0.0, 0.0, 0.0)
        # show the dialog
        self.dlg.set_pg_project_model(self.pg_project_model)
        self.dlg.set_offline_layer_model(self.offline_layer_model)
        self.dlg.refresh_pg_project_list()
        self.dlg.refresh_offline_layer_list()
        self.dlg.initialize_extent_group_box(original_extent,
                                             current_extent,
                                             output_crs,
                                             self.canvas)
        self.dlg.update_go_button_state()
        self.dlg.update_upload_button_state()
        self.offliner.progressModeSet.connect(
            self.set_progress_mode
        )
        self.offliner.progressStarted.connect(self.progress_dlg.show)
        self.offliner.layerProgressUpdated.connect(
            self.progress_dlg.set_progress_label
        )
        self.offliner.progressUpdated.connect(
            self.progress_dlg.set_progress_bar
        )
        self.offliner.progressStopped.connect(self.progress_dlg.hide)
        self.pg_project_model.model_changed.connect(
            self.dlg.refresh_pg_project_list
        )
        self.offline_layer_model.model_changed.connect(
            self.dlg.refresh_offline_layer_list
        )
        self.offline_layer_model.model_changed.connect(
            self.dlg.update_upload_button_state
        )
        self.dlg.pg_project_selection_model().selectionChanged.connect(
            self.dlg.update_go_button_state
        )
        self.dlg.downloadCheckBox.stateChanged.connect(
            self.dlg.update_go_button_state
        )
        self.dlg.pgProjectDestFileWidget.fileChanged.connect(
            self.dlg.update_go_button_state
        )
        self.dlg.goButton.clicked.connect(
            self.add_pg_layers_and_convert_to_offline
        )
        self.dlg.uploadButton.clicked.connect(
            self.synchronize_offline_layers
        )
        if self.offline_layer_model.is_empty():
            self.dlg.tabWidget.setCurrentIndex(0)
        else:
            self.dlg.tabWidget.setCurrentIndex(1)
        self.dlg.show()
        # Run the dialog event loop
        self.dlg.exec_()
        self.offliner.progressModeSet.disconnect(
            self.set_progress_mode
        )
        self.offliner.progressStarted.disconnect(self.progress_dlg.show)
        self.offliner.layerProgressUpdated.disconnect(
            self.progress_dlg.set_progress_label
        )
        self.offliner.progressUpdated.disconnect(
            self.progress_dlg.set_progress_bar
        )
        self.offliner.progressStopped.disconnect(self.progress_dlg.hide)
        self.dlg.pg_project_selection_model().selectionChanged.disconnect(
            self.dlg.update_go_button_state
        )
        self.dlg.downloadCheckBox.stateChanged.disconnect(
            self.dlg.update_go_button_state
        )
        self.dlg.pgProjectDestFileWidget.fileChanged.disconnect(
            self.dlg.update_go_button_state
        )
        self.dlg.goButton.clicked.disconnect(
            self.add_pg_layers_and_convert_to_offline
        )
        self.dlg.uploadButton.clicked.disconnect(
            self.synchronize_offline_layers
        )
        self.pg_project_model.model_changed.disconnect(
            self.dlg.refresh_pg_project_list
        )
        self.offline_layer_model.model_changed.disconnect(
            self.dlg.refresh_offline_layer_list
        )
        self.offline_layer_model.model_changed.disconnect(
            self.dlg.update_upload_button_state
        )

    def select_feature_by_extent(self, proj, layer_ids, extent):
        for layer_id, layer in proj.mapLayers().items():
            if layer_id not in layer_ids:
                continue
            layer.selectByRect(extent)

    def convert_layers_to_offline(self, layer_ids, dest_path,
                                  only_selected=False):
        dest_path = pathlib.Path(dest_path)
        self.progress_dlg.set_title(self.tr('Downloading layers...'))
        self.offliner.convertToOfflineProject(
            str(dest_path.parent),
            dest_path.name,
            layer_ids,
            onlySelected=only_selected,
            containerType=QgsOfflineEditing.GPKG
        )

    def add_pg_layers_and_convert_to_offline(self):
        """Prepare the project for offline editing."""
        project_name = self.dlg.selected_pg_project()
        with cleanup(
            selections_to_clear=[self.dlg.pg_project_selection_model()],
            models_to_refresh=[self.offline_layer_model],
            file_widget_to_clear=self.dlg.pgProjectDestFileWidget,
        ):
            self.iface.addProject(build_pg_project_url(
                host=self.pg_host,
                port=self.pg_port,
                dbname=self.pg_dbname,
                schema=self.pg_schema,
                authcfg=self.pg_authcfg,
                sslmode=self.pg_sslmode,
                project=project_name
            ))
            if not self.dlg.downloadCheckBox.isChecked():
                return
            dest_path = self.dlg.selected_destination_path()
            with transactional_project(
                dest_url=build_gpkg_project_url(dest_path,
                                                project=project_name)
            ) as proj:
                proj.writeEntryBool('Paths', '/Absolute', False)
            with transactional_project(
                dest_url=build_gpkg_project_url(dest_path,
                                                project=project_name)
            ) as proj:
                layer_ids_to_download = [
                    layer_id
                    for layer_id, layer in proj.mapLayers().items()
                    if (
                        qgis_variable(layer_scope(layer), 'offline') and
                        qgis_variable(layer_scope(layer), 'offline').lower()
                        not in ('no', 'false')
                    )
                ]
                extent = self.dlg.selected_extent()
                if extent is not None:
                    self.select_feature_by_extent(proj, layer_ids_to_download,
                                                  extent)
                    only_selected = True
                else:
                    only_selected = False
                self.convert_layers_to_offline(layer_ids_to_download,
                                               dest_path,
                                               only_selected=only_selected)

    def set_progress_mode(self, mode, max_):
        """Update progress dialog information."""
        map_mode_format = {
            QgsOfflineEditing.CopyFeatures: self.tr(
                '%v / %m features copied'
            ),
            QgsOfflineEditing.ProcessFeatures: self.tr(
                '%v / %m features processed'
            ),
            QgsOfflineEditing.AddFields: self.tr(
                '%v / %m fields added'
            ),
            QgsOfflineEditing.AddFeatures: self.tr(
                '%v / %m features added'
            ),
            QgsOfflineEditing.RemoveFeatures: self.tr(
                '%v / %m features removed'
            ),
            QgsOfflineEditing.UpdateFeatures: self.tr(
                '%v / %m feature updates'
            ),
            QgsOfflineEditing.UpdateGeometries: self.tr(
                '%v / %m feature geometry updates'
            ),
        }
        self.progress_dlg.setup_progress_bar(map_mode_format[mode], max_)

    def synchronize_offline_layers(self):
        """Send edited data from offline layers to postgres and convert the
        project back to offline."""
        with cleanup(
                models_to_refresh=[self.offline_layer_model]
        ):
            self.progress_dlg.set_title(self.tr('Uploading layers...'))
            self.offliner.synchronize()

    def update_download_check_box(self):
        """Check or uncheck download check box depending on the gis_data_home
        global variable."""
        self.root_path = qgis_variable(global_scope(), 'gis_data_home')
        self.root_path = (pathlib.Path(self.root_path) if self.root_path
                          else None)
        if (self.root_path and self.root_path.exists()
                and self.root_path.is_dir()):
            self.dlg.enable_download_check_box()
        else:
            self.dlg.disable_download_check_box()
