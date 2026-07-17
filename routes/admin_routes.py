from datetime import datetime

import mysql.connector
from flask import Response, flash, redirect, render_template, request, session, url_for

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


def register_admin_routes(app, bcrypt, menu_option_name_exists):
    @app.route("/admin/diagnosis_icd_setup", methods=["GET", "POST"])
    @login_required
    @permission_required("diagnosis_icd_setup")
    def diagnosis_icd_setup():
        active_version = execute_query(
            """
            SELECT id, version_year, source_name, effective_date
            FROM icd_versions
            WHERE is_active = 1
            ORDER BY version_year DESC
            LIMIT 1
            """,
            fetchone=True
        )

        specialties = execute_query(
            """
            SELECT DISTINCT specialty
            FROM doctors
            WHERE is_active = 1
              AND specialty IS NOT NULL
              AND TRIM(specialty) <> ''
            ORDER BY specialty
            """,
            fetchall=True
        )

        selected_specialty = (
            request.form.get("specialty")
            if request.method == "POST"
            else request.args.get("specialty")
        )
        if not selected_specialty and specialties:
            selected_specialty = specialties[0]["specialty"]

        if request.method == "POST":
            if not active_version:
                flash("Import an ICD-10-CM version before saving specialty selections.", "error")
                return redirect(url_for("diagnosis_icd_setup"))

            if not selected_specialty:
                flash("Choose a specialty before saving ICD selections.", "error")
                return redirect(url_for("diagnosis_icd_setup"))

            action = request.form.get("action")

            if action == "clear":
                execute_query(
                    """
                    DELETE FROM specialty_icd_enabled_items
                    WHERE version_id = %s
                      AND specialty = %s
                      AND item_type IN ('chapter', 'block')
                    """,
                    (active_version["id"], selected_specialty)
                )

                flash("Diagnosis ICD specialty selection cleared.", "success")
                return redirect(url_for(
                    "diagnosis_icd_setup",
                    specialty=selected_specialty
                ))

            selected_chapter_ids = request.form.getlist("chapter_ids")
            selected_block_ids = request.form.getlist("block_ids")

            execute_query(
                """
                DELETE FROM specialty_icd_enabled_items
                WHERE version_id = %s
                  AND specialty = %s
                  AND item_type IN ('chapter', 'block')
                """,
                (active_version["id"], selected_specialty)
            )

            for chapter_id in selected_chapter_ids:
                execute_query(
                    """
                    INSERT INTO specialty_icd_enabled_items
                    (version_id, specialty, item_type, item_id, enabled_by)
                    VALUES (%s, %s, 'chapter', %s, %s)
                    ON DUPLICATE KEY UPDATE
                        enabled_by = VALUES(enabled_by),
                        enabled_at = CURRENT_TIMESTAMP
                    """,
                    (
                        active_version["id"],
                        selected_specialty,
                        chapter_id,
                        session.get("user_id")
                    )
                )

            for block_id in selected_block_ids:
                execute_query(
                    """
                    INSERT INTO specialty_icd_enabled_items
                    (version_id, specialty, item_type, item_id, enabled_by)
                    VALUES (%s, %s, 'block', %s, %s)
                    ON DUPLICATE KEY UPDATE
                        enabled_by = VALUES(enabled_by),
                        enabled_at = CURRENT_TIMESTAMP
                    """,
                    (
                        active_version["id"],
                        selected_specialty,
                        block_id,
                        session.get("user_id")
                    )
                )

            flash("Diagnosis ICD specialty selection saved successfully.", "success")
            return redirect(url_for(
                "diagnosis_icd_setup",
                specialty=selected_specialty
            ))

        counts = {
            "versions": execute_query(
                "SELECT COUNT(*) AS item_count FROM icd_versions",
                fetchone=True
            )["item_count"],
            "chapters": execute_query(
                "SELECT COUNT(*) AS item_count FROM icd_chapters",
                fetchone=True
            )["item_count"],
            "blocks": execute_query(
                "SELECT COUNT(*) AS item_count FROM icd_blocks",
                fetchone=True
            )["item_count"],
            "categories": execute_query(
                "SELECT COUNT(*) AS item_count FROM icd_categories",
                fetchone=True
            )["item_count"],
            "codes": execute_query(
                "SELECT COUNT(*) AS item_count FROM icd_codes",
                fetchone=True
            )["item_count"],
            "enabled_items": execute_query(
                "SELECT COUNT(*) AS item_count FROM specialty_icd_enabled_items",
                fetchone=True
            )["item_count"]
        }

        chapters = []
        enabled_chapter_ids = set()
        enabled_block_ids = set()
        enabled_code_count = 0
        fine_block_options = []

        if active_version:
            enabled_items = execute_query(
                """
                SELECT item_type, item_id
                FROM specialty_icd_enabled_items
                WHERE version_id = %s
                  AND specialty = %s
                  AND item_type IN ('chapter', 'block')
                """,
                (active_version["id"], selected_specialty),
                fetchall=True
            ) if selected_specialty else []

            enabled_chapter_ids = {
                item["item_id"] for item in enabled_items
                if item["item_type"] == "chapter"
            }
            enabled_block_ids = {
                item["item_id"] for item in enabled_items
                if item["item_type"] == "block"
            }

            chapter_rows = execute_query(
                """
                SELECT id, chapter_code, code_range, title
                FROM icd_chapters
                WHERE version_id = %s
                  AND is_active = 1
                ORDER BY display_order, id
                """,
                (active_version["id"],),
                fetchall=True
            )

            block_rows = execute_query(
                """
                SELECT
                    b.id,
                    b.chapter_id,
                    b.block_code_range,
                    b.title,
                    COUNT(co.id) AS code_count
                FROM icd_blocks b
                LEFT JOIN icd_categories c
                    ON c.block_id = b.id
                LEFT JOIN icd_codes co
                    ON co.category_id = c.id
                   AND co.is_active = 1
                WHERE b.is_active = 1
                  AND b.chapter_id IN (
                      SELECT id
                      FROM icd_chapters
                      WHERE version_id = %s
                  )
                GROUP BY b.id, b.chapter_id, b.block_code_range, b.title, b.display_order
                ORDER BY b.chapter_id, b.display_order, b.id
                """,
                (active_version["id"],),
                fetchall=True
            )

            blocks_by_chapter = {}
            for block in block_rows:
                blocks_by_chapter.setdefault(block["chapter_id"], []).append(block)

            chapters = [
                {
                    "id": chapter["id"],
                    "chapter_code": chapter["chapter_code"],
                    "code_range": chapter["code_range"],
                    "title": chapter["title"],
                    "blocks": blocks_by_chapter.get(chapter["id"], []),
                    "selected": chapter["id"] in enabled_chapter_ids
                }
                for chapter in chapter_rows
            ]

            if enabled_chapter_ids or enabled_block_ids:
                fine_block_options = execute_query(
                    """
                    SELECT DISTINCT b.id, b.block_code_range, b.title
                    FROM icd_blocks b
                    JOIN icd_chapters ch
                        ON ch.id = b.chapter_id
                    WHERE ch.version_id = %s
                      AND b.is_active = 1
                      AND (
                          b.chapter_id IN (
                              SELECT item_id
                              FROM specialty_icd_enabled_items
                              WHERE version_id = %s
                                AND specialty = %s
                                AND item_type = 'chapter'
                          )
                          OR b.id IN (
                              SELECT item_id
                              FROM specialty_icd_enabled_items
                              WHERE version_id = %s
                                AND specialty = %s
                                AND item_type = 'block'
                          )
                      )
                    ORDER BY b.block_code_range, b.title
                    """,
                    (
                        active_version["id"],
                        active_version["id"],
                        selected_specialty,
                        active_version["id"],
                        selected_specialty
                    ),
                    fetchall=True
                )

                enabled_code_count_row = execute_query(
                    """
                    SELECT COUNT(DISTINCT co.id) AS code_count
                    FROM icd_codes co
                    JOIN icd_categories c
                        ON c.id = co.category_id
                    JOIN icd_blocks b
                        ON b.id = c.block_id
                    WHERE co.is_active = 1
                      AND (
                          b.chapter_id IN (
                              SELECT item_id
                              FROM specialty_icd_enabled_items
                              WHERE version_id = %s
                                AND specialty = %s
                                AND item_type = 'chapter'
                          )
                          OR b.id IN (
                              SELECT item_id
                              FROM specialty_icd_enabled_items
                              WHERE version_id = %s
                                AND specialty = %s
                                AND item_type = 'block'
                          )
                      )
                    """,
                    (
                        active_version["id"],
                        selected_specialty,
                        active_version["id"],
                        selected_specialty
                    ),
                    fetchone=True
                )
                enabled_code_count = enabled_code_count_row["code_count"]

        return render_template(
            "diagnosis_icd_setup.html",
            counts=counts,
            active_version=active_version,
            specialties=specialties,
            selected_specialty=selected_specialty,
            chapters=chapters,
            enabled_chapter_ids=enabled_chapter_ids,
            enabled_block_ids=enabled_block_ids,
            enabled_code_count=enabled_code_count,
            fine_block_options=fine_block_options
        )

    @app.route("/admin/diagnosis_icd_fine_tuning", methods=["GET", "POST"])
    @login_required
    @permission_required("diagnosis_icd_setup")
    def diagnosis_icd_fine_tuning():
        active_version = execute_query(
            """
            SELECT id, version_year, source_name, effective_date
            FROM icd_versions
            WHERE is_active = 1
            ORDER BY version_year DESC
            LIMIT 1
            """,
            fetchone=True
        )

        specialties = execute_query(
            """
            SELECT DISTINCT specialty
            FROM doctors
            WHERE is_active = 1
              AND specialty IS NOT NULL
              AND TRIM(specialty) <> ''
            ORDER BY specialty
            """,
            fetchall=True
        )

        selected_specialty = (
            request.form.get("specialty")
            if request.method == "POST"
            else request.args.get("specialty")
        )
        selected_fine_block_id = (
            request.form.get("fine_block_id", type=int)
            if request.method == "POST"
            else request.args.get("fine_block_id", type=int)
        )

        if not selected_specialty and specialties:
            selected_specialty = specialties[0]["specialty"]

        if request.method == "POST":
            if not active_version:
                flash("Import an ICD-10-CM version before saving category/code tuning.", "error")
                return redirect(url_for("diagnosis_icd_fine_tuning"))

            if not selected_specialty:
                flash("Choose a specialty before saving category/code tuning.", "error")
                return redirect(url_for("diagnosis_icd_fine_tuning"))

            if not selected_fine_block_id:
                flash("Choose a block before saving category/code tuning.", "error")
                return redirect(url_for(
                    "diagnosis_icd_fine_tuning",
                    specialty=selected_specialty
                ))

            fine_block = execute_query(
                """
                SELECT b.id
                FROM icd_blocks b
                JOIN icd_chapters ch
                    ON ch.id = b.chapter_id
                WHERE b.id = %s
                  AND ch.version_id = %s
                """,
                (selected_fine_block_id, active_version["id"]),
                fetchone=True
            )

            if not fine_block:
                flash("Selected ICD block was not found for the active version.", "error")
                return redirect(url_for(
                    "diagnosis_icd_fine_tuning",
                    specialty=selected_specialty
                ))

            execute_query(
                """
                DELETE sei
                FROM specialty_icd_enabled_items sei
                LEFT JOIN icd_categories c
                    ON sei.item_type = 'category'
                   AND sei.item_id = c.id
                LEFT JOIN icd_codes co
                    ON sei.item_type = 'code'
                   AND sei.item_id = co.id
                LEFT JOIN icd_categories code_category
                    ON co.category_id = code_category.id
                WHERE sei.version_id = %s
                  AND sei.specialty = %s
                  AND (
                      (sei.item_type = 'category' AND c.block_id = %s)
                      OR (sei.item_type = 'code' AND code_category.block_id = %s)
                  )
                """,
                (
                    active_version["id"],
                    selected_specialty,
                    selected_fine_block_id,
                    selected_fine_block_id
                )
            )

            if request.form.get("action") == "clear_detail":
                flash("ICD category/code tuning cleared for the selected block.", "success")
                return redirect(url_for(
                    "diagnosis_icd_fine_tuning",
                    specialty=selected_specialty,
                    fine_block_id=selected_fine_block_id
                ))

            selected_category_ids = request.form.getlist("category_ids")
            selected_code_ids = request.form.getlist("code_ids")

            for category_id in selected_category_ids:
                execute_query(
                    """
                    INSERT INTO specialty_icd_enabled_items
                    (version_id, specialty, item_type, item_id, enabled_by)
                    VALUES (%s, %s, 'category', %s, %s)
                    ON DUPLICATE KEY UPDATE
                        enabled_by = VALUES(enabled_by),
                        enabled_at = CURRENT_TIMESTAMP
                    """,
                    (
                        active_version["id"],
                        selected_specialty,
                        category_id,
                        session.get("user_id")
                    )
                )

            for code_id in selected_code_ids:
                execute_query(
                    """
                    INSERT INTO specialty_icd_enabled_items
                    (version_id, specialty, item_type, item_id, enabled_by)
                    VALUES (%s, %s, 'code', %s, %s)
                    ON DUPLICATE KEY UPDATE
                        enabled_by = VALUES(enabled_by),
                        enabled_at = CURRENT_TIMESTAMP
                    """,
                    (
                        active_version["id"],
                        selected_specialty,
                        code_id,
                        session.get("user_id")
                    )
                )

            flash("ICD category/code tuning saved for the selected block.", "success")
            return redirect(url_for(
                "diagnosis_icd_fine_tuning",
                specialty=selected_specialty,
                fine_block_id=selected_fine_block_id
            ))

        fine_block_options = []
        selected_fine_block = None
        fine_categories = []
        fine_codes_by_category = {}
        enabled_category_ids = set()
        enabled_detail_code_ids = set()

        if active_version and selected_specialty:
            fine_block_options = execute_query(
                """
                SELECT DISTINCT b.id, b.block_code_range, b.title
                FROM icd_blocks b
                JOIN icd_chapters ch
                    ON ch.id = b.chapter_id
                WHERE ch.version_id = %s
                  AND b.is_active = 1
                  AND (
                      b.chapter_id IN (
                          SELECT item_id
                          FROM specialty_icd_enabled_items
                          WHERE version_id = %s
                            AND specialty = %s
                            AND item_type = 'chapter'
                      )
                      OR b.id IN (
                          SELECT item_id
                          FROM specialty_icd_enabled_items
                          WHERE version_id = %s
                            AND specialty = %s
                            AND item_type = 'block'
                      )
                  )
                ORDER BY b.block_code_range, b.title
                """,
                (
                    active_version["id"],
                    active_version["id"],
                    selected_specialty,
                    active_version["id"],
                    selected_specialty
                ),
                fetchall=True
            )

            if not selected_fine_block_id and fine_block_options:
                selected_fine_block_id = fine_block_options[0]["id"]

            if selected_fine_block_id:
                selected_fine_block = execute_query(
                    """
                    SELECT b.id, b.block_code_range, b.title
                    FROM icd_blocks b
                    JOIN icd_chapters ch
                        ON ch.id = b.chapter_id
                    WHERE b.id = %s
                      AND ch.version_id = %s
                    """,
                    (selected_fine_block_id, active_version["id"]),
                    fetchone=True
                )

                if selected_fine_block:
                    detail_items = execute_query(
                        """
                        SELECT item_type, item_id
                        FROM specialty_icd_enabled_items
                        WHERE version_id = %s
                          AND specialty = %s
                          AND item_type IN ('category', 'code')
                        """,
                        (active_version["id"], selected_specialty),
                        fetchall=True
                    )
                    enabled_category_ids = {
                        item["item_id"] for item in detail_items
                        if item["item_type"] == "category"
                    }
                    enabled_detail_code_ids = {
                        item["item_id"] for item in detail_items
                        if item["item_type"] == "code"
                    }

                    fine_categories = execute_query(
                        """
                        SELECT
                            c.id,
                            c.category_code,
                            c.title,
                            COUNT(co.id) AS billable_code_count
                        FROM icd_categories c
                        LEFT JOIN icd_codes co
                            ON co.category_id = c.id
                           AND co.billable = 1
                           AND co.is_active = 1
                        WHERE c.block_id = %s
                          AND c.is_active = 1
                        GROUP BY c.id, c.category_code, c.title, c.display_order
                        ORDER BY c.display_order, c.category_code
                        """,
                        (selected_fine_block_id,),
                        fetchall=True
                    )

                    fine_codes = execute_query(
                        """
                        SELECT id, category_id, code, description
                        FROM icd_codes
                        WHERE category_id IN (
                            SELECT id
                            FROM icd_categories
                            WHERE block_id = %s
                        )
                          AND billable = 1
                          AND is_active = 1
                        ORDER BY code
                        """,
                        (selected_fine_block_id,),
                        fetchall=True
                    )

                    for code in fine_codes:
                        fine_codes_by_category.setdefault(code["category_id"], []).append(code)

        return render_template(
            "diagnosis_icd_fine_tuning.html",
            active_version=active_version,
            specialties=specialties,
            selected_specialty=selected_specialty,
            fine_block_options=fine_block_options,
            selected_fine_block_id=selected_fine_block_id,
            selected_fine_block=selected_fine_block,
            fine_categories=fine_categories,
            fine_codes_by_category=fine_codes_by_category,
            enabled_category_ids=enabled_category_ids,
            enabled_detail_code_ids=enabled_detail_code_ids
        )

    @app.route("/admin/groups", methods=["GET", "POST"])
    def manage_groups():
        if request.method == "POST":
            group_name = request.form.get("group_name", "").strip()
            description = request.form.get("description")

            if not group_name:
                flash("Group name is required.", "error")
                return redirect(url_for("manage_groups"))

            existing_group = execute_query(
                """
                SELECT id
                FROM user_groups
                WHERE LOWER(group_name) = LOWER(%s)
                """,
                (group_name,),
                fetchone=True
            )

            if existing_group:
                flash("Group already exists.", "error")
                return redirect(url_for("manage_groups"))

            execute_query(
                """
                INSERT INTO user_groups (group_name, description)
                VALUES (%s, %s)
                """,
                (group_name, description)
            )

            flash("Group added successfully.", "success")
            return redirect(url_for("manage_groups"))

        groups = execute_query(
            """
            SELECT 
                ug.id,
                ug.group_name,
                ug.description,
                ug.is_active,
                COUNT(u.id) AS user_count
            FROM user_groups ug
            LEFT JOIN users u ON u.group_id = ug.id
            GROUP BY ug.id, ug.group_name, ug.description, ug.is_active
            ORDER BY ug.group_name
            """,
            fetchall=True
        )

        return render_template("admin_groups.html", groups=groups)


    def build_groups_pdf_report(groups, search_text=""):
        page_width = 612
        page_height = 792
        left = 42
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(groups), 1), rows_per_page):
            page_groups = groups[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Manage Groups Report) Tj ET",
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
                f"BT /F1 11 Tf {left + 6} {table_top - 7} Td (Group Name) Tj ET",
                f"BT /F1 11 Tf {left + 170} {table_top - 7} Td (Description) Tj ET",
                f"BT /F1 11 Tf {left + 380} {table_top - 7} Td (No. Users) Tj ET",
                f"BT /F1 11 Tf {left + 475} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_groups:
                for group in page_groups:
                    active_text = "Yes" if group["is_active"] else "No"
                    commands.extend([
                        f"BT /F1 10 Tf {left + 6} {y} Td ({escape_pdf_text(truncate_pdf_text(group['group_name'], 22))}) Tj ET",
                        f"BT /F1 10 Tf {left + 170} {y} Td ({escape_pdf_text(truncate_pdf_text(group['description'], 31))}) Tj ET",
                        f"BT /F1 10 Tf {left + 380} {y} Td ({escape_pdf_text(group['user_count'])}) Tj ET",
                        f"BT /F1 10 Tf {left + 475} {y} Td ({active_text}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No groups found.) Tj ET"
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


    @app.route("/admin/groups/report")
    def groups_report():
        search_text = request.args.get("q", "").strip()
        params = []
        having_clause = ""

        if search_text:
            like_search = f"%{search_text}%"
            having_clause = """
            HAVING group_name LIKE %s
                OR description LIKE %s
                OR active_text LIKE %s
                OR CAST(user_count AS CHAR) LIKE %s
            """
            params.extend([like_search, like_search, like_search, like_search])

        groups = execute_query(
            """
            SELECT
                ug.group_name,
                ug.description,
                ug.is_active,
                CASE WHEN ug.is_active = 1 THEN 'Yes Active' ELSE 'No Inactive' END AS active_text,
                COUNT(u.id) AS user_count
            FROM user_groups ug
            LEFT JOIN users u ON u.group_id = ug.id
            GROUP BY ug.id, ug.group_name, ug.description, ug.is_active
            """ + having_clause + """
            ORDER BY ug.group_name
            """,
            tuple(params),
            fetchall=True
        )

        pdf_bytes = build_groups_pdf_report(groups, search_text)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=manage_groups_report.pdf"
            }
        )


    @app.route("/admin/groups/update/<int:group_id>", methods=["POST"])
    def update_group(group_id):
        group_name = request.form.get("group_name", "").strip()
        description = request.form.get("description")
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if not group_name:
            flash("Group name is required.", "error")
            return redirect(url_for("manage_groups"))

        existing_group = execute_query(
            """
            SELECT id
            FROM user_groups
            WHERE LOWER(group_name) = LOWER(%s)
              AND id <> %s
            """,
            (group_name, group_id),
            fetchone=True
        )

        if existing_group:
            flash("Group already exists.", "error")
            return redirect(url_for("manage_groups"))

        execute_query(
            """
            UPDATE user_groups
            SET group_name = %s,
                description = %s,
                is_active = %s
            WHERE id = %s
            """,
            (group_name, description, is_active, group_id)
        )

        flash("Group updated successfully.", "success")
        return redirect(url_for("manage_groups"))


    @app.route("/admin/groups/delete/<int:group_id>", methods=["POST"])
    def delete_group(group_id):
        result = execute_query(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE group_id = %s
            """,
            (group_id,),
            fetchone=True
        )

        if result["total"] > 0:
            flash("This group cannot be deleted because users are assigned to it.", "error")
            return redirect(url_for("manage_groups"))

        execute_query(
            "DELETE FROM group_menu_permissions WHERE group_id = %s",
            (group_id,)
        )

        execute_query(
            "DELETE FROM user_groups WHERE id = %s",
            (group_id,)
        )

        flash("Group deleted successfully.", "success")
        return redirect(url_for("manage_groups"))


    @app.route("/admin/permissions", methods=["GET", "POST"])
    def manage_permissions():
        if request.method == "POST":
            group_id = request.form.get("group_id")
            menu_option_id = request.form.get("menu_option_id")

            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group_id, menu_option_id),
                fetchone=True
            )

            if existing_permission:
                flash("This permission is already added to the selected group.", "error")
                return redirect(url_for("manage_permissions"))

            execute_query(
                """
                INSERT INTO group_menu_permissions (group_id, menu_option_id)
                VALUES (%s, %s)
                """,
                (group_id, menu_option_id)
            )

            flash("Permission added successfully.", "success")
            return redirect(url_for("manage_permissions"))

        groups = execute_query(
            "SELECT * FROM user_groups ORDER BY group_name",
            fetchall=True
        )

        menu_options = execute_query(
            """
            SELECT *
            FROM menu_options
            WHERE parent_id IS NOT NULL
            ORDER BY display_order
            """,
            fetchall=True
        )

        permissions = execute_query(
            """
            SELECT 
                gmp.id,
                ug.group_name,
                mo.option_name,
                mo.endpoint_name
            FROM group_menu_permissions gmp
            JOIN user_groups ug ON gmp.group_id = ug.id
            JOIN menu_options mo ON gmp.menu_option_id = mo.id
            ORDER BY ug.group_name, mo.display_order
            """,
            fetchall=True
        )

        return render_template(
            "manage_permissions.html",
            groups=groups,
            menu_options=menu_options,
            permissions=permissions
        )


    def build_permissions_pdf_report(permissions, search_text=""):
        page_width = 612
        page_height = 792
        left = 42
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(permissions), 1), rows_per_page):
            page_permissions = permissions[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Manage Permissions Report) Tj ET",
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
                f"BT /F1 11 Tf {left + 6} {table_top - 7} Td (Group Name) Tj ET",
                f"BT /F1 11 Tf {left + 190} {table_top - 7} Td (Options) Tj ET",
                f"BT /F1 11 Tf {left + 390} {table_top - 7} Td (End Point) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_permissions:
                for permission in page_permissions:
                    commands.extend([
                        f"BT /F1 10 Tf {left + 6} {y} Td ({escape_pdf_text(truncate_pdf_text(permission['group_name'], 26))}) Tj ET",
                        f"BT /F1 10 Tf {left + 190} {y} Td ({escape_pdf_text(truncate_pdf_text(permission['option_name'], 28))}) Tj ET",
                        f"BT /F1 10 Tf {left + 390} {y} Td ({escape_pdf_text(truncate_pdf_text(permission['endpoint_name'], 24))}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No permissions found.) Tj ET"
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


    @app.route("/admin/permissions/report")
    def permissions_report():
        search_text = request.args.get("q", "").strip()
        params = []
        where_clause = ""

        if search_text:
            like_search = f"%{search_text}%"
            where_clause = """
            WHERE ug.group_name LIKE %s
               OR mo.option_name LIKE %s
               OR mo.endpoint_name LIKE %s
            """
            params.extend([like_search, like_search, like_search])

        permissions = execute_query(
            """
            SELECT
                ug.group_name,
                mo.option_name,
                mo.endpoint_name
            FROM group_menu_permissions gmp
            JOIN user_groups ug ON gmp.group_id = ug.id
            JOIN menu_options mo ON gmp.menu_option_id = mo.id
            """ + where_clause + """
            ORDER BY ug.group_name, mo.display_order
            """,
            tuple(params),
            fetchall=True
        )

        pdf_bytes = build_permissions_pdf_report(permissions, search_text)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=manage_permissions_report.pdf"
            }
        )


    @app.route("/admin/permissions/delete/<int:permission_id>", methods=["POST"])
    def delete_permission(permission_id):
        execute_query(
            "DELETE FROM group_menu_permissions WHERE id = %s",
            (permission_id,)
        )

        flash("Permission deleted successfully.", "success")
        return redirect(url_for("manage_permissions"))


    @app.route("/admin/users", methods=["GET", "POST"])
    @login_required
    @permission_required("manage_users")
    def manage_users():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            employee_id = request.form.get("employee_id")
            password = request.form.get("password", "").strip()

            if not password:
                flash("Password is required.", "error")
                return redirect(url_for("manage_users"))

            password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

            # ---- VALIDATIONS ----

            if not username:
                flash("Username is required.", "error")
                return redirect(url_for("manage_users"))

            # Duplicate username
            existing_username = execute_query(
                """
                SELECT id
                FROM users
                WHERE LOWER(username) = LOWER(%s)
                """,
                (username,),
                fetchone=True
            )

            if existing_username:
                flash("Username already exists.", "error")
                return redirect(url_for("manage_users"))

            # Employee already linked to another user
            existing_employee = execute_query(
                """
                SELECT id
                FROM users
                WHERE employee_id = %s
                """,
                (employee_id,),
                fetchone=True
            )

            if existing_employee:
                flash("This employee already has a user account.", "error")
                return redirect(url_for("manage_users"))

            employee = execute_query(
                """
                SELECT
                    id,
                    email,
                    full_name,
                    group_id
                FROM employees
                WHERE id = %s
                """,
                (employee_id,),
                fetchone=True
            )

            if not employee:
                flash("Selected employee not found.", "error")
                return redirect(url_for("manage_users"))

            if employee["email"]:
                existing_email = execute_query(
                    """
                    SELECT id
                    FROM users
                    WHERE LOWER(email) = LOWER(%s)
                    """,
                    (employee["email"],),
                    fetchone=True
                )

                if existing_email:
                    flash("Email already exists.", "error")
                    return redirect(url_for("manage_users"))

            execute_query(
                """
                INSERT INTO users
                (username, email, full_name, password_hash,
                employee_id, group_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                """,
                (
                    username,
                    employee["email"],
                    employee["full_name"],
                    password_hash,
                    employee["id"],
                    employee["group_id"]
                )
            )

            flash("User added successfully.", "success")
            return redirect(url_for("manage_users"))

        users = execute_query(
            """
            SELECT 
                u.id,
                u.username,
                u.email,
                u.employee_id,
                u.is_active,
                e.full_name,
                e.job_title,
                ug.group_name
            FROM users u
            LEFT JOIN employees e ON u.employee_id = e.id
            LEFT JOIN user_groups ug ON u.group_id = ug.id
            ORDER BY e.full_name, u.username
            """,
            fetchall=True
        )

        referenced_user_ids = get_referenced_user_ids()
        current_user_id = session.get("user_id")

        for user in users:
            user["can_delete"] = (
                user["id"] not in referenced_user_ids
                and user["id"] != current_user_id
            )
            if user["id"] == current_user_id:
                user["delete_block_reason"] = "You cannot delete the current logged-in user."
            elif user["id"] in referenced_user_ids:
                user["delete_block_reason"] = "This user is referred to by other records."
            else:
                user["delete_block_reason"] = ""

        employees = execute_query(
            """
            SELECT 
                e.id,
                e.full_name,
                e.job_title,
                ug.group_name
            FROM employees e
            JOIN user_groups ug ON e.group_id = ug.id
            WHERE e.is_active = 1
            ORDER BY e.full_name
            """,
            fetchall=True
        )

        return render_template(
            "admin_users.html",
            users=users,
            employees=employees
        )

    def quote_mysql_identifier(identifier):
        return "`" + str(identifier).replace("`", "``") + "`"

    def get_user_reference_columns():
        return execute_query(
            """
            SELECT TABLE_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND REFERENCED_TABLE_NAME = 'users'
              AND REFERENCED_COLUMN_NAME = 'id'
            ORDER BY TABLE_NAME, COLUMN_NAME
            """,
            fetchall=True
        )

    def get_referenced_user_ids():
        referenced_user_ids = set()

        for reference in get_user_reference_columns():
            table_name = quote_mysql_identifier(reference["TABLE_NAME"])
            column_name = quote_mysql_identifier(reference["COLUMN_NAME"])
            rows = execute_query(
                f"""
                SELECT DISTINCT {column_name} AS user_id
                FROM {table_name}
                WHERE {column_name} IS NOT NULL
                """,
                fetchall=True
            )

            for row in rows:
                referenced_user_ids.add(row["user_id"])

        return referenced_user_ids

    def user_is_referenced(user_id):
        for reference in get_user_reference_columns():
            table_name = quote_mysql_identifier(reference["TABLE_NAME"])
            column_name = quote_mysql_identifier(reference["COLUMN_NAME"])
            row = execute_query(
                f"""
                SELECT 1 AS found
                FROM {table_name}
                WHERE {column_name} = %s
                LIMIT 1
                """,
                (user_id,),
                fetchone=True
            )

            if row:
                return True

        return False

    def build_users_pdf_report(users, search_text=""):
        page_width = 612
        page_height = 792
        left = 42
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(users), 1), rows_per_page):
            page_users = users[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Manage Users Report) Tj ET",
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
                f"BT /F1 11 Tf {left + 6} {table_top - 7} Td (Username) Tj ET",
                f"BT /F1 11 Tf {left + 180} {table_top - 7} Td (Full Name) Tj ET",
                f"BT /F1 11 Tf {left + 390} {table_top - 7} Td (Group) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_users:
                for user in page_users:
                    commands.extend([
                        f"BT /F1 10 Tf {left + 6} {y} Td ({escape_pdf_text(truncate_pdf_text(user['username'], 24))}) Tj ET",
                        f"BT /F1 10 Tf {left + 180} {y} Td ({escape_pdf_text(truncate_pdf_text(user['full_name'], 30))}) Tj ET",
                        f"BT /F1 10 Tf {left + 390} {y} Td ({escape_pdf_text(truncate_pdf_text(user['group_name'], 22))}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No users found.) Tj ET"
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
        content_object_ids = []

        for page_content in pages:
            content_bytes = page_content.encode("latin-1", "replace")
            content_object_id = len(objects) + 1
            content_object_ids.append(content_object_id)
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


    @app.route("/admin/users/report")
    @login_required
    @permission_required("manage_users")
    def users_report():
        search_text = request.args.get("q", "").strip()
        params = []
        where_clause = ""

        if search_text:
            like_search = f"%{search_text}%"
            where_clause = """
            WHERE u.username LIKE %s
               OR e.full_name LIKE %s
               OR ug.group_name LIKE %s
            """
            params.extend([like_search, like_search, like_search])

        users = execute_query(
            """
            SELECT
                u.username,
                e.full_name,
                ug.group_name
            FROM users u
            LEFT JOIN employees e ON u.employee_id = e.id
            LEFT JOIN user_groups ug ON u.group_id = ug.id
            """ + where_clause + """
            ORDER BY e.full_name, u.username
            """,
            tuple(params),
            fetchall=True
        )

        pdf_bytes = build_users_pdf_report(users, search_text)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=manage_users_report.pdf"
            }
        )


    @app.route("/admin/users/update/<int:user_id>", methods=["POST"])
    @login_required
    @permission_required("manage_users")
    def update_user(user_id):
        username = request.form.get("username", "").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("manage_users"))

        user = execute_query(
            """
            SELECT id, employee_id
            FROM users
            WHERE id = %s
            """,
            (user_id,),
            fetchone=True
        )

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("manage_users"))

        employee = execute_query(
            """
            SELECT id, email, full_name, group_id
            FROM employees
            WHERE id = %s
            """,
            (user["employee_id"],),
            fetchone=True
        )

        if not employee:
            flash("Linked employee not found.", "error")
            return redirect(url_for("manage_users"))

        existing_username = execute_query(
            """
            SELECT id
            FROM users
            WHERE LOWER(username) = LOWER(%s)
              AND id <> %s
            """,
            (username, user_id),
            fetchone=True
        )

        if existing_username:
            flash("Username already exists.", "error")
            return redirect(url_for("manage_users"))

        if employee["email"]:
            existing_email = execute_query(
                """
                SELECT id
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                  AND id <> %s
                """,
                (employee["email"], user_id),
                fetchone=True
            )

            if existing_email:
                flash("Email already exists.", "error")
                return redirect(url_for("manage_users"))

        execute_query(
            """
            UPDATE users
            SET username = %s,
                email = %s,
                full_name = %s,
                employee_id = %s,
                group_id = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                username,
                employee["email"],
                employee["full_name"],
                employee["id"],
                employee["group_id"],
                is_active,
                user_id
            )
        )

        flash("User updated successfully.", "success")
        return redirect(url_for("manage_users"))

    @app.route("/admin/users/stop/<int:user_id>", methods=["POST"])
    @login_required
    @permission_required("manage_users")
    def stop_user(user_id):
        execute_query(
            """
            UPDATE users
            SET is_active = 0
            WHERE id = %s
            """,
            (user_id,)
        )

        flash("User stopped successfully.", "success")
        return redirect(url_for("manage_users"))

    @app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
    @login_required
    @permission_required("manage_users")
    def delete_user(user_id):
        if user_id == session.get("user_id"):
            flash("You cannot delete the current logged-in user.", "error")
            return redirect(url_for("manage_users"))

        user = execute_query(
            "SELECT id FROM users WHERE id = %s",
            (user_id,),
            fetchone=True
        )

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("manage_users"))

        if user_is_referenced(user_id):
            flash("This user cannot be deleted because it is referred to by other records.", "error")
            return redirect(url_for("manage_users"))

        execute_query(
            "DELETE FROM users WHERE id = %s",
            (user_id,)
        )

        flash("User deleted successfully.", "success")
        return redirect(url_for("manage_users"))

    @app.route("/create_first_admin")
    def create_first_admin():
        password_hash = bcrypt.generate_password_hash("admin123").decode("utf-8")

        admin_group = execute_query(
            "SELECT id FROM user_groups WHERE group_name = 'Admin'",
            fetchone=True
        )

        if not admin_group:
            flash("Admin group not found.", "error")
            return "Admin group not found."

        execute_query(
            """
            INSERT INTO employees
            (employee_code, full_name, email, phone_number, job_title, specialty, group_id, is_active)
            VALUES
            ('EMP_ADMIN', 'System Administrator', 'admin@clinic.com', '000-000-0000',
             'System Administrator', NULL, %s, 1)
            ON DUPLICATE KEY UPDATE full_name = VALUES(full_name)
            """,
            (admin_group["id"],)
        )

        employee = execute_query(
            "SELECT id FROM employees WHERE employee_code = 'EMP_ADMIN'",
            fetchone=True
        )

        execute_query(
            """
            INSERT INTO users
            (username, email, full_name, password_hash, employee_id, group_id, is_active)
            VALUES
            ('admin', 'admin@clinic.com', 'System Administrator', %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                password_hash = VALUES(password_hash),
                is_active = 1
            """,
            (password_hash, employee["id"], admin_group["id"])
        )

        return "Admin user created. Username: admin / Password: admin123"

    @app.route("/admin/menu_options", methods=["GET", "POST"])
    @login_required
    @permission_required("admin_menu_options")
    def admin_menu_options():

        # =====================================================
        # ADD NEW MENU OPTION
        # =====================================================

        if request.method == "POST":

            option_name = request.form.get("option_name", "").strip()

            endpoint_name = request.form.get(
                "endpoint_name",
                ""
            ).strip()

            url = request.form.get("url", "").strip()

            icon_class = request.form.get(
                "icon_class",
                ""
            ).strip()

            parent_id = request.form.get("parent_id")
            display_order = request.form.get(
                "display_order",
                0,
                type=int
            )

            if parent_id == "":
                parent_id = None

            if not option_name:
                flash("Option name is required.", "error")
                return redirect(url_for("admin_menu_options"))

            if menu_option_name_exists(option_name, parent_id):
                flash("An option with this name already exists under the selected parent.", "error")
                return redirect(url_for("admin_menu_options"))

            execute_query(
                """
                INSERT INTO menu_options
                (
                    option_name,
                    endpoint_name,
                    url,
                    icon_class,
                    parent_id,
                    display_order,
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
                    option_name,
                    endpoint_name,
                    url,
                    icon_class,
                    parent_id,
                    display_order
                )
            )

            flash("Menu option added successfully.", "success")

            return redirect(url_for("admin_menu_options"))

        # =====================================================
        # SEARCH
        # =====================================================

        search = request.args.get("search", "").strip()

        # =====================================================
        # MENU OPTIONS
        # =====================================================

        menu_options = execute_query(
            """
            SELECT
                mo.id,
                mo.option_name,
                mo.endpoint_name,
                mo.url,
                mo.icon_class,
                mo.parent_id,
                mo.display_order,
                mo.is_active,

                parent.option_name AS parent_name,

                (
                    SELECT COUNT(*)
                    FROM group_menu_permissions gmp
                    WHERE gmp.menu_option_id = mo.id
                ) AS permission_count,

                (
                    SELECT COUNT(*)
                    FROM menu_options child
                    WHERE child.parent_id = mo.id
                ) AS child_count

            FROM menu_options mo

            LEFT JOIN menu_options parent
                ON mo.parent_id = parent.id

            WHERE
                mo.option_name LIKE %s

            ORDER BY
                COALESCE(mo.parent_id, mo.id),
                mo.parent_id IS NOT NULL,
                mo.display_order,
                mo.option_name
            """,
            (f"%{search}%",),
            fetchall=True
        )

        # =====================================================
        # PARENT OPTIONS
        # =====================================================

        parent_options = execute_query(
            """
            SELECT
                id,
                option_name
            FROM menu_options
            WHERE parent_id IS NULL
            ORDER BY option_name
            """,
            fetchall=True
        )

        # =====================================================
        # RENDER
        # =====================================================

        return render_template(
            "admin_menu_options.html",
            menu_options=menu_options,
            parent_options=parent_options,
            search=search
        )

    def build_menu_options_pdf_report(menu_options, search_text=""):
        page_width = 612
        page_height = 792
        left = 34
        top = standard_pdf_content_top(page_height)
        row_height = 22
        rows_per_page = 24
        pages = []
        image_names = standard_pdf_image_names()

        for start in range(0, max(len(menu_options), 1), rows_per_page):
            page_options = menu_options[start:start + rows_per_page]
            commands = [
                "0.12 0.31 0.47 rg",
                f"BT /F1 18 Tf {left} {top} Td (Manage Menu Options Report) Tj ET",
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
                f"BT /F1 10 Tf {left + 4} {table_top - 7} Td (Option Name) Tj ET",
                f"BT /F1 10 Tf {left + 150} {table_top - 7} Td (Parent Name) Tj ET",
                f"BT /F1 10 Tf {left + 285} {table_top - 7} Td (No. Users) Tj ET",
                f"BT /F1 10 Tf {left + 365} {table_top - 7} Td (Order) Tj ET",
                f"BT /F1 10 Tf {left + 430} {table_top - 7} Td (Assigned) Tj ET",
                f"BT /F1 10 Tf {left + 515} {table_top - 7} Td (Active) Tj ET",
                f"{left} {table_top - 14} m {page_width - left} {table_top - 14} l S",
                "0 g"
            ])

            y = table_top - 33

            if page_options:
                for option in page_options:
                    active_text = "Yes" if option["is_active"] else "No"
                    commands.extend([
                        f"BT /F1 9 Tf {left + 4} {y} Td ({escape_pdf_text(truncate_pdf_text(option['option_name'], 22))}) Tj ET",
                        f"BT /F1 9 Tf {left + 150} {y} Td ({escape_pdf_text(truncate_pdf_text(option['parent_name'] or 'Main option', 20))}) Tj ET",
                        f"BT /F1 9 Tf {left + 285} {y} Td ({escape_pdf_text(option['user_count'])}) Tj ET",
                        f"BT /F1 9 Tf {left + 365} {y} Td ({escape_pdf_text(option['display_order'])}) Tj ET",
                        f"BT /F1 9 Tf {left + 430} {y} Td ({escape_pdf_text(option['permission_count'])}) Tj ET",
                        f"BT /F1 9 Tf {left + 515} {y} Td ({active_text}) Tj ET",
                        f"0.85 0.85 0.85 RG {left} {y - 7} m {page_width - left} {y - 7} l S",
                        "0 g"
                    ])
                    y -= row_height
            else:
                commands.append(
                    f"BT /F1 10 Tf {left + 6} {y} Td (No menu options found.) Tj ET"
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


    @app.route("/admin/menu_options/report")
    @login_required
    @permission_required("admin_menu_options")
    def menu_options_report():
        search = request.args.get("search", "").strip()

        menu_options = execute_query(
            """
            SELECT
                mo.option_name,
                parent.option_name AS parent_name,
                mo.display_order,
                mo.is_active,
                (
                    SELECT COUNT(*)
                    FROM group_menu_permissions gmp
                    WHERE gmp.menu_option_id = mo.id
                ) AS permission_count,
                (
                    SELECT COUNT(DISTINCT u.id)
                    FROM group_menu_permissions gmp
                    JOIN users u ON u.group_id = gmp.group_id
                    WHERE gmp.menu_option_id = mo.id
                ) AS user_count
            FROM menu_options mo
            LEFT JOIN menu_options parent
                ON mo.parent_id = parent.id
            WHERE mo.option_name LIKE %s
            ORDER BY
                COALESCE(mo.parent_id, mo.id),
                mo.parent_id IS NOT NULL,
                mo.display_order,
                mo.option_name
            """,
            (f"%{search}%",),
            fetchall=True
        )

        pdf_bytes = build_menu_options_pdf_report(menu_options, search)

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=menu_options_report.pdf"
            }
        )

    @app.route("/admin/menu_options/update/<int:menu_option_id>", methods=["POST"])
    @login_required
    @permission_required("admin_menu_options")
    def update_menu_option(menu_option_id):
        option_name = request.form.get("option_name", "").strip()
        endpoint_name = request.form.get("endpoint_name", "").strip() or None
        url = request.form.get("url", "").strip() or None
        icon_class = request.form.get("icon_class", "").strip() or None
        parent_id = request.form.get("parent_id") or None
        display_order = request.form.get("display_order") or 0
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if not option_name:
            flash("Option name is required.", "error")
            return redirect(url_for("admin_menu_options"))

        if str(menu_option_id) == str(parent_id):
            flash("A menu option cannot be its own parent.", "error")
            return redirect(url_for("admin_menu_options"))

        if menu_option_name_exists(option_name, parent_id, menu_option_id):
            flash("An option with this name already exists under the selected parent.", "error")
            return redirect(url_for("admin_menu_options"))

        execute_query(
            """
            UPDATE menu_options
            SET option_name = %s,
                endpoint_name = %s,
                url = %s,
                icon_class = %s,
                parent_id = %s,
                display_order = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                option_name,
                endpoint_name,
                url,
                icon_class,
                parent_id,
                display_order,
                is_active,
                menu_option_id
            )
        )

        flash("Menu option updated successfully.", "success")
        return redirect(url_for("admin_menu_options"))


    @app.route("/admin/menu_options/delete/<int:menu_option_id>", methods=["POST"])
    @login_required
    @permission_required("admin_menu_options")
    def delete_menu_option(menu_option_id):
        assigned = execute_query(
            """
            SELECT COUNT(*) AS total
            FROM group_menu_permissions
            WHERE menu_option_id = %s
            """,
            (menu_option_id,),
            fetchone=True
        )

        children = execute_query(
            """
            SELECT COUNT(*) AS total
            FROM menu_options
            WHERE parent_id = %s
            """,
            (menu_option_id,),
            fetchone=True
        )

        if assigned["total"] > 0:
            flash("This menu option cannot be deleted because it is assigned to a group.", "error")
            return redirect(url_for("admin_menu_options"))

        if children["total"] > 0:
            flash("This main menu option cannot be deleted because it has child options.", "error")
            return redirect(url_for("admin_menu_options"))

        execute_query(
            "DELETE FROM menu_options WHERE id = %s",
            (menu_option_id,)
        )

        flash("Menu option deleted successfully.", "success")
        return redirect(url_for("admin_menu_options"))

    @app.route("/admin/menu_options/add_ajax", methods=["POST"])
    @login_required
    @permission_required("admin_menu_options")
    def add_menu_option_ajax():
        option_name = request.form.get("option_name", "").strip()
        endpoint_name = request.form.get("endpoint_name", "").strip() or None
        url = request.form.get("url", "").strip() or None
        icon_class = request.form.get("icon_class", "").strip() or None
        parent_id = request.form.get("parent_id") or None
        display_order = request.form.get("display_order") or 0

        if not option_name:
            return {
                "success": False,
                "message": "Option name is required."
            }, 400

        if menu_option_name_exists(option_name, parent_id):
            return {
                "success": False,
                "message": "An option with this name already exists under the selected parent."
            }, 400

        execute_query(
            """
            INSERT INTO menu_options
            (option_name, endpoint_name, url, icon_class,
            parent_id, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """,
            (
                option_name,
                endpoint_name,
                url,
                icon_class,
                parent_id,
                display_order
            )
        )

        return {"success": True}
