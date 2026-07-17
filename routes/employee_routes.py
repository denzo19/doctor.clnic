from datetime import datetime

from flask import Response, flash, redirect, render_template, request, url_for

from auth import login_required, permission_required
from database import execute_query
from pdf_utils import (
    add_standard_pdf_image_objects,
    escape_pdf_text,
    standard_pdf_chrome_commands,
    standard_pdf_content_top,
    standard_pdf_image_names,
    truncate_pdf_text
)


def register_employee_routes(app):
    def employee_email_exists(email, exclude_employee_id=None):
        if not email:
            return False

        if exclude_employee_id:
            return execute_query(
                """
                SELECT id
                FROM employees
                WHERE LOWER(email) = LOWER(%s)
                  AND id <> %s
                """,
                (email, exclude_employee_id),
                fetchone=True
            )

        return execute_query(
            """
            SELECT id
            FROM employees
            WHERE LOWER(email) = LOWER(%s)
            """,
            (email,),
            fetchone=True
        )


    @app.route("/admin/employees", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_employees")
    def manage_employees():

        # =====================================================
        # ADD EMPLOYEE
        # =====================================================

        if request.method == "POST":

            employee_code = request.form.get(
                "employee_code",
                ""
            ).strip()

            full_name = request.form.get(
                "full_name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip()

            phone_number = request.form.get(
                "phone_number",
                ""
            ).strip()

            job_title = request.form.get(
                "job_title",
                ""
            ).strip()

            specialty = request.form.get(
                "specialty",
                ""
            ).strip()

            group_id = request.form.get(
                "group_id"
            )

            if employee_email_exists(email):

                flash("Employee email already exists.", "error")

                return redirect(
                    url_for("manage_employees")
                )

            # =====================================================
            # CHECK DUPLICATE EMPLOYEE CODE
            # =====================================================

            existing_employee = execute_query(
                """
                SELECT id
                FROM employees
                WHERE employee_code = %s
                """,
                (employee_code,),
                fetchone=True
            )

            if existing_employee:

                flash("Employee code already exists.", "error")

                return redirect(
                    url_for("manage_employees")
                )
            execute_query(
                """
                INSERT INTO employees
                (
                    employee_code,
                    full_name,
                    email,
                    phone_number,
                    job_title,
                    specialty,
                    group_id,
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
                    1
                )
                """,
                (
                    employee_code,
                    full_name,
                    email,
                    phone_number,
                    job_title,
                    specialty,
                    group_id
                )
            )

            flash("Employee added successfully.", "success")

            return redirect(
                url_for("manage_employees")
            )

        # =====================================================
        # SEARCH
        # =====================================================

        search = request.args.get(
            "search",
            ""
        ).strip()

        like_search = f"%{search}%"

        # =====================================================
        # EMPLOYEES
        # =====================================================

        employees = execute_query(
            """
            SELECT
                e.id,
                e.employee_code,
                e.full_name,
                e.email,
                e.phone_number,
                e.job_title,
                e.specialty,
                e.group_id,
                e.is_active,

                ug.group_name

            FROM employees e

            LEFT JOIN user_groups ug
                ON e.group_id = ug.id

            WHERE
                e.employee_code LIKE %s
                OR e.full_name LIKE %s
                OR e.email LIKE %s
                OR e.phone_number LIKE %s
                OR e.job_title LIKE %s
                OR e.specialty LIKE %s

            ORDER BY
                e.full_name
            """,
            (
                like_search,
                like_search,
                like_search,
                like_search,
                like_search,
                like_search
            ),
            fetchall=True
        )

        # =====================================================
        # GROUPS
        # =====================================================

        groups = execute_query(
            """
            SELECT
                id,
                group_name
            FROM user_groups
            ORDER BY group_name
            """,
            fetchall=True
        )

        doctor_specialties = execute_query(
            """
            SELECT specialty_name
            FROM doctor_specialties
            WHERE is_active = 1
            ORDER BY specialty_name
            """,
            fetchall=True
        )

        # =====================================================
        # RENDER
        # =====================================================

        return render_template(
            "admin_employees.html",
            employees=employees,
            groups=groups,
            doctor_specialties=doctor_specialties,
            search=search
        )

    def build_employees_pdf_report(employees, search_text=""):
        page_width = 612
        page_height = 792
        left = 24
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(employees), 1), rows_per_page):
            page_employees = employees[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Employees Report) Tj ET",
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
                f"BT /F1 8 Tf {left + 3} {table_top - 7} Td (Code) Tj ET",
                f"BT /F1 8 Tf {left + 73} {table_top - 7} Td (Full Name) Tj ET",
                f"BT /F1 8 Tf {left + 190} {table_top - 7} Td (Email) Tj ET",
                f"BT /F1 8 Tf {left + 310} {table_top - 7} Td (Phone) Tj ET",
                f"BT /F1 8 Tf {left + 382} {table_top - 7} Td (Job Title) Tj ET",
                f"BT /F1 8 Tf {left + 465} {table_top - 7} Td (Group) Tj ET",
                f"BT /F1 8 Tf {left + 545} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_employees:
                for employee in page_employees:
                    active_text = "Yes" if employee["is_active"] else "No"
                    commands.extend([
                        f"BT /F1 7.5 Tf {left + 3} {y} Td ({escape_pdf_text(truncate_pdf_text(employee['employee_code'], 9))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 73} {y} Td ({escape_pdf_text(truncate_pdf_text(employee['full_name'], 17))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 190} {y} Td ({escape_pdf_text(truncate_pdf_text(employee['email'], 18))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 310} {y} Td ({escape_pdf_text(truncate_pdf_text(employee['phone_number'], 10))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 382} {y} Td ({escape_pdf_text(truncate_pdf_text(employee['job_title'], 12))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 465} {y} Td ({escape_pdf_text(truncate_pdf_text(employee['group_name'], 11))}) Tj ET",
                        f"BT /F1 7.5 Tf {left + 545} {y} Td ({active_text}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No employees found.) Tj ET"
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


    @app.route("/admin/employees/report")
    @login_required
    @permission_required("manage_employees")
    def employees_report():
        search = request.args.get("search", "").strip()
        like_search = f"%{search}%"

        employees = execute_query(
            """
            SELECT
                e.employee_code,
                e.full_name,
                e.email,
                e.phone_number,
                e.job_title,
                e.specialty,
                e.is_active,
                ug.group_name
            FROM employees e
            LEFT JOIN user_groups ug
                ON e.group_id = ug.id
            WHERE
                e.employee_code LIKE %s
                OR e.full_name LIKE %s
                OR e.email LIKE %s
                OR e.phone_number LIKE %s
                OR e.job_title LIKE %s
                OR e.specialty LIKE %s
            ORDER BY e.full_name
            """,
            (
                like_search,
                like_search,
                like_search,
                like_search,
                like_search,
                like_search
            ),
            fetchall=True
        )

        pdf_bytes = build_employees_pdf_report(employees, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=employees_report.pdf"
            }
        )


    @app.route("/admin/employees/update/<int:employee_id>", methods=["POST"])
    @login_required
    @permission_required("manage_employees")
    def update_employee(employee_id):
        employee_code = request.form.get("employee_code", "").strip()
        email = request.form.get("email", "").strip()

        if employee_email_exists(email, employee_id):

            flash("Employee email already exists.", "error")

            return redirect(
                url_for("manage_employees")
            )

        # =====================================================
        # CHECK DUPLICATE EMPLOYEE CODE
        # =====================================================

        existing_employee = execute_query(
            """
            SELECT id
            FROM employees
            WHERE employee_code = %s
            AND id <> %s
            """,
            (
                employee_code,
                employee_id
            ),
            fetchone=True
        )

        if existing_employee:

            flash("Employee code already exists.", "error")

            return redirect(
                url_for("manage_employees")
            )    
        execute_query(
            """
            UPDATE employees
            SET employee_code = %s,
                full_name = %s,
                email = %s,
                phone_number = %s,
                job_title = %s,
                specialty = %s,
                group_id = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                request.form.get("employee_code", "").strip(),
                request.form.get("full_name", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("phone_number", "").strip(),
                request.form.get("job_title", "").strip(),
                request.form.get("specialty", "").strip(),
                request.form.get("group_id"),
                1 if request.form.get("is_active") == "1" else 0,
                employee_id
            )
        )

        flash("Employee updated successfully.", "success")
        return redirect(url_for("manage_employees"))


    @app.route("/admin/employees/stop/<int:employee_id>", methods=["POST"])
    @login_required
    @permission_required("manage_employees")
    def stop_employee(employee_id):
        execute_query(
            """
            UPDATE employees
            SET is_active = 0
            WHERE id = %s
            """,
            (employee_id,)
        )

        execute_query(
            """
            UPDATE users
            SET is_active = 0
            WHERE employee_id = %s
            """,
            (employee_id,)
        )

        flash("Employee stopped successfully.", "success")
        return redirect(url_for("manage_employees"))

    @app.route("/admin/employees/add_ajax", methods=["POST"])
    @login_required
    @permission_required("manage_employees")
    def add_employee_ajax():
        email = request.form.get("email", "").strip()

        if employee_email_exists(email):
            return {
                "success": False,
                "message": "Employee email already exists."
            }, 409

        execute_query(
            """
            INSERT INTO employees
            (employee_code, full_name, email, phone_number,
             job_title, specialty, group_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (
                request.form.get("employee_code", "").strip(),
                request.form.get("full_name", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("phone_number", "").strip(),
                request.form.get("job_title", "").strip(),
                request.form.get("specialty", "").strip(),
                request.form.get("group_id")
            )
        )

        return {"success": True}
