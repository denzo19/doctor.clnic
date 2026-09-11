from datetime import date, datetime
import uuid

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


def register_lab_routes(app, get_logged_doctor_id):
    def flash_t(message, category="success"):
        flash(translate(message, session.get("language", "en")), category)

    def get_lab_test_filters():
        search_mode = request.args.get("search_mode", "category").strip()
        if search_mode not in ("category", "text"):
            search_mode = "category"

        selected_category = request.args.get("category", "").strip()
        search = request.args.get("search", "").strip()

        return search_mode, selected_category, search

    def fetch_lab_tests(search_mode, selected_category, search):
        where_clause = "1 = 1"
        query_params = []

        if search_mode == "category" and selected_category:
            where_clause = "category = %s"
            query_params.append(selected_category)
        elif search_mode == "text" and search:
            like_search = f"%{search}%"
            where_clause = """
                test_name LIKE %s
                OR loinc_code LIKE %s
                OR unit LIKE %s
                OR category LIKE %s
            """
            query_params.extend([
                like_search,
                like_search,
                like_search,
                like_search
            ])

        return execute_query(
            """
            SELECT
                id,
                test_name,
                loinc_code,
                unit,
                CAST(normal_low AS CHAR) AS normal_low,
                CAST(normal_high AS CHAR) AS normal_high,
                category,
                `group`,
                CASE
                    WHEN normal_low IS NOT NULL AND normal_high IS NOT NULL
                        THEN CONCAT(normal_low, ' - ', normal_high)
                    WHEN normal_low IS NOT NULL
                        THEN CONCAT('>= ', normal_low)
                    WHEN normal_high IS NOT NULL
                        THEN CONCAT('<= ', normal_high)
                    ELSE ''
                END AS normal_range
            FROM lab_tests
            WHERE """ + where_clause + """
            ORDER BY category, test_name
            """,
            tuple(query_params),
            fetchall=True
        )

    def build_lab_tests_pdf_report(tests, search_mode, selected_category, search):
        page_width = 612
        page_height = 792
        left = 34
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        filter_text = ""
        if search_mode == "category" and selected_category:
            filter_text = f"Category: {selected_category}"
        elif search_mode == "text" and search:
            filter_text = f"Search: {search}"

        for start in range(0, max(len(tests), 1), rows_per_page):
            page_tests = tests[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Lab Tests Report) Tj ET",
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
                f"BT /F1 9 Tf {left + 4} {table_top - 7} Td (Test Name) Tj ET",
                f"BT /F1 9 Tf {left + 175} {table_top - 7} Td (LOINC) Tj ET",
                f"BT /F1 9 Tf {left + 255} {table_top - 7} Td (Unit) Tj ET",
                f"BT /F1 9 Tf {left + 315} {table_top - 7} Td (Range) Tj ET",
                f"BT /F1 9 Tf {left + 405} {table_top - 7} Td (Category) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_tests:
                for test in page_tests:
                    commands.extend([
                        f"BT /F1 8 Tf {left + 4} {y} Td ({escape_pdf_text(truncate_pdf_text(test['test_name'], 27))}) Tj ET",
                        f"BT /F1 8 Tf {left + 175} {y} Td ({escape_pdf_text(truncate_pdf_text(test['loinc_code'], 12))}) Tj ET",
                        f"BT /F1 8 Tf {left + 255} {y} Td ({escape_pdf_text(truncate_pdf_text(test['unit'], 8))}) Tj ET",
                        f"BT /F1 8 Tf {left + 315} {y} Td ({escape_pdf_text(truncate_pdf_text(test['normal_range'], 13))}) Tj ET",
                        f"BT /F1 8 Tf {left + 405} {y} Td ({escape_pdf_text(truncate_pdf_text(test['category'], 22))}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No lab tests found.) Tj ET"
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

    @app.route("/laboratory")
    @login_required
    @permission_required("laboratory")
    def laboratory():
        return render_template("laboratory.html")

    @app.route("/vital_signs", methods=["GET", "POST"])
    @login_required
    @permission_required("vital_signs")
    def vital_signs():
        selected_patient_id = request.args.get("patient_id", type=int)

        patients = execute_query(
            """
            SELECT id, patient_code, first_name, middle_name, last_name, phone_number
            FROM patients
            WHERE is_active = TRUE
            ORDER BY last_name, first_name, patient_code
            """,
            fetchall=True
        )

        vital_records = []

        if selected_patient_id:
            vital_records = execute_query(
                """
                SELECT
                    id,
                    blood_pressure,
                    heart_rate,
                    respiratory_rate,
                    CAST(body_temperature AS CHAR) AS body_temperature,
                    CAST(oxygen_saturation AS CHAR) AS oxygen_saturation,
                    CAST(weight AS CHAR) AS weight,
                    CAST(height AS CHAR) AS height,
                    DATE_FORMAT(mdate, '%Y-%m-%d') AS mdate,
                    vital_status
                FROM vital_signs
                WHERE patient_id = %s
                ORDER BY mdate DESC, id DESC
                """,
                (selected_patient_id,),
                fetchall=True
            )

        if request.method == "POST":
            patient_id = request.form.get("patient_id", type=int)
            mdate = request.form.get("mdate") or date.today().isoformat()
            blood_pressure = request.form.get("blood_pressure", "").strip()
            heart_rate = request.form.get("heart_rate") or None
            respiratory_rate = request.form.get("respiratory_rate") or None
            body_temperature = request.form.get("body_temperature") or None
            oxygen_saturation = request.form.get("oxygen_saturation") or None
            weight = request.form.get("weight") or None
            height = request.form.get("height") or None
            save_type = request.form.get("save_type")
            vital_status = "final" if save_type == "final" else "draft"

            if not patient_id or not mdate:
                flash_t("Choose patient and date before saving vital signs.", "error")
                return redirect(url_for("vital_signs", patient_id=patient_id))

            if not any([
                blood_pressure,
                heart_rate,
                respiratory_rate,
                body_temperature,
                oxygen_saturation,
                weight,
                height
            ]):
                flash_t("Enter at least one vital sign value.", "error")
                return redirect(url_for("vital_signs", patient_id=patient_id))

            execute_query(
                """
                INSERT INTO vital_signs
                (
                    patient_id,
                    blood_pressure,
                    heart_rate,
                    respiratory_rate,
                    body_temperature,
                    oxygen_saturation,
                    weight,
                    height,
                    mdate,
                    vital_status,
                    finalized_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s = 'final' THEN NOW() ELSE NULL END)
                """,
                (
                    patient_id,
                    blood_pressure or None,
                    heart_rate,
                    respiratory_rate,
                    body_temperature,
                    oxygen_saturation,
                    weight,
                    height,
                    mdate,
                    vital_status,
                    vital_status
                )
            )

            flash_t("Vital signs saved successfully.", "success")
            return redirect(url_for("vital_signs", patient_id=patient_id))

        return render_template(
            "vital_signs.html",
            patients=patients,
            selected_patient_id=selected_patient_id,
            vital_records=vital_records,
            default_date=date.today().isoformat()
        )

    @app.route("/vital_signs/update/<int:vital_id>", methods=["POST"])
    @login_required
    @permission_required("vital_signs")
    def update_vital_signs(vital_id):
        vital_record = execute_query(
            """
            SELECT id, patient_id, vital_status
            FROM vital_signs
            WHERE id = %s
            """,
            (vital_id,),
            fetchone=True
        )

        if not vital_record:
            flash_t("Vital signs record not found.", "error")
            return redirect(url_for("vital_signs"))

        if vital_record["vital_status"] != "draft":
            flash_t("Only draft vital signs can be edited.", "error")
            return redirect(url_for("vital_signs", patient_id=vital_record["patient_id"]))

        patient_id = request.form.get("patient_id", type=int) or vital_record["patient_id"]
        mdate = request.form.get("mdate") or date.today().isoformat()
        blood_pressure = request.form.get("blood_pressure", "").strip()
        heart_rate = request.form.get("heart_rate") or None
        respiratory_rate = request.form.get("respiratory_rate") or None
        body_temperature = request.form.get("body_temperature") or None
        oxygen_saturation = request.form.get("oxygen_saturation") or None
        weight = request.form.get("weight") or None
        height = request.form.get("height") or None
        save_type = request.form.get("save_type")
        vital_status = "final" if save_type == "final" else "draft"

        if not patient_id or not mdate:
            flash_t("Choose patient and date before saving vital signs.", "error")
            return redirect(url_for("vital_signs", patient_id=vital_record["patient_id"]))

        if not any([
            blood_pressure,
            heart_rate,
            respiratory_rate,
            body_temperature,
            oxygen_saturation,
            weight,
            height
        ]):
            flash_t("Enter at least one vital sign value.", "error")
            return redirect(url_for("vital_signs", patient_id=patient_id))

        execute_query(
            """
            UPDATE vital_signs
            SET patient_id = %s,
                blood_pressure = %s,
                heart_rate = %s,
                respiratory_rate = %s,
                body_temperature = %s,
                oxygen_saturation = %s,
                weight = %s,
                height = %s,
                mdate = %s,
                vital_status = %s,
                finalized_at = CASE WHEN %s = 'final' THEN NOW() ELSE finalized_at END
            WHERE id = %s
            """,
            (
                patient_id,
                blood_pressure or None,
                heart_rate,
                respiratory_rate,
                body_temperature,
                oxygen_saturation,
                weight,
                height,
                mdate,
                vital_status,
                vital_status,
                vital_id
            )
        )

        flash_t("Vital signs updated successfully.", "success")
        return redirect(url_for("vital_signs", patient_id=patient_id))

    @app.route("/lab/tests")
    @login_required
    @permission_required("lab_tests")
    def lab_tests_page():
        search_mode, selected_category, search = get_lab_test_filters()

        categories = execute_query(
            """
            SELECT DISTINCT category
            FROM lab_tests
            WHERE category IS NOT NULL
              AND TRIM(category) <> ''
            ORDER BY category
            """,
            fetchall=True
        )

        tests = fetch_lab_tests(search_mode, selected_category, search)

        return render_template(
            "lab_tests.html",
            tests=tests,
            categories=categories,
            search_mode=search_mode,
            selected_category=selected_category,
            search=search
        )

    @app.route("/lab/tests/report")
    @login_required
    @permission_required("lab_tests")
    def lab_tests_report():
        search_mode, selected_category, search = get_lab_test_filters()
        tests = fetch_lab_tests(search_mode, selected_category, search)
        pdf_bytes = build_lab_tests_pdf_report(tests, search_mode, selected_category, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=lab_tests_report.pdf"
            }
        )

    @app.route("/lab/tests/add", methods=["POST"])
    @login_required
    @permission_required("lab_tests")
    def add_lab_test():
        loinc_code = request.form.get("loinc_code", "").strip()

        if loinc_code:
            existing_test = execute_query(
                """
                SELECT id
                FROM lab_tests
                WHERE loinc_code = %s
                """,
                (loinc_code,),
                fetchone=True
            )

            if existing_test:
                flash_t("LOINC code already exists.", "error")
                return redirect(url_for("lab_tests_page"))

        execute_query(
            """
            INSERT INTO lab_tests
                (test_name, loinc_code, unit, normal_low, normal_high, category, `group`)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.form.get("test_name", "").strip(),
                loinc_code or None,
                request.form.get("unit", "").strip() or None,
                request.form.get("normal_low") or None,
                request.form.get("normal_high") or None,
                request.form.get("category", "").strip() or None,
                request.form.get("group", "").strip() or None
            )
        )

        flash_t("Lab test added successfully.", "success")
        return redirect(url_for("lab_tests_page"))

    @app.route("/lab/tests/add_ajax", methods=["POST"])
    @login_required
    @permission_required("lab_tests")
    def add_lab_test_ajax():
        loinc_code = request.form.get("loinc_code", "").strip()

        if loinc_code:
            existing_test = execute_query(
                """
                SELECT id
                FROM lab_tests
                WHERE loinc_code = %s
                """,
                (loinc_code,),
                fetchone=True
            )

            if existing_test:
                return {
                    "success": False,
                    "message": translate("LOINC code already exists.", session.get("language", "en"))
                }

        execute_query(
            """
            INSERT INTO lab_tests
                (test_name, loinc_code, unit, normal_low, normal_high, category, `group`)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.form.get("test_name", "").strip(),
                loinc_code or None,
                request.form.get("unit", "").strip() or None,
                request.form.get("normal_low") or None,
                request.form.get("normal_high") or None,
                request.form.get("category", "").strip() or None,
                request.form.get("group", "").strip() or None
            )
        )

        return {"success": True}

    @app.route("/lab/tests/update/<int:test_id>", methods=["POST"])
    @login_required
    @permission_required("lab_tests")
    def update_lab_test(test_id):
        loinc_code = request.form.get("loinc_code", "").strip()

        if loinc_code:
            existing_test = execute_query(
                """
                SELECT id
                FROM lab_tests
                WHERE loinc_code = %s
                  AND id <> %s
                """,
                (loinc_code, test_id),
                fetchone=True
            )

            if existing_test:
                flash_t("LOINC code already exists.", "error")
                return redirect(url_for("lab_tests_page"))

        execute_query(
            """
            UPDATE lab_tests
            SET test_name = %s,
                loinc_code = %s,
                unit = %s,
                normal_low = %s,
                normal_high = %s,
                category = %s,
                `group` = %s
            WHERE id = %s
            """,
            (
                request.form.get("test_name", "").strip(),
                loinc_code or None,
                request.form.get("unit", "").strip() or None,
                request.form.get("normal_low") or None,
                request.form.get("normal_high") or None,
                request.form.get("category", "").strip() or None,
                request.form.get("group", "").strip() or None,
                test_id
            )
        )

        flash_t("Lab test updated successfully.", "success")
        return redirect(url_for("lab_tests_page"))

    @app.route("/lab/tests/delete/<int:test_id>", methods=["POST"])
    @login_required
    @permission_required("lab_tests")
    def delete_lab_test(test_id):
        used_test = execute_query(
            """
            SELECT id
            FROM patient_lab_results
            WHERE test_id = %s
            LIMIT 1
            """,
            (test_id,),
            fetchone=True
        )

        if used_test:
            flash_t("This lab test is used by patient lab results and cannot be deleted.", "error")
            return redirect(url_for("lab_tests_page"))

        execute_query(
            """
            DELETE FROM lab_tests
            WHERE id = %s
            """,
            (test_id,)
        )

        flash_t("Lab test deleted successfully.", "success")
        return redirect(url_for("lab_tests_page"))

    @app.route("/secretary/lab_order", methods=["GET"])
    @login_required
    @permission_required("lab_order")
    def lab_order():
        logged_doctor_id = get_logged_doctor_id()

        doctors = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE is_active = TRUE
            ORDER BY full_name
            """,
            fetchall=True
        )

        patients = execute_query(
            """
            SELECT id, patient_code, first_name, middle_name, last_name
            FROM patients
            WHERE is_active = TRUE
            ORDER BY first_name, last_name, patient_code
            """,
            fetchall=True
        )

        selected_doctor_id = request.args.get("doctor_id", type=int) or logged_doctor_id
        selected_patient_id = request.args.get("patient_id", type=int)
        selected_status = request.args.get("status", "").strip()

        order_filters = []
        order_params = []

        if selected_doctor_id:
            order_filters.append("plr.doctor_id = %s")
            order_params.append(selected_doctor_id)

        if selected_patient_id:
            order_filters.append("plr.patient_id = %s")
            order_params.append(selected_patient_id)

        if selected_status:
            order_filters.append("plr.order_status = %s")
            order_params.append(selected_status)

        order_where = ""
        if order_filters:
            order_where = "WHERE " + " AND ".join(order_filters)

        orders = execute_query(
            """
            SELECT
                COALESCE(plr.lab_order_code, CAST(plr.id AS CHAR)) AS order_key,
                MIN(plr.id) AS first_order_id,
                plr.patient_id,
                plr.doctor_id,
                p.patient_code,
                CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                d.full_name AS doctor_name,
                d.specialty AS doctor_specialty,
                DATE_FORMAT(MIN(plr.result_date), '%Y-%m-%d') AS result_date,
                MAX(plr.notes) AS notes,
                GROUP_CONCAT(lt.test_name ORDER BY lt.test_name SEPARATOR ', ') AS tests,
                GROUP_CONCAT(lt.id ORDER BY lt.id SEPARATOR ',') AS test_ids,
                COUNT(*) AS test_count,
                CASE
                    WHEN SUM(plr.order_status = 'cancelled') = COUNT(*) THEN 'cancelled'
                    WHEN SUM(plr.order_status IN ('completed', 'cancelled')) = COUNT(*)
                         AND SUM(plr.order_status = 'completed') > 0 THEN 'completed'
                    WHEN SUM(plr.order_status = 'ordered') > 0 THEN 'ordered'
                    ELSE 'draft'
                END AS order_status
            FROM patient_lab_results plr
            JOIN patients p ON plr.patient_id = p.id
            JOIN lab_tests lt ON plr.test_id = lt.id
            LEFT JOIN doctors d ON plr.doctor_id = d.id
            """ + order_where + """
            GROUP BY
                COALESCE(plr.lab_order_code, CAST(plr.id AS CHAR)),
                plr.patient_id,
                plr.doctor_id,
                p.patient_code,
                p.first_name,
                p.middle_name,
                p.last_name,
                d.full_name,
                d.specialty
            ORDER BY MIN(plr.result_date) DESC, MIN(plr.id) DESC
            """,
            tuple(order_params),
            fetchall=True
        )

        return render_template(
            "lab_order.html",
            doctors=doctors,
            patients=patients,
            orders=orders,
            selected_doctor_id=selected_doctor_id,
            selected_patient_id=selected_patient_id,
            selected_status=selected_status
        )

    @app.route("/secretary/lab_order/view/<order_key>", methods=["GET"])
    @login_required
    @permission_required("lab_order")
    def view_lab_order_group(order_key):
        fallback_order_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT
                plr.id,
                plr.result_value,
                DATE_FORMAT(plr.result_date, '%Y-%m-%d') AS result_date,
                plr.notes,
                plr.order_status,
                p.patient_code,
                CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                d.full_name AS doctor_name,
                d.specialty AS doctor_specialty,
                lt.test_name,
                lt.category,
                lt.unit
            FROM patient_lab_results plr
            JOIN patients p ON plr.patient_id = p.id
            JOIN lab_tests lt ON plr.test_id = lt.id
            LEFT JOIN doctors d ON plr.doctor_id = d.id
            WHERE plr.lab_order_code = %s
               OR (plr.lab_order_code IS NULL AND plr.id = %s)
            ORDER BY lt.category, lt.test_name, plr.id
            """,
            (order_key, fallback_order_id),
            fetchall=True
        )

        if not rows:
            return {
                "success": False,
                "message": translate("Lab order not found.", session.get("language", "en"))
            }, 404

        first_row = rows[0]
        first_order_id = min(row["id"] for row in rows)

        return {
            "success": True,
            "order": {
                "order_id": first_order_id,
                "result_date": first_row["result_date"] or "",
                "patient": f"{first_row['patient_code']} - {first_row['patient_name']}",
                "doctor": (
                    (first_row["doctor_name"] or "") +
                    (f" - {first_row['doctor_specialty']}" if first_row["doctor_specialty"] else "")
                ),
                "status": first_row["order_status"] or ""
            },
            "tests": [
                {
                    "test_name": row["test_name"] or "",
                    "category": row["category"] or "",
                    "unit": row["unit"] or "",
                    "result_value": row["result_value"] or "",
                    "status": row["order_status"] or "",
                    "notes": row["notes"] or ""
                }
                for row in rows
            ]
        }

    def get_lab_order_status(rows):
        statuses = [row["order_status"] for row in rows]

        if all(status == "cancelled" for status in statuses):
            return "cancelled"
        if (
            all(status in ("completed", "cancelled") for status in statuses)
            and any(status == "completed" for status in statuses)
        ):
            return "completed"
        if any(status == "ordered" for status in statuses):
            return "ordered"
        return "draft"

    def build_lab_order_pdf(order, tests, include_results=True):
        page_width = 612
        page_height = 792
        left = 42
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 21
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(tests), 1), rows_per_page):
            page_tests = tests[start:start + rows_per_page]
            report_title = "Lab Order Results" if include_results else "Laboratory Order"
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 20 Tf {left} {top} Td ({report_title}) Tj ET",
                "0 g",
                "0.12 0.31 0.47 RG",
                f"{left} {top - 32} m {page_width - left} {top - 32} l S",
                "0 g",
                f"BT /F1 10 Tf {left} {top - 54} Td (Order: {escape_pdf_text(order['order_id'])}) Tj ET",
                f"BT /F1 10 Tf {left + 180} {top - 54} Td (Date: {escape_pdf_text(order['result_date'])}) Tj ET",
                f"BT /F1 10 Tf {left} {top - 74} Td (Patient: {escape_pdf_text(truncate_pdf_text(order['patient'], 58))}) Tj ET",
                f"BT /F1 10 Tf {left} {top - 94} Td (Ordered by: {escape_pdf_text(truncate_pdf_text(order['doctor'], 58))}) Tj ET",
            ]

            table_top = top - 124
            commands.extend([
                "0.12 0.31 0.47 RG",
                f"{left} {table_top + 8} m {page_width - left} {table_top + 8} l S",
                f"BT /F1 9 Tf {left + 4} {table_top - 7} Td (Test) Tj ET",
                f"BT /F1 9 Tf {left + 180} {table_top - 7} Td (Category) Tj ET",
            ])

            if include_results:
                commands.extend([
                    f"BT /F1 9 Tf {left + 300} {table_top - 7} Td (Unit) Tj ET",
                    f"BT /F1 9 Tf {left + 365} {table_top - 7} Td (Result) Tj ET",
                    f"BT /F1 9 Tf {left + 455} {table_top - 7} Td (Notes) Tj ET",
                ])
            else:
                commands.append(
                    f"BT /F1 9 Tf {left + 330} {table_top - 7} Td (Notes) Tj ET"
                )

            commands.extend([
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_tests:
                for test in page_tests:
                    commands.extend([
                        f"BT /F1 8.5 Tf {left + 4} {y} Td ({escape_pdf_text(truncate_pdf_text(test['test_name'], 26))}) Tj ET",
                        f"BT /F1 8.5 Tf {left + 180} {y} Td ({escape_pdf_text(truncate_pdf_text(test['category'], 17))}) Tj ET",
                    ])

                    if include_results:
                        commands.extend([
                            f"BT /F1 8.5 Tf {left + 300} {y} Td ({escape_pdf_text(truncate_pdf_text(test['unit'], 9))}) Tj ET",
                            f"BT /F1 8.5 Tf {left + 365} {y} Td ({escape_pdf_text(truncate_pdf_text(test['result_value'], 13))}) Tj ET",
                            f"BT /F1 8.5 Tf {left + 455} {y} Td ({escape_pdf_text(truncate_pdf_text(test['notes'], 16))}) Tj ET",
                        ])
                    else:
                        commands.append(
                            f"BT /F1 8.5 Tf {left + 330} {y} Td ({escape_pdf_text(truncate_pdf_text(test['notes'], 34))}) Tj ET"
                        )

                    commands.extend([
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No tests found.) Tj ET"
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


    @app.route("/secretary/lab_order/print/<order_key>", methods=["GET"])
    @login_required
    @permission_required("lab_order")
    def print_lab_order_group(order_key):
        fallback_order_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT
                plr.id,
                plr.result_value,
                DATE_FORMAT(plr.result_date, '%Y-%m-%d') AS result_date,
                plr.notes,
                plr.order_status,
                p.patient_code,
                CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                d.full_name AS doctor_name,
                d.specialty AS doctor_specialty,
                lt.test_name,
                lt.category,
                lt.unit
            FROM patient_lab_results plr
            JOIN patients p ON plr.patient_id = p.id
            JOIN lab_tests lt ON plr.test_id = lt.id
            LEFT JOIN doctors d ON plr.doctor_id = d.id
            WHERE plr.lab_order_code = %s
               OR (plr.lab_order_code IS NULL AND plr.id = %s)
            ORDER BY lt.category, lt.test_name, plr.id
            """,
            (order_key, fallback_order_id),
            fetchall=True
        )

        if not rows:
            flash_t("Lab order not found.", "error")
            return redirect(url_for("lab_order"))

        order_status = get_lab_order_status(rows)
        print_mode = request.args.get("print_mode", "").strip()

        if not print_mode:
            print_mode = "with_results" if order_status == "completed" else "without_results"

        if print_mode not in ("with_results", "without_results"):
            flash_t("Invalid print option.", "error")
            return redirect(url_for("lab_order"))

        if print_mode == "with_results" and order_status != "completed":
            flash_t("Only completed lab orders can be printed with results.", "error")
            return redirect(url_for("lab_order"))

        if print_mode == "without_results" and order_status != "ordered":
            flash_t("Only ordered lab orders can be printed without results.", "error")
            return redirect(url_for("lab_order"))

        include_results = print_mode == "with_results"
        first_row = rows[0]
        order = {
            "order_id": min(row["id"] for row in rows),
            "result_date": first_row["result_date"] or "",
            "patient": f"{first_row['patient_code']} - {first_row['patient_name']}",
            "doctor": (
                (first_row["doctor_name"] or "") +
                (f" - {first_row['doctor_specialty']}" if first_row["doctor_specialty"] else "")
            ),
            "status": order_status
        }
        tests = [
            {
                "test_name": row["test_name"] or "",
                "category": row["category"] or "",
                "unit": row["unit"] or "",
                "result_value": row["result_value"] or "",
                "status": row["order_status"] or "",
                "notes": row["notes"] or ""
            }
            for row in rows
        ]

        pdf_bytes = build_lab_order_pdf(order, tests, include_results)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=lab_order_{order['order_id']}_{print_mode}.pdf"
            }
        )

    @app.route("/secretary/lab_order/new", methods=["GET", "POST"])
    @login_required
    @permission_required("lab_order")
    def new_lab_order():
        logged_doctor_id = get_logged_doctor_id()
        selected_doctor_id = logged_doctor_id or request.args.get("doctor_id", type=int)
        selected_patient_id = request.args.get("patient_id", type=int)
        return_to_patient = request.args.get("return_to_patient") == "1"

        doctors = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE is_active = TRUE
            ORDER BY full_name
            """,
            fetchall=True
        )

        patients = execute_query(
            """
            SELECT id, patient_code, first_name, middle_name, last_name
            FROM patients
            WHERE is_active = TRUE
            ORDER BY first_name, last_name, patient_code
            """,
            fetchall=True
        )

        lab_tests = execute_query(
            """
            SELECT id, test_name, loinc_code, unit, category
            FROM lab_tests
            ORDER BY category, test_name
            """,
            fetchall=True
        )

        if request.method == "POST":
            patient_id = request.form.get("patient_id", type=int)
            doctor_id = request.form.get("doctor_id", type=int) or selected_doctor_id
            test_ids = request.form.getlist("test_ids")
            result_date = request.form.get("result_date")
            notes = request.form.get("notes")
            save_type = request.form.get("save_type")
            return_to_patient = request.form.get("return_to_patient") == "1"
            order_status = "ordered" if save_type in ("final", "final_print") else "draft"

            if not patient_id or not doctor_id or not result_date or not test_ids:
                flash_t("Choose patient, doctor, order date, and at least one lab test.", "error")
                return redirect(url_for(
                    "new_lab_order",
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    return_to_patient=1 if return_to_patient else None
                ))

            lab_order_code = uuid.uuid4().hex

            for test_id in test_ids:
                execute_query(
                    """
                    INSERT INTO patient_lab_results
                    (patient_id, test_id, result_value, result_date, notes,
                     order_status, finalized_at, doctor_id, lab_order_code)
                    VALUES (%s, %s, NULL, %s, %s, %s,
                            CASE WHEN %s = 'ordered' THEN NOW() ELSE NULL END,
                            %s, %s)
                    """,
                    (
                        patient_id,
                        test_id,
                        result_date,
                        notes,
                        order_status,
                        order_status,
                        doctor_id,
                        lab_order_code
                    )
                )

            flash_t("Lab order saved successfully.", "success")
            if save_type == "final_print":
                return redirect(url_for(
                    "print_lab_order_group",
                    order_key=lab_order_code,
                    print_mode="without_results"
                ))

            if return_to_patient:
                return redirect(url_for("patient_details", patient_id=patient_id, doctor_id=doctor_id))

            return redirect(url_for("lab_order"))

        order = {
            "patient_id": selected_patient_id,
            "result_date": date.today().isoformat(),
            "notes": "",
            "test_ids": []
        } if selected_patient_id else None

        return render_template(
            "lab_order_form.html",
            doctors=doctors,
            patients=patients,
            lab_tests=lab_tests,
            order=order,
            selected_doctor_id=selected_doctor_id,
            default_order_date=date.today().isoformat(),
            form_action=url_for(
                "new_lab_order",
                patient_id=selected_patient_id,
                doctor_id=selected_doctor_id,
                return_to_patient=1 if return_to_patient else None
            ),
            return_to_patient=return_to_patient,
            show_final_print_button=True
        )

    @app.route("/secretary/lab_order/update/<order_key>", methods=["GET", "POST"])
    @login_required
    @permission_required("lab_order")
    def update_lab_order_group(order_key):
        logged_doctor_id = get_logged_doctor_id()
        fallback_order_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT *, DATE_FORMAT(result_date, '%Y-%m-%d') AS result_date_value
            FROM patient_lab_results
            WHERE lab_order_code = %s
               OR (lab_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_order_id),
            fetchall=True
        )

        if not rows:
            flash_t("Lab order not found.", "error")
            return redirect(url_for("lab_order"))

        if any(row["order_status"] != "draft" for row in rows):
            flash_t("Only draft lab orders can be edited.", "error")
            return redirect(url_for("lab_order"))

        doctors = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE is_active = TRUE
            ORDER BY full_name
            """,
            fetchall=True
        )

        patients = execute_query(
            """
            SELECT id, patient_code, first_name, middle_name, last_name
            FROM patients
            WHERE is_active = TRUE
            ORDER BY first_name, last_name, patient_code
            """,
            fetchall=True
        )

        lab_tests = execute_query(
            """
            SELECT id, test_name, loinc_code, unit, category
            FROM lab_tests
            ORDER BY category, test_name
            """,
            fetchall=True
        )

        if request.method == "GET":
            selected_doctor_id = rows[0]["doctor_id"] or logged_doctor_id
            order = {
                "patient_id": rows[0]["patient_id"],
                "doctor_id": selected_doctor_id,
                "result_date": rows[0]["result_date_value"],
                "notes": rows[0]["notes"],
                "test_ids": [str(row["test_id"]) for row in rows]
            }

            return render_template(
                "lab_order_form.html",
                doctors=doctors,
                patients=patients,
                lab_tests=lab_tests,
                order=order,
                selected_doctor_id=selected_doctor_id,
                default_order_date=date.today().isoformat(),
                form_action=url_for("update_lab_order_group", order_key=order_key)
            )

        patient_id = request.form.get("patient_id", type=int)
        doctor_id = request.form.get("doctor_id", type=int) or logged_doctor_id
        test_ids = request.form.getlist("test_ids")
        result_date = request.form.get("result_date")
        notes = request.form.get("notes")
        save_type = request.form.get("save_type")
        order_status = "ordered" if save_type == "final" else "draft"

        if not patient_id or not doctor_id or not result_date or not test_ids:
            flash_t("Choose patient, doctor, order date, and at least one lab test.", "error")
            return redirect(url_for("update_lab_order_group", order_key=order_key))

        lab_order_code = rows[0].get("lab_order_code") or uuid.uuid4().hex

        execute_query(
            """
            DELETE FROM patient_lab_results
            WHERE lab_order_code = %s
               OR (lab_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_order_id)
        )

        for test_id in test_ids:
            execute_query(
                """
                INSERT INTO patient_lab_results
                (patient_id, test_id, result_value, result_date, notes,
                 order_status, finalized_at, doctor_id, lab_order_code, updated_at)
                VALUES (%s, %s, NULL, %s, %s, %s,
                        CASE WHEN %s = 'ordered' THEN NOW() ELSE NULL END,
                        %s, %s, NOW())
                """,
                (
                    patient_id,
                    test_id,
                    result_date,
                    notes,
                    order_status,
                    order_status,
                    doctor_id,
                    lab_order_code
                )
            )

        flash_t("Lab order updated successfully.", "success")
        return redirect(url_for("lab_order"))

    @app.route("/secretary/lab_order/delete/<order_key>", methods=["POST"])
    @login_required
    @permission_required("lab_order")
    def delete_lab_order_group(order_key):
        fallback_order_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT *
            FROM patient_lab_results
            WHERE lab_order_code = %s
               OR (lab_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_order_id),
            fetchall=True
        )

        if not rows:
            flash_t("Lab order not found.", "error")
            return redirect(url_for("lab_order"))

        if any(row["order_status"] != "draft" for row in rows):
            flash_t("Only draft lab orders can be deleted.", "error")
            return redirect(url_for("lab_order"))

        execute_query(
            """
            DELETE FROM patient_lab_results
            WHERE lab_order_code = %s
               OR (lab_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_order_id)
        )

        flash_t("Draft lab order deleted successfully.", "success")
        return redirect(url_for("lab_order"))

    @app.route("/secretary/lab_order/cancel/<order_key>", methods=["POST"])
    @login_required
    @permission_required("lab_order")
    def cancel_lab_order_group(order_key):
        fallback_order_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT *
            FROM patient_lab_results
            WHERE lab_order_code = %s
               OR (lab_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_order_id),
            fetchall=True
        )

        if not rows:
            flash_t("Lab order not found.", "error")
            return redirect(url_for("lab_order"))

        if any(row["order_status"] != "ordered" for row in rows):
            flash_t("Only ordered lab orders can be cancelled.", "error")
            return redirect(url_for("lab_order"))

        execute_query(
            """
            UPDATE patient_lab_results
            SET order_status = 'cancelled',
                cancelled_at = NOW(),
                updated_at = NOW()
            WHERE lab_order_code = %s
               OR (lab_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_order_id)
        )

        flash_t("Lab order cancelled successfully.", "success")
        return redirect(url_for("lab_order"))

    @app.route("/secretary/lab_result", methods=["GET"])
    @login_required
    @permission_required("lab_result")
    def lab_result():
        logged_doctor_id = get_logged_doctor_id()

        doctors = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE is_active = TRUE
            ORDER BY full_name
            """,
            fetchall=True
        )

        selected_doctor_id = request.args.get("doctor_id", type=int) or logged_doctor_id
        selected_order_key = request.args.get("order_key", "").strip()

        order_filters = []
        order_params = []

        if selected_doctor_id:
            order_filters.append("plr.doctor_id = %s")
            order_params.append(selected_doctor_id)

        order_where = ""
        if order_filters:
            order_where = "WHERE " + " AND ".join(order_filters)

        orders = execute_query(
            """
            SELECT
                COALESCE(plr.lab_order_code, CAST(plr.id AS CHAR)) AS order_key,
                MIN(plr.id) AS first_order_id,
                COUNT(*) AS test_count,
                GROUP_CONCAT(lt.test_name ORDER BY lt.test_name SEPARATOR ', ') AS tests,
                DATE_FORMAT(MIN(plr.result_date), '%Y-%m-%d') AS result_date,
                p.patient_code,
                CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                d.full_name AS doctor_name,
                d.specialty AS doctor_specialty,
                CASE
                    WHEN SUM(plr.order_status = 'cancelled') = COUNT(*) THEN 'cancelled'
                    WHEN SUM(plr.order_status IN ('completed', 'cancelled')) = COUNT(*)
                         AND SUM(plr.order_status = 'completed') > 0 THEN 'completed'
                    WHEN SUM(plr.order_status = 'ordered') > 0 THEN 'ordered'
                    ELSE 'draft'
                END AS order_status
            FROM patient_lab_results plr
            JOIN lab_tests lt ON plr.test_id = lt.id
            JOIN patients p ON plr.patient_id = p.id
            LEFT JOIN doctors d ON plr.doctor_id = d.id
            """ + order_where + """
            GROUP BY
                COALESCE(plr.lab_order_code, CAST(plr.id AS CHAR)),
                p.patient_code,
                p.first_name,
                p.middle_name,
                p.last_name,
                d.full_name,
                d.specialty
            HAVING SUM(plr.order_status = 'ordered') > 0
            ORDER BY MIN(plr.result_date) DESC, MIN(plr.id) DESC
            """,
            tuple(order_params),
            fetchall=True
        )

        valid_order_keys = {str(order["order_key"]) for order in orders}
        selected_order = next(
            (order for order in orders if str(order["order_key"]) == selected_order_key),
            None
        )

        if selected_order_key and selected_order_key not in valid_order_keys:
            flash_t("Selected lab order was not found for the current filters.", "error")
            selected_order_key = ""
            selected_order = None

        results = []

        if selected_order:
            selected_first_order_id = selected_order["first_order_id"]
            results = execute_query(
                """
                SELECT
                    plr.id,
                    COALESCE(plr.lab_order_code, CAST(plr.id AS CHAR)) AS order_key,
                    plr.result_value,
                    DATE_FORMAT(plr.result_date, '%Y-%m-%d') AS result_date,
                    plr.notes,
                    COALESCE(plr.order_status, 'draft') AS order_status,
                    plr.doctor_id,
                    lt.test_name,
                    lt.loinc_code,
                    lt.category,
                    lt.unit,
                    CAST(lt.normal_low AS CHAR) AS normal_low,
                    CAST(lt.normal_high AS CHAR) AS normal_high,
                    CASE
                        WHEN lt.normal_low IS NOT NULL AND lt.normal_high IS NOT NULL
                            THEN CONCAT(lt.normal_low, ' - ', lt.normal_high)
                        WHEN lt.normal_low IS NOT NULL
                            THEN CONCAT('>= ', lt.normal_low)
                        WHEN lt.normal_high IS NOT NULL
                            THEN CONCAT('<= ', lt.normal_high)
                        ELSE ''
                    END AS normal_range,
                    p.patient_code,
                    CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                    p.phone_number,
                    d.full_name AS doctor_name,
                    d.specialty AS doctor_specialty
                FROM patient_lab_results plr
                JOIN lab_tests lt ON plr.test_id = lt.id
                JOIN patients p ON plr.patient_id = p.id
                LEFT JOIN doctors d ON plr.doctor_id = d.id
                WHERE (
                    plr.id = %s
                    OR plr.lab_order_code = (
                        SELECT source.lab_order_code
                        FROM patient_lab_results source
                        WHERE source.id = %s
                          AND source.lab_order_code IS NOT NULL
                    )
                )
                  AND COALESCE(plr.order_status, 'draft') <> 'cancelled'
                ORDER BY lt.test_name, plr.id
                """,
                (selected_first_order_id, selected_first_order_id),
                fetchall=True
            )

        return render_template(
            "lab_result.html",
            doctors=doctors,
            orders=orders,
            selected_order=selected_order,
            results=results,
            selected_doctor_id=selected_doctor_id,
            selected_order_key=selected_order_key
        )

    @app.route("/secretary/lab_result/update/<int:result_id>", methods=["POST"])
    @login_required
    @permission_required("lab_result")
    def update_lab_result(result_id):
        result = execute_query(
            """
            SELECT
                id,
                order_status,
                DATE_FORMAT(result_date, '%Y-%m-%d') AS result_date,
                notes
            FROM patient_lab_results
            WHERE id = %s
            """,
            (result_id,),
            fetchone=True
        )

        if not result:
            flash_t("Lab result not found.", "error")
            return redirect(url_for("lab_result"))

        if result["order_status"] != "ordered":
            flash_t("Only ordered lab tests can receive results.", "error")
            return redirect(url_for("lab_result"))

        result_value = request.form.get("result_value", "").strip()
        result_date = request.form.get("result_date") or result["result_date"]
        notes = (
            request.form.get("notes", "").strip()
            if "notes" in request.form
            else result.get("notes")
        )
        save_type = request.form.get("save_type")
        order_status = "completed" if save_type == "final" else "ordered"

        if not result_value or not result_date:
            flash_t("Result value and result date are required.", "error")
            return redirect(url_for("lab_result"))

        execute_query(
            """
            UPDATE patient_lab_results
            SET result_value = %s,
                result_date = %s,
                notes = %s,
                order_status = %s,
                updated_at = NOW(),
                finalized_at = CASE WHEN %s = 'completed' THEN NOW() ELSE finalized_at END
            WHERE id = %s
            """,
            (
                result_value,
                result_date,
                notes or None,
                order_status,
                order_status,
                result_id
            )
        )

        redirect_args = {}

        if request.form.get("selected_doctor_id"):
            redirect_args["doctor_id"] = request.form.get("selected_doctor_id")

        if request.form.get("selected_order_key"):
            redirect_args["order_key"] = request.form.get("selected_order_key")

        flash_t("Lab result saved successfully.", "success")
        return redirect(url_for("lab_result", **redirect_args))

    @app.route("/secretary/lab_result/final_save/<int:first_order_id>", methods=["POST"])
    @login_required
    @permission_required("lab_result")
    def final_save_lab_result_order(first_order_id):
        selected_doctor_id = request.form.get("selected_doctor_id", type=int)
        selected_order_key = request.form.get("selected_order_key", "").strip()

        redirect_args = {}
        if selected_doctor_id:
            redirect_args["doctor_id"] = selected_doctor_id
        if selected_order_key:
            redirect_args["order_key"] = selected_order_key

        order_rows = execute_query(
            """
            SELECT id, result_value, order_status
            FROM patient_lab_results plr
            WHERE (
                plr.id = %s
                OR plr.lab_order_code = (
                    SELECT source.lab_order_code
                    FROM patient_lab_results source
                    WHERE source.id = %s
                      AND source.lab_order_code IS NOT NULL
                )
            )
              AND COALESCE(plr.order_status, 'draft') <> 'cancelled'
            """,
            (first_order_id, first_order_id),
            fetchall=True
        )

        if not order_rows:
            flash_t("Lab order not found.", "error")
            return redirect(url_for("lab_result", **redirect_args))

        if any(row["order_status"] != "ordered" for row in order_rows):
            flash_t("Only ordered lab orders can be final saved.", "error")
            return redirect(url_for("lab_result", **redirect_args))

        missing_results = [
            row for row in order_rows
            if row["result_value"] is None or str(row["result_value"]).strip() == ""
        ]

        if missing_results:
            flash_t("Enter all result values before final saving this lab order.", "error")
            return redirect(url_for("lab_result", **redirect_args))

        order_row_ids = [row["id"] for row in order_rows]
        placeholders = ", ".join(["%s"] * len(order_row_ids))

        execute_query(
            f"""
            UPDATE patient_lab_results
            SET order_status = 'completed',
                finalized_at = NOW(),
                updated_at = NOW()
            WHERE id IN ({placeholders})
            """,
            tuple(order_row_ids)
        )

        flash_t("Lab order final saved successfully.", "success")
        return redirect(url_for("lab_result", doctor_id=selected_doctor_id) if selected_doctor_id else url_for("lab_result"))

    @app.route("/lab_order/edit/<int:order_id>", methods=["GET", "POST"])
    def edit_lab_order(order_id):
        doctor_id = request.args.get("doctor_id", type=int)

        order = execute_query(
            """
            SELECT
                plr.*,
                lt.test_name,
                lt.loinc_code,
                lt.category,
                lt.unit,
                lt.normal_low,
                lt.normal_high,
                CASE
                    WHEN lt.normal_low IS NOT NULL AND lt.normal_high IS NOT NULL
                        THEN CONCAT(lt.normal_low, ' - ', lt.normal_high)
                    WHEN lt.normal_low IS NOT NULL
                        THEN CONCAT('>= ', lt.normal_low)
                    WHEN lt.normal_high IS NOT NULL
                        THEN CONCAT('<= ', lt.normal_high)
                    ELSE ''
                END AS normal_range
            FROM patient_lab_results plr
            JOIN lab_tests lt ON plr.test_id = lt.id
            WHERE plr.id = %s
            """,
            (order_id,),
            fetchone=True
        )

        if not order:
            flash_t("Lab order not found.", "error")
            return redirect(url_for("checked_in_patients", doctor_id=doctor_id))

        if order["order_status"] in ("ordered", "cancelled"):
            flash_t("This lab order is finalized and cannot be edited.", "error")
            return redirect(url_for(
                "patient_details",
                patient_id=order["patient_id"],
                doctor_id=doctor_id
            ))

        lab_tests = execute_query(
            """
            SELECT id, test_name, loinc_code, unit, normal_low, normal_high, category
            FROM lab_tests
            ORDER BY test_name
            """,
            fetchall=True
        )

        if request.method == "POST":
            save_type = request.form.get("save_type")
            order_status = "ordered" if save_type == "final" else "draft"

            execute_query(
                """
                UPDATE patient_lab_results
                SET test_id = %s,
                    result_date = %s,
                    notes = %s,
                    order_status = %s,
                    updated_at = NOW(),
                    finalized_at = CASE WHEN %s = 'ordered' THEN NOW() ELSE finalized_at END
                WHERE id = %s
                """,
                (
                    request.form.get("test_id"),
                    request.form.get("result_date"),
                    request.form.get("notes"),
                    order_status,
                    order_status,
                    order_id
                )
            )

            flash_t("Lab order updated successfully.", "success")
            return redirect(url_for(
                "patient_details",
                patient_id=order["patient_id"],
                doctor_id=doctor_id
            ))

        return render_template(
            "edit_lab_order.html",
            order=order,
            lab_tests=lab_tests,
            doctor_id=doctor_id
        )

    @app.route("/lab_order/delete/<int:order_id>", methods=["POST"])
    def delete_lab_order(order_id):
        doctor_id = request.args.get("doctor_id", type=int)

        order = execute_query(
            "SELECT * FROM patient_lab_results WHERE id = %s",
            (order_id,),
            fetchone=True
        )

        if order["order_status"] != "draft":
            flash_t("Only draft lab orders can be deleted.", "error")
            return redirect(url_for("patient_details", patient_id=order["patient_id"], doctor_id=doctor_id))

        execute_query(
            "DELETE FROM patient_lab_results WHERE id = %s",
            (order_id,)
        )

        flash_t("Draft lab order deleted successfully.", "success")
        return redirect(url_for("patient_details", patient_id=order["patient_id"], doctor_id=doctor_id))

    @app.route("/lab_order/cancel/<int:order_id>", methods=["POST"])
    def cancel_lab_order(order_id):
        doctor_id = request.args.get("doctor_id", type=int)

        order = execute_query(
            "SELECT * FROM patient_lab_results WHERE id = %s",
            (order_id,),
            fetchone=True
        )

        if order["order_status"] != "ordered":
            flash_t("Only ordered lab tests can be cancelled.", "error")
            return redirect(url_for("patient_details", patient_id=order["patient_id"], doctor_id=doctor_id))

        execute_query(
            """
            UPDATE patient_lab_results
            SET order_status = 'cancelled',
                cancelled_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (order_id,)
        )

        flash_t("Lab order cancelled successfully.", "success")
        return redirect(url_for("patient_details", patient_id=order["patient_id"], doctor_id=doctor_id))
