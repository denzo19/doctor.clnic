from flask import Flask, render_template, request, redirect, url_for, flash
from env_loader import load_env_file
from config import SECRET_KEY
from database import execute_query
from flask_bcrypt import Bcrypt
from flask import session
from datetime import date
import os
import uuid
import re
from auth import login_required, permission_required
from menu_helpers import build_user_menu
from i18n import language_direction, normalize_language, translate
from routes.lab_routes import register_lab_routes
from routes.prescription_routes import register_prescription_routes
from routes.admin_routes import register_admin_routes
from routes.patient_routes import register_patient_routes
from routes.medication_routes import register_medication_routes
from routes.employee_routes import register_employee_routes
from routes.medical_settings_routes import register_medical_settings_routes
from routes.appointment_routes import register_appointment_routes
from routes.id_card_routes import register_id_card_routes
from routes.doctor_specialty_routes import register_doctor_specialty_routes
from services.bootstrap_service import run_runtime_bootstrap

load_env_file(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
app.secret_key = SECRET_KEY

bcrypt = Bcrypt(app)

def get_logged_doctor_id():
    employee_id = session.get("employee_id")
    user_id = session.get("user_id")

    if not employee_id and not user_id:
        return None

    doctor = execute_query(
        """
        SELECT d.id
        FROM doctors d
        LEFT JOIN employees e
            ON e.id = %s
        LEFT JOIN users u
            ON u.id = %s
        WHERE (
                LOWER(d.email) = LOWER(e.email)
             OR LOWER(d.email) = LOWER(u.email)
             OR LOWER(d.email) = LOWER(u.username)
             OR LOWER(d.full_name) = LOWER(u.full_name)
             OR LOWER(d.full_name) = LOWER(e.full_name)
        )
          AND d.is_active = 1
        ORDER BY d.id
        LIMIT 1
        """,
        (employee_id, user_id),
        fetchone=True
    )

    return doctor["id"] if doctor else None


def is_logged_doctor_user():
    group_id = session.get("group_id")

    if not group_id:
        return False

    group = execute_query(
        """
        SELECT group_name
        FROM user_groups
        WHERE id = %s
          AND is_active = 1
        """,
        (group_id,),
        fetchone=True
    )

    if not group:
        return False

    return group["group_name"].strip().lower() in ("doctors", "doctor", "doctord")


def get_active_icd_version():
    return execute_query(
        """
        SELECT id, version_year
        FROM icd_versions
        WHERE is_active = 1
        ORDER BY version_year DESC, id DESC
        LIMIT 1
        """,
        fetchone=True
    )


def get_doctor_specialty(doctor_id):
    if not doctor_id:
        return None

    doctor = execute_query(
        """
        SELECT specialty
        FROM doctors
        WHERE id = %s
        """,
        (doctor_id,),
        fetchone=True
    )

    return doctor["specialty"] if doctor and doctor["specialty"] else None


def clean_icd_display_name(name):
    if not name:
        return ""

    return re.sub(
        r"\s*\([A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]+)?(?:-[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]+)?)?\)\s*$",
        "",
        str(name)
    ).strip()


def flash_t(message, category="success"):
    flash(translate(message, session.get("language", "en")), category)


def get_visit_diagnosis_choices(doctor_id):
    specialty = get_doctor_specialty(doctor_id)
    active_version = get_active_icd_version()

    if not specialty or not active_version:
        return specialty, [], {}

    blocks = execute_query(
        """
        SELECT DISTINCT
            b.id,
            ch.chapter_code,
            ch.title AS chapter_title,
            b.block_code_range,
            b.title,
            ch.display_order AS chapter_order,
            b.display_order AS block_order
        FROM specialty_icd_enabled_items sei
        JOIN icd_blocks b
            ON b.id = sei.item_id
           AND sei.item_type = 'block'
        JOIN icd_chapters ch
            ON ch.id = b.chapter_id
        WHERE sei.version_id = %s
          AND sei.specialty = %s
          AND b.is_active = 1
        ORDER BY chapter_order, block_order, b.block_code_range
        """,
        (active_version["id"], specialty),
        fetchall=True
    )

    for block in blocks:
        block["display_title"] = clean_icd_display_name(block["title"])

    block_ids = [block["id"] for block in blocks]
    if not block_ids:
        return specialty, [], {}

    enabled_codes = execute_query(
        """
        SELECT
            c.id,
            c.code,
            c.description,
            cat.block_id
        FROM specialty_icd_enabled_items sei
        JOIN icd_codes c
            ON c.id = sei.item_id
           AND sei.item_type = 'code'
        JOIN icd_categories cat
            ON cat.id = c.category_id
        WHERE sei.version_id = %s
          AND sei.specialty = %s
          AND c.is_active = 1
        ORDER BY cat.display_order, c.code
        """,
        (active_version["id"], specialty),
        fetchall=True
    )

    enabled_categories = execute_query(
        """
        SELECT
            cat.id,
            cat.category_code,
            cat.title,
            cat.block_id
        FROM specialty_icd_enabled_items sei
        JOIN icd_categories cat
            ON cat.id = sei.item_id
           AND sei.item_type = 'category'
        WHERE sei.version_id = %s
          AND sei.specialty = %s
          AND cat.is_active = 1
        ORDER BY cat.display_order, cat.category_code
        """,
        (active_version["id"], specialty),
        fetchall=True
    )

    options_by_block = {str(block_id): [] for block_id in block_ids}

    for code in enabled_codes:
        block_key = str(code["block_id"])
        if block_key in options_by_block:
            options_by_block[block_key].append({
                "value": f"code:{code['id']}",
                "label": clean_icd_display_name(code["description"]),
                "item_type": "code",
                "item_id": code["id"]
            })

    for category in enabled_categories:
        block_key = str(category["block_id"])
        if block_key in options_by_block:
            options_by_block[block_key].append({
                "value": f"category:{category['id']}",
                "label": clean_icd_display_name(category["title"]),
                "item_type": "category",
                "item_id": category["id"]
            })

    missing_detail_block_ids = [
        block_id for block_id in block_ids
        if not options_by_block.get(str(block_id))
    ]

    if missing_detail_block_ids:
        placeholders = ", ".join(["%s"] * len(missing_detail_block_ids))
        fallback_categories = execute_query(
            f"""
            SELECT
                id,
                category_code,
                title,
                block_id
            FROM icd_categories
            WHERE block_id IN ({placeholders})
              AND is_active = 1
            ORDER BY block_id, display_order, category_code
            """,
            tuple(missing_detail_block_ids),
            fetchall=True
        )

        for category in fallback_categories:
            options_by_block[str(category["block_id"])].append({
                "value": f"category:{category['id']}",
                "label": clean_icd_display_name(category["title"]),
                "item_type": "category",
                "item_id": category["id"]
            })

    return specialty, blocks, options_by_block


def resolve_visit_diagnosis(diagnosis_block_id, diagnosis_item_value):
    if not diagnosis_block_id or not diagnosis_item_value:
        return {
            "diagnosis": "",
            "diagnosis_block_label": None,
            "diagnosis_item_type": None,
            "diagnosis_item_id": None,
            "diagnosis_name": None
        }

    block = execute_query(
        """
        SELECT
            b.id,
            ch.chapter_code,
            b.block_code_range,
            b.title
        FROM icd_blocks b
        JOIN icd_chapters ch
            ON ch.id = b.chapter_id
        WHERE b.id = %s
        """,
        (diagnosis_block_id,),
        fetchone=True
    )

    if not block or ":" not in diagnosis_item_value:
        return {
            "diagnosis": "",
            "diagnosis_block_label": None,
            "diagnosis_item_type": None,
            "diagnosis_item_id": None,
            "diagnosis_name": None
        }

    diagnosis_item_type, item_id_text = diagnosis_item_value.split(":", 1)
    try:
        diagnosis_item_id = int(item_id_text)
    except ValueError:
        diagnosis_item_id = None

    diagnosis_name = None

    if diagnosis_item_type == "code" and diagnosis_item_id:
        code = execute_query(
            """
            SELECT code, description
            FROM icd_codes
            WHERE id = %s
            """,
            (diagnosis_item_id,),
            fetchone=True
        )
        if code:
            diagnosis_name = clean_icd_display_name(code["description"])
    elif diagnosis_item_type == "category" and diagnosis_item_id:
        category = execute_query(
            """
            SELECT category_code, title
            FROM icd_categories
            WHERE id = %s
            """,
            (diagnosis_item_id,),
            fetchone=True
        )
        if category:
            diagnosis_name = clean_icd_display_name(category["title"])
    else:
        diagnosis_item_type = None
        diagnosis_item_id = None

    if not diagnosis_name:
        diagnosis_item_type = None
        diagnosis_item_id = None

    diagnosis_block_label = clean_icd_display_name(block["title"])

    return {
        "diagnosis": (
            f"{diagnosis_block_label}: {diagnosis_name}"
            if diagnosis_name else diagnosis_block_label
        ),
        "diagnosis_block_label": diagnosis_block_label,
        "diagnosis_item_type": diagnosis_item_type,
        "diagnosis_item_id": diagnosis_item_id,
        "diagnosis_name": diagnosis_name
    }


def menu_option_name_exists(option_name, parent_id, exclude_id=None):
    if exclude_id:
        return execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = LOWER(%s)
              AND parent_id <=> %s
              AND id <> %s
            """,
            (option_name, parent_id, exclude_id),
            fetchone=True
        )

    return execute_query(
        """
        SELECT id
        FROM menu_options
        WHERE LOWER(option_name) = LOWER(%s)
          AND parent_id <=> %s
        """,
        (option_name, parent_id),
        fetchone=True
    )


@app.context_processor
def inject_user():
    user = {
        "username": session.get("username"),
        "full_name": session.get("full_name")
    } if "user_id" in session else None

    return dict(current_app_user=user)

@app.context_processor
def inject_menu():
    group_id = session.get("group_id")
    language = normalize_language(session.get("language", "en"))

    user_menu = build_user_menu(group_id, language) if group_id else []

    return dict(user_menu=user_menu)


@app.context_processor
def inject_language():
    language = normalize_language(session.get("language", "en"))

    return dict(
        current_language=language,
        current_direction=language_direction(language),
        t=lambda text: translate(text, language)
    )

@app.before_request
def bootstrap_runtime_menu_options():
    if request.endpoint in ("login", "logout", "static", "set_language"):
        return

    if "user_id" in session:
        run_runtime_bootstrap()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = execute_query(
            """
            SELECT *
            FROM users
            WHERE username = %s
              AND is_active = 1
            """,
            (username,),
            fetchone=True
        )

        if user and bcrypt.check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["group_id"] = user["group_id"]
            session["employee_id"] = user["employee_id"]

            execute_query(
                "UPDATE users SET last_login = NOW() WHERE id = %s",
                (user["id"],)
            )

            return redirect(url_for("home"))

        flash(translate(
            "Invalid username or password.",
            session.get("language", "en")
        ), "error")

    return render_template("login.html")


@app.route("/set_language/<language>")
def set_language(language):
    session["language"] = normalize_language(language)
    return redirect(request.referrer or url_for("home"))


@app.route("/logout")
def logout():
    selected_language = session.get("language", "en")
    session.clear()
    session["language"] = normalize_language(selected_language)
    return redirect(url_for("login"))

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        user = execute_query(
            """
            SELECT id, password_hash
            FROM users
            WHERE username = %s
              AND is_active = 1
            """,
            (username,),
            fetchone=True
        )

        if not user:
            flash(translate(
                "User not found or inactive.",
                session.get("language", "en")
            ), "error")
            return redirect(url_for("change_password"))

        if not bcrypt.check_password_hash(user["password_hash"], current_password):
            flash(translate(
                "Current password is incorrect.",
                session.get("language", "en")
            ), "error")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash(translate(
                "New passwords do not match.",
                session.get("language", "en")
            ), "error")
            return redirect(url_for("change_password"))

        new_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")

        execute_query(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, user["id"])
        )

        flash(translate(
            "Password changed successfully. Please login.",
            session.get("language", "en")
        ), "success")
        return redirect(url_for("login"))

    return render_template("change_password.html")

@app.route("/")
@login_required
def home():
    return render_template("home.html")

@app.route("/checked_in_patients")
def checked_in_patients():
    doctor_id = get_logged_doctor_id()

    if not doctor_id:
        doctor_id = request.args.get("doctor_id", type=int)

    doctors = execute_query(
        "SELECT id, full_name, specialty FROM doctors WHERE is_active = TRUE ORDER BY full_name",
        fetchall=True
    )

    patients = []

    if doctor_id:
        patients = execute_query(
            """
            SELECT 
                cii.id AS check_in_item_id,
                cii.status AS check_in_status,
                cii.check_in_type,
                cii.check_in_time,
                p.id AS patient_id,
                p.patient_code,
                p.first_name,
                p.middle_name,
                p.last_name,
                p.date_of_birth,
                p.gender,
                p.phone_number
            FROM check_in_items cii
            JOIN check_in_lists cil ON cii.check_in_list_id = cil.id
            JOIN patients p ON cii.patient_id = p.id
            WHERE cil.doctor_id = %s
              AND cil.list_date = CURDATE()
              AND cil.status = 'active'
              AND cii.status IN ('waiting', 'in_visit')
            ORDER BY cii.check_in_time ASC
            """,
            (doctor_id,),
            fetchall=True
        )

    return render_template(
        "checked_in_patients.html",
        doctors=doctors,
        patients=patients,
        doctor_id=doctor_id
    )



@app.route("/patient/<int:patient_id>")
def patient_details(patient_id):
    doctor_id = request.args.get("doctor_id", type=int)
    selected_lab_test_id = request.args.get("lab_test_id", type=int)

    patient = execute_query(
        "SELECT * FROM patients WHERE id = %s",
        (patient_id,),
        fetchone=True
    )

    diseases = execute_query(
        """
        SELECT pd.id, dl.disease_name, dl.disease_category,
               pd.diagnosis_date, pd.status, pd.notes
        FROM patient_diseases pd
        JOIN disease_list dl ON pd.disease_id = dl.id
        WHERE pd.patient_id = %s
        ORDER BY pd.diagnosis_date DESC
        """,
        (patient_id,),
        fetchall=True
    )

    medications = execute_query(
        """
        SELECT 
            pm.id,
            m.medication_name,
            m.strength,
            m.dosage_form,
            pm.dose,
            pm.frequency,
            pm.start_date,
            pm.end_date,
            pm.notes,
            COALESCE(pm.prescription_status, 'draft') AS prescription_status
        FROM patient_medications pm
        JOIN medications m ON pm.medication_id = m.id
        WHERE pm.patient_id = %s
          AND COALESCE(pm.prescription_status, 'draft') = 'active'
        ORDER BY pm.start_date DESC, pm.id DESC
        """,
        (patient_id,),
        fetchall=True
    )

    vital_signs = execute_query(
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
            DATE_FORMAT(mdate, '%Y-%m-%d') AS mdate
        FROM vital_signs
        WHERE patient_id = %s
        ORDER BY mdate DESC, id DESC
        """,
        (patient_id,),
        fetchall=True
    )

    lab_test_options = execute_query(
        """
        SELECT DISTINCT
            lt.id,
            lt.test_name,
            lt.category
        FROM patient_lab_results plr
        JOIN lab_tests lt ON plr.test_id = lt.id
        WHERE plr.patient_id = %s
          AND plr.order_status = 'completed'
        ORDER BY lt.test_name, lt.category
        """,
        (patient_id,),
        fetchall=True
    )

    lab_result_filters = [
        "plr.patient_id = %s",
        "plr.order_status = 'completed'"
    ]
    lab_result_params = [patient_id]

    if selected_lab_test_id:
        lab_result_filters.append("plr.test_id = %s")
        lab_result_params.append(selected_lab_test_id)

    lab_results = execute_query(
        """
        SELECT plr.id,
            lt.test_name,
            lt.category,
            lt.loinc_code,
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
            END AS normal_range,
            plr.result_value,
            CASE
                WHEN lt.normal_high IS NOT NULL
                     AND CAST(
                        CASE
                            WHEN plr.result_value REGEXP '^-?[0-9]+([.,][0-9]+)?$'
                            THEN REPLACE(plr.result_value, ',', '.')
                            ELSE NULL
                        END AS DECIMAL(10,2)
                     ) > lt.normal_high
                    THEN 'High'
                WHEN lt.normal_low IS NOT NULL
                     AND CAST(
                        CASE
                            WHEN plr.result_value REGEXP '^-?[0-9]+([.,][0-9]+)?$'
                            THEN REPLACE(plr.result_value, ',', '.')
                            ELSE NULL
                        END AS DECIMAL(10,2)
                     ) < lt.normal_low
                    THEN 'Low'
                ELSE ''
            END AS result_level,
            plr.result_date,
            plr.notes,
            COALESCE(plr.order_status, 'draft') AS order_status
        FROM patient_lab_results plr
        JOIN lab_tests lt ON plr.test_id = lt.id
        WHERE """ + " AND ".join(lab_result_filters) + """
        ORDER BY plr.result_date DESC, plr.id DESC
        """,
        tuple(lab_result_params),
        fetchall=True
    )

    visit_reports = execute_query(
    """
        SELECT id,
            patient_id,
            visit_date,
            chief_complaint,
            diagnosis,
            treatment_plan,
            doctor_notes,
            visit_status
        FROM visit_reports
        WHERE patient_id = %s
        ORDER BY visit_date DESC, id DESC
        """,
        (patient_id,),
        fetchall=True
    )

    active_check_in = execute_query(
        """
        SELECT cii.id
        FROM check_in_items cii
        JOIN check_in_lists cil ON cii.check_in_list_id = cil.id
        WHERE cii.patient_id = %s
        AND cil.list_date = CURDATE()
        AND cil.status = 'active'
        AND cii.status IN ('waiting', 'in_visit')
        ORDER BY cii.check_in_time DESC
        LIMIT 1
        """,
        (patient_id,),
        fetchone=True
    )
    return render_template(
        "patient_details.html",
        patient=patient,
        diseases=diseases,
        medications=medications,
        vital_signs=vital_signs,
        lab_test_options=lab_test_options,
        selected_lab_test_id=selected_lab_test_id,
        lab_results=lab_results,
        visit_reports=visit_reports,
        active_check_in=active_check_in,
        doctor_id=doctor_id
    )

@app.route("/patients/history", methods=["GET"])
@login_required
@permission_required("patient_history")
def patient_history():
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
        ORDER BY last_name, first_name, patient_code
        """,
        fetchall=True
    )

    return render_template(
        "patient_history.html",
        patients=patients
    )

@app.route("/patients/history/<int:patient_id>", methods=["GET"])
@login_required
@permission_required("patient_history")
def patient_history_details(patient_id):
    return patient_details(patient_id)

@app.route("/visit/<int:patient_id>", methods=["GET", "POST"])
def start_visit(patient_id):
    doctor_id = request.args.get("doctor_id", type=int)
    patient = execute_query(
        "SELECT * FROM patients WHERE id = %s",
        (patient_id,),
        fetchone=True
    )

    if request.method == "POST":
        check_in_item_id = request.form.get("check_in_item_id", type=int)

        save_type = request.form.get("save_type")
        visit_status = "final" if save_type == "final" else "draft"

        chief_complaint = request.form.get("chief_complaint")
        diagnosis_block_id = request.form.get("diagnosis_block_id", type=int)
        diagnosis_item_value = request.form.get("diagnosis_item_value", "").strip()
        resolved_diagnosis = resolve_visit_diagnosis(
            diagnosis_block_id,
            diagnosis_item_value
        )
        diagnosis = resolved_diagnosis["diagnosis"]
        treatment_plan = request.form.get("treatment_plan")
        doctor_notes = request.form.get("doctor_notes")

        execute_query(
            """
            INSERT INTO visit_reports
            (patient_id, visit_date, chief_complaint, diagnosis,
             diagnosis_block_id, diagnosis_block_label,
             diagnosis_item_type, diagnosis_item_id, diagnosis_name,
             treatment_plan, doctor_notes, visit_status, finalized_at)
            VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'final' THEN NOW() ELSE NULL END)
            """,
            (
                patient_id,
                chief_complaint,
                diagnosis,
                diagnosis_block_id,
                resolved_diagnosis["diagnosis_block_label"],
                resolved_diagnosis["diagnosis_item_type"],
                resolved_diagnosis["diagnosis_item_id"],
                resolved_diagnosis["diagnosis_name"],
                treatment_plan,
                doctor_notes,
                visit_status,
                visit_status
            )
        )

        if visit_status == "final" and check_in_item_id:
            execute_query(
                """
                UPDATE check_in_items
                SET status = 'completed'
                WHERE id = %s
                """,
                (check_in_item_id,)
            )

        flash_t("Visit saved successfully.", "success")
        doctor_id = request.form.get("doctor_id", type=int)

        return redirect(url_for(
            "patient_details",
            patient_id=patient_id,
            doctor_id=doctor_id
        ))

    check_in_item_id = request.args.get("check_in_item_id", type=int)
    doctor_specialty, diagnosis_blocks, diagnosis_options_by_block = (
        get_visit_diagnosis_choices(doctor_id)
    )

    return render_template(
        "visit.html",
        patient=patient,
        check_in_item_id=check_in_item_id,
        doctor_id=doctor_id,
        doctor_specialty=doctor_specialty,
        diagnosis_blocks=diagnosis_blocks,
        diagnosis_options_by_block=diagnosis_options_by_block
    )

@app.route("/patient/<int:patient_id>/add_medication", methods=["POST"])
def add_medication_to_patient(patient_id):
    medication_id = request.form.get("medication_id")
    dose = request.form.get("dose")
    frequency = request.form.get("frequency")

    execute_query(
        """
        INSERT INTO patient_medications
        (patient_id, medication_id, dose, frequency, start_date)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (patient_id, medication_id, dose, frequency)
    )

    return redirect(url_for("start_visit", patient_id=patient_id))

@app.route("/patient/<int:patient_id>/add_lab", methods=["POST"])
def add_lab_to_patient(patient_id):
    test_id = request.form.get("test_id")

    execute_query(
        """
        INSERT INTO patient_lab_results
        (patient_id, test_id, result_value, result_date, notes)
        VALUES (%s, %s, NULL, NOW(), 'Ordered')
        """,
        (patient_id, test_id)
    )

    return redirect(url_for("start_visit", patient_id=patient_id))

@app.route("/visit/edit/<int:visit_id>", methods=["GET", "POST"])
def edit_visit(visit_id):
    doctor_id = request.args.get("doctor_id", type=int)

    visit = execute_query(
        "SELECT * FROM visit_reports WHERE id = %s",
        (visit_id,),
        fetchone=True
    )

    if not visit:
        flash_t("Visit not found.", "error")
        return redirect(url_for("checked_in_patients"))

    if not doctor_id:
        doctor = execute_query(
            """
            SELECT cil.doctor_id
            FROM check_in_items cii
            JOIN check_in_lists cil ON cii.check_in_list_id = cil.id
            WHERE cii.patient_id = %s
              AND cil.list_date = CURDATE()
            ORDER BY cii.check_in_time DESC
            LIMIT 1
            """,
            (visit["patient_id"],),
            fetchone=True
        )
        doctor_id = doctor["doctor_id"] if doctor else None

    if visit["visit_status"] == "final":
        flash_t("This visit is finalized and cannot be modified.", "error")
        return redirect(url_for(
            "patient_details",
            patient_id=visit["patient_id"],
            doctor_id=doctor_id
        ))

    if request.method == "POST":
        save_type = request.form.get("save_type")
        visit_status = "final" if save_type == "final" else "draft"
        diagnosis_block_id = request.form.get("diagnosis_block_id", type=int)
        diagnosis_item_value = request.form.get("diagnosis_item_value", "").strip()
        resolved_diagnosis = resolve_visit_diagnosis(
            diagnosis_block_id,
            diagnosis_item_value
        )

        execute_query(
            """
            UPDATE visit_reports
            SET chief_complaint = %s,
                diagnosis = %s,
                diagnosis_block_id = %s,
                diagnosis_block_label = %s,
                diagnosis_item_type = %s,
                diagnosis_item_id = %s,
                diagnosis_name = %s,
                treatment_plan = %s,
                doctor_notes = %s,
                visit_status = %s,
                updated_at = NOW(),
                finalized_at = CASE WHEN %s = 'final' THEN NOW() ELSE finalized_at END
            WHERE id = %s
            """,
            (
                request.form.get("chief_complaint"),
                resolved_diagnosis["diagnosis"],
                diagnosis_block_id,
                resolved_diagnosis["diagnosis_block_label"],
                resolved_diagnosis["diagnosis_item_type"],
                resolved_diagnosis["diagnosis_item_id"],
                resolved_diagnosis["diagnosis_name"],
                request.form.get("treatment_plan"),
                request.form.get("doctor_notes"),
                visit_status,
                visit_status,
                visit_id
            )
        )

        if visit_status == "final":
            execute_query(
                """
                UPDATE check_in_items cii
                JOIN check_in_lists cil ON cii.check_in_list_id = cil.id
                SET cii.status = 'completed'
                WHERE cii.patient_id = %s
                  AND cil.list_date = CURDATE()
                  AND cil.status = 'active'
                  AND cii.status = 'in_visit'
                """,
                (visit["patient_id"],)
            )

        return redirect(url_for(
            "patient_details",
            patient_id=visit["patient_id"],
            doctor_id=doctor_id
        ))

    doctor_specialty, diagnosis_blocks, diagnosis_options_by_block = (
        get_visit_diagnosis_choices(doctor_id)
    )

    return render_template(
        "edit_visit.html",
        visit=visit,
        doctor_id=doctor_id,
        doctor_specialty=doctor_specialty,
        diagnosis_blocks=diagnosis_blocks,
        diagnosis_options_by_block=diagnosis_options_by_block
    )

@app.route("/visit/delete/<int:visit_id>", methods=["POST"])
def delete_visit(visit_id):
    doctor_id = request.args.get("doctor_id", type=int)
    visit = execute_query(
        "SELECT * FROM visit_reports WHERE id = %s",
        (visit_id,),
        fetchone=True
    )

    if visit["visit_status"] == "final":
        flash_t("Finalized visits cannot be deleted.", "error")
        return redirect(url_for(
                "patient_details",
                patient_id=visit["patient_id"],
                doctor_id=doctor_id
            ))

    execute_query(
        "DELETE FROM visit_reports WHERE id = %s",
        (visit_id,)
    )

    flash_t("Draft visit deleted successfully.", "success")
    return redirect(url_for(
            "patient_details",
            patient_id=visit["patient_id"],
            doctor_id=doctor_id
        ))

@app.route("/pharmacy")
def pharmacy():
    return render_template("pharmacy.html")


@app.route("/voice_search")
def voice_search():
    return render_template("voice_search.html")

@app.route("/secretary")
def secretary_dashboard():
    return redirect(url_for("checkin_lists"))

@app.route("/secretary/checkin_lists", methods=["GET"])
def checkin_lists():
    lists = execute_query(
        """
        SELECT 
            cil.id,
            cil.list_date,
            cil.status,
            cil.created_at,
            d.full_name AS doctor_name,
            d.specialty
        FROM check_in_lists cil
        JOIN doctors d ON cil.doctor_id = d.id
        WHERE cil.list_date = CURDATE()
        ORDER BY d.full_name
        """,
        fetchall=True
    )

    return render_template(
        "checkin_lists.html",
        lists=lists
    )

@app.route("/secretary/checkin_lists/<int:list_id>/patients", methods=["GET"])
def checkin_list_patients(list_id):
    checkin_list = execute_query(
        """
        SELECT
            cil.id,
            DATE_FORMAT(cil.list_date, '%Y-%m-%d') AS list_date,
            cil.status,
            d.full_name AS doctor_name,
            d.specialty
        FROM check_in_lists cil
        JOIN doctors d ON cil.doctor_id = d.id
        WHERE cil.id = %s
        """,
        (list_id,),
        fetchone=True
    )

    if not checkin_list:
        return {
            "success": False,
            "message": translate(
                "Check-in list not found.",
                session.get("language", "en")
            )
        }

    patients = execute_query(
        """
        SELECT
            cii.id,
            cii.check_in_type,
            cii.status,
            DATE_FORMAT(cii.check_in_time, '%Y-%m-%d %H:%i') AS check_in_time,
            cii.notes,
            p.patient_code,
            p.first_name,
            p.middle_name,
            p.last_name,
            DATE_FORMAT(p.date_of_birth, '%Y-%m-%d') AS date_of_birth,
            p.phone_number
        FROM check_in_items cii
        JOIN patients p ON cii.patient_id = p.id
        WHERE cii.check_in_list_id = %s
        ORDER BY cii.check_in_time, p.last_name, p.first_name
        """,
        (list_id,),
        fetchall=True
    )

    return {
        "success": True,
        "list": checkin_list,
        "patients": patients
    }
@app.route("/secretary/add_patient", methods=["GET", "POST"])
def secretary_add_patient():
    pass

def get_or_create_checkin_list(doctor_id, list_date=None):
    list_date = list_date or date.today().isoformat()

    execute_query(
        """
        INSERT INTO check_in_lists (doctor_id, list_date, status)
        VALUES (%s, %s, 'active')
        ON DUPLICATE KEY UPDATE
            status = 'active',
            closed_at = NULL
        """,
        (doctor_id, list_date)
    )

    return execute_query(
        """
        SELECT id
        FROM check_in_lists
        WHERE doctor_id = %s
          AND list_date = %s
        """,
        (doctor_id, list_date),
        fetchone=True
    )

@app.route("/secretary/appointment_checkin", methods=["GET"])
@login_required
@permission_required("appointment_checkin")
def appointment_checkin():
    search = request.args.get("search", "").strip()
    selected_patient_id = request.args.get("patient_id", type=int)
    selected_date = request.args.get("appointment_date")
    today_date = date.today().isoformat()
    is_doctor_user = is_logged_doctor_user()
    doctor_scope_id = get_logged_doctor_id() if is_doctor_user else None
    doctor_filter_id = doctor_scope_id if doctor_scope_id else (-1 if is_doctor_user else None)

    if not selected_date:
        selected_date = today_date

    like_search = f"%{search}%"
    can_check_in = selected_date == today_date

    appointment_patients = execute_query(
        """
        SELECT DISTINCT
            p.id,
            p.patient_code,
            p.first_name,
            p.middle_name,
            p.last_name,
            p.phone_number,
            CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS patient_name
        FROM appointments a
        JOIN appointment_slots aps
            ON a.slot_id = aps.id
        JOIN patients p
            ON a.patient_id = p.id
        WHERE aps.slot_date = %s
          AND a.appointment_status = 'booked'
          AND (%s IS NULL OR aps.doctor_id = %s)
        ORDER BY p.last_name, p.first_name, p.patient_code
        """,
        (selected_date, doctor_filter_id, doctor_filter_id),
        fetchall=True
    )

    appointments = execute_query(
        """
        SELECT
            a.id AS appointment_id,
            a.patient_id,
            a.notes AS appointment_notes,
            aps.doctor_id,
            DATE_FORMAT(aps.slot_date, '%Y-%m-%d') AS slot_date,
            TIME_FORMAT(aps.start_time, '%H:%i') AS start_time,
            TIME_FORMAT(aps.end_time, '%H:%i') AS end_time,
            d.full_name AS doctor_name,
            d.specialty AS doctor_specialty,
            mc.center_name,
            p.patient_code,
            p.first_name,
            p.middle_name,
            p.last_name,
            p.date_of_birth,
            p.phone_number,
            cii.id AS check_in_item_id,
            cii.status AS check_in_status,
            cii.check_in_time
        FROM appointments a
        JOIN appointment_slots aps
            ON a.slot_id = aps.id
        JOIN doctors d
            ON aps.doctor_id = d.id
        JOIN medical_centers mc
            ON aps.center_id = mc.id
        JOIN patients p
            ON a.patient_id = p.id
        LEFT JOIN check_in_lists cil
            ON cil.doctor_id = aps.doctor_id
           AND cil.list_date = aps.slot_date
        LEFT JOIN check_in_items cii
            ON cii.check_in_list_id = cil.id
           AND cii.patient_id = p.id
        WHERE aps.slot_date = %s
          AND a.appointment_status = 'booked'
          AND (%s IS NULL OR aps.doctor_id = %s)
          AND (%s IS NULL OR p.id = %s)
          AND (
                p.patient_code LIKE %s
             OR p.first_name LIKE %s
             OR p.middle_name LIKE %s
             OR p.last_name LIKE %s
             OR CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) LIKE %s
             OR p.phone_number LIKE %s
          )
        ORDER BY aps.start_time, d.full_name, p.last_name, p.first_name
        """,
        (
            selected_date,
            doctor_filter_id,
            doctor_filter_id,
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

    return render_template(
        "appointment_checkin.html",
        appointments=appointments,
        search=search,
        selected_patient_id=selected_patient_id,
        selected_date=selected_date,
        today_date=today_date,
        can_check_in=can_check_in,
        appointment_patients=appointment_patients
    )

@app.route("/secretary/appointment_checkin/checkin/<int:appointment_id>", methods=["POST"])
@login_required
@permission_required("appointment_checkin")
def checkin_appointment_patient(appointment_id):
    search = request.form.get("search", "").strip()
    selected_patient_id = request.form.get("patient_id", type=int)
    today_date = date.today().isoformat()
    selected_date = request.form.get("appointment_date") or today_date
    is_doctor_user = is_logged_doctor_user()
    doctor_scope_id = get_logged_doctor_id() if is_doctor_user else None
    doctor_filter_id = doctor_scope_id if doctor_scope_id else (-1 if is_doctor_user else None)

    redirect_args = {}
    if search:
        redirect_args["search"] = search
    if selected_patient_id:
        redirect_args["patient_id"] = selected_patient_id
    redirect_args["appointment_date"] = selected_date

    if selected_date != today_date:
        flash_t("Only today's appointments can be checked in.", "error")
        return redirect(url_for("appointment_checkin", **redirect_args))

    appointment = execute_query(
        """
        SELECT
            a.id,
            a.patient_id,
            a.notes,
            aps.doctor_id,
            DATE_FORMAT(aps.slot_date, '%Y-%m-%d') AS slot_date
        FROM appointments a
        JOIN appointment_slots aps
            ON a.slot_id = aps.id
        WHERE a.id = %s
          AND aps.slot_date = %s
          AND a.appointment_status = 'booked'
          AND (%s IS NULL OR aps.doctor_id = %s)
        """,
        (appointment_id, selected_date, doctor_filter_id, doctor_filter_id),
        fetchone=True
    )

    if not appointment:
        flash_t("Appointment not found for today's booked appointments.", "error")
        return redirect(url_for("appointment_checkin", **redirect_args))

    check_list = get_or_create_checkin_list(
        appointment["doctor_id"],
        appointment["slot_date"]
    )

    execute_query(
        """
        INSERT INTO check_in_items
        (
            check_in_list_id,
            patient_id,
            check_in_type,
            status,
            notes
        )
        VALUES
        (
            %s,
            %s,
            'appointment',
            'waiting',
            %s
        )
        ON DUPLICATE KEY UPDATE
            check_in_type = 'appointment',
            status = 'waiting',
            notes = VALUES(notes),
            check_in_time = CURRENT_TIMESTAMP
        """,
        (
            check_list["id"],
            appointment["patient_id"],
            appointment["notes"]
        )
    )

    flash_t("Appointment patient checked in successfully.", "success")
    return redirect(url_for("appointment_checkin", **redirect_args))

@app.route("/secretary/checkin", methods=["GET", "POST"])
@login_required
@permission_required("checkin_patient")
def checkin_patient():

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

    selected_doctor_id = request.args.get(
        "doctor_id",
        type=int
    )

    patients = execute_query(
        """
        SELECT
            id,
            patient_code,
            first_name,
            middle_name,
            last_name,
            date_of_birth,
            phone_number,
            NULL AS start_time,
            NULL AS center_name
        FROM patients
        WHERE is_active = 1
        ORDER BY last_name,
                 first_name
        """,
        fetchall=True
    )

    if selected_doctor_id:

        patients = execute_query(
            """
            SELECT
                p.id,
                p.patient_code,
                p.first_name,
                p.middle_name,
                p.last_name,
                p.date_of_birth,
                p.phone_number,

                today_appointments.start_time,
                today_appointments.center_name

            FROM patients p

            LEFT JOIN (
                SELECT
                    a.patient_id,
                    aps.start_time,
                    mc.center_name

                FROM appointments a

                JOIN appointment_slots aps
                    ON a.slot_id = aps.id

                JOIN medical_centers mc
                    ON aps.center_id = mc.id

                WHERE aps.doctor_id = %s
                  AND aps.slot_date = CURDATE()
                  AND a.appointment_status = 'booked'
            ) today_appointments
                ON today_appointments.patient_id = p.id

            WHERE p.is_active = 1

            ORDER BY
                CASE
                    WHEN today_appointments.start_time IS NULL
                    THEN 1
                    ELSE 0
                END,
                today_appointments.start_time,
                p.last_name,
                p.first_name
            """,
            (selected_doctor_id,),
            fetchall=True
        )

    if request.method == "POST":

        doctor_id = request.form.get("doctor_id")
        patient_id = request.form.get("patient_id")
        check_in_type = "walk_in"
        notes = request.form.get("notes")

        check_list = get_or_create_checkin_list(doctor_id)

        execute_query(
            """
            INSERT INTO check_in_items
            (
                check_in_list_id,
                patient_id,
                check_in_type,
                status,
                notes
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'waiting',
                %s
            )
            ON DUPLICATE KEY UPDATE
                check_in_type = VALUES(check_in_type),
                status = 'waiting',
                notes = VALUES(notes),
                check_in_time = CURRENT_TIMESTAMP
            """,
            (
                check_list["id"],
                patient_id,
                check_in_type,
                notes
            )
        )

        flash_t("Patient checked in successfully.", "success")

        return redirect(
            url_for(
                "checkin_patient",
                doctor_id=doctor_id
            )
        )

    checked_in = execute_query(
        """
        SELECT
            cii.id,
            cii.status,
            cii.check_in_type,
            cii.check_in_time,
            cii.notes,

            d.full_name AS doctor_name,

            p.patient_code,
            p.first_name,
            p.middle_name,
            p.last_name,
            p.date_of_birth,
            p.phone_number

        FROM check_in_items cii

        JOIN check_in_lists cil
            ON cii.check_in_list_id = cil.id

        JOIN doctors d
            ON cil.doctor_id = d.id

        JOIN patients p
            ON cii.patient_id = p.id

        WHERE cil.list_date = CURDATE()

        ORDER BY d.full_name,
                 cii.check_in_time
        """,
        fetchall=True
    )

    return render_template(
        "checkin_patient.html",
        doctors=doctors,
        patients=patients,
        checked_in=checked_in,
        selected_doctor_id=selected_doctor_id
    )

@app.route("/checked_in/open/<int:check_in_item_id>")
def open_checked_in_patient(check_in_item_id):

    item = execute_query(
        """
        SELECT
            cii.id,
            cii.patient_id,
            cil.doctor_id
        FROM check_in_items cii
        JOIN check_in_lists cil
            ON cii.check_in_list_id = cil.id
        WHERE cii.id = %s
        """,
        (check_in_item_id,),
        fetchone=True
    )

    if not item:
        flash_t("Check-in item not found.", "error")
        return redirect(url_for("checked_in_patients"))

    execute_query(
        """
        UPDATE check_in_items
        SET status = 'in_visit'
        WHERE id = %s
        """,
        (check_in_item_id,)
    )

    return redirect(
        url_for(
            "patient_details",
            patient_id=item["patient_id"],
            doctor_id=item["doctor_id"]
        )
    )

@app.route("/checked_in/complete/<int:check_in_item_id>", methods=["POST"])
def complete_checked_in_patient(check_in_item_id):
    execute_query(
        """
        UPDATE check_in_items
        SET status = 'completed'
        WHERE id = %s
        """,
        (check_in_item_id,)
    )

    flash_t("Patient visit marked as completed.", "success")
    return redirect(url_for("checked_in_patients"))

@app.route("/secretary/checkin_lists/clear/<int:doctor_id>", methods=["POST"])
def clear_checkin_list(doctor_id):
    pass

@app.route("/checked_in/order_test/<int:patient_id>", methods=["POST"])
def order_test(patient_id):
    doctor_id = request.form.get("doctor_id", type=int)

    test_id = request.form.get("test_id")
    result_date = request.form.get("result_date")
    notes = request.form.get("notes")
    save_type = request.form.get("save_type")

    order_status = "ordered" if save_type == "final" else "draft"
    lab_order_code = uuid.uuid4().hex

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

    flash_t("Lab test order saved successfully.", "success")
    return redirect(url_for("checked_in_patients", doctor_id=doctor_id))

register_appointment_routes(app)
register_medical_settings_routes(app)
register_employee_routes(app)
register_medication_routes(app, get_logged_doctor_id)
register_patient_routes(app)
register_admin_routes(app, bcrypt, menu_option_name_exists)
register_prescription_routes(app, get_logged_doctor_id)
register_lab_routes(app, get_logged_doctor_id)
register_id_card_routes(app)
register_doctor_specialty_routes(app)

if __name__ == "__main__":
    app.run(debug=True)
