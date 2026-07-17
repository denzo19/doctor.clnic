from functools import wraps

from flask import flash, redirect, session, url_for

from database import execute_query


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def permission_required(endpoint_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if "group_id" not in session:
                return redirect(url_for("login"))

            permission = execute_query(
                """
                SELECT gmp.id
                FROM group_menu_permissions gmp
                JOIN menu_options mo
                    ON gmp.menu_option_id = mo.id
                WHERE gmp.group_id = %s
                  AND mo.endpoint_name = %s
                """,
                (session["group_id"], endpoint_name),
                fetchone=True
            )

            if not permission:
                flash("Access denied.", "error")
                return redirect(url_for("home"))

            return f(*args, **kwargs)

        return decorated_function
    return decorator
