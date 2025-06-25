from __future__ import annotations

from abc import abstractmethod

from qtpy.QtCore import QObject


class BundleConnection(QObject):
    bundle_name: str

    @abstractmethod
    def connect(self):
        """
        Connects the bundle to the target widget or application.
        This method should be implemented by subclasses to define how the bundle interacts with the target.
        """

    @abstractmethod
    def disconnect(self):
        """
        Disconnects the bundle from the target widget or application.
        This method should be implemented by subclasses to define how to clean up connections.
        """
