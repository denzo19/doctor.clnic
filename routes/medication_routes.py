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


def register_medication_routes(app, get_logged_doctor_id):
    def flash_t(message, category="success"):
        flash(translate(message, session.get("language", "en")), category)

    def translate_message(message):
        return translate(message, session.get("language", "en"))

    def medication_exists(medication_name, strength, dosage_form, exclude_id=None):
        params = [medication_name, strength or "", dosage_form or ""]
        exclude_clause = ""

        if exclude_id:
            exclude_clause = "AND id <> %s"
            params.append(exclude_id)

        existing_medication = execute_query(
            f"""
            SELECT id
            FROM medications
            WHERE medication_name = %s
              AND COALESCE(strength, '') = %s
              AND COALESCE(dosage_form, '') = %s
              {exclude_clause}
            """,
            tuple(params),
            fetchone=True
        )

        return bool(existing_medication)

    @app.route("/medications", methods=["GET", "POST"])
    @login_required
    @permission_required("medications")
    def medications():
        if request.method == "POST":
            medication_name = request.form.get("medication_name", "").strip()
            strength = request.form.get("strength", "").strip()
            dosage_form = request.form.get("dosage_form", "").strip()
            notes = request.form.get("notes", "").strip()

            if not medication_name:
                flash_t("Medication name is required.", "error")
                return redirect(url_for("medications"))

            if medication_exists(medication_name, strength, dosage_form):
                flash_t("Medication already exists.", "error")
                return redirect(url_for("medications"))

            execute_query(
                """
                INSERT INTO medications
                    (medication_name, strength, dosage_form, notes, is_active)
                VALUES
                    (%s, %s, %s, %s, 1)
                """,
                (
                    medication_name,
                    strength or None,
                    dosage_form or None,
                    notes or None
                )
            )

            flash_t("Medication added successfully.", "success")
            return redirect(url_for("medications"))

        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        medication_rows = execute_query(
            """
            SELECT
                id,
                medication_name,
                strength,
                dosage_form,
                notes,
                is_active
            FROM medications
            WHERE medication_name LIKE %s
               OR strength LIKE %s
               OR dosage_form LIKE %s
               OR notes LIKE %s
            ORDER BY medication_name, strength, dosage_form
            """,
            (like_search, like_search, like_search, like_search),
            fetchall=True
        )

        return render_template(
            "medications.html",
            medications=medication_rows,
            search=search
        )

    def build_medications_pdf_report(medications, search_text=""):
        page_width = 612
        page_height = 792
        left = 34
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(medications), 1), rows_per_page):
            page_medications = medications[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Medications Report) Tj ET",
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
                f"BT /F1 10 Tf {left + 4} {table_top - 7} Td (Medication) Tj ET",
                f"BT /F1 10 Tf {left + 185} {table_top - 7} Td (Strength) Tj ET",
                f"BT /F1 10 Tf {left + 280} {table_top - 7} Td (Dosage Form) Tj ET",
                f"BT /F1 10 Tf {left + 395} {table_top - 7} Td (Notes) Tj ET",
                f"BT /F1 10 Tf {left + 525} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_medications:
                for medication in page_medications:
                    active_text = "Yes" if medication["is_active"] else "No"
                    commands.extend([
                        f"BT /F1 9 Tf {left + 4} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['medication_name'], 27))}) Tj ET",
                        f"BT /F1 9 Tf {left + 185} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['strength'], 13))}) Tj ET",
                        f"BT /F1 9 Tf {left + 280} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['dosage_form'], 16))}) Tj ET",
                        f"BT /F1 9 Tf {left + 395} {y} Td ({escape_pdf_text(truncate_pdf_text(medication['notes'], 18))}) Tj ET",
                        f"BT /F1 9 Tf {left + 525} {y} Td ({active_text}) Tj ET",
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


    @app.route("/medications/report")
    @login_required
    @permission_required("medications")
    def medications_report():
        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        medication_rows = execute_query(
            """
            SELECT
                medication_name,
                strength,
                dosage_form,
                notes,
                is_active
            FROM medications
            WHERE medication_name LIKE %s
               OR strength LIKE %s
               OR dosage_form LIKE %s
               OR notes LIKE %s
            ORDER BY medication_name, strength, dosage_form
            """,
            (like_search, like_search, like_search, like_search),
            fetchall=True
        )

        pdf_bytes = build_medications_pdf_report(medication_rows, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=medications_report.pdf"
            }
        )

    @app.route("/medications/update/<int:medication_id>", methods=["POST"])
    @login_required
    @permission_required("medications")
    def update_medication(medication_id):
        medication_name = request.form.get("medication_name", "").strip()
        strength = request.form.get("strength", "").strip()
        dosage_form = request.form.get("dosage_form", "").strip()
        notes = request.form.get("notes", "").strip()

        if not medication_name:
            flash_t("Medication name is required.", "error")
            return redirect(url_for("medications"))

        if medication_exists(medication_name, strength, dosage_form, medication_id):
            flash_t("Medication already exists.", "error")
            return redirect(url_for("medications"))

        execute_query(
            """
            UPDATE medications
            SET medication_name = %s,
                strength = %s,
                dosage_form = %s,
                notes = %s,
                is_active = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                medication_name,
                strength or None,
                dosage_form or None,
                notes or None,
                1 if request.form.get("is_active") == "1" else 0,
                medication_id
            )
        )

        flash_t("Medication updated successfully.", "success")
        return redirect(url_for("medications"))

    @app.route("/medications/stop/<int:medication_id>", methods=["POST"])
    @login_required
    @permission_required("medications")
    def stop_medication(medication_id):
        execute_query(
            """
            UPDATE medications
            SET is_active = 0,
                updated_at = NOW()
            WHERE id = %s
            """,
            (medication_id,)
        )

        flash_t("Medication stopped successfully.", "success")
        return redirect(url_for("medications"))

    @app.route("/medications/add_ajax", methods=["POST"])
    @login_required
    @permission_required("medications")
    def add_medication_ajax():
        medication_name = request.form.get("medication_name", "").strip()
        strength = request.form.get("strength", "").strip()
        dosage_form = request.form.get("dosage_form", "").strip()
        notes = request.form.get("notes", "").strip()

        if not medication_name:
            return {"success": False, "message": translate_message("Medication name is required.")}

        if medication_exists(medication_name, strength, dosage_form):
            return {"success": False, "message": translate_message("Medication already exists.")}

        execute_query(
            """
            INSERT INTO medications
                (medication_name, strength, dosage_form, notes, is_active)
            VALUES
                (%s, %s, %s, %s, 1)
            """,
            (
                medication_name,
                strength or None,
                dosage_form or None,
                notes or None
            )
        )

        return {"success": True}

    @app.route("/doctor/favorite_medications", methods=["GET"])
    @login_required
    @permission_required("doctor_favorite_medications")
    def doctor_favorite_medications():
        doctor_id = get_logged_doctor_id() or request.args.get("doctor_id", type=int)

        if not doctor_id:
            flash_t("Doctor profile not found for this user.", "error")
            return redirect(url_for("home"))

        doctor = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE id = %s
            """,
            (doctor_id,),
            fetchone=True
        )

        if not doctor:
            flash_t("Doctor profile not found.", "error")
            return redirect(url_for("home"))

        favorite_search = request.args.get("favorite_search", "").strip()
        favorite_like = f"%{favorite_search}%"

        favorite_medications = execute_query(
            """
            SELECT
                dm.id AS favorite_id,
                dm.notes AS favorite_notes,
                dm.is_active AS favorite_is_active,
                m.id AS medication_id,
                m.medication_name,
                m.strength,
                m.dosage_form,
                m.notes AS medication_notes
            FROM doctor_medications dm
            JOIN medications m
                ON dm.medication_id = m.id
            WHERE dm.doctor_id = %s
              AND dm.is_active = 1
              AND (
                    m.medication_name LIKE %s
                 OR m.strength LIKE %s
                 OR m.dosage_form LIKE %s
                 OR dm.notes LIKE %s
              )
            ORDER BY m.medication_name, m.strength, m.dosage_form
            """,
            (doctor_id, favorite_like, favorite_like, favorite_like, favorite_like),
            fetchall=True
        )

        all_medications = execute_query(
            """
            SELECT
                m.id,
                m.medication_name,
                m.strength,
                m.dosage_form,
                m.notes,
                CASE WHEN dm.id IS NULL THEN 0 ELSE 1 END AS is_favorite
            FROM medications m
            LEFT JOIN doctor_medications dm
                ON dm.medication_id = m.id
               AND dm.doctor_id = %s
               AND dm.is_active = 1
            WHERE m.is_active = 1
            ORDER BY m.medication_name, m.strength, m.dosage_form
            """,
            (doctor_id,),
            fetchall=True
        )

        return render_template(
            "doctor_favorite_medications.html",
            doctor=doctor,
            doctor_id=doctor_id,
            favorite_medications=favorite_medications,
            all_medications=all_medications,
            favorite_search=favorite_search
        )

    @app.route("/doctor/favorite_medications/save_selection", methods=["POST"])
    @login_required
    @permission_required("doctor_favorite_medications")
    def save_doctor_favorite_medication_selection():
        doctor_id = get_logged_doctor_id() or request.form.get("doctor_id", type=int)
        selected_medication_ids = [
            int(medication_id)
            for medication_id in request.form.getlist("medication_ids")
            if medication_id.isdigit()
        ]

        if not doctor_id:
            flash_t("Doctor profile not found for this user.", "error")
            return redirect(url_for("home"))

        if selected_medication_ids:
            placeholders = ", ".join(["%s"] * len(selected_medication_ids))

            execute_query(
                f"""
                UPDATE doctor_medications
                SET is_active = 0,
                    updated_at = NOW()
                WHERE doctor_id = %s
                  AND medication_id NOT IN ({placeholders})
                """,
                tuple([doctor_id] + selected_medication_ids)
            )

            for medication_id in selected_medication_ids:
                execute_query(
                    """
                    INSERT INTO doctor_medications
                        (doctor_id, medication_id, is_active)
                    VALUES
                        (%s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                        is_active = 1,
                        updated_at = NOW()
                    """,
                    (doctor_id, medication_id)
                )
        else:
            execute_query(
                """
                UPDATE doctor_medications
                SET is_active = 0,
                    updated_at = NOW()
                WHERE doctor_id = %s
                """,
                (doctor_id,)
            )

        flash_t("Favorite medication selection saved.", "success")
        return redirect(url_for("doctor_favorite_medications", doctor_id=doctor_id))

    @app.route("/doctor/favorite_medications/add", methods=["POST"])
    @login_required
    @permission_required("doctor_favorite_medications")
    def add_doctor_favorite_medication():
        doctor_id = get_logged_doctor_id() or request.form.get("doctor_id", type=int)
        medication_id = request.form.get("medication_id", type=int)
        notes = request.form.get("notes", "").strip()
        catalog_search = request.form.get("catalog_search", "").strip()
        favorite_search = request.form.get("favorite_search", "").strip()

        redirect_args = {"doctor_id": doctor_id}
        if catalog_search:
            redirect_args["catalog_search"] = catalog_search
        if favorite_search:
            redirect_args["favorite_search"] = favorite_search

        if not doctor_id or not medication_id:
            flash_t("Choose a medication to add.", "error")
            return redirect(url_for("doctor_favorite_medications", **redirect_args))

        execute_query(
            """
            INSERT INTO doctor_medications
                (doctor_id, medication_id, notes, is_active)
            VALUES
                (%s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                notes = VALUES(notes),
                is_active = 1,
                updated_at = NOW()
            """,
            (doctor_id, medication_id, notes or None)
        )

        flash_t("Medication added to favorites.", "success")
        return redirect(url_for("doctor_favorite_medications", **redirect_args))

    @app.route("/doctor/favorite_medications/update/<int:favorite_id>", methods=["POST"])
    @login_required
    @permission_required("doctor_favorite_medications")
    def update_doctor_favorite_medication(favorite_id):
        doctor_id = get_logged_doctor_id() or request.form.get("doctor_id", type=int)
        notes = request.form.get("notes", "").strip()

        execute_query(
            """
            UPDATE doctor_medications
            SET notes = %s,
                updated_at = NOW()
            WHERE id = %s
              AND doctor_id = %s
            """,
            (notes or None, favorite_id, doctor_id)
        )

        flash_t("Favorite medication updated.", "success")
        return redirect(url_for("doctor_favorite_medications", doctor_id=doctor_id))

    @app.route("/doctor/favorite_medications/remove/<int:favorite_id>", methods=["POST"])
    @login_required
    @permission_required("doctor_favorite_medications")
    def remove_doctor_favorite_medication(favorite_id):
        doctor_id = get_logged_doctor_id() or request.form.get("doctor_id", type=int)

        execute_query(
            """
            UPDATE doctor_medications
            SET is_active = 0,
                updated_at = NOW()
            WHERE id = %s
              AND doctor_id = %s
            """,
            (favorite_id, doctor_id)
        )

        flash_t("Medication removed from favorites.", "success")
        return redirect(url_for("doctor_favorite_medications", doctor_id=doctor_id))
