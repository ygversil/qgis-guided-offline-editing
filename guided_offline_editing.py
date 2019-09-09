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

import uuid

from PyQt5.QtCore import (QSettings, QTranslator, qVersion, QCoreApplication,
                          QStringListModel)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMessageBox
from qgis.core import Qgis, QgsOfflineEditing, QgsProject, QgsVectorLayer


from .db_manager import PostgresLayerDownloader
# Initialize Qt resources from file resources.py
# from .resources import *
# Import the code for the dialog
from .guided_offline_editing_dialog import GuidedOfflineEditingPluginDialog
from .layer_model import PostgresLayer, PostgresLayerTableModel, LAYER_ATTRS
from .project_context_manager import transactional_project
import os.path


_IS_OFFLINE_EDITABLE = 'isOfflineEditable'


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
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GuidedOfflineEditingPlugin_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Guided Offline Editing Plugin')

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
                self.tr(u'&Guided Offline Editing Plugin'),
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
            self.clock_seq = 0
        self.dlg.downloadButton.clicked.connect(
            self.prepare_project_for_offline_editing
        )
        self.dlg.uploadButton.clicked.connect(
            self.synchronize_offline_layers
        )
        self.dlg.busy.connect(self.dlg.setBusy)
        self.dlg.idle.connect(self.dlg.setIdle)
        proj = QgsProject.instance()
        if (proj.projectStorage() is None and proj.fileName() == ''):
            QMessageBox.critical(self.iface.mainWindow(),
                                 self.tr('No project file'),
                                 self.tr('Please save the project to a '
                                         'file first.'))
            return
        self.layer_model = PostgresLayerTableModel()
        self.offline_layer_model = QStringListModel()
        self.offline_layers = dict()
        self.offliner = QgsOfflineEditing()
        self.refreshDownloadableLayerTable()
        self.refreshOfflineLayerList()
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass
            # and substitute with your code.
            pass
        self.dlg.downloadButton.clicked.disconnect(
            self.prepare_project_for_offline_editing
        )
        self.dlg.uploadButton.clicked.disconnect(
            self.synchronize_offline_layers
        )
        self.dlg.busy.disconnect(self.dlg.setBusy)
        self.dlg.idle.disconnect(self.dlg.setIdle)

    def refreshDownloadableLayerTable(self):
        """Refresh the downloadable layer table."""
        fetch_layers = PostgresLayerDownloader(host='db.priv.ariegenature.fr',
                                               port=5432,
                                               dbname='ana',
                                               schema='common',
                                               authcfg='ldapana')
        for layer_dict in fetch_layers():
            self.layer_model.addLayer(
                PostgresLayer(**{k: v for k, v in layer_dict.items()
                                 if k in LAYER_ATTRS})
            )
        self.dlg.refresh_downloadable_layer_table(self.layer_model)

    def refreshOfflineLayerList(self):
        """Refresh the offline layer list."""
        proj = QgsProject.instance()
        self.offline_layers = dict(filter(
            lambda item: item[1].customProperty(_IS_OFFLINE_EDITABLE),
            proj.mapLayers().items()
        ))
        self.offline_layer_model.setStringList(
            layer.name() for layer in self.offline_layers.values()
        )
        self.dlg.refresh_offline_layer_list(self.offline_layer_model)

    def add_selected_layers(self, proj):
        """Add the selected layers to the project legend."""
        added_layer_ids = []
        for i in self.dlg.selected_row_indices():
            pg_layer = self.layer_model.available_layers[i]
            qgs_layer = QgsVectorLayer(
                "host=db.priv.ariegenature.fr port=5432 dbname='ana' "
                'table="{schema}"."{table}" ({geom})'
                "authcfg=ldapana estimatedmetadata=true "
                "checkPrimaryKeyUnicity='0' sql=".format(
                    schema=pg_layer.schema_name,
                    table=pg_layer.table_name,
                    geom=pg_layer.geometry_column
                ),
                pg_layer.title,
                'postgres'
            )
            added_layer = proj.addMapLayer(qgs_layer)
            if added_layer is None:
                self.iface.messageBar().pushMessage(
                    'Layer not added',
                    'Cannot add layer "{}"'.format(pg_layer.title),
                    Qgis.Critical,
                    10
                )
                raise RuntimeError('Cannot add layer '
                                   '"{}"'.format(pg_layer.title))
            added_layer_ids.append(added_layer.id())
        return added_layer_ids

    def prepare_project_for_offline_editing(self):
        """Prepare the project for offline editing."""
        self.dlg.busy.emit()
        self.clock_seq += 1
        with transactional_project(self.iface) as proj:
            proj.setTitle(proj.title().replace(' (offline)', ''))
            added_layer_ids = self.add_selected_layers(proj)
            # XXX: if called multiple times for the same QGIS project, this
            # works because, as of QGIS 3.8, the convertToOfflineProject
            # method does not check if the project is already an offline
            # project. So new layers can be converted offline although the
            # project is already offline himself.
            self.offliner.convertToOfflineProject(
                proj.absolutePath(),
                'offline-{id_}.gpkg'.format(
                    id_=uuid.uuid1(clock_seq=self.clock_seq)
                ),
                added_layer_ids,
                containerType=QgsOfflineEditing.GPKG
            )
        self.dlg.idle.emit()

    def synchronize_offline_layers(self):
        """Synchronize offline layers."""
        self.dlg.busy.emit()
        with transactional_project(self.iface):
            self.offliner.synchronize()
        self.dlg.idle.emit()
