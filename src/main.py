"""Application entrypoint."""

import sys

from PyQt6.QtWidgets import QApplication

from window import AgentChatWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AgentChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
