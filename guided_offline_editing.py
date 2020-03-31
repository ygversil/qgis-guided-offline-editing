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
from pathlib import Path
import os.path
import pathlib

from PyQt5.QtCore import QCoreApplication, QSettings, QTranslator, qVersion
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataProvider,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsGeometry,
    QgsOfflineEditing,
    QgsPathResolver,
    QgsProject,
    QgsProjectBadLayerHandler,
    QgsRectangle,
    QgsVectorLayer,
)

from .context_managers import (
    busy_refreshing,
    qgis_group_settings,
    removing,
    temporary_connect_signal_slot,
    transactional_project,
)
from .db_manager import (
    PG_PROJECT_STORAGE_TYPE,
    build_gpkg_project_url,
    build_pg_project_url,
)
from .guided_offline_editing_dialog import GuidedOfflineEditingPluginDialog
from .guided_offline_editing_progress_dialog import (
    GuidedOfflineEditingPluginProgressDialog,
)
from .resources import *  # noqa
from .model import OfflineLayerListModel, PostgresProjectListModel, Settings
from .utils import log_message, path_relative_to


PATH_PREFIX = ':gisdatahome:'
SETTINGS_GROUP = 'Plugin-GuidedOfflineEditing/databases'

# Shorter names for these functions
qgis_variable = QgsExpressionContextScope.variable
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
        # Read config and variables and set up env
        self.bad_layer_handlers = QgsProjectBadLayerHandler()
        self.root_path = self.read_gis_data_home()
        if self.root_path:
            log_message('Adding path preprocessor to replace :gisdatahome: '
                        'prefix with: "{}"'.format(self.root_path),
                        level='Info')
            QgsPathResolver.setPathPreprocessor(self.replace_prefix)
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
                   add_to_toolbar=False,
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
            be added to the toolbar. Defaults to False.
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
        icon_path = (':/plugins/guided_offline_editing/icons/'
                     'guided_offline_editing_copy.png')
        # Clear actions before creating them dynamically
        plugin_actions = [
            action for action in self.iface.databaseMenu().actions()
            if action.text() == self.menu
        ]
        if plugin_actions:
            plugin_actions[0].menu().clear()
        # Create menu actions by reading settings
        with qgis_group_settings(self.iface, SETTINGS_GROUP) as s:
            db_titles = s.childGroups()
            if not db_titles:
                log_message(self.tr('No database configured'), level='Warning',
                            feedback=True, iface=self.iface, duration=3)
            for db_title in db_titles:
                callback = partial(self.run, db_title)
                self.add_action(
                    text=db_title,
                    icon_path=icon_path,
                    callback=callback,
                    parent=self.iface.mainWindow()
                )
            self.prepare_action = self.add_action(
                text=self.tr('Prepare and save project for guided editing'),
                icon_path=':/plugins/guided_offline_editing/icons/'
                'save_project_to_postgres.png',
                callback=self.prepare_project,
                parent=self.iface.mainWindow(),
                add_to_toolbar=True,
            )
            self.update_prepare_action()
            self.iface.projectRead.connect(self.update_prepare_action)
            self.iface.newProjectCreated.connect(self.update_prepare_action)
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
        if not self.root_path:
            self.dlg.disable_download_check_box()
        else:
            self.dlg.enable_download_check_box()
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
            self.load_project
        )
        getattr(self.dlg.pgProjectList.doubleClicked, action)(
            self.load_project
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
        """Download selected project to convert it offline."""
        project_name = self.dlg.selected_pg_project()
        qgz_name = pathlib.Path(
            '{project_name}.qgz'.format(project_name=project_name)
        )
        gpkg_name = pathlib.Path(
            '{project_name}_offline.gpkg'.format(project_name=project_name)
        )
        qgz_path = self.root_path / qgz_name
        gpkg_path = self.root_path / gpkg_name
        with removing(self.iface, path=qgz_path):
            # Save the project to a .qgz file first, with relative paths for
            # layers. Then convert layers to offline in a .gpkg. Save
            # project into this .gpkg. And finally delete the .qgz.
            with busy_refreshing(self.iface), \
                    transactional_project(self.iface,
                                          dest_url=str(qgz_path)) as proj:
                proj.writeEntryBool('Paths', '/Absolute', False)
                proj.setAutoTransaction(False)
            with busy_refreshing(self.iface), \
                    transactional_project(
                        self.iface,
                        dest_url=build_gpkg_project_url(gpkg_path,
                                                        project=project_name)
                    ) as proj:
                layer_ids_to_download = [
                    layer_id
                    for layer_id, layer in proj.mapLayers().items()
                    if (isinstance(layer, QgsVectorLayer) and
                        layer.dataProvider().storageType().lower().startswith(
                            'postgresql'
                        ))
                ]
                extent, extent_crs_id = self.dlg.selected_extent()
                if extent is not None:
                    self.select_feature_by_extent(proj,
                                                  layer_ids_to_download,
                                                  extent,
                                                  extent_crs_id)
                    only_selected = True
                else:
                    only_selected = False
                self.convert_layers_to_offline(layer_ids_to_download,
                                               gpkg_path,
                                               only_selected=only_selected)

    def load_project(self):
        """Load selected project and download it if asked."""
        proj = QgsProject.instance()
        proj_storage = proj.projectStorage()
        project_name = self.dlg.selected_pg_project()
        if (not proj_storage or proj_storage.type() != PG_PROJECT_STORAGE_TYPE
                or proj.baseName() != project_name):
            self.iface.addProject(build_pg_project_url(
                host=self.settings.pg_host,
                port=self.settings.pg_port,
                dbname=self.settings.pg_dbname,
                schema=self.settings.pg_schema,
                authcfg=self.settings.pg_authcfg,
                sslmode=self.settings.pg_sslmode,
                project=project_name
            ))
        if self.dlg.downloadCheckBox.isChecked():
            self.download_project()
        if self.dlg.zoomFullCheckBox.isChecked():
            self.iface.zoomFull()
        self.done = True

    def prepare_project(self):
        """Prepare project for guided editing and save it into PostgreSQL.

        Actual tasks that are done here:

        * for each local filesystem layer, rewrite its path with
          ``:gisdatahome:`` prefix,
        """
        with busy_refreshing(self.iface):
            unused_proj = QgsProject.instance()  # Needed to connect signal
            with temporary_connect_signal_slot(
                self.iface,
                unused_proj.writeMapLayer,
                self.set_prefixed_datasource_in_layer_node
            ), \
                    transactional_project(self.iface) as proj:
                for _, layer in proj.mapLayers().items():
                    layer_source = layer.source()
                    layer_path = Path(layer_source)
                    try:
                        is_file = Path(layer_source.split('|')[0]).is_file()
                    except OSError:
                        is_file = False
                    if layer_source.startswith('?query=') or not is_file:
                        continue
                    if not self.root_path:
                        log_message(
                            self.tr(
                                'gis_data_home global variable not set. '
                                'Unable to rewrite path for local layers.'
                            ),
                            level='Warning',
                            feedback=True,
                            iface=self.iface,
                        )
                        break
                    rel_path = path_relative_to(layer_path, self.root_path)
                    if not rel_path:
                        log_message(
                            self.tr('You have local layers outside '
                                    'gis_data_home folder. Unable to rewrite '
                                    'path for those.'),
                            level='Warning',
                            feedback=True,
                            iface=self.iface,
                        )
                        break
                    prefixed_path = '{}{}'.format(PATH_PREFIX,
                                                  rel_path.as_posix())
                    log_message(
                        'Rewriting layer path: {} -> {}'.format(layer_path,
                                                                prefixed_path),
                        level='Info',
                    )
                    layer.setDataSource(
                        prefixed_path,
                        layer.name(),
                        layer.providerType(),
                        QgsDataProvider.ProviderOptions()
                    )
                else:
                    log_message(
                        self.tr('Successfully prepared project.'),
                        level='Success',
                        feedback=True,
                        iface=self.iface,
                        duration=3
                    )

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
        proj_storage = proj.projectStorage()
        project_index = (self.pg_project_model.index_for_project_name(
            proj.baseName()
        ) if proj_storage and proj_storage.type() == PG_PROJECT_STORAGE_TYPE
                         else None)
        # If already offline project, show upload tab
        tab_index = 0 if self.offline_layer_model.is_empty() else 1
        # Allow downloading or not
        allow_download = True if self.root_path else False
        self.dlg.update_widgets(project_index_to_select=project_index,
                                tab_index_to_show=tab_index,
                                allow_download=allow_download)

    def replace_prefix(self, path):
        """Replace ``:gisdatahome:`` prefix with path stored in
        ``gis_data_home`` global variable."""
        if PATH_PREFIX not in path:
            return path
        rel_path = Path(path.replace(PATH_PREFIX, ''))
        return str(self.root_path / rel_path)

    def select_feature_by_extent(self, proj, layer_ids, extent, extent_crs_id):
        for layer_id, layer in proj.mapLayers().items():
            if layer_id not in layer_ids:
                continue
            layer_crs_id = layer.sourceCrs().authid()
            if extent_crs_id != layer_crs_id:
                geom = QgsGeometry.fromRect(extent)
                extent_crs = QgsCoordinateReferenceSystem(extent_crs_id)
                layer_crs = QgsCoordinateReferenceSystem(layer_crs_id)
                tr = QgsCoordinateTransform(extent_crs, layer_crs, proj)
                transform_res = geom.transform(tr)
                if transform_res != 0:
                    log_message('Unable to reproject extent from CRS "{}" '
                                'to CRS "{}"'.format(
                                    extent_crs_id,
                                    layer_crs_id
                                ), level='Warning')
                else:
                    extent = geom.boundingBox()
            layer.selectByRect(extent)
            log_message('{} selected features for downloading '
                        'in layer "{}"'.format(
                            layer.selectedFeatureCount(),
                            layer.name()
                        ))

    def set_prefixed_datasource_in_layer_node(self, layer, layer_elem, doc):
        """Slot to be connected to a ``QgsProject.writeMapLayer`` signal and
        that writes layer source with ``:gisdatahome:`` prefix in
        ``<datasource>`` tag in project XML.
        """
        if PATH_PREFIX in layer.source():
            log_message('Saving path in project XML: {}'.format(
                layer.source()
            ), level='Info')
            self.bad_layer_handlers.setDataSource(layer_elem, layer.source())

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
        project_name = QgsProject.instance().baseName()
        self.iface.addProject(build_pg_project_url(
            host=self.settings.pg_host,
            port=self.settings.pg_port,
            dbname=self.settings.pg_dbname,
            schema=self.settings.pg_schema,
            authcfg=self.settings.pg_authcfg,
            sslmode=self.settings.pg_sslmode,
            project=project_name
        ))
        self.done = True

    def update_prepare_action(self):
        """Enable or disable prepare action in menu depending on project
        state."""
        proj = QgsProject.instance()
        proj_storage = proj.projectStorage()
        if not proj_storage or proj_storage.type() != PG_PROJECT_STORAGE_TYPE:
            self.prepare_action.setEnabled(False)
        else:
            self.prepare_action.setEnabled(True)
