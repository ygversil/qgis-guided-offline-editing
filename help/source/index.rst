.. GuidedOfflineEditingPlugin documentation master file, created by
   sphinx-quickstart on Sun Feb 12 17:11:03 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Guided Offline Editing QGIS plugin
==================================

Guided Offline Editing is a little QGIS plugin that provides some simple
automations to ease projects sharing across an organization. At the moment, it
relies heavily on PostgreSQL.

How it works ? First, a "power user" (a GIS admin, a DBA, or the like) prepares
beforehand one or more projects for working with PostgreSQL/Postgis layers.
That is: she loads PostgreSQL layers in QGIS and prepares everything to work
with these layers: symbology, forms, and so on. She does so with as much
details as possible (form widgets, field validation, field help, relationships,
...). She also indicates which layers must be downloaded for offline edition (a
variable to set in layer properties). Then these projects are saved in
PostgreSQL.

Now, on the "normal user" side, the plugin shows the list of available projects
that have been prepared in this manner. The user just has to select one project
and click the `Go!` button.  That's it! The project is loaded like it was
prepared. The user can also choose to download the project for offline edition.
The whole project is then saved into one GeoPackage file. Later, when back
online, the user clicks the `Upload` button and the layers are synchronised
into PostgreSQL.

Contents:

.. toctree::
   :maxdepth: 2

   admin_guide.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

