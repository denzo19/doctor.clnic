from database import execute_query


_home_menu_bootstrapped = False


def build_user_menu(group_id, language="en"):
    option_label = (
        "COALESCE(NULLIF(mo.option_name_ar, ''), mo.option_name)"
        if language == "ar" else
        "mo.option_name"
    )
    parent_label = (
        "COALESCE(NULLIF(parent.option_name_ar, ''), parent.option_name)"
        if language == "ar" else
        "parent.option_name"
    )

    rows = execute_query(
        f"""
        SELECT 
            mo.id AS option_id,
            mo.option_name,
            {option_label} AS option_label,
            mo.endpoint_name,
            mo.url,
            mo.icon_class,
            mo.parent_id,
            mo.display_order,
            parent.id AS parent_id,
            parent.option_name AS parent_name,
            {parent_label} AS parent_label,
            parent.icon_class AS parent_icon,
            parent.display_order AS parent_display_order
        FROM group_menu_permissions gmp
        JOIN menu_options mo ON gmp.menu_option_id = mo.id
        LEFT JOIN menu_options parent ON mo.parent_id = parent.id
        WHERE gmp.group_id = %s
          AND mo.is_active = TRUE
          AND (mo.parent_id IS NULL OR parent.is_active = TRUE)
        ORDER BY
            COALESCE(parent.display_order, mo.display_order),
            CASE WHEN mo.parent_id IS NULL THEN 0 ELSE 1 END,
            mo.display_order
        """,
        (group_id,),
        fetchall=True
    )

    menu = {}

    for row in rows:
        parent_id = row["parent_id"] or row["option_id"]

        if parent_id not in menu:
            menu[parent_id] = {
                "name": row["parent_label"] or row["option_label"],
                "icon": row["parent_icon"] or row["icon_class"],
                "url": row["url"] if row["parent_id"] is None else None,
                "children": []
            }

        if row["parent_id"] is not None:
            menu[parent_id]["children"].append({
                "name": row["option_label"],
                "endpoint": row["endpoint_name"],
                "url": row["url"],
                "icon": row["icon_class"]
            })

    return list(menu.values())


def ensure_home_menu():
    global _home_menu_bootstrapped

    if _home_menu_bootstrapped:
        return

    try:
        home_option = execute_query(
            """
            SELECT id
            FROM menu_options
            WHERE endpoint_name = 'home'
            LIMIT 1
            """,
            fetchone=True
        )

        if home_option:
            home_option_id = home_option["id"]
            execute_query(
                """
                UPDATE menu_options
                SET option_name = 'Home',
                    url = '/',
                    icon_class = 'fas fa-home',
                    parent_id = NULL,
                    display_order = 0,
                    is_active = 1
                WHERE id = %s
                """,
                (home_option_id,)
            )
        else:
            execute_query(
                """
                INSERT INTO menu_options
                (option_name, endpoint_name, url, icon_class, parent_id, display_order, is_active)
                VALUES ('Home', 'home', '/', 'fas fa-home', NULL, 0, 1)
                """
            )
            home_option = execute_query(
                """
                SELECT id
                FROM menu_options
                WHERE endpoint_name = 'home'
                LIMIT 1
                """,
                fetchone=True
            )
            home_option_id = home_option["id"]

        groups = execute_query("SELECT id FROM user_groups", fetchall=True)

        for group in groups:
            existing_permission = execute_query(
                """
                SELECT id
                FROM group_menu_permissions
                WHERE group_id = %s
                  AND menu_option_id = %s
                """,
                (group["id"], home_option_id),
                fetchone=True
            )

            if not existing_permission:
                execute_query(
                    """
                    INSERT INTO group_menu_permissions
                    (group_id, menu_option_id)
                    VALUES (%s, %s)
                    """,
                    (group["id"], home_option_id)
                )

        _home_menu_bootstrapped = True
    except Exception as error:
        print("Home menu bootstrap error:", error)
