"""Prefer Qt 6. Qt 5.15 exposes the same scoped enums used by this UI."""
try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    BINDING = "PyQt6"
except ModuleNotFoundError as error:
    if error.name != "PyQt6":
        raise
    from PyQt5 import QtCore, QtGui, QtWidgets
    BINDING = "PyQt5"

Qt = QtCore.Qt
