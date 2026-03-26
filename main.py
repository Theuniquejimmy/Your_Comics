"""Entry point for ComicVault application."""
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImageReader
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

from app_ui import ComicBrowser


def _qt_message_filter(msg_type, context, message):
    """Suppress harmless Qt noise in console."""
    ml = message.lower()
    if ("icc" in ml or "fromIccProfile" in message
            or "IDComposition" in message
            or "direct_composition" in ml
            or "QueryInterface" in message
            or "0x80004002" in message):
        return
    if msg_type == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        print(f"Qt Error: {message}")


def main():
    qInstallMessageHandler(_qt_message_filter)
    QImageReader.setAllocationLimit(0)  # Remove 256MB restriction for large comics

    app = QApplication(sys.argv)
    window = ComicBrowser()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
