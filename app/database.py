import sqlite3

connection = sqlite3.connect("database.db")
cursor = connection.cursor()


def get_connection(db_name):
    try:
        return sqlite3.connect(db_name)
    except Exception as e:
        print(f"Error: {e}")


connection.close()
