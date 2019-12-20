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

from functools import partial
import os.path
import pathlib

from PyQt5.QtCore import QCoreApplication, QSettings, QTranslator, qVersion
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMessageBox
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsDataProvider,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsOfflineEditing,
    QgsProject,
    QgsRectangle,
)

from .context_managers import (
    busy_refreshing,
    qgis_group_settings,
    transactional_project,
)
from .db_manager import build_gpkg_project_url, build_pg_project_url
from .guided_offline_editing_dialog import GuidedOfflineEditingPluginDialog
from .guided_offline_editing_progress_dialog import (
    GuidedOfflineEditingPluginProgressDialog,
)
from .resources import *  # noqa
from .model import OfflineLayerListModel, PostgresProjectListModel, Settings
from .utils import log_message

PROJECT_ENTRY_SCOPE_GUIDED = 'GuidedOfflineEditingPlugin'
PROJECT_ENTRY_KEY_FROM_POSTGRES = '/FromPostgres'
SETTINGS_GROUP = 'Plugin-GuidedOfflineEditing/databases'

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
        self.menu = self.tr(u'&Guided Editing')
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
                   text,
                   callback,
                   icon_path=None,
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
        if icon_path:
            icon = QIcon(icon_path)
            action = QAction(icon, text, parent)
        else:
            action = QAction(text, parent)
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
        with qgis_group_settings(self.iface, SETTINGS_GROUP) as s:
            db_titles = s.childGroups()
            if not db_titles:
                log_message(self.tr('No database configured'), level='Warning',
                            feedback=True, iface=self.iface, duration=3)
            for db_title in db_titles:
                callback = partial(self.run, db_title)
                self.add_action(
                    text=db_title,
                    callback=callback,
                    parent=self.iface.mainWindow()
                )
        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginDatabaseMenu(
                self.tr(u'&Guided Offline Editing'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self, db_title):
        """Run method that performs all the real work"""
        log_message('Running plugin with database "{}"'.format(db_title))
        self.root_path = self.read_gis_data_home()
        if not self.root_path:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr('gis_data_home variable not set or invalid'),
                self.tr('You must set the global variable gis_data_home to '
                        'the path of the folder which contains you GIS '
                        'data.\n\n'
                        'For more information, see '
                        'https://qgis-guided-offline-editing'
                        '.readthedocs.io/en/latest/admin_guide.html'
                        '#qgis-prerequisites')
            )
            return
        # Create the dialog with elements (after translation) and keep
        # reference. Only create GUI ONCE in callback, so that it will only
        # load when the plugin is started
        if self.first_start is True:
            self.first_start = False
            self.dlg = GuidedOfflineEditingPluginDialog()
            self.progress_dlg = GuidedOfflineEditingPluginProgressDialog(
                parent=self.iface.mainWindow()
            )
        self.dlg.set_db_title(db_title)
        self.done = False
        self.settings = self.read_database_settings(db_title)
        self.offliner = QgsOfflineEditing()
        self.pg_project_model = PostgresProjectListModel(
            host=self.settings.pg_host,
            port=self.settings.pg_port,
            dbname=self.settings.pg_dbname,
            schema=self.settings.pg_schema,
            authcfg=self.settings.pg_authcfg,
            sslmode=self.settings.pg_sslmode,
        )
        self.dlg.set_pg_project_model(self.pg_project_model)
        self.offline_layer_model = OfflineLayerListModel()
        self.dlg.set_offline_layer_model(self.offline_layer_model)
        self.connect_signals()
        with busy_refreshing(self.iface, self.refresh_data_and_dialog):
            self.dlg.show()
        self.dlg.exec_()
        if self.done:
            self.disconnect_signals()

    # Helper methods below

    def _manage_signals(self, action):
        """Connect or disconnect all signals."""
        getattr(self.offliner.progressModeSet, action)(
            self.set_progress_mode
        )
        getattr(self.offliner.progressStarted, action)(
            self.progress_dlg.show
        )
        getattr(self.offliner.layerProgressUpdated, action)(
            self.progress_dlg.set_progress_label
        )
        getattr(self.offliner.progressUpdated, action)(
            self.progress_dlg.set_progress_bar
        )
        getattr(self.offliner.progressStopped, action)(
            self.progress_dlg.hide
        )
        getattr(self.pg_project_model.model_changed, action)(
            self.dlg.refresh_pg_project_list
        )
        getattr(self.offline_layer_model.model_changed, action)(
            self.dlg.refresh_offline_layer_list
        )
        getattr(self.offline_layer_model.model_changed, action)(
            self.dlg.update_upload_button_state
        )
        getattr(self.dlg.downloadCheckBox.toggled, action)(
            self.dlg.update_extent_group_box_state
        )
        getattr(self.dlg.goButton.clicked, action)(
            self.download_project
        )
        getattr(self.dlg.uploadButton.clicked, action)(
            self.synchronize_offline_layers
        )

    def connect_signals(self):
        """Connect all signals."""
        self._manage_signals(action='connect')

    def convert_layers_to_offline(self, layer_ids, dest_path,
                                  only_selected=False):
        self.progress_dlg.set_title(self.tr('Downloading layers...'))
        self.offliner.convertToOfflineProject(
            str(dest_path.parent),
            dest_path.name,
            layer_ids,
            onlySelected=only_selected,
            containerType=QgsOfflineEditing.GPKG
        )

    def disconnect_signals(self):
        """Disconnect all signals."""
        self._manage_signals(action='disconnect')

    def download_project(self):
        """Prepare the project for offline editing."""
        project_name = self.dlg.selected_pg_project()
        project_url = build_pg_project_url(
            host=self.settings.pg_host,
            port=self.settings.pg_port,
            dbname=self.settings.pg_dbname,
            schema=self.settings.pg_schema,
            authcfg=self.settings.pg_authcfg,
            sslmode=self.settings.pg_sslmode,
            project=project_name
        )
        qgz_name = pathlib.Path(
            '{project_name}.qgz'.format(project_name=project_name)
        )
        qgz_path = self.root_path / qgz_name
        current_proj = QgsProject.instance()
        if (not current_proj.readBoolEntry(PROJECT_ENTRY_SCOPE_GUIDED,
                                           PROJECT_ENTRY_KEY_FROM_POSTGRES)[0]
                or current_proj.baseName() != project_name):
            with busy_refreshing(self.iface), \
                    transactional_project(self.iface, src_url=project_url,
                                          dest_url=str(qgz_path)) as proj:
                for layer_id, layer in proj.mapLayers().items():
                    if layer.source().startswith(str(proj.homePath())):
                        new_source = layer.source().replace(
                            proj.homePath().rstrip('/\\'),
                            str(self.root_path)
                        )
                        log_message('Updating layer source: {} -> {}'.format(
                            layer.source(),
                            new_source,
                        ),
                                    level='Info')
                        layer.setDataSource(
                            layer.source().replace(
                                proj.homePath().rstrip('/\\'),
                                str(self.root_path)
                            ),
                            layer.name(),
                            layer.providerType(),
                            QgsDataProvider.ProviderOptions(),
                        )
            with busy_refreshing(self.iface), \
                    transactional_project(self.iface,
                                          src_url=str(qgz_path)) as proj:
                proj.setPresetHomePath('')
                proj.writeEntryBool('Paths', '/Absolute', False)
                proj.writeEntryBool(PROJECT_ENTRY_SCOPE_GUIDED,
                                    PROJECT_ENTRY_KEY_FROM_POSTGRES,
                                    True)
            self.iface.addProject(str(qgz_path))
            if self.dlg.zoomFullCheckBox.isChecked():
                self.iface.zoomFull()
        if not self.dlg.downloadCheckBox.isChecked():
            return
        gpkg_name = pathlib.Path(
            '{project_name}_offline.gpkg'.format(project_name=project_name)
        )
        gpkg_path = self.root_path / gpkg_name
        with busy_refreshing(self.iface), \
                transactional_project(
                    self.iface,
                    dest_url=build_gpkg_project_url(gpkg_path,
                                                    project=project_name)
                ) as proj:
            layer_ids_to_download = [
                layer_id
                for layer_id, layer in proj.mapLayers().items()
                if (
                    qgis_variable(layer_scope(layer), 'offline') and
                    qgis_variable(layer_scope(layer), 'offline')
                    .lower() not in ('no', 'false')
                )
            ]
            extent = self.dlg.selected_extent()
            if extent is not None:
                self.select_feature_by_extent(proj,
                                              layer_ids_to_download,
                                              extent)
                only_selected = True
            else:
                only_selected = False
            self.convert_layers_to_offline(layer_ids_to_download,
                                           gpkg_path,
                                           only_selected=only_selected)
        self.done = True

    def read_gis_data_home(self):
        """Read global ``gis_data_home`` QGIS variable and return a
        ``pathlib.Path`` object with it, or ``None`` if it is not valid."""
        path = qgis_variable(global_scope(), 'gis_data_home')
        path = pathlib.Path(path) if path else None
        return (path if (path and path.exists() and path.is_dir()
                         and path.is_absolute())
                else None)

    def read_database_settings(self, db_title):
        """Read plugin settings from config file."""
        with qgis_group_settings(self.iface, SETTINGS_GROUP) as s:
            d = dict()
            d['pg_host'] = s.value('{}/host'.format(db_title),
                                   'localhost')
            d['pg_port'] = s.value('{}/port'.format(db_title), 5432)
            d['pg_authcfg'] = s.value('{}/authcfg'.format(db_title),
                                      'authorg')
            d['pg_dbname'] = s.value('{}/dbname'.format(db_title),
                                     'orgdb')
            d['pg_schema'] = s.value('{}/schema'.format(db_title),
                                     'qgis')
            d['pg_sslmode'] = s.value('{}/sslmode'.format(db_title),
                                      'disabled')
            return Settings(**d)

    def refresh_data_and_dialog(self):
        """Refresh models and update dialog widgets accordingly."""
        proj = QgsProject.instance()
        # Init extent widget
        self.pg_project_model.refresh_data()
        self.offline_layer_model.refresh_data()
        output_crs = QgsCoordinateReferenceSystem(proj.crs())
        original_extent = QgsRectangle(0.0, 0.0, 0.0, 0.0)
        current_extent = QgsRectangle(0.0, 0.0, 0.0, 0.0)
        self.dlg.initialize_extent_group_box(original_extent,
                                             current_extent,
                                             output_crs,
                                             self.canvas)
        # Select current project in project list
        project_index = (self.pg_project_model.index_for_project_name(
            proj.baseName()
        ) if proj.readBoolEntry(PROJECT_ENTRY_SCOPE_GUIDED,
                                PROJECT_ENTRY_KEY_FROM_POSTGRES)[0]
                         else None)
        # If already offline project, show upload tab
        tab_index = 0 if self.offline_layer_model.is_empty() else 1
        self.dlg.update_widgets(project_index_to_select=project_index,
                                tab_index_to_show=tab_index)

    def select_feature_by_extent(self, proj, layer_ids, extent):
        for layer_id, layer in proj.mapLayers().items():
            if layer_id not in layer_ids:
                continue
            layer.selectByRect(extent)
            log_message('{} selected features for downloading '
                        'in layer "{}"'.format(
                            layer.selectedFeatureCount(),
                            layer.name()
                        ))

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
        with busy_refreshing(self.iface):
            self.progress_dlg.set_title(self.tr('Uploading layers...'))
            self.offliner.synchronize()
        self.done = True
