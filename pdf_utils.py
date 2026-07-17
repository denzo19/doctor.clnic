import io
import os

from flask import current_app
from PIL import Image


STANDARD_PDF_MARGIN = 34
STANDARD_PDF_HEADER_HEIGHT = 42
STANDARD_PDF_FOOTER_HEIGHT = 28
STANDARD_PDF_HEADER_TOP_MARGIN = 14
STANDARD_PDF_FOOTER_BOTTOM_MARGIN = 12


def escape_pdf_text(value):
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def truncate_pdf_text(value, max_chars):
    text = "" if value is None else str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def standard_pdf_content_top(page_height):
    return page_height - STANDARD_PDF_HEADER_TOP_MARGIN - STANDARD_PDF_HEADER_HEIGHT - 26


def standard_pdf_content_bottom():
    return STANDARD_PDF_FOOTER_BOTTOM_MARGIN + STANDARD_PDF_FOOTER_HEIGHT + 22


def _load_pdf_image(image_path):
    if not os.path.exists(image_path):
        return None

    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        output = io.BytesIO()
        rgb_image.save(output, format="JPEG", quality=92)
        return {
            "data": output.getvalue(),
            "width": rgb_image.width,
            "height": rgb_image.height
        }


def get_standard_pdf_images(app_root_path=None):
    root_path = app_root_path or current_app.root_path
    image_dir = os.path.join(root_path, "static", "images")

    return {
        "header": _load_pdf_image(os.path.join(image_dir, "pdf_header.png")),
        "footer": _load_pdf_image(os.path.join(image_dir, "pdf_footer.jpg"))
    }


def standard_pdf_image_names(app_root_path=None):
    images = get_standard_pdf_images(app_root_path)
    image_names = {}

    if images.get("header"):
        image_names["header"] = "PdfHeader"
    if images.get("footer"):
        image_names["footer"] = "PdfFooter"

    return image_names


def standard_pdf_chrome_commands(page_width, page_height, page_number, image_names=None):
    image_names = image_names or {}
    commands = []

    header_name = image_names.get("header")
    if header_name:
        header_width = page_width - (STANDARD_PDF_MARGIN * 2)
        header_y = page_height - STANDARD_PDF_HEADER_TOP_MARGIN - STANDARD_PDF_HEADER_HEIGHT
        commands.append(
            f"q {header_width} 0 0 {STANDARD_PDF_HEADER_HEIGHT} "
            f"{STANDARD_PDF_MARGIN} {header_y} cm /{header_name} Do Q"
        )

    footer_name = image_names.get("footer")
    if footer_name:
        footer_width = page_width - (STANDARD_PDF_MARGIN * 2)
        footer_y = STANDARD_PDF_FOOTER_BOTTOM_MARGIN
        commands.append(
            f"q {footer_width} 0 0 {STANDARD_PDF_FOOTER_HEIGHT} "
            f"{STANDARD_PDF_MARGIN} {footer_y} cm /{footer_name} Do Q"
        )

    commands.append(
        f"BT /F1 9 Tf {page_width - 94} {standard_pdf_content_bottom() - 16} "
        f"Td (Page {page_number}) Tj ET"
    )

    return commands


def add_standard_pdf_image_objects(objects, app_root_path=None):
    images = get_standard_pdf_images(app_root_path)
    resource_entries = []
    image_names = {}

    for resource_name, image_key in (("PdfHeader", "header"), ("PdfFooter", "footer")):
        image = images.get(image_key)
        if not image:
            continue

        image_object_id = len(objects) + 1
        image_bytes = image["data"]
        objects.append(
            (
                f"<< /Type /XObject /Subtype /Image /Width {image['width']} "
                f"/Height {image['height']} /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(image_bytes)} >>\n"
            ).encode("ascii") +
            b"stream\n" +
            image_bytes +
            b"\nendstream"
        )
        resource_entries.append(f"/{resource_name} {image_object_id} 0 R")
        image_names[image_key] = resource_name

    xobject_resource = ""
    if resource_entries:
        xobject_resource = " /XObject << " + " ".join(resource_entries) + " >>"

    return xobject_resource, image_names
