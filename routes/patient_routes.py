from datetime import datetime

from flask import Response, flash, redirect, render_template, request, session, url_for

from auth import login_required, permission_required
from database import execute_query
from i18n import translate
from pdf_utils import (
    add_standard_pdf_image_objects,
    escape_pdf_text,
    standard_pdf_chrome_commands,
    standard_pdf_content_top,
    standard_pdf_image_names,
    truncate_pdf_text
)


def register_patient_routes(app):
    def flash_t(message, category="success"):
        flash(translate(message, session.get("language", "en")), category)

    @app.route("/patients/add", methods=["POST"])
    def add_patient():
        patient_code = request.form.get("patient_code")
        first_name = request.form.get("first_name")
        middle_name = request.form.get("middle_name")
        last_name = request.form.get("last_name")
        date_of_birth = request.form.get("date_of_birth")
        gender = request.form.get("gender")
        phone_number = request.form.get("phone_number")
        address = request.form.get("address")

        execute_query(
            """
            INSERT INTO patients
            (patient_code, first_name, middle_name, last_name, date_of_birth, gender, phone_number, address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                patient_code,
                first_name,
                middle_name,
                last_name,
                date_of_birth,
                gender,
                phone_number,
                address
            )
        )

        flash_t("Patient added successfully.", "success")
        return redirect(url_for("patients"))

    @app.route("/patients", methods=["GET", "POST"])
    @login_required
    @permission_required("patients")
    def patients():

        # =====================================================
        # ADD PATIENT
        # =====================================================

        if request.method == "POST":

            patient_code = request.form.get(
                "patient_code",
                ""
            ).strip()

            first_name = request.form.get(
                "first_name",
                ""
            ).strip()

            middle_name = request.form.get(
                "middle_name",
                ""
            ).strip()

            last_name = request.form.get(
                "last_name",
                ""
            ).strip()

            date_of_birth = request.form.get(
                "date_of_birth"
            )

            gender = request.form.get(
                "gender"
            )

            phone_number = request.form.get(
                "phone_number",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip()

            address = request.form.get(
                "address",
                ""
            ).strip()

            execute_query(
                """
                INSERT INTO patients
                (
                    patient_code,
                    first_name,
                    middle_name,
                    last_name,
                    date_of_birth,
                    gender,
                    phone_number,
                    email,
                    address,
                    is_active
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    1
                )
                """,
                (
                    patient_code,
                    first_name,
                    middle_name,
                    last_name,
                    date_of_birth,
                    gender,
                    phone_number,
                    email,
                    address
                )
            )

            flash_t("Patient added successfully.", "success")

            return redirect(
                url_for("patients")
            )

        # =====================================================
        # SEARCH
        # =====================================================

        selected_patient_id = request.args.get("patient_id", type=int)
        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        # =====================================================
        # PATIENTS
        # =====================================================

        patients = execute_query(
            """
            SELECT
                id,
                patient_code,
                first_name,
                middle_name,
                last_name,
                date_of_birth,
                gender,
                phone_number,
                email,
                address,
                is_active

            FROM patients

            WHERE
                (
                    %s IS NOT NULL
                    AND id = %s
                )
                OR (
                    %s IS NULL
                    AND (
                        patient_code LIKE %s
                        OR first_name LIKE %s
                        OR middle_name LIKE %s
                        OR last_name LIKE %s
                        OR phone_number LIKE %s
                        OR email LIKE %s
                    )
                )

            ORDER BY
                last_name,
                first_name
            """,
            (
                selected_patient_id,
                selected_patient_id,
                selected_patient_id,
                like_search,
                like_search,
                like_search,
                like_search,
                like_search,
                like_search
            ),
            fetchall=True
        )

        patient_options = execute_query(
            """
            SELECT
                id,
                patient_code,
                first_name,
                middle_name,
                last_name,
                phone_number
            FROM patients
            WHERE is_active = 1
            ORDER BY last_name, first_name, patient_code
            """,
            fetchall=True
        )

        # =====================================================
        # RENDER
        # =====================================================

        return render_template(
            "patients.html",
            patients=patients,
            search=search,
            selected_patient_id=selected_patient_id,
            patient_options=patient_options
        )

    def build_patients_pdf_report(patients, search_text=""):
        page_width = 612
        page_height = 792
        left = 28
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(patients), 1), rows_per_page):
            page_patients = patients[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Patients Report) Tj ET",
                "0 g",
                f"BT /F1 9 Tf {left} {top - 18} Td (Generated on {escape_pdf_text(datetime.now().strftime('%Y-%m-%d %H:%M'))}) Tj ET",
            ]

            if search_text:
                commands.append(
                    f"BT /F1 9 Tf {left} {top - 32} Td (Search: {escape_pdf_text(truncate_pdf_text(search_text, 80))}) Tj ET"
                )

            table_top = top - 58
            commands.extend([
                "0.12 0.31 0.47 RG",
                f"{left} {table_top + 8} m {page_width - left} {table_top + 8} l S",
                f"BT /F1 8.5 Tf {left + 4} {table_top - 7} Td (Code) Tj ET",
                f"BT /F1 8.5 Tf {left + 78} {table_top - 7} Td (Full Name) Tj ET",
                f"BT /F1 8.5 Tf {left + 220} {table_top - 7} Td (DOB) Tj ET",
                f"BT /F1 8.5 Tf {left + 290} {table_top - 7} Td (Gender) Tj ET",
                f"BT /F1 8.5 Tf {left + 350} {table_top - 7} Td (Phone) Tj ET",
                f"BT /F1 8.5 Tf {left + 445} {table_top - 7} Td (Email) Tj ET",
                f"BT /F1 8.5 Tf {left + 545} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_patients:
                for patient in page_patients:
                    full_name = " ".join(
                        part for part in [
                            patient["first_name"],
                            patient["middle_name"],
                            patient["last_name"]
                        ]
                        if part
                    )
                    active_text = "Yes" if patient["is_active"] else "No"
                    commands.extend([
                        f"BT /F1 7.5 Tf {left + 4} {y} Td ({escape_pdf_text(truncate_pdf_text(patient['patient_code'], 10))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 78} {y} Td ({escape_pdf_text(truncate_pdf_text(full_name, 21))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 220} {y} Td ({escape_pdf_text(patient['date_of_birth'])}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 290} {y} Td ({escape_pdf_text(patient['gender'])}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 350} {y} Td ({escape_pdf_text(truncate_pdf_text(patient['phone_number'], 13))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 445} {y} Td ({escape_pdf_text(truncate_pdf_text(patient['email'], 15))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 545} {y} Td ({active_text}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No patients found.) Tj ET"
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
        standard_xobject_resource, _ = add_standard_pdf_image_objects(objects)

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
            objects.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 3 0 R >>{standard_xobject_resource} >> "
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


    @app.route("/patients/report")
    @login_required
    @permission_required("patients")
    def patients_report():
        selected_patient_id = request.args.get("patient_id", type=int)
        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        patient_rows = execute_query(
            """
            SELECT
                patient_code,
                first_name,
                middle_name,
                last_name,
                date_of_birth,
                gender,
                phone_number,
                email,
                is_active
            FROM patients
            WHERE
                (
                    %s IS NOT NULL
                    AND id = %s
                )
                OR (
                    %s IS NULL
                    AND (
                        patient_code LIKE %s
                        OR first_name LIKE %s
                        OR middle_name LIKE %s
                        OR last_name LIKE %s
                        OR phone_number LIKE %s
                        OR email LIKE %s
                    )
                )
            ORDER BY
                last_name,
                first_name
            """,
            (
                selected_patient_id,
                selected_patient_id,
                selected_patient_id,
                like_search,
                like_search,
                like_search,
                like_search,
                like_search,
                like_search
            ),
            fetchall=True
        )

        pdf_bytes = build_patients_pdf_report(patient_rows, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=patients_report.pdf"
            }
        )


    @app.route("/patients/update/<int:patient_id>", methods=["POST"])
    @login_required
    @permission_required("patients")
    def update_patient(patient_id):
        execute_query(
            """
            UPDATE patients
            SET patient_code = %s,
                first_name = %s,
                middle_name = %s,
                last_name = %s,
                date_of_birth = %s,
                gender = %s,
                phone_number = %s,
                email = %s,
                address = %s,
                is_active = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                request.form.get("patient_code", "").strip(),
                request.form.get("first_name", "").strip(),
                request.form.get("middle_name", "").strip(),
                request.form.get("last_name", "").strip(),
                request.form.get("date_of_birth") or None,
                request.form.get("gender") or None,
                request.form.get("phone_number", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("address", "").strip(),
                1 if request.form.get("is_active") == "1" else 0,
                patient_id
            )
        )

        flash_t("Patient updated successfully.", "success")
        return redirect(url_for("patients"))


    @app.route("/patients/stop/<int:patient_id>", methods=["POST"])
    @login_required
    @permission_required("patients")
    def stop_patient(patient_id):
        execute_query(
            """
            UPDATE patients
            SET is_active = 0,
                updated_at = NOW()
            WHERE id = %s
            """,
            (patient_id,)
        )

        flash_t("Patient stopped successfully.", "success")
        return redirect(url_for("patients"))

    @app.route("/patients/add_ajax", methods=["POST"])
    @login_required
    @permission_required("patients")
    def add_patient_ajax():
        execute_query(
            """
            INSERT INTO patients
            (patient_code, first_name, middle_name, last_name,
             date_of_birth, gender, phone_number, email, address, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (
                request.form.get("patient_code", "").strip(),
                request.form.get("first_name", "").strip(),
                request.form.get("middle_name", "").strip(),
                request.form.get("last_name", "").strip(),
                request.form.get("date_of_birth") or None,
                request.form.get("gender") or None,
                request.form.get("phone_number", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("address", "").strip()
            )
        )

        return {"success": True}
