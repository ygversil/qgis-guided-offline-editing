.. GuidedOfflineEditingPlugin documentation master file, created by
   sphinx-quickstart on Sun Feb 12 17:11:03 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Guided Offline Editing QGIS plugin
==================================

Guided Offline Editing is a little QGIS plugin to make life easier when editing
PostgreSQL/Postgis layers offline. It allows a user to simply select the
project he or she wants to work on, and download it without worrying about the
details. After offline work, he or she can upload the changes to PostgreSQL
when needed. The plugin does not try to reinvent the wheel, it makes use of the
built-in Offline Editing plugin.

Beforehand, the project must have been prepared: relevant PostgreSQL/Postgis
layers must have been loaded, relationships between layers must have been
declared, and forms to edit layers must have been defined. In addition to these
classical prerequisites, the plugin requires two more tasks. First, layers to
be downloaded for offline edition must be marked using a variable. And second,
the project must be saved in PostgreSQL in a known and common schema.

In summary, Guided Offline Editing allows other users (and yourself!) to
benefit from your hard work to set up nice forms to edit PostgreSQL layers in
QGIS. Save the project in PostgreSQL and let them all use your forms.

Contents:

.. toctree::
   :maxdepth: 2

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

