from flask import flash, redirect, render_template, request, url_for

from auth import login_required, permission_required
from database import execute_query


def register_doctor_specialty_routes(app):
    def specialty_code_exists(specialty_code, exclude_specialty_id=None):
        if exclude_specialty_id:
            return execute_query(
                """
                SELECT id
                FROM doctor_specialties
                WHERE LOWER(specialty_code) = LOWER(%s)
                  AND id <> %s
                """,
                (specialty_code, exclude_specialty_id),
                fetchone=True
            )

        return execute_query(
            """
            SELECT id
            FROM doctor_specialties
            WHERE LOWER(specialty_code) = LOWER(%s)
            """,
            (specialty_code,),
            fetchone=True
        )

    def specialty_name_exists(
        specialty_name,
        classification_system,
        exclude_specialty_id=None
    ):
        if exclude_specialty_id:
            return execute_query(
                """
                SELECT id
                FROM doctor_specialties
                WHERE LOWER(specialty_name) = LOWER(%s)
                  AND LOWER(classification_system) = LOWER(%s)
                  AND id <> %s
                """,
                (specialty_name, classification_system, exclude_specialty_id),
                fetchone=True
            )

        return execute_query(
            """
            SELECT id
            FROM doctor_specialties
            WHERE LOWER(specialty_name) = LOWER(%s)
              AND LOWER(classification_system) = LOWER(%s)
            """,
            (specialty_name, classification_system),
            fetchone=True
        )

    @app.route("/clinic/doctor_specialties", methods=["GET", "POST"])
    @login_required
    @permission_required("doctor_specialties")
    def doctor_specialties():
        if request.method == "POST":
            specialty_code = request.form.get("specialty_code", "").strip()
            specialty_name = request.form.get("specialty_name", "").strip()
            specialty_group = request.form.get("specialty_group", "").strip()
            classification_system = request.form.get(
                "classification_system",
                "ABMS/ACGME"
            ).strip()
            description = request.form.get("description", "").strip()

            if not specialty_code or not specialty_name or not classification_system:
                flash("Specialty code, name, and classification system are required.", "error")
                return redirect(url_for("doctor_specialties"))

            if specialty_code_exists(specialty_code):
                flash("Specialty code already exists.", "error")
                return redirect(url_for("doctor_specialties"))

            if specialty_name_exists(specialty_name, classification_system):
                flash("Specialty already exists in this classification system.", "error")
                return redirect(url_for("doctor_specialties"))

            execute_query(
                """
                INSERT INTO doctor_specialties
                (
                    specialty_code,
                    specialty_name,
                    specialty_group,
                    classification_system,
                    description,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s, 1)
                """,
                (
                    specialty_code,
                    specialty_name,
                    specialty_group or None,
                    classification_system,
                    description or None
                )
            )

            flash("Doctor speciality added successfully.", "success")
            return redirect(url_for("doctor_specialties"))

        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        specialties = execute_query(
            """
            SELECT
                id,
                specialty_code,
                specialty_name,
                specialty_group,
                classification_system,
                description,
                is_active
            FROM doctor_specialties
            WHERE specialty_code LIKE %s
               OR specialty_name LIKE %s
               OR specialty_group LIKE %s
               OR classification_system LIKE %s
            ORDER BY
                classification_system,
                specialty_group,
                specialty_name
            """,
            (like_search, like_search, like_search, like_search),
            fetchall=True
        )

        classification_systems = execute_query(
            """
            SELECT DISTINCT classification_system
            FROM doctor_specialties
            WHERE classification_system IS NOT NULL
              AND TRIM(classification_system) <> ''
            ORDER BY classification_system
            """,
            fetchall=True
        )

        specialty_groups = execute_query(
            """
            SELECT DISTINCT specialty_group
            FROM doctor_specialties
            WHERE specialty_group IS NOT NULL
              AND TRIM(specialty_group) <> ''
            ORDER BY specialty_group
            """,
            fetchall=True
        )

        return render_template(
            "doctor_specialties.html",
            specialties=specialties,
            classification_systems=classification_systems,
            specialty_groups=specialty_groups,
            search=search
        )

    @app.route("/clinic/doctor_specialties/update/<int:specialty_id>", methods=["POST"])
    @login_required
    @permission_required("doctor_specialties")
    def update_doctor_specialty(specialty_id):
        specialty_code = request.form.get("specialty_code", "").strip()
        specialty_name = request.form.get("specialty_name", "").strip()
        specialty_group = request.form.get("specialty_group", "").strip()
        classification_system = request.form.get(
            "classification_system",
            "ABMS/ACGME"
        ).strip()
        description = request.form.get("description", "").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if not specialty_code or not specialty_name or not classification_system:
            flash("Specialty code, name, and classification system are required.", "error")
            return redirect(url_for("doctor_specialties"))

        if specialty_code_exists(specialty_code, specialty_id):
            flash("Specialty code already exists.", "error")
            return redirect(url_for("doctor_specialties"))

        if specialty_name_exists(specialty_name, classification_system, specialty_id):
            flash("Specialty already exists in this classification system.", "error")
            return redirect(url_for("doctor_specialties"))

        execute_query(
            """
            UPDATE doctor_specialties
            SET specialty_code = %s,
                specialty_name = %s,
                specialty_group = %s,
                classification_system = %s,
                description = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                specialty_code,
                specialty_name,
                specialty_group or None,
                classification_system,
                description or None,
                is_active,
                specialty_id
            )
        )

        flash("Doctor speciality updated successfully.", "success")
        return redirect(url_for("doctor_specialties"))

    @app.route("/clinic/doctor_specialties/stop/<int:specialty_id>", methods=["POST"])
    @login_required
    @permission_required("doctor_specialties")
    def stop_doctor_specialty(specialty_id):
        execute_query(
            """
            UPDATE doctor_specialties
            SET is_active = 0
            WHERE id = %s
            """,
            (specialty_id,)
        )

        flash("Doctor speciality deactivated.", "success")
        return redirect(url_for("doctor_specialties"))
