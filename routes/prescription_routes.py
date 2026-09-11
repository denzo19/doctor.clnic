from datetime import date
import uuid

from flask import Response, flash, redirect, render_template, request, session, url_for

from auth import login_required, permission_required
from database import execute_query
from i18n import translate
import prescription_pdf as prescription_pdf_helpers


def flash_t(message, category="success"):
    flash(translate(message, session.get("language", "en")), category)


def register_prescription_routes(app, get_logged_doctor_id):
    @app.route("/checked_in/prescribe/<int:patient_id>", methods=["POST"])
    def prescribe_medication(patient_id):
        doctor_id = request.form.get("doctor_id", type=int)

        medication_id = request.form.get("medication_id")
        dose = request.form.get("dose")
        frequency = request.form.get("frequency")
        start_date = request.form.get("start_date")
        notes = request.form.get("notes")
        save_type = request.form.get("save_type")

        prescription_status = "active" if save_type == "final" else "draft"
        prescription_order_code = uuid.uuid4().hex

        execute_query(
            """
            INSERT INTO patient_medications
            (patient_id, medication_id, dose, frequency, start_date, notes,
             prescription_status, finalized_at, doctor_id, prescription_order_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'active' THEN NOW() ELSE NULL END,
                    %s, %s)
            """,
            (
                patient_id,
                medication_id,
                dose,
                frequency,
                start_date,
                notes,
                prescription_status,
                prescription_status,
                doctor_id,
                prescription_order_code
            )
        )

        flash_t("Prescription saved successfully.", "success")
        return redirect(url_for("checked_in_patients", doctor_id=doctor_id))

    @app.route("/prescription/edit/<int:prescription_id>", methods=["GET", "POST"])
    def edit_prescription(prescription_id):
        doctor_id = request.args.get("doctor_id", type=int)

        prescription = execute_query(
            """
            SELECT pm.*, m.medication_name, m.strength, m.dosage_form
            FROM patient_medications pm
            JOIN medications m ON pm.medication_id = m.id
            WHERE pm.id = %s
            """,
            (prescription_id,),
            fetchone=True
        )

        if not prescription:
            flash_t("Prescription not found.", "error")
            return redirect(url_for("checked_in_patients", doctor_id=doctor_id))

        if prescription["prescription_status"] in ("active", "stopped"):
            flash_t("This prescription is finalized and cannot be edited.", "error")
            return redirect(url_for(
                "patient_details",
                patient_id=prescription["patient_id"],
                doctor_id=doctor_id
            ))

        medications = execute_query(
            """
            SELECT id, medication_name, strength, dosage_form
            FROM medications
            ORDER BY medication_name
            """,
            fetchall=True
        )

        if request.method == "POST":
            save_type = request.form.get("save_type")
            prescription_status = "active" if save_type == "final" else "draft"

            execute_query(
                """
                UPDATE patient_medications
                SET medication_id = %s,
                    dose = %s,
                    frequency = %s,
                    start_date = %s,
                    notes = %s,
                    prescription_status = %s,
                    updated_at = NOW(),
                    finalized_at = CASE WHEN %s = 'active' THEN NOW() ELSE finalized_at END
                WHERE id = %s
                """,
                (
                    request.form.get("medication_id"),
                    request.form.get("dose"),
                    request.form.get("frequency"),
                    request.form.get("start_date"),
                    request.form.get("notes"),
                    prescription_status,
                    prescription_status,
                    prescription_id
                )
            )

            flash_t("Prescription updated successfully.", "success")
            return redirect(url_for(
                "patient_details",
                patient_id=prescription["patient_id"],
                doctor_id=doctor_id
            ))

        return render_template(
            "edit_prescription.html",
            prescription=prescription,
            medications=medications,
            doctor_id=doctor_id
        )

    @app.route("/prescription/delete/<int:prescription_id>", methods=["POST"])
    def delete_prescription(prescription_id):
        doctor_id = request.args.get("doctor_id", type=int)

        prescription = execute_query(
            "SELECT * FROM patient_medications WHERE id = %s",
            (prescription_id,),
            fetchone=True
        )

        if not prescription:
            flash_t("Prescription not found.", "error")
            return redirect(url_for("checked_in_patients", doctor_id=doctor_id))

        if prescription["prescription_status"] != "draft":
            flash_t("Only draft prescriptions can be deleted.", "error")
            return redirect(url_for(
                "patient_details",
                patient_id=prescription["patient_id"],
                doctor_id=doctor_id
            ))

        execute_query(
            "DELETE FROM patient_medications WHERE id = %s",
            (prescription_id,)
        )

        flash_t("Draft prescription deleted successfully.", "success")
        return redirect(url_for(
            "patient_details",
            patient_id=prescription["patient_id"],
            doctor_id=doctor_id
        ))

    @app.route("/prescription/stop/<int:prescription_id>", methods=["POST"])
    def stop_prescription(prescription_id):
        doctor_id = request.args.get("doctor_id", type=int)

        prescription = execute_query(
            "SELECT * FROM patient_medications WHERE id = %s",
            (prescription_id,),
            fetchone=True
        )

        if not prescription:
            flash_t("Prescription not found.", "error")
            return redirect(url_for("checked_in_patients", doctor_id=doctor_id))

        if prescription["prescription_status"] != "active":
            flash_t("Only active prescriptions can be stopped.", "error")
            return redirect(url_for(
                "patient_details",
                patient_id=prescription["patient_id"],
                doctor_id=doctor_id
            ))

        execute_query(
            """
            UPDATE patient_medications
            SET prescription_status = 'stopped',
                end_date = CURDATE(),
                stopped_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (prescription_id,)
        )

        flash_t("Medication stopped successfully.", "success")
        return redirect(url_for(
            "patient_details",
            patient_id=prescription["patient_id"],
            doctor_id=doctor_id
        ))

    def fetch_prescription_form_lists():
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

        medications = execute_query(
            """
            SELECT id, medication_name, strength, dosage_form
            FROM medications
            WHERE is_active = 1
            ORDER BY medication_name, strength, dosage_form
            """,
            fetchall=True
        )

        return doctors, patients, medications

    @app.route("/prescriptions/manage", methods=["GET"])
    @login_required
    @permission_required("manage_prescriptions")
    def manage_prescriptions():
        logged_doctor_id = get_logged_doctor_id()
        doctors, patients, _ = fetch_prescription_form_lists()

        selected_doctor_id = request.args.get("doctor_id", type=int) or logged_doctor_id
        selected_patient_id = request.args.get("patient_id", type=int)
        selected_status = request.args.get("status", "").strip()

        filters = []
        params = []

        if selected_doctor_id:
            filters.append("pm.doctor_id = %s")
            params.append(selected_doctor_id)

        if selected_patient_id:
            filters.append("pm.patient_id = %s")
            params.append(selected_patient_id)

        if selected_status:
            filters.append("pm.prescription_status = %s")
            params.append(selected_status)

        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        prescriptions = execute_query(
            """
            SELECT
                COALESCE(pm.prescription_order_code, CAST(pm.id AS CHAR)) AS order_key,
                MIN(pm.id) AS first_prescription_id,
                pm.patient_id,
                pm.doctor_id,
                p.patient_code,
                CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                d.full_name AS doctor_name,
                d.specialty AS doctor_specialty,
                DATE_FORMAT(MIN(pm.start_date), '%Y-%m-%d') AS start_date,
                GROUP_CONCAT(
                    CONCAT(m.medication_name,
                        IF(m.strength IS NULL OR m.strength = '', '', CONCAT(' ', m.strength)),
                        IF(m.dosage_form IS NULL OR m.dosage_form = '', '', CONCAT(' ', m.dosage_form))
                    )
                    ORDER BY m.medication_name SEPARATOR ', '
                ) AS medications,
                COUNT(*) AS medication_count,
                CASE
                    WHEN SUM(pm.prescription_status = 'stopped') > 0 THEN 'stopped'
                    WHEN SUM(pm.prescription_status = 'active') > 0 THEN 'active'
                    ELSE 'draft'
                END AS prescription_status
            FROM patient_medications pm
            JOIN patients p ON pm.patient_id = p.id
            JOIN medications m ON pm.medication_id = m.id
            LEFT JOIN doctors d ON pm.doctor_id = d.id
            """ + where_clause + """
            GROUP BY
                COALESCE(pm.prescription_order_code, CAST(pm.id AS CHAR)),
                pm.patient_id,
                pm.doctor_id,
                p.patient_code,
                p.first_name,
                p.middle_name,
                p.last_name,
                d.full_name,
                d.specialty
            ORDER BY MIN(pm.start_date) DESC, MIN(pm.id) DESC
            """,
            tuple(params),
            fetchall=True
        )

        return render_template(
            "manage_prescriptions.html",
            doctors=doctors,
            patients=patients,
            prescriptions=prescriptions,
            selected_doctor_id=selected_doctor_id,
            selected_patient_id=selected_patient_id,
            selected_status=selected_status
        )

    @app.route("/prescriptions/manage/view/<order_key>", methods=["GET"])
    @login_required
    @permission_required("manage_prescriptions")
    def view_managed_prescription(order_key):
        fallback_prescription_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT
                pm.id,
                pm.dose,
                pm.frequency,
                DATE_FORMAT(pm.start_date, '%Y-%m-%d') AS start_date,
                DATE_FORMAT(pm.end_date, '%Y-%m-%d') AS end_date,
                pm.notes,
                pm.prescription_status,
                p.patient_code,
                CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                d.full_name AS doctor_name,
                d.specialty AS doctor_specialty,
                m.medication_name,
                m.strength,
                m.dosage_form
            FROM patient_medications pm
            JOIN patients p ON pm.patient_id = p.id
            JOIN medications m ON pm.medication_id = m.id
            LEFT JOIN doctors d ON pm.doctor_id = d.id
            WHERE pm.prescription_order_code = %s
               OR (pm.prescription_order_code IS NULL AND pm.id = %s)
            ORDER BY m.medication_name, pm.id
            """,
            (order_key, fallback_prescription_id),
            fetchall=True
        )

        if not rows:
            return {
                "success": False,
                "message": translate("Prescription not found.", session.get("language", "en"))
            }, 404

        first_row = rows[0]
        first_prescription_id = min(row["id"] for row in rows)
        statuses = [row["prescription_status"] for row in rows]

        if "stopped" in statuses:
            prescription_status = "stopped"
        elif "active" in statuses:
            prescription_status = "active"
        else:
            prescription_status = "draft"

        return {
            "success": True,
            "prescription": {
                "prescription_id": first_prescription_id,
                "start_date": first_row["start_date"] or "",
                "patient": f"{first_row['patient_code']} - {first_row['patient_name']}",
                "doctor": (
                    (first_row["doctor_name"] or "") +
                    (f" - {first_row['doctor_specialty']}" if first_row["doctor_specialty"] else "")
                ),
                "status": prescription_status
            },
            "medications": [
                {
                    "medication": " ".join(
                        part for part in [
                            row["medication_name"] or "",
                            row["strength"] or "",
                            row["dosage_form"] or ""
                        ]
                        if part
                    ),
                    "dose": row["dose"] or "",
                    "frequency": row["frequency"] or "",
                    "start_date": row["start_date"] or "",
                    "end_date": row["end_date"] or "",
                    "status": row["prescription_status"] or "",
                    "notes": row["notes"] or ""
                }
                for row in rows
            ]
        }

    @app.route("/prescriptions/manage/print/<order_key>", methods=["GET"])
    @login_required
    @permission_required("manage_prescriptions")
    def print_managed_prescription(order_key):
        fallback_prescription_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT
                pm.id,
                pm.dose,
                pm.frequency,
                DATE_FORMAT(pm.start_date, '%Y-%m-%d') AS start_date,
                DATE_FORMAT(pm.end_date, '%Y-%m-%d') AS end_date,
                pm.notes,
                pm.prescription_status,
                p.patient_code,
                CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name,
                d.full_name AS doctor_name,
                d.specialty AS doctor_specialty,
                m.medication_name,
                m.strength,
                m.dosage_form
            FROM patient_medications pm
            JOIN patients p ON pm.patient_id = p.id
            JOIN medications m ON pm.medication_id = m.id
            LEFT JOIN doctors d ON pm.doctor_id = d.id
            WHERE pm.prescription_order_code = %s
               OR (pm.prescription_order_code IS NULL AND pm.id = %s)
            ORDER BY m.medication_name, pm.id
            """,
            (order_key, fallback_prescription_id),
            fetchall=True
        )

        if not rows:
            flash_t("Prescription not found.", "error")
            return redirect(url_for("manage_prescriptions"))

        first_row = rows[0]
        first_prescription_id = min(row["id"] for row in rows)
        prescription = {
            "prescription_id": first_prescription_id,
            "start_date": first_row["start_date"] or "",
            "patient": f"{first_row['patient_code']} - {first_row['patient_name']}",
            "doctor": (
                (first_row["doctor_name"] or "") +
                (f" - {first_row['doctor_specialty']}" if first_row["doctor_specialty"] else "")
            ),
            "status": prescription_pdf_helpers.get_prescription_status(rows)
        }
        medications = [
            {
                "medication": prescription_pdf_helpers.format_prescription_medication(row),
                "dose": row["dose"] or "",
                "frequency": row["frequency"] or "",
                "end_date": row["end_date"] or "",
                "notes": row["notes"] or ""
            }
            for row in rows
        ]

        pdf_bytes = prescription_pdf_helpers.build_prescription_pdf(
            prescription,
            medications,
            app.root_path
        )

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=prescription_{first_prescription_id}.pdf"
            }
        )

    @app.route("/prescriptions/manage/new", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_prescriptions")
    def new_managed_prescription():
        logged_doctor_id = get_logged_doctor_id()
        selected_doctor_id = logged_doctor_id or request.args.get("doctor_id", type=int)
        selected_patient_id = request.args.get("patient_id", type=int)
        return_to_patient = request.args.get("return_to_patient") == "1"
        doctors, patients, medications = fetch_prescription_form_lists()

        if request.method == "POST":
            patient_id = request.form.get("patient_id", type=int)
            doctor_id = request.form.get("doctor_id", type=int) or selected_doctor_id
            medication_ids = request.form.getlist("medication_ids")
            doses = request.form.getlist("doses")
            frequencies = request.form.getlist("frequencies")
            start_dates = request.form.getlist("start_dates")
            end_dates = request.form.getlist("end_dates")
            notes_list = request.form.getlist("line_notes")
            save_type = request.form.get("save_type")
            return_to_patient = request.form.get("return_to_patient") == "1"
            prescription_status = "active" if save_type in ("final", "final_print") else "draft"

            if not patient_id or not doctor_id or not medication_ids:
                flash_t("Choose patient, doctor, and at least one medication.", "error")
                return redirect(url_for(
                    "new_managed_prescription",
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    return_to_patient=1 if return_to_patient else None
                ))

            prescription_order_code = uuid.uuid4().hex

            for index, medication_id in enumerate(medication_ids):
                execute_query(
                    """
                    INSERT INTO patient_medications
                        (patient_id, medication_id, dose, frequency, start_date, end_date,
                         notes, prescription_status, finalized_at, doctor_id, prescription_order_code)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s,
                         CASE WHEN %s = 'active' THEN NOW() ELSE NULL END, %s, %s)
                    """,
                    (
                        patient_id,
                        medication_id,
                        doses[index] if index < len(doses) else None,
                        frequencies[index] if index < len(frequencies) else None,
                        start_dates[index] if index < len(start_dates) and start_dates[index] else date.today().isoformat(),
                        end_dates[index] if index < len(end_dates) and end_dates[index] else None,
                        notes_list[index] if index < len(notes_list) else None,
                        prescription_status,
                        prescription_status,
                        doctor_id,
                        prescription_order_code
                    )
                )

            flash_t("Prescription saved successfully.", "success")
            if save_type == "final_print":
                return redirect(url_for(
                    "print_managed_prescription",
                    order_key=prescription_order_code
                ))

            if return_to_patient:
                return redirect(url_for("patient_details", patient_id=patient_id, doctor_id=doctor_id))

            return redirect(url_for("manage_prescriptions"))

        prescription = {
            "patient_id": selected_patient_id,
            "items": []
        } if selected_patient_id else None

        return render_template(
            "prescription_order_form.html",
            doctors=doctors,
            patients=patients,
            medications=medications,
            prescription=prescription,
            selected_doctor_id=selected_doctor_id,
            default_start_date=date.today().isoformat(),
            form_action=url_for(
                "new_managed_prescription",
                patient_id=selected_patient_id,
                doctor_id=selected_doctor_id,
                return_to_patient=1 if return_to_patient else None
            ),
            return_to_patient=return_to_patient,
            show_final_print_button=True
        )

    @app.route("/prescriptions/manage/update/<order_key>", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_prescriptions")
    def update_managed_prescription(order_key):
        logged_doctor_id = get_logged_doctor_id()
        fallback_prescription_id = int(order_key) if order_key.isdigit() else 0

        rows = execute_query(
            """
            SELECT *,
                   DATE_FORMAT(start_date, '%Y-%m-%d') AS start_date_value,
                   DATE_FORMAT(end_date, '%Y-%m-%d') AS end_date_value
            FROM patient_medications
            WHERE prescription_order_code = %s
               OR (prescription_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_prescription_id),
            fetchall=True
        )

        if not rows:
            flash_t("Prescription not found.", "error")
            return redirect(url_for("manage_prescriptions"))

        if any(row["prescription_status"] != "draft" for row in rows):
            flash_t("Only draft prescriptions can be edited.", "error")
            return redirect(url_for("manage_prescriptions"))

        doctors, patients, medications = fetch_prescription_form_lists()

        if request.method == "GET":
            selected_doctor_id = rows[0]["doctor_id"] or logged_doctor_id
            prescription = {
                "patient_id": rows[0]["patient_id"],
                "doctor_id": selected_doctor_id,
                "items": [
                    {
                        "medication_id": str(row["medication_id"]),
                        "dose": row["dose"] or "",
                        "frequency": row["frequency"] or "",
                        "start_date": row["start_date_value"] or date.today().isoformat(),
                        "end_date": row["end_date_value"] or "",
                        "notes": row["notes"] or ""
                    }
                    for row in rows
                ]
            }

            return render_template(
                "prescription_order_form.html",
                doctors=doctors,
                patients=patients,
                medications=medications,
                prescription=prescription,
                selected_doctor_id=selected_doctor_id,
                default_start_date=date.today().isoformat(),
                form_action=url_for("update_managed_prescription", order_key=order_key)
            )

        patient_id = request.form.get("patient_id", type=int)
        doctor_id = request.form.get("doctor_id", type=int) or logged_doctor_id
        medication_ids = request.form.getlist("medication_ids")
        doses = request.form.getlist("doses")
        frequencies = request.form.getlist("frequencies")
        start_dates = request.form.getlist("start_dates")
        end_dates = request.form.getlist("end_dates")
        notes_list = request.form.getlist("line_notes")
        save_type = request.form.get("save_type")
        prescription_status = "active" if save_type == "final" else "draft"

        if not patient_id or not doctor_id or not medication_ids:
            flash_t("Choose patient, doctor, and at least one medication.", "error")
            return redirect(url_for("update_managed_prescription", order_key=order_key))

        prescription_order_code = rows[0].get("prescription_order_code") or uuid.uuid4().hex

        execute_query(
            """
            DELETE FROM patient_medications
            WHERE prescription_order_code = %s
               OR (prescription_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_prescription_id)
        )

        for index, medication_id in enumerate(medication_ids):
            execute_query(
                """
                INSERT INTO patient_medications
                    (patient_id, medication_id, dose, frequency, start_date, end_date,
                     notes, prescription_status, finalized_at, doctor_id, prescription_order_code, updated_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s,
                     CASE WHEN %s = 'active' THEN NOW() ELSE NULL END, %s, %s, NOW())
                """,
                (
                    patient_id,
                    medication_id,
                    doses[index] if index < len(doses) else None,
                    frequencies[index] if index < len(frequencies) else None,
                    start_dates[index] if index < len(start_dates) and start_dates[index] else date.today().isoformat(),
                    end_dates[index] if index < len(end_dates) and end_dates[index] else None,
                    notes_list[index] if index < len(notes_list) else None,
                    prescription_status,
                    prescription_status,
                    doctor_id,
                    prescription_order_code
                )
            )

        flash_t("Prescription updated successfully.", "success")
        return redirect(url_for("manage_prescriptions"))

    @app.route("/prescriptions/manage/delete/<order_key>", methods=["POST"])
    @login_required
    @permission_required("manage_prescriptions")
    def delete_managed_prescription(order_key):
        fallback_prescription_id = int(order_key) if order_key.isdigit() else 0
        rows = execute_query(
            """
            SELECT *
            FROM patient_medications
            WHERE prescription_order_code = %s
               OR (prescription_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_prescription_id),
            fetchall=True
        )

        if not rows:
            flash_t("Prescription not found.", "error")
            return redirect(url_for("manage_prescriptions"))

        if any(row["prescription_status"] != "draft" for row in rows):
            flash_t("Only draft prescriptions can be deleted.", "error")
            return redirect(url_for("manage_prescriptions"))

        execute_query(
            """
            DELETE FROM patient_medications
            WHERE prescription_order_code = %s
               OR (prescription_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_prescription_id)
        )

        flash_t("Draft prescription deleted successfully.", "success")
        return redirect(url_for("manage_prescriptions"))

    @app.route("/prescriptions/manage/stop/<order_key>", methods=["POST"])
    @login_required
    @permission_required("manage_prescriptions")
    def stop_managed_prescription(order_key):
        fallback_prescription_id = int(order_key) if order_key.isdigit() else 0
        rows = execute_query(
            """
            SELECT *
            FROM patient_medications
            WHERE prescription_order_code = %s
               OR (prescription_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_prescription_id),
            fetchall=True
        )

        if not rows:
            flash_t("Prescription not found.", "error")
            return redirect(url_for("manage_prescriptions"))

        if any(row["prescription_status"] != "active" for row in rows):
            flash_t("Only active prescriptions can be stopped.", "error")
            return redirect(url_for("manage_prescriptions"))

        execute_query(
            """
            UPDATE patient_medications
            SET prescription_status = 'stopped',
                stopped_at = NOW(),
                updated_at = NOW()
            WHERE prescription_order_code = %s
               OR (prescription_order_code IS NULL AND id = %s)
            """,
            (order_key, fallback_prescription_id)
        )

        flash_t("Prescription stopped successfully.", "success")
        return redirect(url_for("manage_prescriptions"))
