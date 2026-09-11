from datetime import date, datetime, timedelta

import mysql.connector
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


def register_appointment_routes(app):
    def flash_t(message, category="success"):
        flash(translate(message, session.get("language", "en")), category)

    def fetch_patient_for_appointments(patient_id):
        if not patient_id:
            return None

        return execute_query(
            """
            SELECT
                id,
                patient_code,
                first_name,
                middle_name,
                last_name,
                phone_number
            FROM patients
            WHERE id = %s
            """,
            (patient_id,),
            fetchone=True
        )

    def fetch_patient_appointments(patient_id):
        return execute_query(
            """
            SELECT
                a.id,
                a.slot_id,
                a.patient_id,
                a.appointment_status,
                a.notes,

                aps.doctor_id,
                aps.center_id,
                aps.slot_date,
                aps.start_time,
                aps.end_time,

                d.full_name AS doctor_name,
                mc.center_name

            FROM appointments a

            JOIN appointment_slots aps
                ON a.slot_id = aps.id

            JOIN doctors d
                ON aps.doctor_id = d.id

            JOIN medical_centers mc
                ON aps.center_id = mc.id

            WHERE a.patient_id = %s

            ORDER BY aps.slot_date DESC,
                     aps.start_time DESC
            """,
            (patient_id,),
            fetchall=True
        )

    def build_patient_appointments_pdf_report(patient, appointments):
        page_width = 612
        page_height = 792
        left = 34
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()
        patient_name = " ".join(
            part for part in [
                patient["first_name"],
                patient["middle_name"] or "",
                patient["last_name"]
            ]
            if part
        )

        for start in range(0, max(len(appointments), 1), rows_per_page):
            page_appointments = appointments[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Patient Appointments Report) Tj ET",
                "0 g",
                f"BT /F1 9 Tf {left} {top - 18} Td (Generated on {escape_pdf_text(datetime.now().strftime('%Y-%m-%d %H:%M'))}) Tj ET",
                f"BT /F1 9 Tf {left} {top - 32} Td (Patient: {escape_pdf_text(truncate_pdf_text(patient['patient_code'] + ' - ' + patient_name, 80))}) Tj ET",
            ]

            table_top = top - 58
            commands.extend([
                "0.12 0.31 0.47 RG",
                f"{left} {table_top + 8} m {page_width - left} {table_top + 8} l S",
                f"BT /F1 9 Tf {left + 4} {table_top - 7} Td (Date) Tj ET",
                f"BT /F1 9 Tf {left + 78} {table_top - 7} Td (Start) Tj ET",
                f"BT /F1 9 Tf {left + 128} {table_top - 7} Td (End) Tj ET",
                f"BT /F1 9 Tf {left + 178} {table_top - 7} Td (Doctor) Tj ET",
                f"BT /F1 9 Tf {left + 322} {table_top - 7} Td (Center) Tj ET",
                f"BT /F1 9 Tf {left + 445} {table_top - 7} Td (Status) Tj ET",
                f"BT /F1 9 Tf {left + 500} {table_top - 7} Td (Notes) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_appointments:
                for appointment in page_appointments:
                    commands.extend([
                        f"BT /F1 7.5 Tf {left + 4} {y} Td ({escape_pdf_text(appointment['slot_date'])}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 78} {y} Td ({escape_pdf_text(str(appointment['start_time']))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 128} {y} Td ({escape_pdf_text(str(appointment['end_time']))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 178} {y} Td ({escape_pdf_text(truncate_pdf_text(appointment['doctor_name'], 22))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 322} {y} Td ({escape_pdf_text(truncate_pdf_text(appointment['center_name'], 19))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 445} {y} Td ({escape_pdf_text(appointment['appointment_status'])}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 500} {y} Td ({escape_pdf_text(truncate_pdf_text(appointment['notes'], 13))}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No appointments found for this patient.) Tj ET"
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

    def generate_slots_for_date_range(start_date, end_date):
        programs = execute_query(
            """
            SELECT *
            FROM doctor_weekly_programs
            WHERE is_active = 1
            """,
            fetchall=True
        )

        created = 0
        skipped = 0

        current_date = start_date

        while current_date <= end_date:
            day_of_week = current_date.isoweekday()

            for program in programs:
                if program["day_of_week"] != day_of_week:
                    continue

                doctor_id = program["doctor_id"]
                center_id = program["center_id"]
                duration = int(program["slot_duration_minutes"])

                start_time = (datetime.min + program["start_time"]).time()
                end_time = (datetime.min + program["end_time"]).time()

                start_dt = datetime.combine(current_date, start_time)
                end_dt = datetime.combine(current_date, end_time)

                slot_start = start_dt

                while slot_start + timedelta(minutes=duration) <= end_dt:
                    slot_end = slot_start + timedelta(minutes=duration)

                    absence = execute_query(
                        """
                        SELECT id
                        FROM doctor_absences
                        WHERE doctor_id = %s
                          AND is_active = 1
                          AND %s BETWEEN absence_date AND COALESCE(end_date, absence_date)
                          AND (center_id IS NULL OR center_id = %s)
                          AND (
                                absence_type IN ('full_day', 'date_range')
                                OR (
                                    start_time < %s
                                    AND end_time > %s
                                )
                              )
                        LIMIT 1
                        """,
                        (
                            doctor_id,
                            current_date,
                            center_id,
                            slot_end.time(),
                            slot_start.time()
                        ),
                        fetchone=True
                    )

                    status = "unavailable" if absence else "available"

                    try:
                        execute_query(
                            """
                            INSERT INTO appointment_slots
                            (doctor_id, center_id, slot_date,
                            start_time, end_time, status)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                doctor_id,
                                center_id,
                                current_date,
                                slot_start.time(),
                                slot_end.time(),
                                status
                            )
                        )

                        created += 1

                    except mysql.connector.IntegrityError:
                        skipped += 1

                    slot_start = slot_end

            current_date += timedelta(days=1)

        return created, skipped

    def end_of_following_month(start_date):
        first_of_month = start_date.replace(day=1)
        next_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_after_next = (next_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        return month_after_next - timedelta(days=1)

    @app.route("/appointments", methods=["GET", "POST"])
    def appointments():
        pass

    @app.route("/secretary/manage_appointments", methods=["GET"])
    @login_required
    @permission_required("manage_appointments")
    def manage_appointments():

        patients = execute_query(
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
            ORDER BY last_name,
                     first_name
            """,
            fetchall=True
        )

        selected_patient_id = request.args.get("patient_id", type=int)

        patient = None
        appointments = []

        if selected_patient_id:
            patient = fetch_patient_for_appointments(selected_patient_id)
            appointments = fetch_patient_appointments(selected_patient_id)

        return render_template(
            "manage_appointments.html",
            patients=patients,
            patient=patient,
            appointments=appointments,
            selected_patient_id=selected_patient_id
        )

    @app.route("/secretary/manage_appointments/report", methods=["GET"])
    @login_required
    @permission_required("manage_appointments")
    def manage_appointments_report():
        selected_patient_id = request.args.get("patient_id", type=int)

        if not selected_patient_id:
            flash_t("Choose a patient before generating the appointments report.", "error")
            return redirect(url_for("manage_appointments"))

        patient = fetch_patient_for_appointments(selected_patient_id)

        if not patient:
            flash_t("Patient not found.", "error")
            return redirect(url_for("manage_appointments"))

        appointments = fetch_patient_appointments(selected_patient_id)
        pdf_bytes = build_patient_appointments_pdf_report(patient, appointments)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=patient_appointments_report.pdf"
            }
        )

    @app.route("/secretary/manage_appointments/edit/<int:appointment_id>", methods=["GET"])
    @login_required
    @permission_required("manage_appointments")
    def edit_managed_appointment(appointment_id):

        appointment = execute_query(
            """
            SELECT
                a.id,
                a.slot_id,
                a.patient_id,
                a.appointment_status,
                a.notes,

                aps.doctor_id,
                aps.center_id,
                aps.slot_date,
                aps.start_time,
                aps.end_time,

                d.full_name AS doctor_name,
                d.specialty,
                mc.center_name,

                p.patient_code,
                p.first_name,
                p.middle_name,
                p.last_name,
                p.phone_number

            FROM appointments a

            JOIN appointment_slots aps
                ON a.slot_id = aps.id

            JOIN doctors d
                ON aps.doctor_id = d.id

            JOIN medical_centers mc
                ON aps.center_id = mc.id

            JOIN patients p
                ON a.patient_id = p.id

            WHERE a.id = %s
            """,
            (appointment_id,),
            fetchone=True
        )

        if not appointment:
            flash_t("Appointment not found.", "error")
            return redirect(url_for("manage_appointments"))

        if appointment["appointment_status"] != "booked":
            flash_t("Only booked appointments can be updated.", "error")
            return redirect(url_for("manage_appointments", patient_id=appointment["patient_id"]))

        doctors = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE is_active = 1
            ORDER BY full_name
            """,
            fetchall=True
        )

        medical_centers = execute_query(
            """
            SELECT id, center_name
            FROM medical_centers
            WHERE is_active = 1
            ORDER BY center_name
            """,
            fetchall=True
        )

        selected_doctor = request.args.get("doctor_id") or str(appointment["doctor_id"])
        selected_center = request.args.get("center_id") or str(appointment["center_id"])
        selected_date = request.args.get("slot_date")
        selected_notes = request.args.get("notes")
        if selected_notes is None:
            selected_notes = appointment["notes"] or ""
        search_mode = request.args.get("search_mode", "earliest")

        slots = []

        if selected_doctor:
            if search_mode == "date":
                query = """
                    SELECT
                        aps.id,
                        aps.slot_date,
                        aps.start_time,
                        aps.end_time,

                        d.full_name AS doctor_name,
                        mc.center_name

                    FROM appointment_slots aps

                    JOIN doctors d
                        ON aps.doctor_id = d.id

                    JOIN medical_centers mc
                        ON aps.center_id = mc.id

                    WHERE aps.doctor_id = %s
                      AND aps.slot_date = %s
                      AND aps.status = 'available'
                """
                params = [selected_doctor, selected_date]
            else:
                query = """
                    SELECT
                        aps.id,
                        aps.slot_date,
                        aps.start_time,
                        aps.end_time,

                        d.full_name AS doctor_name,
                        mc.center_name

                    FROM appointment_slots aps

                    JOIN doctors d
                        ON aps.doctor_id = d.id

                    JOIN medical_centers mc
                        ON aps.center_id = mc.id

                    WHERE aps.doctor_id = %s
                      AND aps.status = 'available'
                      AND aps.slot_date >= CURDATE()
                """
                params = [selected_doctor]

            if selected_center != "all":
                query += " AND aps.center_id = %s"
                params.append(selected_center)

            query += """
                ORDER BY aps.slot_date,
                         aps.start_time
                LIMIT 100
            """

            slots = execute_query(
                query,
                tuple(params),
                fetchall=True
            )

        return render_template(
            "reschedule_appointment.html",
            appointment=appointment,
            doctors=doctors,
            medical_centers=medical_centers,
            slots=slots,
            selected_doctor=selected_doctor,
            selected_center=selected_center,
            selected_date=selected_date,
            selected_notes=selected_notes,
            search_mode=search_mode
        )

    @app.route("/secretary/manage_appointments/rebook/<int:appointment_id>/<int:slot_id>", methods=["POST"])
    @login_required
    @permission_required("manage_appointments")
    def rebook_managed_appointment(appointment_id, slot_id):

        notes = request.form.get("notes")

        appointment = execute_query(
            """
            SELECT id, slot_id, patient_id, appointment_status, notes
            FROM appointments
            WHERE id = %s
            """,
            (appointment_id,),
            fetchone=True
        )

        if not appointment:
            flash_t("Appointment not found.", "error")
            return redirect(url_for("manage_appointments"))

        if appointment["appointment_status"] != "booked":
            flash_t("Only booked appointments can be updated.", "error")
            return redirect(url_for("manage_appointments", patient_id=appointment["patient_id"]))

        if notes is None:
            notes = appointment["notes"] or ""
        else:
            notes = notes.strip()

        new_slot = execute_query(
            """
            SELECT id
            FROM appointment_slots
            WHERE id = %s
              AND status = 'available'
              AND slot_date >= CURDATE()
            """,
            (slot_id,),
            fetchone=True
        )

        if not new_slot:
            flash_t("Selected slot is not available.", "error")
            return redirect(url_for("edit_managed_appointment", appointment_id=appointment_id))

        execute_query(
            """
            UPDATE appointment_slots
            SET status = 'available'
            WHERE id = %s
            """,
            (appointment["slot_id"],)
        )

        execute_query(
            "DELETE FROM appointments WHERE id = %s",
            (appointment_id,)
        )

        execute_query(
            """
            INSERT INTO appointments
            (
                slot_id,
                patient_id,
                appointment_status,
                notes
            )
            VALUES (%s, %s, 'booked', %s)
            """,
            (
                slot_id,
                appointment["patient_id"],
                notes
            )
        )

        execute_query(
            """
            UPDATE appointment_slots
            SET status = 'unavailable'
            WHERE id = %s
            """,
            (slot_id,)
        )

        flash_t("Appointment updated successfully.", "success")
        return redirect(url_for("manage_appointments", patient_id=appointment["patient_id"]))

    @app.route("/secretary/manage_appointments/update/<int:appointment_id>", methods=["POST"])
    @login_required
    @permission_required("manage_appointments")
    def update_managed_appointment(appointment_id):

        selected_patient_id = request.form.get("patient_id", type=int)
        new_slot_id = request.form.get("slot_id", type=int)
        notes = request.form.get("notes", "").strip()

        appointment = execute_query(
            """
            SELECT id, slot_id, patient_id, appointment_status
            FROM appointments
            WHERE id = %s
            """,
            (appointment_id,),
            fetchone=True
        )

        if not appointment:
            flash_t("Appointment not found.", "error")
            return redirect(url_for("manage_appointments", patient_id=selected_patient_id))

        selected_patient_id = selected_patient_id or appointment["patient_id"]

        if appointment["appointment_status"] != "booked":
            flash_t("Only booked appointments can be updated.", "error")
            return redirect(url_for("manage_appointments", patient_id=selected_patient_id))

        if not new_slot_id:
            execute_query(
                """
                UPDATE appointments
                SET notes = %s
                WHERE id = %s
                """,
                (notes, appointment_id)
            )

            flash_t("Appointment notes updated successfully.", "success")
            return redirect(url_for("manage_appointments", patient_id=selected_patient_id))

        new_slot = execute_query(
            """
            SELECT id
            FROM appointment_slots
            WHERE id = %s
              AND status = 'available'
              AND slot_date >= CURDATE()
            """,
            (new_slot_id,),
            fetchone=True
        )

        if not new_slot:
            flash_t("Selected slot is not available.", "error")
            return redirect(url_for("manage_appointments", patient_id=selected_patient_id))

        execute_query(
            """
            UPDATE appointment_slots
            SET status = 'available'
            WHERE id = %s
            """,
            (appointment["slot_id"],)
        )

        execute_query(
            """
            UPDATE appointments
            SET slot_id = %s,
                notes = %s,
                appointment_status = 'booked'
            WHERE id = %s
            """,
            (new_slot_id, notes, appointment_id)
        )

        execute_query(
            """
            UPDATE appointment_slots
            SET status = 'unavailable'
            WHERE id = %s
            """,
            (new_slot_id,)
        )

        flash_t("Appointment updated successfully.", "success")
        return redirect(url_for("manage_appointments", patient_id=selected_patient_id))

    @app.route("/secretary/manage_appointments/delete/<int:appointment_id>", methods=["POST"])
    @login_required
    @permission_required("manage_appointments")
    def delete_managed_appointment(appointment_id):

        selected_patient_id = request.form.get("patient_id", type=int)

        appointment = execute_query(
            """
            SELECT id, slot_id, patient_id, appointment_status
            FROM appointments
            WHERE id = %s
            """,
            (appointment_id,),
            fetchone=True
        )

        if not appointment:
            flash_t("Appointment not found.", "error")
            return redirect(url_for("manage_appointments", patient_id=selected_patient_id))

        selected_patient_id = selected_patient_id or appointment["patient_id"]

        if appointment["appointment_status"] == "booked":
            execute_query(
                """
                UPDATE appointment_slots
                SET status = 'available'
                WHERE id = %s
                """,
                (appointment["slot_id"],)
            )

        execute_query(
            "DELETE FROM appointments WHERE id = %s",
            (appointment_id,)
        )

        flash_t("Appointment deleted successfully.", "success")
        return redirect(url_for("manage_appointments", patient_id=selected_patient_id))

    @app.route("/admin/generate_slots", methods=["GET", "POST"])
    @login_required
    @permission_required("generate_appointment_slots")
    def generate_appointment_slots():
        if request.method == "POST":
            start_date = date.today()
            end_date = start_date + timedelta(days=365)

            created, skipped = generate_slots_for_date_range(start_date, end_date)

            flash(
                translate(
                    "Slot generation completed. Created: {created}, skipped existing: {skipped}.",
                    session.get("language", "en")
                ).format(
                    created=created,
                    skipped=skipped
                ),
                "success"
            )
            return redirect(url_for("generate_appointment_slots"))

        return render_template("generate_slots.html")

    @app.route("/admin/extend_schedule", methods=["GET", "POST"])
    @login_required
    @permission_required("extend_schedule")
    def extend_schedule():
        latest_slot = execute_query(
            """
            SELECT MAX(slot_date) AS latest_slot_date
            FROM appointment_slots
            """,
            fetchone=True
        )

        latest_slot_date = latest_slot["latest_slot_date"] if latest_slot else None
        start_date = (latest_slot_date + timedelta(days=1)) if latest_slot_date else date.today()
        end_date = end_of_following_month(start_date)

        if request.method == "POST":
            created, skipped = generate_slots_for_date_range(start_date, end_date)

            flash(
                translate(
                    "Schedule extended from {start_date} to {end_date}. Created: {created}, skipped existing: {skipped}.",
                    session.get("language", "en")
                ).format(
                    start_date=start_date,
                    end_date=end_date,
                    created=created,
                    skipped=skipped
                ),
                "success"
            )
            return redirect(url_for("extend_schedule"))

        return render_template(
            "extend_schedule.html",
            latest_slot_date=latest_slot_date,
            start_date=start_date,
            end_date=end_date
        )

    @app.route("/appointments/search_book", methods=["GET"])
    @login_required
    @permission_required("manage_appointments")
    def search_book_appointment():

        doctors = execute_query(
            """
            SELECT id, full_name, specialty
            FROM doctors
            WHERE is_active = 1
            ORDER BY full_name
            """,
            fetchall=True
        )

        patients = execute_query(
            """
            SELECT id,
                   first_name,
                   middle_name,
                   last_name,
                   phone_number
            FROM patients
            WHERE is_active = 1
            ORDER BY last_name, first_name
            """,
            fetchall=True
        )

        medical_centers = execute_query(
            """
            SELECT id, center_name
            FROM medical_centers
            WHERE is_active = 1
            ORDER BY center_name
            """,
            fetchall=True
        )

        selected_doctor = request.args.get("doctor_id")
        selected_center = request.args.get("center_id") or "all"
        selected_date = request.args.get("slot_date")
        selected_notes = request.args.get("notes", "").strip()
        search_mode = request.args.get("search_mode", "earliest")
        selected_doctor_name = ""

        for doctor in doctors:
            if str(selected_doctor or "") == str(doctor["id"]):
                selected_doctor_name = doctor["full_name"]
                break

        slots = []

        if selected_doctor:

            if search_mode == "earliest":

                query = """
                    SELECT
                        aps.id,
                        aps.slot_date,
                        aps.start_time,
                        aps.end_time,
                        mc.center_name
                    FROM appointment_slots aps
                    JOIN medical_centers mc
                        ON aps.center_id = mc.id
                    WHERE aps.doctor_id = %s
                      AND aps.status = 'available'
                      AND aps.slot_date >= CURDATE()
                """
                params = [selected_doctor]

                if selected_center != "all":
                    query += " AND aps.center_id = %s"
                    params.append(selected_center)

                query += """
                    ORDER BY aps.slot_date,
                             aps.start_time
                    LIMIT 30
                """

                slots = execute_query(
                    query,
                    tuple(params),
                    fetchall=True
                )

            else:

                query = """
                    SELECT
                        aps.id,
                        aps.slot_date,
                        aps.start_time,
                        aps.end_time,
                        mc.center_name
                    FROM appointment_slots aps
                    JOIN medical_centers mc
                        ON aps.center_id = mc.id
                    WHERE aps.doctor_id = %s
                      AND aps.slot_date = %s
                      AND aps.status = 'available'
                """
                params = [selected_doctor, selected_date]

                if selected_center != "all":
                    query += " AND aps.center_id = %s"
                    params.append(selected_center)

                query += """
                    ORDER BY aps.start_time
                """

                slots = execute_query(
                    query,
                    tuple(params),
                    fetchall=True
                )

        return render_template(
            "search_book_appointment.html",
            doctors=doctors,
            medical_centers=medical_centers,
            patients=patients,
            slots=slots,
            selected_doctor=selected_doctor,
            selected_doctor_name=selected_doctor_name,
            selected_center=selected_center,
            selected_date=selected_date,
            selected_notes=selected_notes,
            search_mode=search_mode
        )

    @app.route("/appointments/book/<int:slot_id>", methods=["POST"])
    @login_required
    @permission_required("manage_appointments")
    def book_appointment(slot_id):

        patient_id = request.form.get("patient_id")
        notes = request.form.get("notes", "").strip()

        slot = execute_query(
            """
            SELECT *
            FROM appointment_slots
            WHERE id = %s
              AND status = 'available'
            """,
            (slot_id,),
            fetchone=True
        )

        if not slot:
            flash_t("Slot already booked or unavailable.", "error")
            return redirect(url_for("search_book_appointment"))

        existing = execute_query(
            """
            SELECT id
            FROM appointments
            WHERE slot_id = %s
            """,
            (slot_id,),
            fetchone=True
        )

        if existing:
            flash_t("This slot is already booked.", "error")
            return redirect(url_for("search_book_appointment"))

        execute_query(
            """
            INSERT INTO appointments
            (
                slot_id,
                patient_id,
                appointment_status,
                notes
            )
            VALUES (%s, %s, 'booked', %s)
            """,
            (
                slot_id,
                patient_id,
                notes
            )
        )

        execute_query(
            """
            UPDATE appointment_slots
            SET status = 'unavailable'
            WHERE id = %s
            """,
            (slot_id,)
        )

        flash_t("Appointment booked successfully.", "success")

        return redirect(url_for("search_book_appointment"))

    @app.route("/appointments/search_cancel", methods=["GET"])
    @login_required
    @permission_required("search_cancel_appointment")
    def search_cancel_appointment():

        search = request.args.get("search", "").strip()

        appointments = []

        if search:

            like_search = f"%{search}%"

            appointments = execute_query(
                """
                SELECT
                    a.id,
                    a.slot_id,
                    a.patient_id,
                    a.appointment_status,

                    aps.slot_date,
                    aps.start_time,

                    d.full_name AS doctor_name,
                    mc.center_name,

                    p.first_name,
                    p.middle_name,
                    p.last_name,
                    p.phone_number

                FROM appointments a

                JOIN appointment_slots aps
                    ON a.slot_id = aps.id

                JOIN doctors d
                    ON aps.doctor_id = d.id

                JOIN medical_centers mc
                    ON aps.center_id = mc.id

                JOIN patients p
                    ON a.patient_id = p.id

                WHERE
                    (
                        p.first_name LIKE %s
                        OR p.middle_name LIKE %s
                        OR p.last_name LIKE %s
                        OR p.phone_number LIKE %s
                    )
                    AND a.appointment_status = 'booked'

                ORDER BY aps.slot_date,
                         aps.start_time
                """,
                (
                    like_search,
                    like_search,
                    like_search,
                    like_search
                ),
                fetchall=True
            )

        return render_template(
            "search_cancel_appointment.html",
            appointments=appointments,
            search=search
        )
    @app.route("/appointments/cancel/<int:appointment_id>", methods=["POST"])
    @login_required
    @permission_required("search_cancel_appointment")
    def cancel_appointment(appointment_id):

        appointment = execute_query(
            """
            SELECT *
            FROM appointments
            WHERE id = %s
              AND appointment_status = 'booked'
            """,
            (appointment_id,),
            fetchone=True
        )

        if not appointment:
            flash_t("Appointment already cancelled.", "error")
            return redirect(url_for("search_cancel_appointment"))

        execute_query(
            """
            UPDATE appointments
            SET appointment_status = 'cancelled',
                cancelled_at = NOW()
            WHERE id = %s
            """,
            (appointment_id,)
        )

        execute_query(
            """
            UPDATE appointment_slots
            SET status = 'available'
            WHERE id = %s
            """,
            (appointment["slot_id"],)
        )

        flash_t("Appointment cancelled successfully.", "success")

        return redirect(url_for(
            "search_cancel_appointment",
            search=request.form.get("search", "")
        ))

    @app.route("/appointments/doctor_appointments", methods=["GET"])
    @login_required
    @permission_required("doctor_appointments")
    def doctor_appointments():

        doctors = execute_query(
            """
            SELECT id,
                   full_name,
                   specialty
            FROM doctors
            WHERE is_active = 1
            ORDER BY full_name
            """,
            fetchall=True
        )

        doctor_id = request.args.get("doctor_id")
        search_mode = request.args.get("search_mode", "today")

        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")

        appointments = []

        if doctor_id:

            if search_mode == "today":

                appointments = execute_query(
                    """
                    SELECT
                        a.id,

                        aps.slot_date,
                        aps.start_time,
                        aps.end_time,

                        mc.center_name,

                        p.first_name,
                        p.middle_name,
                        p.last_name,
                        p.phone_number,

                        a.appointment_status

                    FROM appointments a

                    JOIN appointment_slots aps
                        ON a.slot_id = aps.id

                    JOIN medical_centers mc
                        ON aps.center_id = mc.id

                    JOIN patients p
                        ON a.patient_id = p.id

                    WHERE aps.doctor_id = %s
                      AND aps.slot_date = CURDATE()

                    ORDER BY aps.start_time
                    """,
                    (doctor_id,),
                    fetchall=True
                )

            else:

                appointments = execute_query(
                    """
                    SELECT
                        a.id,

                        aps.slot_date,
                        aps.start_time,
                        aps.end_time,

                        mc.center_name,

                        p.first_name,
                        p.middle_name,
                        p.last_name,
                        p.phone_number,

                        a.appointment_status

                    FROM appointments a

                    JOIN appointment_slots aps
                        ON a.slot_id = aps.id

                    JOIN medical_centers mc
                        ON aps.center_id = mc.id

                    JOIN patients p
                        ON a.patient_id = p.id

                    WHERE aps.doctor_id = %s
                      AND aps.slot_date BETWEEN %s AND %s

                    ORDER BY aps.slot_date,
                             aps.start_time
                    """,
                    (
                        doctor_id,
                        from_date,
                        to_date
                    ),
                    fetchall=True
                )

        return render_template(
            "doctor_appointments.html",
            doctors=doctors,
            appointments=appointments,
            doctor_id=doctor_id,
            search_mode=search_mode,
            from_date=from_date,
            to_date=to_date
        )
