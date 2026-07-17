import os

from pdf_utils import (
    add_standard_pdf_image_objects,
    escape_pdf_text,
    standard_pdf_chrome_commands,
    standard_pdf_content_top,
    standard_pdf_image_names,
    truncate_pdf_text
)


def get_prescription_status(rows):
    statuses = [row["prescription_status"] for row in rows]

    if "stopped" in statuses:
        return "stopped"
    if "active" in statuses:
        return "active"
    return "draft"


def format_prescription_medication(row):
    return " ".join(
        part for part in [
            row["medication_name"] or "",
            row["strength"] or "",
            row["dosage_form"] or ""
        ]
        if part
    )


def get_prescription_header_image(app_root_path):
    image_path = os.path.join(app_root_path, "static", "images", "prescription_header.jpeg")

    if not os.path.exists(image_path):
        return None

    with open(image_path, "rb") as image_file:
        return {
            "data": image_file.read(),
            "width": 1380,
            "height": 222
        }


def build_prescription_pdf(prescription, medications, app_root_path):
    page_width = 612
    page_height = 792
    left = 42
    header_image = None
    header_width = page_width - (left * 2)
    header_height = 85
    header_y = page_height - 104
    top = 642 if header_image else standard_pdf_content_top(page_height)
    row_height = 24
    rows_per_page = 20
    pages = []
    image_names = standard_pdf_image_names(app_root_path)

    for start in range(0, max(len(medications), 1), rows_per_page):
        page_medications = medications[start:start + rows_per_page]
        commands = []

        if header_image:
            commands.append(
                f"q {header_width} 0 0 {header_height} {left} {header_y} cm /Im1 Do Q"
            )

        commands.extend([
            "0.12 0.31 0.47 rg",
            f"BT /F1 20 Tf {left} {top} Td (Prescription) Tj ET",
            "0 g",
            "0.12 0.31 0.47 RG",
            f"{left} {top - 32} m {page_width - left} {top - 32} l S",
            "0 g",
            f"BT /F1 10 Tf {left} {top - 54} Td (Prescription: {escape_pdf_text(prescription['prescription_id'])}) Tj ET",
            f"BT /F1 10 Tf {left + 180} {top - 54} Td (Start Date: {escape_pdf_text(prescription['start_date'])}) Tj ET",
            f"BT /F1 10 Tf {left} {top - 74} Td (Patient: {escape_pdf_text(truncate_pdf_text(prescription['patient'], 58))}) Tj ET",
            f"BT /F1 10 Tf {left} {top - 94} Td (Ordered by: {escape_pdf_text(truncate_pdf_text(prescription['doctor'], 58))}) Tj ET",
        ])

        table_top = top - 124
        commands.extend([
            "0.12 0.31 0.47 RG",
            f"{left} {table_top + 8} m {page_width - left} {table_top + 8} l S",
            f"BT /F1 9 Tf {left + 4} {table_top - 7} Td (Medication) Tj ET",
            f"BT /F1 9 Tf {left + 190} {table_top - 7} Td (Dose) Tj ET",
            f"BT /F1 9 Tf {left + 270} {table_top - 7} Td (Frequency) Tj ET",
            f"BT /F1 9 Tf {left + 355} {table_top - 7} Td (End Date) Tj ET",
            f"BT /F1 9 Tf {left + 430} {table_top - 7} Td (Notes) Tj ET",
            f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
            "0 g"
        ])

        y = table_top - 33

        if page_medications:
            for medication in page_medications:
                commands.extend([
                    f"BT /F1 8.5 Tf {left + 4} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['medication'], 31))}) Tj ET",
                    f"BT /F1 8.5 Tf {left + 190} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['dose'], 12))}) Tj ET",
                    f"BT /F1 8.5 Tf {left + 270} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['frequency'], 13))}) Tj ET",
                    f"BT /F1 8.5 Tf {left + 355} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['end_date'], 10))}) Tj ET",
                    f"BT /F1 8.5 Tf {left + 430} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['notes'], 22))}) Tj ET",
                    f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                    "0 g"
                ])
                y -= row_height
        else:
            commands.append(
                f"BT /F1 10 Tf {left + 6} {y} Td (No medications found.) Tj ET"
            )

        page_number = len(pages) + 1
        commands.extend(
            standard_pdf_chrome_commands(page_width, page_height, page_number, image_names)
        )
        pages.append("\n".join(commands))

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    ]

    standard_xobject_resource, _ = add_standard_pdf_image_objects(objects, app_root_path)

    image_object_id = None

    if header_image:
        image_object_id = len(objects) + 1
        image_bytes = header_image["data"]
        objects.append(
            (
                f"<< /Type /XObject /Subtype /Image /Width {header_image['width']} "
                f"/Height {header_image['height']} /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(image_bytes)} >>\n"
            ).encode("ascii") +
            b"stream\n" +
            image_bytes +
            b"\nendstream"
        )

    page_object_ids = []

    for page_content in pages:
        content_bytes = page_content.encode("latin-1", "replace")
        content_object_id = len(objects) + 1
        objects.append(
            b"<< /Length " + str(len(content_bytes)).encode("ascii") + b" >>\nstream\n" +
            content_bytes +
            b"\nendstream"
        )

        page_object_id = len(objects) + 1
        page_object_ids.append(page_object_id)
        xobject_resource = standard_xobject_resource

        if image_object_id:
            if xobject_resource:
                xobject_resource = xobject_resource[:-3] + f" /Im1 {image_object_id} 0 R >>"
            else:
                xobject_resource = f" /XObject << /Im1 {image_object_id} 0 R >>"

        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 3 0 R >>{xobject_resource} >> "
            f"/Contents {content_object_id} 0 R >>".encode("ascii")
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("ascii")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF".encode("ascii")
    )

    return bytes(pdf)
