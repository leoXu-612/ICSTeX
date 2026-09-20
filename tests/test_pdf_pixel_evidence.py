from unittest import TestCase
from PySide6.QtGui import QColor, QImage
from tools.pdf_pixel_evidence import interior_ink_pixels


class PdfPixelEvidenceTests(TestCase):
    def test_blank_control_and_outside_border_do_not_count_as_content(self):
        image = QImage(100, 100, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        self.assertEqual(interior_ink_pixels(image), 0)
        for x in range(100):
            image.setPixelColor(x, 0, QColor("black"))
        self.assertEqual(interior_ink_pixels(image), 0)

    def test_antialiased_thin_gray_pixels_between_old_sample_points_are_seen(self):
        image = QImage(100, 100, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        for x in (41, 43, 45, 47):
            image.setPixelColor(x, 51, QColor(150, 150, 150))
        self.assertEqual(interior_ink_pixels(image), 4)
