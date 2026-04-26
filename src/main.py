"""Application entrypoint."""

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from constants import APP_LOGO_PATH
from window import AgentChatWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(APP_LOGO_PATH)))
    window = AgentChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
