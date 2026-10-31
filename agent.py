
import os
import re
import json
import shutil

from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import mysql.connector
from mysql.connector import Error


# ============================================================
# 1. INITIAL SETUP
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")

if not GEMINI_API_KEY:
    raise ValueError("Gemini API key not found in .env file.")

client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-3.5-flash-lite"

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"

STORAGE_DIR.mkdir(exist_ok=True)

print("Gemini client initialized.")


# ============================================================
# 2. VALIDATION FUNCTIONS
# ============================================================

IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]{0,62}$"
)

ALLOWED_SQL_TYPES = {
    "INTEGER",
    "INT",
    "BIGINT",
    "SMALLINT",
    "VARCHAR",
    "TEXT",
    "DATE",
    "DATETIME",
    "DECIMAL",
    "FLOAT",
    "DOUBLE",
    "BOOLEAN"
}


def validate_identifier(name):
    return (
        isinstance(name, str)
        and bool(IDENTIFIER_PATTERN.fullmatch(name))
    )


def quote_identifier(name):
    if not validate_identifier(name):
        raise ValueError("Invalid SQL identifier.")

    return f"`{name}`"


def get_safe_file_path(file_path):

    target = (STORAGE_DIR / file_path).resolve()

    try:
        target.relative_to(STORAGE_DIR.resolve())
    except ValueError:
        raise ValueError(
            "Access denied: path is outside approved storage."
        )

    return target


def parse_json_object(value, field_name):

    try:
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ValueError(
            f"{field_name} must contain valid JSON."
        )

    if not isinstance(result, dict) or not result:
        raise ValueError(
            f"{field_name} must be a non-empty JSON object."
        )

    return result


def confirm_action(message):

    answer = input(
        f"\nCONFIRMATION REQUIRED: {message}\n"
        "Type YES to continue: "
    )

    return answer.strip().upper() == "YES"


# ============================================================
# 3. MYSQL CONNECTION
# ============================================================

def get_mysql_connection(database_name=None):

    config = {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD
    }

    if database_name:
        if not validate_identifier(database_name):
            raise ValueError("Invalid database name.")

        config["database"] = database_name

    return mysql.connector.connect(**config)


def test_mysql_connection():

    connection = None

    try:
        connection = get_mysql_connection()

        if connection.is_connected():
            print("MySQL Server connection successful.")

    except Error as error:
        raise RuntimeError(
            f"Could not connect to MySQL Server: {error}"
        )

    finally:
        if connection and connection.is_connected():
            connection.close()


test_mysql_connection()


# ============================================================
# 4. DEMO DATABASE INITIALIZATION
# ============================================================

def initialize_demo_database():

    connection = None
    cursor = None

    try:

        connection = get_mysql_connection()
        cursor = connection.cursor()

        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS `CollegeDB`"
        )

        cursor.execute(
            "USE `CollegeDB`"
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL
            )
        """)

        cursor.execute(
            "SELECT COUNT(*) FROM students"
        )

        count = cursor.fetchone()[0]

        if count == 0:

            cursor.executemany(
                """
                INSERT INTO students
                (id, name, department)
                VALUES (%s, %s, %s)
                """,
                [
                    (101, "Rahul", "CSE"),
                    (102, "Priya", "ECE"),
                    (103, "Arjun", "CSE")
                ]
            )

        connection.commit()

        print("CollegeDB demo database initialized.")

    except Error as error:

        if connection:
            connection.rollback()

        raise RuntimeError(
            f"Demo database initialization failed: {error}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


initialize_demo_database()


# ============================================================
# 5. TEMPORARY SECURITY CHECK
# ============================================================

# This is a prototype policy check.
# Member 3 will integrate the actual Security Engine.

FILE_OPERATIONS = {
    "search",
    "read",
    "create_folder",
    "copy",
    "rename",
    "edit",
    "delete"
}

DATABASE_OPERATIONS = {
    "create_database",
    "create_table",
    "insert",
    "read",
    "search",
    "update",
    "delete",
    "list_tables",
    "describe_table"
}


def security_check(tool_name, arguments):

    print("\n[SECURITY ENGINE] Checking request...")

    operation = arguments.get("operation")

    if tool_name == "file_access_manager":

        if operation not in FILE_OPERATIONS:
            return False, "File operation is not permitted."

        try:

            if operation in {"read", "edit", "delete"}:
                get_safe_file_path(arguments["file_path"])

            elif operation == "create_folder":
                get_safe_file_path(arguments["folder_name"])

            elif operation == "copy":
                get_safe_file_path(arguments["source"])
                get_safe_file_path(arguments["destination"])

            elif operation == "rename":

                get_safe_file_path(arguments["file_path"])

                new_name = arguments.get("new_name", "")

                if (
                    not new_name
                    or Path(new_name).name != new_name
                    or new_name in {".", ".."}
                ):
                    return False, "Invalid new file name."

        except (KeyError, ValueError) as error:

            return False, str(error)

    elif tool_name == "database_manager":

        if operation not in DATABASE_OPERATIONS:
            return False, "Database operation is not permitted."

        database_name = arguments.get(
            "database_name", "CollegeDB"
        )

        if not validate_identifier(database_name):
            return False, "Invalid database name."

        if operation not in {
            "create_database",
            "list_tables"
        }:

            if not validate_identifier(
                arguments.get("table")
            ):
                return False, "Invalid table name."

        if operation == "create_table":

            columns = arguments.get("columns")

            if not isinstance(columns, list) or not columns:
                return False, "Column definitions are required."

            for column in columns:

                if not isinstance(column, dict):
                    return False, "Invalid column definition."

                if not validate_identifier(
                    column.get("name")
                ):
                    return False, "Invalid column name."

                column_type = column.get(
                    "type", "TEXT"
                ).upper()

                if column_type not in ALLOWED_SQL_TYPES:
                    return False, "Unsupported column type."

        if operation in {"insert", "update"}:

            json_field = (
                "record_json"
                if operation == "insert"
                else "updates_json"
            )

            try:
                parse_json_object(
                    arguments.get(json_field),
                    json_field
                )
            except ValueError as error:
                return False, str(error)

    else:

        return False, "Unknown tool."

    print("[SECURITY ENGINE] Request passed prototype checks.")
    print("[SECURITY ENGINE] ALLOW")

    return True, "Approved"


# ============================================================
# 6. FILE ACCESS MANAGER
# ============================================================

def file_access_manager(operation, **arguments):

    try:

        # SEARCH FILES

        if operation == "search":

            keyword = arguments.get("keyword", "")

            results = []

            for item in STORAGE_DIR.rglob("*"):

                if keyword.lower() in item.name.lower():

                    results.append(
                        str(item.relative_to(STORAGE_DIR))
                    )

            return {
                "status": "SUCCESS",
                "files": results
            }

        # READ FILE

        elif operation == "read":

            path = get_safe_file_path(
                arguments["file_path"]
            )

            if not path.is_file():
                return {
                    "status": "ERROR",
                    "message": "File not found."
                }

            content = path.read_text(
                encoding="utf-8"
            )

            return {
                "status": "SUCCESS",
                "content": content
            }

        # CREATE FOLDER

        elif operation == "create_folder":

            path = get_safe_file_path(
                arguments["folder_name"]
            )

            path.mkdir(
                parents=True,
                exist_ok=True
            )

            return {
                "status": "SUCCESS",
                "message": "Folder created successfully."
            }

        # COPY FILE

        elif operation == "copy":

            source = get_safe_file_path(
                arguments["source"]
            )

            destination = get_safe_file_path(
                arguments["destination"]
            )

            if not source.is_file():
                return {
                    "status": "ERROR",
                    "message": "Source file not found."
                }

            if destination.exists():
                return {
                    "status": "ERROR",
                    "message": "Destination already exists."
                }

            destination.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            shutil.copy2(source, destination)

            return {
                "status": "SUCCESS",
                "message": "File copied successfully."
            }

        # RENAME FILE

        elif operation == "rename":

            source = get_safe_file_path(
                arguments["file_path"]
            )

            new_name = arguments["new_name"]

            if (
                not new_name
                or Path(new_name).name != new_name
                or new_name in {".", ".."}
            ):
                return {
                    "status": "ERROR",
                    "message": "Invalid new file name."
                }

            if not source.is_file():
                return {
                    "status": "ERROR",
                    "message": "File not found."
                }

            destination = get_safe_file_path(
                str(
                    source.relative_to(STORAGE_DIR).parent
                    / new_name
                )
            )

            if destination.exists():
                return {
                    "status": "ERROR",
                    "message": "Destination already exists."
                }

            if not confirm_action(
                f"Rename {source.name} to {new_name}"
            ):
                return {
                    "status": "CANCELLED",
                    "message": "Rename cancelled."
                }

            source.rename(destination)

            return {
                "status": "SUCCESS",
                "message": "File renamed successfully."
            }

        # EDIT FILE

        elif operation == "edit":

            path = get_safe_file_path(
                arguments["file_path"]
            )

            if not path.is_file():
                return {
                    "status": "ERROR",
                    "message": "File not found."
                }

            content = arguments.get("content")

            if not isinstance(content, str):
                return {
                    "status": "ERROR",
                    "message": "New content is required."
                }

            if not confirm_action(
                f"Replace the contents of {path.name}"
            ):
                return {
                    "status": "CANCELLED",
                    "message": "Edit cancelled."
                }

            path.write_text(
                content,
                encoding="utf-8"
            )

            return {
                "status": "SUCCESS",
                "message": "File edited successfully."
            }

        # DELETE FILE

        elif operation == "delete":

            path = get_safe_file_path(
                arguments["file_path"]
            )

            if not path.is_file():
                return {
                    "status": "ERROR",
                    "message": "File not found."
                }

            if not confirm_action(
                f"Delete {path.name}"
            ):
                return {
                    "status": "CANCELLED",
                    "message": "Delete cancelled."
                }

            path.unlink()

            return {
                "status": "SUCCESS",
                "message": "File deleted successfully."
            }

        return {
            "status": "ERROR",
            "message": "Unsupported file operation."
        }

    except Exception as error:

        return {
            "status": "ERROR",
            "message": str(error)
        }


# ============================================================
# 7. DATABASE MANAGER - MYSQL
# ============================================================

def database_manager(operation, **arguments):

    database_name = arguments.get(
        "database_name", "CollegeDB"
    )

    connection = None
    cursor = None

    try:

        if not validate_identifier(database_name):
            return {
                "status": "ERROR",
                "message": "Invalid database name."
            }

        # CREATE DATABASE

        if operation == "create_database":

            connection = get_mysql_connection()
            cursor = connection.cursor()

            cursor.execute(
                f"CREATE DATABASE {quote_identifier(database_name)}"
            )

            return {
                "status": "SUCCESS",
                "message": f"Database {database_name} created successfully."
            }

        # CONNECT TO SELECTED DATABASE

        connection = get_mysql_connection(database_name)
        cursor = connection.cursor()

        table = arguments.get("table")

        # CREATE TABLE

        if operation == "create_table":

            if not validate_identifier(table):
                return {
                    "status": "ERROR",
                    "message": "Invalid table name."
                }

            columns = arguments.get("columns", [])

            if not columns:
                return {
                    "status": "ERROR",
                    "message": "Column definitions are required."
                }

            definitions = []

            for column in columns:

                name = column["name"]
                column_type = column.get(
                    "type", "TEXT"
                ).upper()

                if not validate_identifier(name):
                    return {
                        "status": "ERROR",
                        "message": "Invalid column name."
                    }

                if column_type not in ALLOWED_SQL_TYPES:
                    return {
                        "status": "ERROR",
                        "message": "Unsupported column type."
                    }

                # Optional VARCHAR length

                if column_type == "VARCHAR":

                    length = column.get("length", 255)

                    if (
                        not isinstance(length, int)
                        or not 1 <= length <= 65535
                    ):
                        return {
                            "status": "ERROR",
                            "message": "Invalid VARCHAR length."
                        }

                    column_type = f"VARCHAR({length})"

                definition = (
                    f"{quote_identifier(name)} {column_type}"
                )

                if column.get("primary_key"):
                    definition += " PRIMARY KEY"

                if column.get("not_null"):
                    definition += " NOT NULL"

                definitions.append(definition)

            sql = (
                f"CREATE TABLE {quote_identifier(table)} "
                f"({', '.join(definitions)})"
            )

            cursor.execute(sql)

            return {
                "status": "SUCCESS",
                "message": f"Table {table} created successfully."
            }

        # LIST TABLES

        elif operation == "list_tables":

            cursor.execute("SHOW TABLES")

            tables = [
                row[0] for row in cursor.fetchall()
            ]

            return {
                "status": "SUCCESS",
                "tables": tables
            }

        # VALIDATE TABLE

        if not validate_identifier(table):
            return {
                "status": "ERROR",
                "message": "Invalid table name."
            }

        # CHECK TABLE EXISTS

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (database_name, table)
        )

        if cursor.fetchone()[0] == 0:
            return {
                "status": "ERROR",
                "message": "Table not found."
            }

        # DESCRIBE TABLE

        if operation == "describe_table":

            cursor.execute(
                f"DESCRIBE {quote_identifier(table)}"
            )

            columns = cursor.fetchall()

            description = []

            for column in columns:

                description.append({
                    "name": column[0],
                    "type": column[1],
                    "nullable": column[2],
                    "key": column[3],
                    "default": column[4],
                    "extra": column[5]
                })

            return {
                "status": "SUCCESS",
                "columns": description
            }

        # GET TABLE COLUMNS AND PRIMARY KEY

        cursor.execute(
            f"DESCRIBE {quote_identifier(table)}"
        )

        table_columns = cursor.fetchall()

        valid_columns = {
            column[0] for column in table_columns
        }

        primary_key = next(
            (
                column[0]
                for column in table_columns
                if column[3] == "PRI"
            ),
            None
        )

        # READ RECORDS

        if operation == "read":

            record_id = arguments.get("record_id")

            if record_id is None:

                cursor.execute(
                    f"SELECT * FROM {quote_identifier(table)}"
                )

            else:

                if not primary_key:
                    return {
                        "status": "ERROR",
                        "message": "Table has no primary key."
                    }

                cursor.execute(
                    f"SELECT * FROM {quote_identifier(table)} "
                    f"WHERE {quote_identifier(primary_key)} = %s",
                    (record_id,)
                )

            rows = cursor.fetchall()

            return {
                "status": "SUCCESS",
                "columns": [
                    column[0] for column in cursor.description
                ],
                "records": rows
            }

        # SEARCH RECORDS

        elif operation == "search":

            keyword = arguments.get("keyword")

            if not keyword:

                cursor.execute(
                    f"SELECT * FROM {quote_identifier(table)}"
                )

            else:

                conditions = " OR ".join(
                    f"CAST({quote_identifier(column)} AS CHAR) LIKE %s"
                    for column in valid_columns
                )

                sql = (
                    f"SELECT * FROM {quote_identifier(table)} "
                    f"WHERE {conditions}"
                )

                values = [
                    f"%{keyword}%"
                    for _ in valid_columns
                ]

                cursor.execute(sql, values)

            rows = cursor.fetchall()

            return {
                "status": "SUCCESS",
                "columns": [
                    column[0] for column in cursor.description
                ],
                "records": rows
            }

        # INSERT RECORD

        elif operation == "insert":

            record = parse_json_object(
                arguments.get("record_json"),
                "record_json"
            )

            if not set(record).issubset(valid_columns):
                return {
                    "status": "ERROR",
                    "message": "One or more columns do not exist."
                }

            columns = list(record.keys())

            column_sql = ", ".join(
                quote_identifier(column)
                for column in columns
            )

            placeholders = ", ".join(
                ["%s"] * len(columns)
            )

            sql = (
                f"INSERT INTO {quote_identifier(table)} "
                f"({column_sql}) VALUES ({placeholders})"
            )

            cursor.execute(
                sql,
                list(record.values())
            )

            connection.commit()

            return {
                "status": "SUCCESS",
                "message": "Record inserted successfully.",
                "record_id": cursor.lastrowid
            }

        # UPDATE RECORD

        elif operation == "update":

            record_id = arguments.get("record_id")

            if record_id is None:
                return {
                    "status": "ERROR",
                    "message": "Record ID is required."
                }

            if not primary_key:
                return {
                    "status": "ERROR",
                    "message": "Table has no primary key."
                }

            updates = parse_json_object(
                arguments.get("updates_json"),
                "updates_json"
            )

            if not set(updates).issubset(valid_columns):
                return {
                    "status": "ERROR",
                    "message": "One or more columns do not exist."
                }

            if primary_key in updates:
                return {
                    "status": "ERROR",
                    "message": "Updating the primary key is not supported."
                }

            if not confirm_action(
                f"Update record {record_id} in {table}"
            ):
                return {
                    "status": "CANCELLED",
                    "message": "Update cancelled."
                }

            set_clause = ", ".join(
                f"{quote_identifier(column)} = %s"
                for column in updates
            )

            values = list(updates.values())
            values.append(record_id)

            sql = (
                f"UPDATE {quote_identifier(table)} "
                f"SET {set_clause} "
                f"WHERE {quote_identifier(primary_key)} = %s"
            )

            cursor.execute(sql, values)
            connection.commit()

            return {
                "status": "SUCCESS",
                "message": "Record updated successfully.",
                "rows_updated": cursor.rowcount
            }

        # DELETE RECORD

        elif operation == "delete":

            record_id = arguments.get("record_id")

            if record_id is None:
                return {
                    "status": "ERROR",
                    "message": "Record ID is required."
                }

            if not primary_key:
                return {
                    "status": "ERROR",
                    "message": "Table has no primary key."
                }

            if not confirm_action(
                f"Delete record {record_id} from {table}"
            ):
                return {
                    "status": "CANCELLED",
                    "message": "Delete cancelled."
                }

            cursor.execute(
                f"DELETE FROM {quote_identifier(table)} "
                f"WHERE {quote_identifier(primary_key)} = %s",
                (record_id,)
            )

            connection.commit()

            return {
                "status": "SUCCESS",
                "message": "Record deleted successfully.",
                "rows_deleted": cursor.rowcount
            }

        return {
            "status": "ERROR",
            "message": "Unsupported database operation."
        }

    except Error as error:

        if connection and connection.is_connected():
            connection.rollback()

        return {
            "status": "ERROR",
            "message": str(error)
        }

    except Exception as error:

        if connection and connection.is_connected():
            connection.rollback()

        return {
            "status": "ERROR",
            "message": str(error)
        }

    finally:

        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


# ============================================================
# 8. GEMINI FUNCTION DECLARATIONS
# ============================================================

file_access_declaration = types.FunctionDeclaration(

    name="file_access_manager",

    description=(
        "Manage files inside the approved storage folder. "
        "Search, read, create folders, copy, rename, edit and delete files."
    ),

    parameters={

        "type": "OBJECT",

        "properties": {

            "operation": {
                "type": "STRING",
                "enum": [
                    "search",
                    "read",
                    "create_folder",
                    "copy",
                    "rename",
                    "edit",
                    "delete"
                ]
            },

            "keyword": {
                "type": "STRING"
            },

            "file_path": {
                "type": "STRING"
            },

            "folder_name": {
                "type": "STRING"
            },

            "source": {
                "type": "STRING"
            },

            "destination": {
                "type": "STRING"
            },

            "new_name": {
                "type": "STRING"
            },

            "content": {
                "type": "STRING"
            }
        },

        "required": ["operation"]
    }
)


database_declaration = types.FunctionDeclaration(

    name="database_manager",

    description=(
        "Manage MySQL databases. Create databases and tables, "
        "insert, read, search, update and delete records, "
        "list tables and describe tables."
    ),

    parameters={

        "type": "OBJECT",

        "properties": {

            "operation": {
                "type": "STRING",
                "enum": [
                    "create_database",
                    "create_table",
                    "insert",
                    "read",
                    "search",
                    "update",
                    "delete",
                    "list_tables",
                    "describe_table"
                ]
            },

            "database_name": {
                "type": "STRING"
            },

            "table": {
                "type": "STRING"
            },

            "columns": {
                "type": "ARRAY",

                "items": {

                    "type": "OBJECT",

                    "properties": {

                        "name": {
                            "type": "STRING"
                        },

                        "type": {
                            "type": "STRING",
                            "enum": [
                                "INTEGER",
                                "INT",
                                "BIGINT",
                                "SMALLINT",
                                "VARCHAR",
                                "TEXT",
                                "DATE",
                                "DATETIME",
                                "DECIMAL",
                                "FLOAT",
                                "DOUBLE",
                                "BOOLEAN"
                            ]
                        },

                        "length": {
                            "type": "INTEGER"
                        },

                        "primary_key": {
                            "type": "BOOLEAN"
                        },

                        "not_null": {
                            "type": "BOOLEAN"
                        }
                    },

                    "required": [
                        "name",
                        "type"
                    ]
                }
            },

            "record_json": {
                "type": "STRING",
                "description": "JSON string containing record data."
            },

            "updates_json": {
                "type": "STRING",
                "description": "JSON string containing update values."
            },

            "record_id": {
                "type": "STRING"
            },

            "keyword": {
                "type": "STRING"
            }
        },

        "required": ["operation"]
    }
)


# ============================================================
# 9. GEMINI AGENT CONFIGURATION
# ============================================================

system_instruction = """
You are Aegis AI, an AI-powered secure file and database assistant.

AVAILABLE TOOLS:

1. file_access_manager:
- search
- read
- create_folder
- copy
- rename
- edit
- delete

2. database_manager:
- create_database
- create_table
- insert
- read
- search
- update
- delete
- list_tables
- describe_table

RULES:

1. Understand the user's natural-language request.
2. Select the appropriate predefined tool.
3. Never generate or execute arbitrary Python code.
4. Never generate or execute arbitrary SQL.
5. Use only the predefined tools.
6. Never claim an operation succeeded before receiving its result.
7. Never invent database records or file contents.
8. Ask for missing information when necessary.
9. Default database name is CollegeDB.
10. Search without a keyword means return all records.
11. Read without a record ID means return all records.
12. Ask for column definitions when creating a table if missing.

JSON RULES:

For inserting records, use record_json as a JSON string.

Example:
"{\"id\":104,\"name\":\"Sam\",\"department\":\"CSE\"}"

For updating records, use updates_json as a JSON string.

Example:
"{\"name\":\"Sam Updated\",\"department\":\"ECE\"}"

For creating tables, use columns as an array.

Example:
[
  {
    "name":"id",
    "type":"INTEGER",
    "primary_key":true
  },
  {
    "name":"name",
    "type":"VARCHAR",
    "length":100,
    "not_null":true
  }
]

Security decisions are handled by the Security Engine.
Do not claim that you independently perform threat detection.
"""


agent_tools = [

    types.Tool(
        function_declarations=[
            file_access_declaration,
            database_declaration
        ]
    )

]


# ============================================================
# 10. TOOL EXECUTION ROUTER
# ============================================================

def execute_tool(tool_name, arguments):

    print("\n[AI AGENT] Tool selected:", tool_name)
    print("[AI AGENT] Arguments:", arguments)

    approved, message = security_check(
        tool_name,
        arguments
    )

    if not approved:

        print("[SECURITY ENGINE] DENY")

        return {
            "status": "DENIED",
            "message": message
        }

    if tool_name == "file_access_manager":

        return file_access_manager(
            **arguments
        )

    if tool_name == "database_manager":

        return database_manager(
            **arguments
        )

    return {
        "status": "ERROR",
        "message": "Unknown tool."
    }


# ============================================================
# 11. CREATE GEMINI CHAT
# ============================================================

chat = client.chats.create(

    model=MODEL_NAME,

    config=types.GenerateContentConfig(

        system_instruction=system_instruction,

        tools=agent_tools,

        temperature=0.2
    )
)


# ============================================================
# 12. PROCESS USER MESSAGE
# ============================================================

def process_message(user_message):

    try:

        response = chat.send_message(user_message)

        for _ in range(10):

            function_calls = response.function_calls

            if not function_calls:

                return response.text or (
                    "I could not generate a text response."
                )

            function_responses = []

            for function_call in function_calls:

                tool_name = function_call.name

                arguments = dict(
                    function_call.args or {}
                )

                result = execute_tool(
                    tool_name,
                    arguments
                )

                print("\n[TOOL RESULT]", result)

                function_responses.append(

                    types.Part.from_function_response(

                        name=tool_name,

                        response={
                            "result": result
                        }
                    )

                )

            response = chat.send_message(
                function_responses
            )

        return (
            "Too many tool operations were requested. "
            "Please break your request into smaller steps."
        )

    except Exception as error:

        print("\n[ERROR]", error)

        return (
            "Something went wrong. "
            "Check the terminal for the error details."
        )


# ============================================================
# 13. TERMINAL INTERFACE
# ============================================================

def main():

    print("\n====================================")
    print("       AEGIS AI SECURE AGENT")
    print("====================================")

    print("\nGemini connection initialized.")
    print("MySQL Server connection initialized.")

    print("\nType 'exit' to stop the agent.")

    print("\nApproved storage folder:")
    print(STORAGE_DIR)

    while True:

        user_message = input("\nYou: ").strip()

        if user_message.lower() in {
            "exit",
            "quit",
            "stop"
        }:

            print("\nAegis AI: Goodbye!")
            break

        if not user_message:
            continue

        answer = process_message(
            user_message
        )

        print("\nAegis AI:", answer)


if __name__ == "__main__":

    main()
