import mysql.connector
from config import DB_CONFIG


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def execute_query(query, params=None, fetchone=False, fetchall=False):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(query, params or ())

        if fetchone:
            result = cursor.fetchone()
            return result

        if fetchall:
            result = cursor.fetchall()
            return result

        conn.commit()
        return cursor.lastrowid

    except Exception as e:
        conn.rollback()
        print("Database error:", e)
        raise

    finally:
        cursor.close()
        conn.close()