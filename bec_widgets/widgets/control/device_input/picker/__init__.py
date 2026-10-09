"""Searchable device and signal pickers with a QWidget and a QML popup.

The pickers keep the public API of :class:`DeviceComboBox` and :class:`SignalComboBox` (they are
subclasses) and replace the plain drop-down list with a popup that searches, groups and shows
the live value of the highlighted entry. :mod:`picker_model` holds the toolkit-independent
model and :mod:`picker_common` the combobox and popup base classes both versions share.
"""
