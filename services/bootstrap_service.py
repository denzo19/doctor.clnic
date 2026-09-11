from database import execute_query
from menu_helpers import ensure_home_menu


_appointment_menu_bootstrapped = False
_extend_schedule_menu_bootstrapped = False
_patient_workflow_schema_bootstrapped = False
_lab_menu_bootstrapped = False
_lab_tests_schema_bootstrapped = False
_vital_signs_schema_bootstrapped = False
_lab_result_menu_bootstrapped = False
_medications_schema_bootstrapped = False
_doctor_medications_schema_bootstrapped = False
_medications_menu_bootstrapped = False
_doctor_favorite_medications_menu_bootstrapped = False
_checkin_walkin_menu_bootstrapped = False
_appointment_checkin_menu_bootstrapped = False
_manage_prescriptions_menu_bootstrapped = False
_patient_history_menu_bootstrapped = False
_id_card_schema_bootstrapped = False
_id_card_menu_bootstrapped = False
_icd_schema_bootstrapped = False
_icd_setup_menu_bootstrapped = False
_doctor_specialties_schema_bootstrapped = False
_doctor_specialties_menu_bootstrapped = False
_visit_diagnosis_schema_bootstrapped = False
_menu_translation_schema_bootstrapped = False

def ensure_column(table_name, column_name, ddl):
    existing_column = execute_query(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
        fetchone=True
    )

    if not existing_column:
        execute_query(ddl)


def ensure_menu_translation_schema():
    global _menu_translation_schema_bootstrapped

    if _menu_translation_schema_bootstrapped:
        return

    try:
        ensure_column(
            "menu_options",
            "option_name_ar",
            "ALTER TABLE menu_options ADD COLUMN option_name_ar VARCHAR(255) NULL AFTER option_name"
        )

        menu_translations = {
            "home": "الرئيسية",
            "manage_employees": "إدارة الموظفين",
            "manage_users": "إدارة المستخدمين",
            "manage_groups": "إدارة المجموعات",
            "manage_permissions": "إدارة الصلاحيات",
            "admin_menu_options": "إدارة القوائم",
            "patients": "إدارة المرضى",
            "checkin_patient": "تسجيل حضور المرضى",
            "appointment_checkin": "استعلام المواعيد وتسجيل الحضور",
            "checked_in_patients": "المرضى المسجل حضورهم",
            "checkin_lists": "قوائم الحضور",
            "patient_history": "المرضى غير المفحوصين",
            "manage_appointments": "إدارة المواعيد",
            "search_book_appointment": "بحث وحجز موعد",
            "search_cancel_appointment": "بحث وإلغاء موعد",
            "doctor_appointments": "مواعيد الطبيب",
            "manage_medical_centers": "إدارة المراكز الطبية",
            "manage_doctor_center_assignments": "ربط الأطباء بالمراكز",
            "manage_doctor_weekly_programs": "برنامج الطبيب الأسبوعي",
            "manage_doctor_absences": "غيابات الطبيب",
            "generate_appointment_slots": "إنشاء جدول المواعيد",
            "extend_schedule": "تمديد الجدول",
            "doctor_favorite_medications": "الأدوية المفضلة",
            "manage_prescriptions": "إدارة الوصفات",
            "medications": "الأدوية",
            "laboratory": "المختبر",
            "lab_results": "نتائج المختبر",
            "lab_tests": "الفحوصات المخبرية",
            "lab_order": "طلب فحص مخبري",
            "lab_result": "نتائج المختبر",
            "vital_signs": "العلامات الحيوية",
            "id_card": "بطاقة التعريف",
            "doctor_specialties": "اختصاصات الأطباء",
            "diagnosis_icd_setup": "إعداد تشخيصات ICD",
            "diagnosis_icd_fine_tuning": "ضبط تشخيصات ICD"
        }

        parent_translations = {
            "admin": "الإدارة",
            "basic setings": "الإعدادات الأساسية",
            "basic settings": "الإعدادات الأساسية",
            "clinic management": "إدارة العيادة",
            "secretary": "السكرتارية",
            "doctor": "الطبيب",
            "doctors": "الأطباء",
            "patients": "المرضى",
            "medications": "الأدوية",
            "lab & vital signs": "المختبر والعلامات الحيوية",
            "medical setings": "الإعدادات الطبية",
            "medical settings": "الإعدادات الطبية",
            "laboratory": "المختبر"
        }

        for endpoint_name, option_name_ar in menu_translations.items():
            execute_query(
                """
                UPDATE menu_options
                SET option_name_ar = %s
                WHERE endpoint_name = %s
                """,
                (option_name_ar, endpoint_name)
            )

        for option_name, option_name_ar in parent_translations.items():
            execute_query(
                """
                UPDATE menu_options
                SET option_name_ar = %s
                WHERE LOWER(option_name) = %s
                  AND endpoint_name IS NULL
                """,
                (option_name_ar, option_name)
            )

        _menu_translation_schema_bootstrapped = True

    except Exception as error:
        print("Menu translation schema bootstrap error:", error)

def ensure_patient_workflow_schema():
    global _patient_workflow_schema_bootstrapped

    if _patient_workflow_schema_bootstrapped:
        return

    try:
        ensure_column(
            "patient_medications",
            "prescription_status",
            "ALTER TABLE patient_medications ADD COLUMN prescription_status VARCHAR(20) NOT NULL DEFAULT 'draft'"
        )
        ensure_column(
            "patient_medications",
            "finalized_at",
            "ALTER TABLE patient_medications ADD COLUMN finalized_at DATETIME NULL"
        )
        ensure_column(
            "patient_medications",
            "stopped_at",
            "ALTER TABLE patient_medications ADD COLUMN stopped_at DATETIME NULL"
        )
        ensure_column(
            "patient_medications",
            "updated_at",
            "ALTER TABLE patient_medications ADD COLUMN updated_at DATETIME NULL"
        )
        ensure_column(
            "patient_medications",
            "doctor_id",
            "ALTER TABLE patient_medications ADD COLUMN doctor_id INT NULL"
        )
        ensure_column(
            "patient_medications",
            "prescription_order_code",
            "ALTER TABLE patient_medications ADD COLUMN prescription_order_code VARCHAR(36) NULL"
        )
        ensure_column(
            "patient_lab_results",
            "order_status",
            "ALTER TABLE patient_lab_results ADD COLUMN order_status VARCHAR(20) NOT NULL DEFAULT 'draft'"
        )
        ensure_column(
            "patient_lab_results",
            "finalized_at",
            "ALTER TABLE patient_lab_results ADD COLUMN finalized_at DATETIME NULL"
        )
        ensure_column(
            "patient_lab_results",
            "cancelled_at",
            "ALTER TABLE patient_lab_results ADD COLUMN cancelled_at DATETIME NULL"
        )
        ensure_column(
            "patient_lab_results",
            "updated_at",
            "ALTER TABLE patient_lab_results ADD COLUMN updated_at DATETIME NULL"
        )
        ensure_column(
            "patient_lab_results",
            "doctor_id",
            "ALTER TABLE patient_lab_results ADD COLUMN doctor_id INT NULL"
        )
        ensure_column(
            "patient_lab_results",
            "lab_order_code",
            "ALTER TABLE patient_lab_results ADD COLUMN lab_order_code VARCHAR(36) NULL"
        )
        ensure_column(
            "visit_reports",
            "visit_status",
            "ALTER TABLE visit_reports ADD COLUMN visit_status VARCHAR(20) NOT NULL DEFAULT 'draft'"
        )
        ensure_column(
            "visit_reports",
            "finalized_at",
            "ALTER TABLE visit_reports ADD COLUMN finalized_at DATETIME NULL"
        )
        ensure_column(
            "visit_reports",
            "updated_at",
            "ALTER TABLE visit_reports ADD COLUMN updated_at DATETIME NULL"
        )

        _patient_workflow_schema_bootstrapped = True

    except Exception as error:
        print("Patient workflow schema bootstrap error:", error)


def ensure_visit_diagnosis_schema():
    global _visit_diagnosis_schema_bootstrapped

    if _visit_diagnosis_schema_bootstrapped:
        return

    try:
        ensure_column(
            "visit_reports",
            "diagnosis_block_id",
            "ALTER TABLE visit_reports ADD COLUMN diagnosis_block_id INT NULL AFTER diagnosis"
        )
        ensure_column(
            "visit_reports",
            "diagnosis_block_label",
            "ALTER TABLE visit_reports ADD COLUMN diagnosis_block_label VARCHAR(300) NULL AFTER diagnosis_block_id"
        )
        ensure_column(
            "visit_reports",
            "diagnosis_item_type",
            "ALTER TABLE visit_reports ADD COLUMN diagnosis_item_type VARCHAR(20) NULL AFTER diagnosis_block_label"
        )
        ensure_column(
            "visit_reports",
            "diagnosis_item_id",
            "ALTER TABLE visit_reports ADD COLUMN diagnosis_item_id INT NULL AFTER diagnosis_item_type"
        )
        ensure_column(
            "visit_reports",
            "diagnosis_name",
            "ALTER TABLE visit_reports ADD COLUMN diagnosis_name VARCHAR(600) NULL AFTER diagnosis_item_id"
        )

        _visit_diagnosis_schema_bootstrapped = True

    except Exception as error:
        print("Visit diagnosis schema bootstrap error:", error)

def ensure_medications_schema():
    global _medications_schema_bootstrapped

    if _medications_schema_bootstrapped:
        return

    try:
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS medications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medication_name VARCHAR(255) NOT NULL,
                strength VARCHAR(100) NULL,
                dosage_form VARCHAR(100) NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_medication_name (medication_name)
            )
            """
        )

        ensure_column(
            "medications",
            "strength",
            "ALTER TABLE medications ADD COLUMN strength VARCHAR(100) NULL AFTER medication_name"
        )
        ensure_column(
            "medications",
            "dosage_form",
            "ALTER TABLE medications ADD COLUMN dosage_form VARCHAR(100) NULL AFTER strength"
        )
        ensure_column(
            "medications",
            "notes",
            "ALTER TABLE medications ADD COLUMN notes TEXT NULL AFTER dosage_form"
        )
        ensure_column(
            "medications",
            "is_active",
            "ALTER TABLE medications ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
        )
        ensure_column(
            "medications",
            "created_at",
            "ALTER TABLE medications ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )
        ensure_column(
            "medications",
            "updated_at",
            "ALTER TABLE medications ADD COLUMN updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP"
        )

        common_medications = [
            ("Acetaminophen", "500 mg", "Tablet"),
            ("Ibuprofen", "400 mg", "Tablet"),
            ("Naproxen", "250 mg", "Tablet"),
            ("Aspirin", "81 mg", "Tablet"),
            ("Amoxicillin", "500 mg", "Capsule"),
            ("Amoxicillin/Clavulanate", "875/125 mg", "Tablet"),
            ("Azithromycin", "250 mg", "Tablet"),
            ("Cephalexin", "500 mg", "Capsule"),
            ("Ciprofloxacin", "500 mg", "Tablet"),
            ("Doxycycline", "100 mg", "Capsule"),
            ("Metronidazole", "500 mg", "Tablet"),
            ("Clindamycin", "300 mg", "Capsule"),
            ("Trimethoprim/Sulfamethoxazole", "160/800 mg", "Tablet"),
            ("Nitrofurantoin", "100 mg", "Capsule"),
            ("Fluconazole", "150 mg", "Tablet"),
            ("Acyclovir", "400 mg", "Tablet"),
            ("Valacyclovir", "500 mg", "Tablet"),
            ("Lisinopril", "10 mg", "Tablet"),
            ("Losartan", "50 mg", "Tablet"),
            ("Amlodipine", "5 mg", "Tablet"),
            ("Hydrochlorothiazide", "25 mg", "Tablet"),
            ("Furosemide", "40 mg", "Tablet"),
            ("Metoprolol Tartrate", "50 mg", "Tablet"),
            ("Metoprolol Succinate", "50 mg", "Extended-Release Tablet"),
            ("Carvedilol", "6.25 mg", "Tablet"),
            ("Atenolol", "50 mg", "Tablet"),
            ("Diltiazem", "120 mg", "Extended-Release Capsule"),
            ("Verapamil", "120 mg", "Extended-Release Tablet"),
            ("Spironolactone", "25 mg", "Tablet"),
            ("Clonidine", "0.1 mg", "Tablet"),
            ("Atorvastatin", "20 mg", "Tablet"),
            ("Rosuvastatin", "10 mg", "Tablet"),
            ("Simvastatin", "20 mg", "Tablet"),
            ("Ezetimibe", "10 mg", "Tablet"),
            ("Metformin", "500 mg", "Tablet"),
            ("Metformin", "500 mg", "Extended-Release Tablet"),
            ("Glipizide", "5 mg", "Tablet"),
            ("Glyburide", "5 mg", "Tablet"),
            ("Pioglitazone", "30 mg", "Tablet"),
            ("Sitagliptin", "100 mg", "Tablet"),
            ("Empagliflozin", "10 mg", "Tablet"),
            ("Dapagliflozin", "10 mg", "Tablet"),
            ("Insulin Glargine", "100 units/mL", "Injection"),
            ("Insulin Lispro", "100 units/mL", "Injection"),
            ("Levothyroxine", "50 mcg", "Tablet"),
            ("Omeprazole", "20 mg", "Capsule"),
            ("Pantoprazole", "40 mg", "Tablet"),
            ("Famotidine", "20 mg", "Tablet"),
            ("Ondansetron", "4 mg", "Tablet"),
            ("Promethazine", "25 mg", "Tablet"),
            ("Loperamide", "2 mg", "Capsule"),
            ("Docusate Sodium", "100 mg", "Capsule"),
            ("Polyethylene Glycol", "17 g", "Powder"),
            ("Bisacodyl", "5 mg", "Tablet"),
            ("Cetirizine", "10 mg", "Tablet"),
            ("Loratadine", "10 mg", "Tablet"),
            ("Fexofenadine", "180 mg", "Tablet"),
            ("Diphenhydramine", "25 mg", "Capsule"),
            ("Fluticasone", "50 mcg/spray", "Nasal Spray"),
            ("Albuterol", "90 mcg/actuation", "Inhaler"),
            ("Budesonide/Formoterol", "160/4.5 mcg", "Inhaler"),
            ("Fluticasone/Salmeterol", "250/50 mcg", "Inhaler"),
            ("Montelukast", "10 mg", "Tablet"),
            ("Prednisone", "20 mg", "Tablet"),
            ("Methylprednisolone", "4 mg", "Tablet"),
            ("Hydrocortisone", "1%", "Cream"),
            ("Triamcinolone", "0.1%", "Cream"),
            ("Mupirocin", "2%", "Ointment"),
            ("Clotrimazole", "1%", "Cream"),
            ("Sertraline", "50 mg", "Tablet"),
            ("Fluoxetine", "20 mg", "Capsule"),
            ("Escitalopram", "10 mg", "Tablet"),
            ("Citalopram", "20 mg", "Tablet"),
            ("Paroxetine", "20 mg", "Tablet"),
            ("Venlafaxine", "75 mg", "Extended-Release Capsule"),
            ("Duloxetine", "30 mg", "Capsule"),
            ("Bupropion", "150 mg", "Extended-Release Tablet"),
            ("Trazodone", "50 mg", "Tablet"),
            ("Amitriptyline", "25 mg", "Tablet"),
            ("Gabapentin", "300 mg", "Capsule"),
            ("Pregabalin", "75 mg", "Capsule"),
            ("Cyclobenzaprine", "10 mg", "Tablet"),
            ("Methocarbamol", "500 mg", "Tablet"),
            ("Baclofen", "10 mg", "Tablet"),
            ("Tramadol", "50 mg", "Tablet"),
            ("Hydrocodone/Acetaminophen", "5/325 mg", "Tablet"),
            ("Oxycodone/Acetaminophen", "5/325 mg", "Tablet"),
            ("Meloxicam", "15 mg", "Tablet"),
            ("Diclofenac", "1%", "Gel"),
            ("Allopurinol", "100 mg", "Tablet"),
            ("Colchicine", "0.6 mg", "Tablet"),
            ("Tamsulosin", "0.4 mg", "Capsule"),
            ("Finasteride", "5 mg", "Tablet"),
            ("Sildenafil", "50 mg", "Tablet"),
            ("Ethinyl Estradiol/Levonorgestrel", "0.03/0.15 mg", "Tablet"),
            ("Medroxyprogesterone", "150 mg/mL", "Injection"),
            ("Ferrous Sulfate", "325 mg", "Tablet"),
            ("Folic Acid", "1 mg", "Tablet"),
            ("Vitamin D3", "2000 IU", "Tablet"),
            ("Potassium Chloride", "20 mEq", "Extended-Release Tablet"),
        ]

        medication_count = execute_query(
            "SELECT COUNT(*) AS medication_count FROM medications",
            fetchone=True
        )

        if medication_count and medication_count["medication_count"] == 0:
            for medication_name, strength, dosage_form in common_medications:
                execute_query(
                    """
                    INSERT INTO medications (medication_name, strength, dosage_form)
                    VALUES (%s, %s, %s)
                    """,
                    (medication_name, strength, dosage_form)
                )

        _medications_schema_bootstrapped = True

    except Exception as error:
        print("Medications schema bootstrap error:", error)

def ensure_doctor_medications_schema():
    global _doctor_medications_schema_bootstrapped

    if _doctor_medications_schema_bootstrapped:
        return

    try:
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS doctor_medications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doctor_id INT NOT NULL,
                medication_id INT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                notes TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_doctor_medication (doctor_id, medication_id),
                INDEX idx_doctor_medications_doctor (doctor_id),
                INDEX idx_doctor_medications_medication (medication_id),
                INDEX idx_doctor_medications_active (doctor_id, is_active),
                CONSTRAINT fk_doctor_medications_employee
                    FOREIGN KEY (doctor_id) REFERENCES employees(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_doctor_medications_medication
                    FOREIGN KEY (medication_id) REFERENCES medications(id)
                    ON DELETE CASCADE
            )
            """
        )

        _doctor_medications_schema_bootstrapped = True

    except Exception as error:
        print("Doctor medications schema bootstrap error:", error)

def ensure_medications_menu():
    global _medications_menu_bootstrapped

    if _medications_menu_bootstrapped:
        return

    try:
        admin_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'admin'
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not admin_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Admin', NULL, NULL, 'fas fa-user-shield', NULL, 10, 1)
                """
            )

            admin_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'admin'
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not admin_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'medications'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Medications',
                    url = '/medications',
                    icon_class = 'fas fa-pills',
                    parent_id = %s,
                    display_order = 18,
                    is_active = 1
                WHERE id = %s
                """,
                (admin_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Medications', 'medications', '/medications', 'fas fa-pills', %s, 18, 1)
                """,
                (admin_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'medications'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN ('admin', 'staff', 'doctors', 'doctor', 'doctord')
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _medications_menu_bootstrapped = True

    except Exception as error:
        print("Medications menu bootstrap error:", error)

def ensure_doctor_favorite_medications_menu():
    global _doctor_favorite_medications_menu_bootstrapped

    if _doctor_favorite_medications_menu_bootstrapped:
        return

    try:
        doctor_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) IN ('doctor', 'doctors')
              AND parent_id IS NULL
            ORDER BY id
            LIMIT 1
            """,
            fetchone=True
        )

        if not doctor_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Doctors', NULL, NULL, 'fas fa-user-md', NULL, 30, 1)
                """
            )

            doctor_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) IN ('doctor', 'doctors')
                  AND parent_id IS NULL
                ORDER BY id
                LIMIT 1
                """,
                fetchone=True
            )

        if not doctor_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'doctor_favorite_medications'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Favorite Medications',
                    url = '/doctor/favorite_medications',
                    icon_class = 'fas fa-star',
                    parent_id = %s,
                    display_order = 12,
                    is_active = 1
                WHERE id = %s
                """,
                (doctor_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Favorite Medications', 'doctor_favorite_medications',
                 '/doctor/favorite_medications', 'fas fa-star', %s, 12, 1)
                """,
                (doctor_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'doctor_favorite_medications'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN ('admin', 'doctors', 'doctor', 'doctord')
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _doctor_favorite_medications_menu_bootstrapped = True

    except Exception as error:
        print("Doctor favorite medications menu bootstrap error:", error)

def ensure_checkin_walkin_menu():
    global _checkin_walkin_menu_bootstrapped

    if _checkin_walkin_menu_bootstrapped:
        return

    try:
        execute_query(
            """
            UPDATE menu_options
            SET option_name = 'Check-in Walk-in',
                url = '/secretary/checkin',
                is_active = 1
            WHERE endpoint_name = 'checkin_patient'
            """
        )

        _checkin_walkin_menu_bootstrapped = True

    except Exception as error:
        print("Check-in walk-in menu bootstrap error:", error)

def ensure_appointment_checkin_menu():
    global _appointment_checkin_menu_bootstrapped

    if _appointment_checkin_menu_bootstrapped:
        return

    try:
        secretary_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'secretary'
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not secretary_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Secretary', NULL, NULL, 'fas fa-user-tie', NULL, 20, 1)
                """
            )

            secretary_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'secretary'
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not secretary_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'appointment_checkin'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Appointments Query & Check-in',
                    url = '/secretary/appointment_checkin',
                    icon_class = 'fas fa-calendar-check',
                    parent_id = %s,
                    display_order = 24,
                    is_active = 1
                WHERE id = %s
                """,
                (secretary_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Appointments Query & Check-in', 'appointment_checkin',
                 '/secretary/appointment_checkin', 'fas fa-calendar-check', %s, 24, 1)
                """,
                (secretary_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'appointment_checkin'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN (
                'admin',
                'secretary',
                'secratery',
                'staff',
                'nurses',
                'nurse',
                'paramedical',
                'doctors',
                'doctor',
                'doctord'
            )
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _appointment_checkin_menu_bootstrapped = True

    except Exception as error:
        print("Appointment check-in menu bootstrap error:", error)

def ensure_manage_prescriptions_menu():
    global _manage_prescriptions_menu_bootstrapped

    if _manage_prescriptions_menu_bootstrapped:
        return

    try:
        doctor_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) IN ('doctor', 'doctors')
              AND parent_id IS NULL
            ORDER BY id
            LIMIT 1
            """,
            fetchone=True
        )

        if not doctor_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Doctors', NULL, NULL, 'fas fa-user-md', NULL, 30, 1)
                """
            )

            doctor_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) IN ('doctor', 'doctors')
                  AND parent_id IS NULL
                ORDER BY id
                LIMIT 1
                """,
                fetchone=True
            )

        if not doctor_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'manage_prescriptions'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Manage Prescriptions',
                    url = '/prescriptions/manage',
                    icon_class = 'fas fa-prescription-bottle-alt',
                    parent_id = %s,
                    display_order = 13,
                    is_active = 1
                WHERE id = %s
                """,
                (doctor_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Manage Prescriptions', 'manage_prescriptions',
                 '/prescriptions/manage', 'fas fa-prescription-bottle-alt', %s, 13, 1)
                """,
                (doctor_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'manage_prescriptions'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN ('admin', 'doctors', 'doctor', 'doctord', 'staff')
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _manage_prescriptions_menu_bootstrapped = True

    except Exception as error:
        print("Manage prescriptions menu bootstrap error:", error)

def column_exists(table_name, column_name):
    existing_column = execute_query(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
        fetchone=True
    )

    return bool(existing_column)

def ensure_lab_tests_schema():
    global _lab_tests_schema_bootstrapped

    if _lab_tests_schema_bootstrapped:
        return

    try:
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS lab_tests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                test_name VARCHAR(100),
                loinc_code VARCHAR(20),
                unit VARCHAR(30),
                normal_low DECIMAL(10,2),
                normal_high DECIMAL(10,2),
                category VARCHAR(50),
                `group` TEXT
            )
            """
        )

        ensure_column(
            "lab_tests",
            "loinc_code",
            "ALTER TABLE lab_tests ADD COLUMN loinc_code VARCHAR(20) NULL AFTER test_name"
        )
        ensure_column(
            "lab_tests",
            "normal_low",
            "ALTER TABLE lab_tests ADD COLUMN normal_low DECIMAL(10,2) NULL AFTER unit"
        )
        ensure_column(
            "lab_tests",
            "normal_high",
            "ALTER TABLE lab_tests ADD COLUMN normal_high DECIMAL(10,2) NULL AFTER normal_low"
        )
        ensure_column(
            "lab_tests",
            "group",
            "ALTER TABLE lab_tests ADD COLUMN `group` TEXT NULL AFTER category"
        )

        execute_query("ALTER TABLE lab_tests MODIFY COLUMN test_name VARCHAR(100) NULL")
        execute_query("ALTER TABLE lab_tests MODIFY COLUMN unit VARCHAR(30) NULL AFTER loinc_code")
        execute_query("ALTER TABLE lab_tests MODIFY COLUMN normal_low DECIMAL(10,2) NULL AFTER unit")
        execute_query("ALTER TABLE lab_tests MODIFY COLUMN normal_high DECIMAL(10,2) NULL AFTER normal_low")
        execute_query("ALTER TABLE lab_tests MODIFY COLUMN category VARCHAR(50) NULL AFTER normal_high")
        execute_query("ALTER TABLE lab_tests MODIFY COLUMN `group` TEXT NULL AFTER category")

        if column_exists("lab_tests", "normal_range"):
            execute_query("ALTER TABLE lab_tests DROP COLUMN normal_range")

        _lab_tests_schema_bootstrapped = True

    except Exception as error:
        print("Lab tests schema bootstrap error:", error)

def ensure_vital_signs_schema():
    global _vital_signs_schema_bootstrapped

    if _vital_signs_schema_bootstrapped:
        return

    try:
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS vital_signs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                patient_id INT NOT NULL,
                blood_pressure VARCHAR(30) NULL,
                heart_rate INT NULL,
                respiratory_rate INT NULL,
                body_temperature DECIMAL(5,2) NULL,
                oxygen_saturation DECIMAL(5,2) NULL,
                weight DECIMAL(7,2) NULL,
                height DECIMAL(7,2) NULL,
                mdate DATE NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_vital_signs_patient_date (patient_id, mdate),
                CONSTRAINT fk_vital_signs_patient
                    FOREIGN KEY (patient_id) REFERENCES patients(id)
                ON DELETE CASCADE
            )
            """
        )

        ensure_column(
            "vital_signs",
            "vital_status",
            "ALTER TABLE vital_signs ADD COLUMN vital_status VARCHAR(20) NOT NULL DEFAULT 'draft' AFTER mdate"
        )
        ensure_column(
            "vital_signs",
            "finalized_at",
            "ALTER TABLE vital_signs ADD COLUMN finalized_at DATETIME NULL AFTER vital_status"
        )

        _vital_signs_schema_bootstrapped = True

    except Exception as error:
        print("Vital signs schema bootstrap error:", error)

def ensure_patient_history_menu():
    global _patient_history_menu_bootstrapped

    if _patient_history_menu_bootstrapped:
        return

    try:
        patient_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) IN ('patients', 'patient')
              AND parent_id IS NULL
            ORDER BY id
            LIMIT 1
            """,
            fetchone=True
        )

        if not patient_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Patients', NULL, NULL, 'fas fa-hospital-user', NULL, 3, 1)
                """
            )

            patient_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) IN ('patients', 'patient')
                  AND parent_id IS NULL
                ORDER BY id
                LIMIT 1
                """,
                fetchone=True
            )

        if not patient_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'patient_history'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Unchecked Patient',
                    url = '/patients/history',
                    icon_class = 'fas fa-notes-medical',
                    parent_id = %s,
                    display_order = 2,
                    is_active = 1
                WHERE id = %s
                """,
                (patient_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Unchecked Patient', 'patient_history', '/patients/history',
                        'fas fa-notes-medical', %s, 2, 1)
                """,
                (patient_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'patient_history'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN ('admin', 'doctors', 'doctor', 'doctord')
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _patient_history_menu_bootstrapped = True

    except Exception as error:
        print("Patient history menu bootstrap error:", error)


def ensure_doctor_specialties_schema():
    global _doctor_specialties_schema_bootstrapped

    if _doctor_specialties_schema_bootstrapped:
        return

    try:
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS doctor_specialties (
                id INT AUTO_INCREMENT PRIMARY KEY,
                specialty_code VARCHAR(50) NOT NULL,
                specialty_name VARCHAR(150) NOT NULL,
                specialty_group VARCHAR(100) NULL,
                classification_system VARCHAR(100) NOT NULL DEFAULT 'ABMS/ACGME',
                description TEXT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_doctor_specialties_code (specialty_code),
                UNIQUE KEY uq_doctor_specialties_name_system
                    (specialty_name, classification_system),
                INDEX idx_doctor_specialties_active (is_active),
                INDEX idx_doctor_specialties_group (specialty_group),
                INDEX idx_doctor_specialties_system (classification_system)
            )
            """
        )

        standard_specialties = [
            ("ALLERGY_IMMUNOLOGY", "Allergy and Immunology", "Medical Specialties"),
            ("ANESTHESIOLOGY", "Anesthesiology", "Hospital-Based Specialties"),
            ("CARDIOLOGY", "Cardiology", "Internal Medicine Subspecialties"),
            ("COLON_RECTAL_SURGERY", "Colon and Rectal Surgery", "Surgical Specialties"),
            ("CRITICAL_CARE_MEDICINE", "Critical Care Medicine", "Internal Medicine Subspecialties"),
            ("DERMATOLOGY", "Dermatology", "Medical Specialties"),
            ("EMERGENCY_MEDICINE", "Emergency Medicine", "Hospital-Based Specialties"),
            ("ENDOCRINOLOGY", "Endocrinology, Diabetes and Metabolism", "Internal Medicine Subspecialties"),
            ("FAMILY_MEDICINE", "Family Medicine", "Primary Care"),
            ("GASTROENTEROLOGY", "Gastroenterology", "Internal Medicine Subspecialties"),
            ("GENERAL_SURGERY", "General Surgery", "Surgical Specialties"),
            ("GERIATRIC_MEDICINE", "Geriatric Medicine", "Internal Medicine Subspecialties"),
            ("HEMATOLOGY_ONCOLOGY", "Hematology and Oncology", "Internal Medicine Subspecialties"),
            ("INFECTIOUS_DISEASE", "Infectious Disease", "Internal Medicine Subspecialties"),
            ("INTERNAL_MEDICINE", "Internal Medicine", "Primary Care"),
            ("MEDICAL_GENETICS", "Medical Genetics and Genomics", "Medical Specialties"),
            ("NEPHROLOGY", "Nephrology", "Internal Medicine Subspecialties"),
            ("NEUROLOGY", "Neurology", "Medical Specialties"),
            ("NEUROLOGICAL_SURGERY", "Neurological Surgery", "Surgical Specialties"),
            ("OBSTETRICS_GYNECOLOGY", "Obstetrics and Gynecology", "Medical and Surgical Specialties"),
            ("OCCUPATIONAL_MEDICINE", "Occupational Medicine", "Preventive Medicine"),
            ("OPHTHALMOLOGY", "Ophthalmology", "Surgical Specialties"),
            ("ORTHOPAEDIC_SURGERY", "Orthopaedic Surgery", "Surgical Specialties"),
            ("OTOLARYNGOLOGY", "Otolaryngology - Head and Neck Surgery", "Surgical Specialties"),
            ("PATHOLOGY", "Pathology", "Hospital-Based Specialties"),
            ("PEDIATRICS", "Pediatrics", "Primary Care"),
            ("PHYSICAL_MEDICINE_REHAB", "Physical Medicine and Rehabilitation", "Medical Specialties"),
            ("PLASTIC_SURGERY", "Plastic Surgery", "Surgical Specialties"),
            ("PREVENTIVE_MEDICINE", "Preventive Medicine", "Preventive Medicine"),
            ("PSYCHIATRY", "Psychiatry", "Medical Specialties"),
            ("PULMONARY_DISEASE", "Pulmonary Disease", "Internal Medicine Subspecialties"),
            ("RADIATION_ONCOLOGY", "Radiation Oncology", "Hospital-Based Specialties"),
            ("RADIOLOGY_DIAGNOSTIC", "Diagnostic Radiology", "Hospital-Based Specialties"),
            ("RHEUMATOLOGY", "Rheumatology", "Internal Medicine Subspecialties"),
            ("THORACIC_SURGERY", "Thoracic Surgery", "Surgical Specialties"),
            ("UROLOGY", "Urology", "Surgical Specialties"),
            ("VASCULAR_SURGERY", "Vascular Surgery", "Surgical Specialties")
        ]

        for specialty_code, specialty_name, specialty_group in standard_specialties:
            execute_query(
                """
                INSERT IGNORE INTO doctor_specialties
                (specialty_code, specialty_name, specialty_group, classification_system, is_active)
                VALUES (%s, %s, %s, 'ABMS/ACGME', 1)
                """,
                (specialty_code, specialty_name, specialty_group)
            )

        existing_doctor_specialties = execute_query(
            """
            SELECT DISTINCT TRIM(specialty) AS specialty_name
            FROM doctors
            WHERE specialty IS NOT NULL
              AND TRIM(specialty) <> ''
            """,
            fetchall=True
        )

        for row in existing_doctor_specialties:
            specialty_name = row["specialty_name"]
            specialty_code = specialty_name.upper().replace("&", "AND")
            specialty_code = "".join(
                character if character.isalnum() else "_"
                for character in specialty_code
            )
            specialty_code = "_".join(
                part for part in specialty_code.split("_") if part
            )[:50]

            execute_query(
                """
                INSERT IGNORE INTO doctor_specialties
                (specialty_code, specialty_name, specialty_group, classification_system, is_active)
                VALUES (%s, %s, 'Clinic Current Specialties', 'Clinic', 1)
                """,
                (specialty_code, specialty_name)
            )

        _doctor_specialties_schema_bootstrapped = True

    except Exception as error:
        print("Doctor specialties schema bootstrap error:", error)


def ensure_doctor_specialties_menu():
    global _doctor_specialties_menu_bootstrapped

    if _doctor_specialties_menu_bootstrapped:
        return

    try:
        clinic_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'clinic management'
              AND parent_id IS NULL
            LIMIT 1
            """,
            fetchone=True
        )

        if not clinic_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Clinic Management', NULL, NULL, 'fas fa-clinic-medical', NULL, 8, 1)
                """
            )

            clinic_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'clinic management'
                  AND parent_id IS NULL
                LIMIT 1
                """,
                fetchone=True
            )

        if not clinic_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'doctor_specialties'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Doctor Speciality',
                    url = '/clinic/doctor_specialties',
                    icon_class = 'fas fa-user-md',
                    parent_id = %s,
                    display_order = 3,
                    is_active = 1
                WHERE id = %s
                """,
                (clinic_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Doctor Speciality', 'doctor_specialties',
                 '/clinic/doctor_specialties', 'fas fa-user-md', %s, 3, 1)
                """,
                (clinic_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'doctor_specialties'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN ('admin', 'staff')
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _doctor_specialties_menu_bootstrapped = True

    except Exception as error:
        print("Doctor specialties menu bootstrap error:", error)


def ensure_id_card_schema():
    global _id_card_schema_bootstrapped

    if _id_card_schema_bootstrapped:
        return

    try:
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS ID_CARD (
                id INT AUTO_INCREMENT PRIMARY KEY,
                first_name VARCHAR(255) NULL,
                name VARCHAR(255) NOT NULL,
                father_name VARCHAR(255) NULL,
                mother_full_name VARCHAR(255) NULL,
                place_of_birth VARCHAR(255) NULL,
                dob DATE NULL,
                national_number VARCHAR(50) NOT NULL,
                gender VARCHAR(50) NULL,
                address TEXT NULL,
                image_path VARCHAR(255) NULL,
                raw_text TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_id_card_national_number (national_number)
            )
            """
        )

        ensure_column(
            "ID_CARD",
            "first_name",
            "ALTER TABLE ID_CARD ADD COLUMN first_name VARCHAR(255) NULL AFTER id"
        )

        _id_card_schema_bootstrapped = True

    except Exception as error:
        print("ID card schema bootstrap error:", error)

def ensure_id_card_menu():
    global _id_card_menu_bootstrapped

    if _id_card_menu_bootstrapped:
        return

    try:
        clinic_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'clinic management'
              AND parent_id IS NULL
            LIMIT 1
            """,
            fetchone=True
        )

        if not clinic_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Clinic Management', NULL, NULL, 'fas fa-clinic-medical', NULL, 8, 1)
                """
            )

            clinic_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'clinic management'
                  AND parent_id IS NULL
                LIMIT 1
                """,
                fetchone=True
            )

        if not clinic_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'id_card'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'ID Card',
                    url = '/clinic/id_card',
                    icon_class = 'fas fa-id-card',
                    parent_id = %s,
                    display_order = 2,
                    is_active = 1
                WHERE id = %s
                """,
                (clinic_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('ID Card', 'id_card', '/clinic/id_card', 'fas fa-id-card', %s, 2, 1)
                """,
                (clinic_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'id_card'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        admin_groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) = 'admin'
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in admin_groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _id_card_menu_bootstrapped = True

    except Exception as error:
        print("ID card menu bootstrap error:", error)

def ensure_manage_appointment_menu():
    global _appointment_menu_bootstrapped

    if _appointment_menu_bootstrapped:
        return

    try:
        secretary_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'secretary'
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not secretary_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Secretary', NULL, NULL, 'fas fa-user-tie', NULL, 20, 1)
                """
            )

            secretary_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'secretary'
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not secretary_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'manage_appointments'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Manage Appointment',
                    url = '/secretary/manage_appointments',
                    icon_class = 'fas fa-calendar-alt',
                    parent_id = %s,
                    is_active = 1
                WHERE id = %s
                """,
                (secretary_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Manage Appointment', 'manage_appointments', '/secretary/manage_appointments',
                 'fas fa-calendar-alt', %s, 40, 1)
                """,
                (secretary_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'manage_appointments'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        execute_query(
            """
            UPDATE menu_options
            SET is_active = 0
            WHERE endpoint_name = 'search_book_appointment'
            """
        )

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN ('admin', 'secretary', 'secratery', 'staff')
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _appointment_menu_bootstrapped = True

    except Exception as error:
        print("Menu bootstrap error:", error)

def ensure_lab_order_menu():
    try:
        lab_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) IN ('lab', 'lab & vital signs')
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not lab_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Lab & Vital Signs', NULL, NULL, 'fas fa-vial', NULL, 5, 1)
                """
            )

            lab_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) IN ('lab', 'lab & vital signs')
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not lab_parent:
            return

        execute_query(
            """
            UPDATE menu_options
            SET option_name = 'Lab & Vital Signs'
            WHERE id = %s
            """,
            (lab_parent["id"],)
        )

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'lab_order'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Lab Orders',
                    url = '/secretary/lab_order',
                    icon_class = 'fas fa-vial',
                    parent_id = %s,
                    display_order = 2,
                    is_active = 1
                WHERE id = %s
                """,
                (lab_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Lab Orders', 'lab_order', '/secretary/lab_order',
                 'fas fa-vial', %s, 2, 1)
                """,
                (lab_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'lab_order'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN (
                'admin',
                'secretary',
                'secratery',
                'staff',
                'doctors',
                'doctor',
                'doctord'
            )
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

    except Exception as error:
        print("Lab order menu bootstrap error:", error)

def ensure_lab_result_menu():
    global _lab_result_menu_bootstrapped

    if _lab_result_menu_bootstrapped:
        return

    try:
        secretary_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'secretary'
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not secretary_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Secretary', NULL, NULL, 'fas fa-user-tie', NULL, 20, 1)
                """
            )

            secretary_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'secretary'
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not secretary_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'lab_result'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Lab Result',
                    url = '/secretary/lab_result',
                    icon_class = 'fas fa-clipboard-check',
                    parent_id = %s,
                    display_order = 46,
                    is_active = 1
                WHERE id = %s
                """,
                (secretary_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Lab Result', 'lab_result', '/secretary/lab_result',
                 'fas fa-clipboard-check', %s, 46, 1)
                """,
                (secretary_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'lab_result'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN (
                'admin',
                'secretary',
                'secratery',
                'staff',
                'doctors',
                'doctor',
                'doctord'
            )
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _lab_result_menu_bootstrapped = True

    except Exception as error:
        print("Lab result menu bootstrap error:", error)

def ensure_extend_schedule_menu():
    global _extend_schedule_menu_bootstrapped

    if _extend_schedule_menu_bootstrapped:
        return

    try:
        admin_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'admin'
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not admin_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Admin', NULL, NULL, 'fas fa-user-shield', NULL, 10, 1)
                """
            )

            admin_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'admin'
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not admin_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'extend_schedule'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Extend Schedule',
                    url = '/admin/extend_schedule',
                    icon_class = 'fas fa-calendar-plus',
                    parent_id = %s,
                    display_order = 11,
                    is_active = 1
                WHERE id = %s
                """,
                (admin_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Extend Schedule', 'extend_schedule', '/admin/extend_schedule',
                 'fas fa-calendar-plus', %s, 11, 1)
                """,
                (admin_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'extend_schedule'
                """,
                fetchone=True
            )

        if not menu_option:
            return

        admin_groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) = 'admin'
              AND is_active = 1
            """,
            fetchall=True
        )

        for group in admin_groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], menu_option["id"]),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], menu_option["id"])
                )

        _extend_schedule_menu_bootstrapped = True

    except Exception as error:
        print("Extend schedule menu bootstrap error:", error)

def ensure_lab_menu():
    global _lab_menu_bootstrapped

    if _lab_menu_bootstrapped:
        return

    try:
        lab_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) IN ('lab', 'lab & vital signs')
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not lab_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Lab & Vital Signs', NULL, NULL, 'fas fa-vial', NULL, 5, 1)
                """
            )

            lab_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) IN ('lab', 'lab & vital signs')
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not lab_parent:
            return

        execute_query(
            """
            UPDATE menu_options
            SET option_name = 'Lab & Vital Signs'
            WHERE id = %s
            """,
            (lab_parent["id"],)
        )

        lab_children = [
            ("Lab Tests", "lab_tests", "/lab/tests", "fas fa-vials", 2),
            ("Vital Signs", "vital_signs", "/vital_signs", "fas fa-heartbeat", 3),
        ]

        execute_query(
            """
            UPDATE menu_options
            SET is_active = 0
            WHERE endpoint_name IN ('laboratory', 'lab_results')
               OR url = '/laboratory'
               OR url = '/lab/results'
            """
        )

        lab_options = []

        for option_name, endpoint_name, url, icon_class, display_order in lab_children:
            lab_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = %s
                """,
                (endpoint_name,),
                fetchone=True
            )

            if lab_option:
                execute_query(
                    """
                    UPDATE menu_options
                    SET option_name = %s,
                        url = %s,
                        icon_class = %s,
                        parent_id = %s,
                        display_order = %s,
                        is_active = 1
                    WHERE id = %s
                    """,
                    (
                        option_name,
                        url,
                        icon_class,
                        lab_parent["id"],
                        display_order,
                        lab_option["id"]
                    )
                )
            else:
                execute_query(
                    """
                    INSERT INTO menu_options
                    (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                    """,
                    (
                        option_name,
                        endpoint_name,
                        url,
                        icon_class,
                        lab_parent["id"],
                        display_order
                    )
                )

                lab_option = execute_query(
                    """
                    SELECT id
                    FROM menu_options
                    WHERE endpoint_name = %s
                    """,
                    (endpoint_name,),
                    fetchone=True
                )

            if lab_option:
                lab_options.append(lab_option)

        groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) IN ('admin', 'secretary', 'staff', 'doctors', 'doctor')
              AND is_active = 1
            """,
            fetchall=True
        )

        for lab_option in lab_options:
            for group in groups:
                existing_permission = execute_query(
                    """
                    SELECT id
                    FROM group_menu_permissions
                    WHERE group_id = %s
                      AND menu_option_id = %s
                    """,
                    (group["id"], lab_option["id"]),
                    fetchone=True
                )

                if not existing_permission:
                    execute_query(
                        """
                        INSERT INTO group_menu_permissions
                        (group_id, menu_option_id)
                        VALUES (%s, %s)
                        """,
                        (group["id"], lab_option["id"])
                    )

        _lab_menu_bootstrapped = True

    except Exception as error:
        print("Lab menu bootstrap error:", error)


def ensure_icd_schema():
    global _icd_schema_bootstrapped

    if _icd_schema_bootstrapped:
        return

    try:
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS icd_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version_year INT NOT NULL,
                effective_date DATE NULL,
                source_name VARCHAR(255) NULL,
                source_url VARCHAR(500) NULL,
                is_active BOOLEAN NOT NULL DEFAULT FALSE,
                imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_icd_version_year (version_year)
            )
            """
        )

        execute_query(
            """
            CREATE TABLE IF NOT EXISTS icd_chapters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version_id INT NOT NULL,
                chapter_code VARCHAR(20) NOT NULL,
                code_range VARCHAR(30) NOT NULL,
                title VARCHAR(255) NOT NULL,
                display_order INT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                UNIQUE KEY uq_icd_chapter (version_id, chapter_code),
                INDEX idx_icd_chapters_version (version_id),
                CONSTRAINT fk_icd_chapters_version
                    FOREIGN KEY (version_id) REFERENCES icd_versions(id)
                    ON DELETE CASCADE
            )
            """
        )

        execute_query(
            """
            CREATE TABLE IF NOT EXISTS icd_blocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chapter_id INT NOT NULL,
                block_code_range VARCHAR(30) NOT NULL,
                title VARCHAR(255) NOT NULL,
                display_order INT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                UNIQUE KEY uq_icd_block (chapter_id, block_code_range),
                INDEX idx_icd_blocks_chapter (chapter_id),
                CONSTRAINT fk_icd_blocks_chapter
                    FOREIGN KEY (chapter_id) REFERENCES icd_chapters(id)
                    ON DELETE CASCADE
            )
            """
        )

        execute_query(
            """
            CREATE TABLE IF NOT EXISTS icd_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                block_id INT NOT NULL,
                category_code VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                display_order INT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                UNIQUE KEY uq_icd_category (block_id, category_code),
                INDEX idx_icd_categories_block (block_id),
                INDEX idx_icd_categories_code (category_code),
                CONSTRAINT fk_icd_categories_block
                    FOREIGN KEY (block_id) REFERENCES icd_blocks(id)
                    ON DELETE CASCADE
            )
            """
        )

        execute_query(
            """
            CREATE TABLE IF NOT EXISTS icd_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                category_id INT NOT NULL,
                code VARCHAR(20) NOT NULL,
                description VARCHAR(500) NOT NULL,
                billable BOOLEAN NOT NULL DEFAULT TRUE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                UNIQUE KEY uq_icd_code (category_id, code),
                INDEX idx_icd_codes_code (code),
                INDEX idx_icd_codes_description (description),
                CONSTRAINT fk_icd_codes_category
                    FOREIGN KEY (category_id) REFERENCES icd_categories(id)
                    ON DELETE CASCADE
            )
            """
        )

        execute_query(
            """
            CREATE TABLE IF NOT EXISTS clinic_icd_enabled_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_type ENUM('chapter', 'block', 'category', 'code') NOT NULL,
                item_id INT NOT NULL,
                enabled_by INT NULL,
                enabled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_clinic_icd_enabled_item (item_type, item_id),
                INDEX idx_clinic_icd_enabled_type (item_type),
                INDEX idx_clinic_icd_enabled_by (enabled_by)
            )
            """
        )

        execute_query(
            """
            CREATE TABLE IF NOT EXISTS specialty_icd_enabled_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version_id INT NOT NULL,
                specialty VARCHAR(150) NOT NULL,
                item_type ENUM('chapter', 'block', 'category', 'code') NOT NULL,
                item_id INT NOT NULL,
                enabled_by INT NULL,
                enabled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_specialty_icd_enabled_item
                    (version_id, specialty, item_type, item_id),
                INDEX idx_specialty_icd_enabled_lookup
                    (version_id, specialty, item_type),
                INDEX idx_specialty_icd_enabled_by (enabled_by),
                CONSTRAINT fk_specialty_icd_enabled_version
                    FOREIGN KEY (version_id) REFERENCES icd_versions(id)
                    ON DELETE CASCADE
            )
            """
        )

        _icd_schema_bootstrapped = True

    except Exception as error:
        print("ICD schema bootstrap error:", error)


def ensure_icd_setup_menu():
    global _icd_setup_menu_bootstrapped

    if _icd_setup_menu_bootstrapped:
        return

    try:
        admin_parent = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE LOWER(option_name) = 'admin'
              AND parent_id IS NULL
            """,
            fetchone=True
        )

        if not admin_parent:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Admin', NULL, NULL, 'fas fa-user-shield', NULL, 10, 1)
                """
            )

            admin_parent = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE LOWER(option_name) = 'admin'
                  AND parent_id IS NULL
                """,
                fetchone=True
            )

        if not admin_parent:
            return

        menu_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'diagnosis_icd_setup'
            """,
            fetchone=True
        )

        if menu_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Diagnosis ICD Setup',
                    url = '/admin/diagnosis_icd_setup',
                    icon_class = 'fas fa-stethoscope',
                    parent_id = %s,
                    display_order = 19,
                    is_active = 1
                WHERE id = %s
                """,
                (admin_parent["id"], menu_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Diagnosis ICD Setup', 'diagnosis_icd_setup',
                 '/admin/diagnosis_icd_setup', 'fas fa-stethoscope', %s, 19, 1)
                """,
                (admin_parent["id"],)
            )

            menu_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'diagnosis_icd_setup'
                """,
                fetchone=True
            )

        fine_tuning_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'diagnosis_icd_fine_tuning'
            """,
            fetchone=True
        )

        if fine_tuning_option:
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Diagnosis ICD Fine Tuning',
                    url = '/admin/diagnosis_icd_fine_tuning',
                    icon_class = 'fas fa-list-check',
                    parent_id = %s,
                    display_order = 20,
                    is_active = 1
                WHERE id = %s
                """,
                (admin_parent["id"], fine_tuning_option["id"])
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES
                ('Diagnosis ICD Fine Tuning', 'diagnosis_icd_fine_tuning',
                 '/admin/diagnosis_icd_fine_tuning', 'fas fa-list-check', %s, 20, 1)
                """,
                (admin_parent["id"],)
            )

            fine_tuning_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'diagnosis_icd_fine_tuning'
                """,
                fetchone=True
            )

        menu_options = []
        if menu_option:
            menu_options.append(menu_option)
        if fine_tuning_option:
            menu_options.append(fine_tuning_option)
        if not menu_options:
            return

        admin_groups = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) = 'admin'
              AND is_active = 1
            """,
            fetchall=True
        )

        for menu_item in menu_options:
            for group in admin_groups:
                existing_permission = execute_query(
                    """
                    SELECT id
                    FROM group_menu_permissions
                    WHERE group_id = %s
                      AND menu_option_id = %s
                    """,
                    (group["id"], menu_item["id"]),
                    fetchone=True
                )

                if not existing_permission:
                    execute_query(
                        """
                        INSERT INTO group_menu_permissions
                        (group_id, menu_option_id)
                        VALUES (%s, %s)
                        """,
                        (group["id"], menu_item["id"])
                    )

        _icd_setup_menu_bootstrapped = True

    except Exception as error:
        print("ICD setup menu bootstrap error:", error)


def run_runtime_bootstrap():
    ensure_home_menu()
    ensure_menu_translation_schema()
    ensure_patient_workflow_schema()
    ensure_visit_diagnosis_schema()
    ensure_medications_schema()
    ensure_doctor_medications_schema()
    ensure_lab_tests_schema()
    ensure_vital_signs_schema()
    ensure_doctor_specialties_schema()
    ensure_id_card_schema()
    ensure_patient_history_menu()
    ensure_doctor_specialties_menu()
    ensure_id_card_menu()
    ensure_lab_menu()
    ensure_icd_schema()
    ensure_icd_setup_menu()
