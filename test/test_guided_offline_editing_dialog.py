# coding=utf-8
"""Dialog test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'ygversil@lilo.org'
__date__ = '2019-06-08'
__copyright__ = 'Copyright 2019, Yann Voté'

import unittest

from PyQt5.QtWidgets import QDialogButtonBox, QDialog

from guided_offline_editing_dialog import GuidedOfflineEditingPluginDialog

from .utilities import get_qgis_app
QGIS_APP = get_qgis_app()


class GuidedOfflineEditingPluginDialogTest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.dialog = GuidedOfflineEditingPluginDialog(None)

    def tearDown(self):
        """Runs after each test."""
        self.dialog = None

    def test_dialog_download(self):
        """Check that clicking Download button close window as rejected."""
        button = self.dialog.downloadButton
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Rejected)

    def test_dialog_upload(self):
        """Check that clicking Download button close window as rejected."""
        button = self.dialog.uploadButton
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Rejected)

    def test_dialog_close(self):
        """Check that clicking Close button close window as rejected."""
        button = self.dialog.closeButtonBox.button(QDialogButtonBox.Close)
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Rejected)


if __name__ == "__main__":
    suite = unittest.makeSuite(GuidedOfflineEditingPluginDialogTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
