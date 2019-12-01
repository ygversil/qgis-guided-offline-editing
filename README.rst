======================
Guided Offline Editing
======================

Guided Offline Editing is a plugin for QGIS to help users with offline edition
of PostgreSQL/Postgis layers.

* Project homepage: https://github.com/ygversil/qgis-guided-offline-editing

* Documentation: https://qgis-guided-offline-editing.readthedocs.io/en/latest/

How does it works ?
===================

Before the plugin can be used, "power users" (may be database administrators or
gis administrator) need to prepare one or more projects for offline edition and
save them into PostgreSQL.

Once some projects have been preprared, "normal users" can use the plugin to
see the list of available projects, pick one, and click the download button to
start offline editing. No need to worry about selecting correct layers to
download offline, just click ``Download``.

Once back online, the plugin can be used to upload changes, just click the
``Upload`` button.


In more details
===============

Power users: prepare projects and save them in PostgreSQL
---------------------------------------------------------

Before the plugin can be used, a "power user" prepares one or more projects for
editing.  For example, it may be a project to collect survey data about
wetlands. He or she:

* creates tables in PostgreSQL/Postgis, trying to be as close as possible to
  normal forms (QGIS won't allow fully normal database design, more details on
  this later) and with as many constraints as possible to ensure data
  consistency,

* loads them as layers in QGIS,

* creates in QGIS relationships between these layers,

* designs forms in QGIS to edit these layers with as much details as possible
  (field validation, error messages, and so on),

* set a special variable named ``offline`` on each layer that needs to be
  downloaded for offline editing,

* save the project in PostgreSQL, in a known schema.

Normal users: just download the needed project
----------------------------------------------

A "normal user" (who may also be a "power user" during the aforementioned
preparation step) who wants to enter data about wetlands then just need to
launch the plugin, select the wetland project, and click the download button.

The result is a single GeoPackage file containing both the project and the
layers (saving a project in a GeoPackage has been introduced in QGIS 3.8).

He or she can now edit the layers offline and, when back online, launch the
plugin again and click the upload button to synchronize the layers online.


Requirements and settings
=========================

QGIS minimum version
--------------------

Since this plugin saves QGIS projects in GeoPackage files, **QGIS 3.8 or
later** is required, and this is the only software requirement.

Common configuration ID in QGIS authentication database
-------------------------------------------------------

In a multi-user context (eg. an organization), for each user to be able to
connect to PostgreSQL and open projects and layers, each user must store its
PostgreSQL credentials in QGIS authentication database under a configuration
with **the same ID for all users**. For example, if ``orgldap`` is the *authid*
to be shared across all users, the user A must store its PostgreSQL credentials
with this specific authid (username: ``usera``, password: ``secreta``, authid:
``orgldap``), and user B must also use the same authid (username: ``userb``,
password: ``secretb``, authid: ``orgldap``). *Under no circumstances you should
let the authid to be automatically generated*.

See the following link for more information:
https://docs.qgis.org/3.4/en/docs/user_manual/auth_system/auth_overview.html

Plugin configuration
--------------------

PostgreSQL connection information must be provided as QGIS settings, in QGIS
INI file (either the global one, or the ``QGIS3.ini`` file in each user
folder), under a ``[Plugin-GuidedOfflineEditing]`` section. Possible values in
this section are:

* ``host``: PostgreSQL host (default: ``localhost``),

* ``port``: PostgreSQL port (default: ``5432``),

* ``authcfg``: configuration ID in QGIS authentication database where
  PostgreSQL credentials are stored (default: ``authorg``),

* ``sslmode``: ``enabled`` or ``disabled`` depending whether SSL is used to
  connect to PostgreSQL (default: ``disabled``),

* ``dbname``: PostgreSQL database where QGIS projects are saved (default:
  ``orgdb``),

* ``schema``: PostgreSQL schema where QGIS projects are saved (default:
  ``qgis``).

Here is an example configuration tu put in ``QGIS3.ini`` file:

::

        [Plugin-GuidedOfflineEditing]
        host=db.priv.acme.org
        port=5432
        authcfg=acmeaut
        dbname=acmedb
        schema=qgis
        sslmode=disabled

If you are deploying QGIS on multiple computer, you can put this configuration
in a global INI file, (eg. ``qgis_acme_sttings.ini``) and set the
``QGIS_GLOBAL_SETTINGS_FILE`` environment variable. See the following link for
more information:
https://docs.qgis.org/3.4/en/docs/user_manual/introduction/qgis_configuration.html#deploying-qgis-within-an-organization


PostgreSQL permissions
----------------------

Finally, care must be taken that each user has sufficient permissions to edit
relevant tables (``SELECT``, ``INSERT``, ``UPDATE``, ``DELETE``). The easiest
way to achieve this is to create a role (a PostgreSQL user with ``NOLOGIN``
permission), grant correct permissions to this role on all tables that need to
be edited, and assign each actual user to this role.

See the following link for more information:
https://www.postgresql.org/docs/current/role-membership.html


Caveats when designing tables
=============================

One important caveat is that **each table to be edited offline must have an
integer primary key**. Even if you have another natural primary key, if that
key is not an integer, then you cannot use it as a primary key: *make it a
unique column*.

Another limitation is that *you cannot use all PostgreSQL data types* for
columns. For example, you cannot use one of the range types for a column
(min-max in the same column): QGIS will not recognize the type, and thus a
range column won't show up in form. In this example, use two columns instead,
one for min and one for max.

On the other hand, QGIS automatically generated forms cannot embrace the whole
power of SQL constraints. For example, you may have a database constraint that
says: "if column A is filled, then column B must be filled too". But the
automatic form in QGIS cannot enforce this constraint, and thus will let user
enter a value for field A and no value for field B. To work around this
limitation, documentation is especially important. *Each field in the form must
be documented to warn user about extra constraints*.


License
=======

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
