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


def register_medical_settings_routes(app):
    def flash_t(message, category="success"):
        flash(translate(message, session.get("language", "en")), category)

    def translate_message(message):
        return translate(message, session.get("language", "en"))

    def medical_center_name_exists(center_name, exclude_id=None):
        if exclude_id:
            return execute_query(
                """
                SELECT id
                FROM medical_centers
                WHERE LOWER(center_name) = LOWER(%s)
                  AND id <> %s
                """,
                (center_name, exclude_id),
                fetchone=True
            )

        return execute_query(
            """
            SELECT id
            FROM medical_centers
            WHERE LOWER(center_name) = LOWER(%s)
            """,
            (center_name,),
            fetchone=True
        )


    def medical_center_phone_exists(phone_number, exclude_id=None):
        if exclude_id:
            return execute_query(
                """
                SELECT id
                FROM medical_centers
                WHERE phone_number = %s
                  AND id <> %s
                """,
                (phone_number, exclude_id),
                fetchone=True
            )

        return execute_query(
            """
            SELECT id
            FROM medical_centers
            WHERE phone_number = %s
            """,
            (phone_number,),
            fetchone=True
        )


    def doctor_center_assignment_exists(doctor_id, center_id, exclude_id=None):
        if exclude_id:
            return execute_query(
                """
                SELECT id, is_active
                FROM doctor_center_assignments
                WHERE doctor_id = %s
                  AND center_id = %s
                  AND id <> %s
                """,
                (doctor_id, center_id, exclude_id),
                fetchone=True
            )

        return execute_query(
            """
            SELECT id, is_active
            FROM doctor_center_assignments
            WHERE doctor_id = %s
              AND center_id = %s
            """,
            (doctor_id, center_id),
            fetchone=True
        )


    def doctor_weekly_program_conflicts(
        doctor_id,
        day_of_week,
        start_time,
        end_time,
        exclude_id=None
    ):
        if exclude_id:
            return execute_query(
                """
                SELECT id
                FROM doctor_weekly_programs
                WHERE doctor_id = %s
                  AND day_of_week = %s
                  AND is_active = 1
                  AND start_time < %s
                  AND end_time > %s
                  AND id <> %s
                """,
                (doctor_id, day_of_week, end_time, start_time, exclude_id),
                fetchone=True
            )

        return execute_query(
            """
            SELECT id
            FROM doctor_weekly_programs
            WHERE doctor_id = %s
              AND day_of_week = %s
              AND is_active = 1
              AND start_time < %s
              AND end_time > %s
            """,
            (doctor_id, day_of_week, end_time, start_time),
            fetchone=True
        )


    def get_absence_form_values():
        absence_type = request.form.get("absence_type") or "hours"
        absence_date = request.form.get("absence_date")
        end_date = request.form.get("end_date") or absence_date

        if absence_type == "date_range":
            start_time = "00:00"
            end_time = "23:59"
        elif absence_type == "full_day":
            end_date = absence_date
            start_time = "00:00"
            end_time = "23:59"
        else:
            absence_type = "hours"
            end_date = absence_date
            start_time = request.form.get("start_time") or "00:00"
            end_time = request.form.get("end_time") or "23:59"

        return {
            "absence_type": absence_type,
            "absence_date": absence_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time
        }


    def absence_values_error(absence_values):
        if (
            absence_values["absence_type"] == "date_range"
            and absence_values["end_date"] < absence_values["absence_date"]
        ):
            return "End date must be on or after absence date."

        if (
            absence_values["absence_type"] == "hours"
            and absence_values["start_time"] >= absence_values["end_time"]
        ):
            return "Start time must be before end time."

        return None

    @app.route("/admin/medical_centers", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_medical_centers")
    def manage_medical_centers():

        # =====================================================
        # ADD MEDICAL CENTER
        # =====================================================

        if request.method == "POST":

            center_name = request.form.get(
                "center_name",
                ""
            ).strip()

            address = request.form.get(
                "address",
                ""
            ).strip()

            phone_number = request.form.get(
                "phone_number",
                ""
            ).strip()

            is_active = 1 if request.form.get(
                "is_active"
            ) else 0

            if not center_name:
                flash_t("Medical center name is required.", "error")
                return redirect(url_for("manage_medical_centers"))

            if not phone_number:
                flash_t("Phone number is required.", "error")
                return redirect(url_for("manage_medical_centers"))

            if medical_center_name_exists(center_name):
                flash_t("Medical center name already exists.", "error")
                return redirect(url_for("manage_medical_centers"))

            if medical_center_phone_exists(phone_number):
                flash_t("Medical center phone number already exists.", "error")
                return redirect(url_for("manage_medical_centers"))

            execute_query(
                """
                INSERT INTO medical_centers
                (
                    center_name,
                    address,
                    phone_number,
                    is_active
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    center_name,
                    address,
                    phone_number,
                    is_active
                )
            )

            flash_t("Medical center added successfully.", "success")

            return redirect(
                url_for("manage_medical_centers")
            )

        # =====================================================
        # SEARCH
        # =====================================================

        search = request.args.get(
            "search",
            ""
        ).strip()

        # =====================================================
        # MEDICAL CENTERS
        # =====================================================

        medical_centers = execute_query(
            """
            SELECT
                id,
                center_name,
                address,
                phone_number,
                is_active

            FROM medical_centers

            WHERE
                center_name LIKE %s
                OR address LIKE %s
                OR phone_number LIKE %s

            ORDER BY center_name
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            ),
            fetchall=True
        )
        # =====================================================
        # RENDER
        # =====================================================

        return render_template(
            "medical_centers.html",
            medical_centers=medical_centers,
            search=search
        )

    def build_medical_centers_pdf_report(medical_centers, search_text=""):
        page_width = 612
        page_height = 792
        left = 42
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(medical_centers), 1), rows_per_page):
            page_centers = medical_centers[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Medical Centers Report) Tj ET",
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
                f"BT /F1 11 Tf {left + 6} {table_top - 7} Td (Center Name) Tj ET",
                f"BT /F1 11 Tf {left + 185} {table_top - 7} Td (Address) Tj ET",
                f"BT /F1 11 Tf {left + 390} {table_top - 7} Td (Phone) Tj ET",
                f"BT /F1 11 Tf {left + 505} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_centers:
                for center in page_centers:
                    active_text = "Yes" if center["is_active"] else "No"
                    commands.extend([
                        f"BT /F1 10 Tf {left + 6} {y} Td ({escape_pdf_text(truncate_pdf_text(center['center_name'], 25))}) Tj ET",
                        f"BT /F1 10 Tf {left + 185} {y} Td ({escape_pdf_text(truncate_pdf_text(center['address'], 30))}) Tj ET",
                        f"BT /F1 10 Tf {left + 390} {y} Td ({escape_pdf_text(truncate_pdf_text(center['phone_number'], 16))}) Tj ET",
                        f"BT /F1 10 Tf {left + 505} {y} Td ({active_text}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No medical centers found.) Tj ET"
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


    @app.route("/admin/medical_centers/report")
    @login_required
    @permission_required("manage_medical_centers")
    def medical_centers_report():
        search = request.args.get("search", "").strip()

        medical_centers = execute_query(
            """
            SELECT
                center_name,
                address,
                phone_number,
                is_active
            FROM medical_centers
            WHERE
                center_name LIKE %s
                OR address LIKE %s
                OR phone_number LIKE %s
            ORDER BY center_name
            """,
            (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            ),
            fetchall=True
        )

        pdf_bytes = build_medical_centers_pdf_report(medical_centers, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=medical_centers_report.pdf"
            }
        )

    @app.route("/admin/medical_centers/add_ajax", methods=["POST"])
    @login_required
    @permission_required("manage_medical_centers")
    def add_medical_center_ajax():
        center_name = request.form.get("center_name", "").strip()
        address = request.form.get("address", "").strip()
        phone_number = request.form.get("phone_number", "").strip()

        if not center_name:
            return {
                "success": False,
                "message": translate_message("Medical center name is required.")
            }, 400

        if not phone_number:
            return {
                "success": False,
                "message": translate_message("Phone number is required.")
            }, 400

        if medical_center_name_exists(center_name):
            return {
                "success": False,
                "message": translate_message("Medical center name already exists.")
            }, 400

        if medical_center_phone_exists(phone_number):
            return {
                "success": False,
                "message": translate_message("Medical center phone number already exists.")
            }, 400

        execute_query(
            """
            INSERT INTO medical_centers
            (center_name, address, phone_number, is_active)
            VALUES (%s, %s, %s, 1)
            """,
            (
                center_name,
                address,
                phone_number
            )
        )

        return {"success": True}

    @app.route("/admin/medical_centers/update/<int:center_id>", methods=["POST"])
    @login_required
    @permission_required("manage_medical_centers")
    def update_medical_center(center_id):
        center_name = request.form.get("center_name", "").strip()
        address = request.form.get("address", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if not center_name:
            flash_t("Medical center name is required.", "error")
            return redirect(url_for("manage_medical_centers"))

        if not phone_number:
            flash_t("Phone number is required.", "error")
            return redirect(url_for("manage_medical_centers"))

        if medical_center_name_exists(center_name, center_id):
            flash_t("Medical center name already exists.", "error")
            return redirect(url_for("manage_medical_centers"))

        if medical_center_phone_exists(phone_number, center_id):
            flash_t("Medical center phone number already exists.", "error")
            return redirect(url_for("manage_medical_centers"))

        execute_query(
            """
            UPDATE medical_centers
            SET center_name = %s,
                address = %s,
                phone_number = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                center_name,
                address,
                phone_number,
                is_active,
                center_id
            )
        )

        flash_t("Medical center updated successfully.", "success")
        return redirect(url_for("manage_medical_centers"))

    @app.route("/admin/medical_centers/stop/<int:center_id>", methods=["POST"])
    @login_required
    @permission_required("manage_medical_centers")
    def stop_medical_center(center_id):
        execute_query(
            """
            UPDATE medical_centers
            SET is_active = 0
            WHERE id = %s
            """,
            (center_id,)
        )

        flash_t("Medical center stopped successfully.", "success")
        return redirect(url_for("manage_medical_centers"))

    @app.route("/admin/doctor_center_assignments", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_doctor_center_assignments")
    def manage_doctor_center_assignments():

        # =====================================================
        # ADD ASSIGNMENT
        # =====================================================

        if request.method == "POST":

            doctor_id = request.form.get("doctor_id")
            center_id = request.form.get("center_id")
            existing_assignment = doctor_center_assignment_exists(doctor_id, center_id)

            if existing_assignment and existing_assignment["is_active"]:
                flash_t("This doctor is already assigned to the selected medical center.", "error")
                return redirect(
                    url_for("manage_doctor_center_assignments")
                )

            if existing_assignment:
                execute_query(
                    """
                    UPDATE doctor_center_assignments
                    SET is_active = 1
                    WHERE id = %s
                    """,
                    (existing_assignment["id"],)
                )

                flash_t("Assignment reactivated successfully.", "success")
                return redirect(
                    url_for("manage_doctor_center_assignments")
                )

            execute_query(
                """
                INSERT INTO doctor_center_assignments
                (
                    doctor_id,
                    center_id,
                    is_active
                )
                VALUES
                (
                    %s,
                    %s,
                    1
                )
                """,
                (
                    doctor_id,
                    center_id
                )
            )

            flash_t("Assignment added successfully.", "success")

            return redirect(
                url_for("manage_doctor_center_assignments")
            )

        # =====================================================
        # SEARCH
        # =====================================================

        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        # =====================================================
        # ASSIGNMENTS
        # =====================================================

        assignments = execute_query(
            """
            SELECT
                dca.id,
                dca.doctor_id,
                dca.center_id,
                dca.is_active,

                d.full_name AS doctor_name,
                d.specialty,

                mc.center_name

            FROM doctor_center_assignments dca

            JOIN doctors d
                ON dca.doctor_id = d.id

            JOIN medical_centers mc
                ON dca.center_id = mc.id

            WHERE
                d.full_name LIKE %s
                OR d.specialty LIKE %s
                OR mc.center_name LIKE %s

            ORDER BY
                d.full_name,
                mc.center_name
            """,
            (
                like_search,
                like_search,
                like_search
            ),
            fetchall=True
        )

        # =====================================================
        # DOCTORS
        # =====================================================

        doctors = execute_query(
            """
            SELECT
                id,
                full_name,
                specialty
            FROM doctors
            WHERE is_active = 1
            ORDER BY full_name
            """,
            fetchall=True
        )

        # =====================================================
        # CENTERS
        # =====================================================

        centers = execute_query(
            """
            SELECT
                id,
                center_name
            FROM medical_centers
            WHERE is_active = 1
            ORDER BY center_name
            """,
            fetchall=True
        )

        # =====================================================
        # RENDER
        # =====================================================

        return render_template(
            "doctor_center_assignments.html",
            assignments=assignments,
            doctors=doctors,
            centers=centers,
            search=search
        )

    def build_doctor_center_assignments_pdf_report(assignments, search_text=""):
        page_width = 612
        page_height = 792
        left = 42
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(assignments), 1), rows_per_page):
            page_assignments = assignments[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Doctor-Center Assignments Report) Tj ET",
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
                f"BT /F1 11 Tf {left + 6} {table_top - 7} Td (Doctor) Tj ET",
                f"BT /F1 11 Tf {left + 210} {table_top - 7} Td (Specialty) Tj ET",
                f"BT /F1 11 Tf {left + 360} {table_top - 7} Td (Medical Center) Tj ET",
                f"BT /F1 11 Tf {left + 515} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_assignments:
                for assignment in page_assignments:
                    active_text = "Yes" if assignment["is_active"] else "No"
                    commands.extend([
                        f"BT /F1 10 Tf {left + 6} {y} Td ({escape_pdf_text(truncate_pdf_text(assignment['doctor_name'], 29))}) Tj ET",
                        f"BT /F1 10 Tf {left + 210} {y} Td ({escape_pdf_text(truncate_pdf_text(assignment['specialty'], 21))}) Tj ET",
                        f"BT /F1 10 Tf {left + 360} {y} Td ({escape_pdf_text(truncate_pdf_text(assignment['center_name'], 21))}) Tj ET",
                        f"BT /F1 10 Tf {left + 515} {y} Td ({active_text}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No doctor-center assignments found.) Tj ET"
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


    @app.route("/admin/doctor_center_assignments/report")
    @login_required
    @permission_required("manage_doctor_center_assignments")
    def doctor_center_assignments_report():
        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        assignments = execute_query(
            """
            SELECT
                d.full_name AS doctor_name,
                d.specialty,
                mc.center_name,
                dca.is_active
            FROM doctor_center_assignments dca
            JOIN doctors d
                ON dca.doctor_id = d.id
            JOIN medical_centers mc
                ON dca.center_id = mc.id
            WHERE
                d.full_name LIKE %s
                OR d.specialty LIKE %s
                OR mc.center_name LIKE %s
            ORDER BY
                d.full_name,
                mc.center_name
            """,
            (
                like_search,
                like_search,
                like_search
            ),
            fetchall=True
        )

        pdf_bytes = build_doctor_center_assignments_pdf_report(assignments, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=doctor_center_assignments_report.pdf"
            }
        )

    @app.route("/admin/doctor_center_assignments/add_ajax", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_center_assignments")
    def add_doctor_center_assignment_ajax():
        doctor_id = request.form.get("doctor_id")
        center_id = request.form.get("center_id")
        existing_assignment = doctor_center_assignment_exists(doctor_id, center_id)

        if existing_assignment and existing_assignment["is_active"]:
            return {
                "success": False,
                "message": translate_message("This doctor is already assigned to the selected medical center.")
            }, 400

        if existing_assignment:
            execute_query(
                """
                UPDATE doctor_center_assignments
                SET is_active = 1
                WHERE id = %s
                """,
                (existing_assignment["id"],)
            )

            return {"success": True}

        execute_query(
            """
            INSERT INTO doctor_center_assignments
            (doctor_id, center_id, is_active)
            VALUES (%s, %s, 1)
            """,
            (
                doctor_id,
                center_id
            )
        )

        return {"success": True}

    @app.route("/admin/doctor_center_assignments/update/<int:assignment_id>", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_center_assignments")
    def update_doctor_center_assignment(assignment_id):
        doctor_id = request.form.get("doctor_id")
        center_id = request.form.get("center_id")
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if doctor_center_assignment_exists(doctor_id, center_id, assignment_id):
            flash_t("This doctor is already assigned to the selected medical center.", "error")
            return redirect(url_for("manage_doctor_center_assignments"))

        execute_query(
            """
            UPDATE doctor_center_assignments
            SET doctor_id = %s,
                center_id = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                doctor_id,
                center_id,
                is_active,
                assignment_id
            )
        )

        flash_t("Doctor-center assignment updated successfully.", "success")
        return redirect(url_for("manage_doctor_center_assignments"))

    @app.route("/admin/doctor_center_assignments/stop/<int:assignment_id>", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_center_assignments")
    def stop_doctor_center_assignment(assignment_id):
        execute_query(
            """
            UPDATE doctor_center_assignments
            SET is_active = 0
            WHERE id = %s
            """,
            (assignment_id,)
        )

        flash_t("Doctor-center assignment stopped successfully.", "success")
        return redirect(url_for("manage_doctor_center_assignments"))

    @app.route("/admin/doctor_weekly_programs", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_doctor_weekly_programs")
    def manage_doctor_weekly_programs():

        # =====================================================
        # ADD PROGRAM
        # =====================================================

        if request.method == "POST":

            doctor_id = request.form.get("doctor_id")
            center_id = request.form.get("center_id")
            day_of_week = request.form.get("day_of_week")

            start_time = request.form.get("start_time") or "08:00"
            end_time = request.form.get("end_time") or "17:00"

            slot_duration_minutes = request.form.get(
                "slot_duration_minutes",
                type=int
            )

            if start_time >= end_time:
                flash_t("Start time must be before end time.", "error")
                return redirect(url_for("manage_doctor_weekly_programs"))

            if doctor_weekly_program_conflicts(doctor_id, day_of_week, start_time, end_time):
                flash_t("This doctor's weekly program overlaps with another program on the selected day.", "error")
                return redirect(url_for("manage_doctor_weekly_programs"))

            execute_query(
                """
                INSERT INTO doctor_weekly_programs
                (
                    doctor_id,
                    center_id,
                    day_of_week,
                    start_time,
                    end_time,
                    slot_duration_minutes,
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
                    1
                )
                """,
                (
                    doctor_id,
                    center_id,
                    day_of_week,
                    start_time,
                    end_time,
                    slot_duration_minutes
                )
            )

            flash_t("Weekly program added successfully.", "success")

            return redirect(
                url_for("manage_doctor_weekly_programs")
            )

        selected_doctor_id = request.args.get("doctor_id", type=int)

        # =====================================================
        # PROGRAMS
        # =====================================================

        programs = execute_query(
            """
            SELECT
                dwp.id,

                dwp.doctor_id,
                dwp.center_id,

                dwp.day_of_week,
                dwp.start_time,
                dwp.end_time,
                dwp.slot_duration_minutes,

                dwp.is_active,

                d.full_name AS doctor_name,
                d.specialty,

                mc.center_name

            FROM doctor_weekly_programs dwp

            JOIN doctors d
                ON dwp.doctor_id = d.id

            JOIN medical_centers mc
                ON dwp.center_id = mc.id

            WHERE
                (%s IS NULL OR dwp.doctor_id = %s)

            ORDER BY
                d.full_name,
                FIELD(
                    dwp.day_of_week,
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7
                ),
                dwp.start_time
            """,
            (
                selected_doctor_id,
                selected_doctor_id
            ),
            fetchall=True
        )

        # =====================================================
        # DOCTORS
        # =====================================================

        doctors = execute_query(
            """
            SELECT
                id,
                full_name,
                specialty
            FROM doctors
            WHERE is_active = 1
            ORDER BY full_name
            """,
            fetchall=True
        )

        # =====================================================
        # CENTERS
        # =====================================================

        centers = execute_query(
            """
            SELECT
                id,
                center_name
            FROM medical_centers
            WHERE is_active = 1
            ORDER BY center_name
            """,
            fetchall=True
        )

        # =====================================================
        # RENDER
        # =====================================================

        return render_template(
            "doctor_weekly_programs.html",
            programs=programs,
            doctors=doctors,
            centers=centers,
            selected_doctor_id=selected_doctor_id
        )

    def weekday_name(day_of_week):
        names = {
            1: "Monday",
            2: "Tuesday",
            3: "Wednesday",
            4: "Thursday",
            5: "Friday",
            6: "Saturday",
            7: "Sunday"
        }
        return names.get(int(day_of_week or 0), "")

    def build_doctor_weekly_programs_pdf_report(programs, filter_text=""):
        page_width = 612
        page_height = 792
        left = 30
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(programs), 1), rows_per_page):
            page_programs = programs[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Doctor Weekly Programs Report) Tj ET",
                "0 g",
                f"BT /F1 9 Tf {left} {top - 18} Td (Generated on {escape_pdf_text(datetime.now().strftime('%Y-%m-%d %H:%M'))}) Tj ET",
            ]

            if filter_text:
                commands.append(
                    f"BT /F1 9 Tf {left} {top - 32} Td ({escape_pdf_text(truncate_pdf_text(filter_text, 80))}) Tj ET"
                )

            table_top = top - 58
            commands.extend([
                "0.12 0.31 0.47 RG",
                f"{left} {table_top + 8} m {page_width - left} {table_top + 8} l S",
                f"BT /F1 9 Tf {left + 4} {table_top - 7} Td (Doctor) Tj ET",
                f"BT /F1 9 Tf {left + 150} {table_top - 7} Td (Center) Tj ET",
                f"BT /F1 9 Tf {left + 295} {table_top - 7} Td (Day) Tj ET",
                f"BT /F1 9 Tf {left + 370} {table_top - 7} Td (Start) Tj ET",
                f"BT /F1 9 Tf {left + 425} {table_top - 7} Td (End) Tj ET",
                f"BT /F1 9 Tf {left + 480} {table_top - 7} Td (Slot) Tj ET",
                f"BT /F1 9 Tf {left + 535} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_programs:
                for program in page_programs:
                    active_text = "Yes" if program["is_active"] else "No"
                    slot_text = f"{program['slot_duration_minutes']} min"
                    commands.extend([
                        f"BT /F1 8.5 Tf {left + 4} {y} Td ({escape_pdf_text(truncate_pdf_text(program['doctor_name'], 21))}) Tj ET",
                        f"BT /F1 8.5 Tf {left + 150} {y} Td ({escape_pdf_text(truncate_pdf_text(program['center_name'], 21))}) Tj ET",
                        f"BT /F1 8.5 Tf {left + 295} {y} Td ({escape_pdf_text(weekday_name(program['day_of_week']))}) Tj ET",
                        f"BT /F1 8.5 Tf {left + 370} {y} Td ({escape_pdf_text(program['start_time'])}) Tj ET",
                        f"BT /F1 8.5 Tf {left + 425} {y} Td ({escape_pdf_text(program['end_time'])}) Tj ET",
                        f"BT /F1 8.5 Tf {left + 480} {y} Td ({escape_pdf_text(slot_text)}) Tj ET",
                        f"BT /F1 8.5 Tf {left + 535} {y} Td ({active_text}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No weekly programs found.) Tj ET"
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


    @app.route("/admin/doctor_weekly_programs/report")
    @login_required
    @permission_required("manage_doctor_weekly_programs")
    def doctor_weekly_programs_report():
        selected_doctor_id = request.args.get("doctor_id", type=int)

        programs = execute_query(
            """
            SELECT
                dwp.day_of_week,
                CAST(dwp.start_time AS CHAR) AS start_time,
                CAST(dwp.end_time AS CHAR) AS end_time,
                dwp.slot_duration_minutes,
                dwp.is_active,
                d.full_name AS doctor_name,
                d.specialty,
                mc.center_name
            FROM doctor_weekly_programs dwp
            JOIN doctors d
                ON dwp.doctor_id = d.id
            JOIN medical_centers mc
                ON dwp.center_id = mc.id
            WHERE
                (%s IS NULL OR dwp.doctor_id = %s)
            ORDER BY
                d.full_name,
                FIELD(dwp.day_of_week, 1, 2, 3, 4, 5, 6, 7),
                dwp.start_time
            """,
            (
                selected_doctor_id,
                selected_doctor_id
            ),
            fetchall=True
        )

        filter_text = "All Doctors"

        if selected_doctor_id:
            doctor = execute_query(
                """
                SELECT full_name
                FROM doctors
                WHERE id = %s
                """,
                (selected_doctor_id,),
                fetchone=True
            )
            filter_text = f"Doctor: {doctor['full_name']}" if doctor else "Selected doctor"

        pdf_bytes = build_doctor_weekly_programs_pdf_report(programs, filter_text)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=doctor_weekly_programs_report.pdf"
            }
        )

    @app.route("/admin/doctor_weekly_programs/add_ajax", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_weekly_programs")
    def add_doctor_weekly_program_ajax():
        doctor_id = request.form.get("doctor_id")
        center_id = request.form.get("center_id")
        day_of_week = request.form.get("day_of_week")
        start_time = request.form.get("start_time") or "08:00"
        end_time = request.form.get("end_time") or "17:00"

        if start_time >= end_time:
            return {
                "success": False,
                "message": translate_message("Start time must be before end time.")
            }, 400

        if doctor_weekly_program_conflicts(doctor_id, day_of_week, start_time, end_time):
            return {
                "success": False,
                "message": translate_message("This doctor's weekly program overlaps with another program on the selected day.")
            }, 400

        execute_query(
            """
            INSERT INTO doctor_weekly_programs
            (doctor_id, center_id, day_of_week, start_time,
             end_time, slot_duration_minutes, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """,
            (
                doctor_id,
                center_id,
                day_of_week,
                start_time,
                end_time,
                request.form.get("slot_duration_minutes")
            )
        )

        return {"success": True}

    @app.route("/admin/doctor_weekly_programs/update/<int:program_id>", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_weekly_programs")
    def update_doctor_weekly_program(program_id):
        doctor_id = request.form.get("doctor_id")
        center_id = request.form.get("center_id")
        day_of_week = request.form.get("day_of_week")
        start_time = request.form.get("start_time") or "08:00"
        end_time = request.form.get("end_time") or "17:00"
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if start_time >= end_time:
            flash_t("Start time must be before end time.", "error")
            return redirect(url_for("manage_doctor_weekly_programs"))

        if is_active and doctor_weekly_program_conflicts(doctor_id, day_of_week, start_time, end_time, program_id):
            flash_t("This doctor's weekly program overlaps with another program on the selected day.", "error")
            return redirect(url_for("manage_doctor_weekly_programs"))

        execute_query(
            """
            UPDATE doctor_weekly_programs
            SET doctor_id = %s,
                center_id = %s,
                day_of_week = %s,
                start_time = %s,
                end_time = %s,
                slot_duration_minutes = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                doctor_id,
                center_id,
                day_of_week,
                start_time,
                end_time,
                request.form.get("slot_duration_minutes"),
                is_active,
                program_id
            )
        )

        flash_t("Doctor weekly program updated successfully.", "success")
        return redirect(url_for("manage_doctor_weekly_programs"))

    @app.route("/admin/doctor_weekly_programs/stop/<int:program_id>", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_weekly_programs")
    def stop_doctor_weekly_program(program_id):
        execute_query(
            """
            UPDATE doctor_weekly_programs
            SET is_active = 0
            WHERE id = %s
            """,
            (program_id,)
        )

        flash_t("Doctor weekly program stopped successfully.", "success")
        return redirect(url_for("manage_doctor_weekly_programs"))

    @app.route("/admin/doctor_assigned_centers/<int:doctor_id>")
    @login_required
    @permission_required("manage_doctor_weekly_programs")
    def doctor_assigned_centers(doctor_id):
        centers = execute_query(
            """
            SELECT mc.id, mc.center_name
            FROM doctor_center_assignments dca
            JOIN medical_centers mc ON dca.center_id = mc.id
            WHERE dca.doctor_id = %s
              AND dca.is_active = 1
              AND mc.is_active = 1
            ORDER BY mc.center_name
            """,
            (doctor_id,),
            fetchall=True
        )

        return {"centers": centers}

    @app.route("/admin/doctor_absences", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_doctor_absences")
    def manage_doctor_absences():
        if request.method == "POST":
            absence_values = get_absence_form_values()
            validation_error = absence_values_error(absence_values)

            if validation_error:
                flash_t(validation_error, "error")
                return redirect(url_for("manage_doctor_absences"))

            execute_query(
                """
                INSERT INTO doctor_absences
                (doctor_id, center_id, absence_type, absence_date, end_date,
                 start_time, end_time, reason, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
                """,
                (
                    request.form.get("doctor_id"),
                    request.form.get("center_id") or None,
                    absence_values["absence_type"],
                    absence_values["absence_date"],
                    absence_values["end_date"],
                    absence_values["start_time"],
                    absence_values["end_time"],
                    request.form.get("reason", "").strip()
                )
            )

            flash_t("Doctor absence added successfully.", "success")
            return redirect(url_for("manage_doctor_absences"))

        search = request.args.get("search", "").strip()
        doctors = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE is_active = 1
            ORDER BY full_name
            """,
            fetchall=True
        )

        centers = execute_query(
            """
            SELECT id, center_name
            FROM medical_centers
            WHERE is_active = 1
            ORDER BY center_name
            """,
            fetchall=True
        )

        like_search = f"%{search}%"

        absences = execute_query(
            """
            SELECT
                da.id,
                da.doctor_id,
                da.center_id,
                da.absence_type,
                da.absence_date,
                da.end_date,
                da.start_time,
                da.end_time,
                da.reason,
                da.is_active,
                d.full_name AS doctor_name,
                d.specialty,
                mc.center_name
            FROM doctor_absences da
            JOIN doctors d ON da.doctor_id = d.id
            LEFT JOIN medical_centers mc ON da.center_id = mc.id
            WHERE %s = ''
               OR d.full_name LIKE %s
               OR d.specialty LIKE %s
               OR mc.center_name LIKE %s
               OR da.reason LIKE %s
               OR da.absence_type LIKE %s
            ORDER BY da.absence_date DESC, d.full_name
            """,
            (search, like_search, like_search, like_search, like_search, like_search),
            fetchall=True
        )

        return render_template(
            "doctor_absences.html",
            absences=absences,
            doctors=doctors,
            centers=centers,
            search=search
        )

    def absence_type_label(absence_type):
        if absence_type == "date_range":
            return "Date range"
        if absence_type == "full_day":
            return "Full day"
        return "Hours"

    def build_doctor_absences_pdf_report(absences, search_text=""):
        page_width = 612
        page_height = 792
        left = 24
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(absences), 1), rows_per_page):
            page_absences = absences[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Doctor Absences Report) Tj ET",
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
                f"BT /F1 8 Tf {left + 3} {table_top - 7} Td (Doctor) Tj ET",
                f"BT /F1 8 Tf {left + 116} {table_top - 7} Td (Center) Tj ET",
                f"BT /F1 8 Tf {left + 221} {table_top - 7} Td (Type) Tj ET",
                f"BT /F1 8 Tf {left + 292} {table_top - 7} Td (From) Tj ET",
                f"BT /F1 8 Tf {left + 350} {table_top - 7} Td (To) Tj ET",
                f"BT /F1 8 Tf {left + 408} {table_top - 7} Td (Start) Tj ET",
                f"BT /F1 8 Tf {left + 455} {table_top - 7} Td (End) Tj ET",
                f"BT /F1 8 Tf {left + 500} {table_top - 7} Td (Active) Tj ET",
                f"BT /F1 8 Tf {left + 544} {table_top - 7} Td (Reason) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_absences:
                for absence in page_absences:
                    active_text = "Yes" if absence["is_active"] else "No"
                    start_text = absence["start_time"] if absence["absence_type"] == "hours" else "Full day"
                    end_text = absence["end_time"] if absence["absence_type"] == "hours" else "Full day"
                    commands.extend([
                        f"BT /F1 7.5 Tf {left + 3} {y} Td ({escape_pdf_text(truncate_pdf_text(absence['doctor_name'], 17))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 116} {y} Td ({escape_pdf_text(truncate_pdf_text(absence['center_name'] or 'All centers', 16))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 221} {y} Td ({escape_pdf_text(absence_type_label(absence['absence_type']))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 292} {y} Td ({escape_pdf_text(absence['absence_date'])}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 350} {y} Td ({escape_pdf_text(absence['end_date'] or absence['absence_date'])}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 408} {y} Td ({escape_pdf_text(start_text)}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 455} {y} Td ({escape_pdf_text(end_text)}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 500} {y} Td ({active_text}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 544} {y} Td ({escape_pdf_text(truncate_pdf_text(absence['reason'], 10))}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No doctor absences found.) Tj ET"
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


    @app.route("/admin/doctor_absences/report")
    @login_required
    @permission_required("manage_doctor_absences")
    def doctor_absences_report():
        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        absences = execute_query(
            """
            SELECT
                da.absence_type,
                da.absence_date,
                da.end_date,
                CAST(da.start_time AS CHAR) AS start_time,
                CAST(da.end_time AS CHAR) AS end_time,
                da.reason,
                da.is_active,
                d.full_name AS doctor_name,
                d.specialty,
                mc.center_name
            FROM doctor_absences da
            JOIN doctors d ON da.doctor_id = d.id
            LEFT JOIN medical_centers mc ON da.center_id = mc.id
            WHERE %s = ''
               OR d.full_name LIKE %s
               OR d.specialty LIKE %s
               OR mc.center_name LIKE %s
               OR da.reason LIKE %s
               OR da.absence_type LIKE %s
            ORDER BY da.absence_date DESC, d.full_name
            """,
            (search, like_search, like_search, like_search, like_search, like_search),
            fetchall=True
        )

        pdf_bytes = build_doctor_absences_pdf_report(absences, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=doctor_absences_report.pdf"
            }
        )

    @app.route("/admin/doctor_absences/add_ajax", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_absences")
    def add_doctor_absence_ajax():
        absence_values = get_absence_form_values()
        validation_error = absence_values_error(absence_values)

        if validation_error:
            return {
                "success": False,
                "message": translate_message(validation_error)
            }, 400

        execute_query(
            """
            INSERT INTO doctor_absences
            (doctor_id, center_id, absence_type, absence_date, end_date,
             start_time, end_time, reason, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (
                request.form.get("doctor_id"),
                request.form.get("center_id") or None,
                absence_values["absence_type"],
                absence_values["absence_date"],
                absence_values["end_date"],
                absence_values["start_time"],
                absence_values["end_time"],
                request.form.get("reason", "").strip()
            )
        )

        return {"success": True}

    @app.route("/admin/doctor_absences/update/<int:absence_id>", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_absences")
    def update_doctor_absence(absence_id):
        absence_values = get_absence_form_values()
        validation_error = absence_values_error(absence_values)

        if validation_error:
            flash_t(validation_error, "error")
            return redirect(url_for("manage_doctor_absences"))

        execute_query(
            """
            UPDATE doctor_absences
            SET doctor_id = %s,
                center_id = %s,
                absence_type = %s,
                absence_date = %s,
                end_date = %s,
                start_time = %s,
                end_time = %s,
                reason = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                request.form.get("doctor_id"),
                request.form.get("center_id") or None,
                absence_values["absence_type"],
                absence_values["absence_date"],
                absence_values["end_date"],
                absence_values["start_time"],
                absence_values["end_time"],
                request.form.get("reason", "").strip(),
                1 if request.form.get("is_active") == "1" else 0,
                absence_id
            )
        )

        flash_t("Doctor absence updated successfully.", "success")
        return redirect(url_for("manage_doctor_absences"))

    @app.route("/admin/doctor_absences/stop/<int:absence_id>", methods=["POST"])
    @login_required
    @permission_required("manage_doctor_absences")
    def stop_doctor_absence(absence_id):
        execute_query(
            """
            UPDATE doctor_absences
            SET is_active = 0
            WHERE id = %s
            """,
            (absence_id,)
        )

        flash_t("Doctor absence stopped successfully.", "success")
        return redirect(url_for("manage_doctor_absences"))
