import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_connection


CDC_SOURCE_URL = (
    "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026/"
    "icd10cm-table%20and%20index-2026.zip"
)
ZIP_PATH = Path.home() / "AppData" / "Local" / "Temp" / "icd10cm-table-index-2026.zip"
XML_NAME = "icd10cm-tabular-2026.xml"
VERSION_YEAR = 2026


def clean_text(value):
    return " ".join((value or "").split())


def code_sort_value(code):
    return code.replace(".", "")


def chapter_title_and_range(description):
    match = re.search(r"\(([^()]+)\)\s*$", description)
    if not match:
        return description, ""

    code_range = match.group(1)
    title = description[:match.start()].strip()
    return title, code_range


def insert_or_update(cursor, sql, params):
    cursor.execute(sql, params)


def fetch_id(cursor, sql, params):
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return row["id"] if row else None


def import_icd():
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"CDC ICD-10-CM ZIP not found: {ZIP_PATH}")

    with zipfile.ZipFile(ZIP_PATH) as archive:
        root = ET.fromstring(archive.read(XML_NAME))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    chapter_count = 0
    block_count = 0
    category_count = 0
    code_count = 0

    try:
        conn.start_transaction()

        insert_or_update(
            cursor,
            """
            INSERT INTO icd_versions
            (version_year, effective_date, source_name, source_url, is_active)
            VALUES (%s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                effective_date = VALUES(effective_date),
                source_name = VALUES(source_name),
                source_url = VALUES(source_url),
                is_active = 1
            """,
            (
                VERSION_YEAR,
                "2025-10-01",
                "CDC ICD-10-CM Tabular List",
                CDC_SOURCE_URL,
            ),
        )

        cursor.execute(
            "UPDATE icd_versions SET is_active = CASE WHEN version_year = %s THEN 1 ELSE 0 END",
            (VERSION_YEAR,),
        )

        version_id = fetch_id(
            cursor,
            "SELECT id FROM icd_versions WHERE version_year = %s",
            (VERSION_YEAR,),
        )

        for chapter_index, chapter in enumerate(root.findall("chapter"), start=1):
            chapter_code = clean_text(chapter.findtext("name"))
            chapter_description = clean_text(chapter.findtext("desc"))
            chapter_title, chapter_range = chapter_title_and_range(chapter_description)

            insert_or_update(
                cursor,
                """
                INSERT INTO icd_chapters
                (version_id, chapter_code, code_range, title, display_order, is_active)
                VALUES (%s, %s, %s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE
                    code_range = VALUES(code_range),
                    title = VALUES(title),
                    display_order = VALUES(display_order),
                    is_active = 1
                """,
                (version_id, chapter_code, chapter_range, chapter_title, chapter_index),
            )
            chapter_id = fetch_id(
                cursor,
                """
                SELECT id
                FROM icd_chapters
                WHERE version_id = %s
                  AND chapter_code = %s
                """,
                (version_id, chapter_code),
            )
            chapter_count += 1

            for block_index, section in enumerate(chapter.findall("section"), start=1):
                block_range = clean_text(section.attrib.get("id", ""))
                block_title = clean_text(section.findtext("desc")) or block_range

                insert_or_update(
                    cursor,
                    """
                    INSERT INTO icd_blocks
                    (chapter_id, block_code_range, title, display_order, is_active)
                    VALUES (%s, %s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                        title = VALUES(title),
                        display_order = VALUES(display_order),
                        is_active = 1
                    """,
                    (chapter_id, block_range, block_title, block_index),
                )
                block_id = fetch_id(
                    cursor,
                    """
                    SELECT id
                    FROM icd_blocks
                    WHERE chapter_id = %s
                      AND block_code_range = %s
                    """,
                    (chapter_id, block_range),
                )
                block_count += 1

                category_ids = {}

                def ensure_category(category_code, title, display_order):
                    if category_code in category_ids:
                        return category_ids[category_code]

                    insert_or_update(
                        cursor,
                        """
                        INSERT INTO icd_categories
                        (block_id, category_code, title, display_order, is_active)
                        VALUES (%s, %s, %s, %s, 1)
                        ON DUPLICATE KEY UPDATE
                            title = VALUES(title),
                            display_order = VALUES(display_order),
                            is_active = 1
                        """,
                        (block_id, category_code, title, display_order),
                    )
                    category_id = fetch_id(
                        cursor,
                        """
                        SELECT id
                        FROM icd_categories
                        WHERE block_id = %s
                          AND category_code = %s
                        """,
                        (block_id, category_code),
                    )
                    category_ids[category_code] = category_id
                    return category_id

                def walk_diag(diag, display_order, current_category_code=None, current_category_id=None):
                    nonlocal category_count, code_count

                    code = clean_text(diag.findtext("name"))
                    description = clean_text(diag.findtext("desc"))
                    child_diags = diag.findall("diag")
                    normalized = code_sort_value(code)

                    category_code = current_category_code
                    category_id = current_category_id

                    if len(normalized) == 3 and "." not in code:
                        category_code = code
                        category_id = ensure_category(category_code, description, display_order)
                        category_count += 1

                    if category_code and category_id:
                        insert_or_update(
                            cursor,
                            """
                            INSERT INTO icd_codes
                            (category_id, code, description, billable, is_active)
                            VALUES (%s, %s, %s, %s, 1)
                            ON DUPLICATE KEY UPDATE
                                description = VALUES(description),
                                billable = VALUES(billable),
                                is_active = 1
                            """,
                            (category_id, code, description, 0 if child_diags else 1),
                        )
                        code_count += 1

                    for child_index, child in enumerate(child_diags, start=1):
                        walk_diag(
                            child,
                            (display_order * 1000) + child_index,
                            category_code,
                            category_id,
                        )

                for diag_index, diag in enumerate(section.findall("diag"), start=1):
                    walk_diag(diag, diag_index)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()

    print(f"Imported ICD-10-CM {VERSION_YEAR}")
    print(f"Chapters: {chapter_count}")
    print(f"Blocks: {block_count}")
    print(f"Categories: {category_count}")
    print(f"Codes: {code_count}")


if __name__ == "__main__":
    import_icd()
