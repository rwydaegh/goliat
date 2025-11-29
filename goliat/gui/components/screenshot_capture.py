"""Screenshot capture component for GUI tabs."""

import logging
from typing import TYPE_CHECKING, Dict, Optional, Any

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI

try:
    from PySide6.QtCore import QBuffer, QIODevice, QRect
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QWidget, QApplication
except ImportError:
    # Fallback for environments without PySide6
    QBuffer = None  # type: ignore
    QIODevice = None  # type: ignore
    QPixmap = None  # type: ignore
    QWidget = None  # type: ignore
    QRect = None  # type: ignore
    QApplication = None  # type: ignore


class ScreenshotCapture:
    """Captures screenshots of GUI tabs for web monitoring."""

    def __init__(self, gui: "ProgressGUI") -> None:
        """Initialize screenshot capture component.

        Args:
            gui: ProgressGUI instance with tabs to capture.
        """
        self.gui = gui
        self.verbose_logger = logging.getLogger("screenshot_capture")

    def capture_all_tabs(self) -> Dict[str, bytes]:
        """Capture all GUI tabs as JPEG bytes.

        Captures each tab widget individually without switching tabs,
        so it doesn't interfere with the user's current view.

        Returns:
            Dictionary mapping tab names to JPEG bytes.
            Empty dict if capture fails or PySide6 not available.
        """
        if QBuffer is None or QWidget is None or QPixmap is None:
            return {}

        screenshots: Dict[str, bytes] = {}

        try:
            if not hasattr(self.gui, "tabs"):
                self.verbose_logger.warning("GUI has no tabs attribute")
                return {}

            tabs = self.gui.tabs
            tab_count = tabs.count()

            for i in range(tab_count):
                try:
                    tab_widget = tabs.widget(i)
                    tab_name = tabs.tabText(i)

                    if tab_widget is None:
                        self.verbose_logger.warning(f"Tab {i} ({tab_name}) has no widget")
                        continue

                    # Skip the main "Progress" tab - its data is already sent via other mechanisms
                    if tab_name == "Progress":
                        continue

                    # Get the size of the tab widget's parent (QTabWidget) to know the proper size
                    # Non-visible tabs might have zero size, so we use parent size as reference
                    parent_size = tabs.size()
                    widget_width = tab_widget.width() if tab_widget.width() > 0 else parent_size.width()
                    widget_height = tab_widget.height() if tab_widget.height() > 0 else parent_size.height()

                    # Fallback to reasonable defaults if sizes are still zero
                    if widget_width == 0:
                        widget_width = 800
                    if widget_height == 0:
                        widget_height = 600

                    # Process events to ensure all widgets are painted
                    if QApplication is not None:
                        QApplication.processEvents()

                    pixmap = QPixmap(widget_width, widget_height)
                    pixmap.fill()
                    tab_widget.render(pixmap)

                    # Process events after rendering
                    if QApplication is not None:
                        QApplication.processEvents()

                    if pixmap.isNull():
                        self.verbose_logger.warning(f"Failed to grab pixmap for tab {tab_name}")
                        continue

                    # Verify pixmap has content (not just empty/white)
                    if pixmap.width() == 0 or pixmap.height() == 0:
                        self.verbose_logger.warning(f"Pixmap for tab {tab_name} has zero size")
                        continue

                    # Convert to JPEG bytes
                    jpeg_bytes = self._compress_to_jpeg(pixmap)

                    if jpeg_bytes:
                        screenshots[tab_name] = jpeg_bytes
                        self.verbose_logger.debug(f"Captured screenshot for tab '{tab_name}' ({len(jpeg_bytes)} bytes)")

                except Exception as e:
                    # Log error but continue capturing other tabs
                    self.verbose_logger.warning(f"Failed to capture tab {i}: {e}", exc_info=True)
                    continue

        except Exception as e:
            self.verbose_logger.error(f"Failed to capture screenshots: {e}", exc_info=True)

        return screenshots

    def _compress_to_jpeg(self, pixmap: Any, quality: int = 70) -> Optional[bytes]:
        """Convert QPixmap to JPEG bytes.

        Args:
            pixmap: QPixmap to compress.
            quality: JPEG quality (0-100), default 70 for balanced compression/quality.

        Returns:
            JPEG bytes, or None if compression fails.
        """
        if QBuffer is None or QIODevice is None:
            return None

        try:
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)

            success = pixmap.save(buffer, "JPEG", quality=quality)

            if not success:
                self.verbose_logger.warning("Failed to save pixmap as JPEG")
                return None

            buffer.close()
            return buffer.data()

        except Exception as e:
            self.verbose_logger.warning(f"Failed to compress pixmap to JPEG: {e}", exc_info=True)
            return None
