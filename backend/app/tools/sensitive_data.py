
# Entirely synthetic sensitive data

SENSITIVE_RECORDS = {
    "employee_01": {
        "name": "Demo Employee",
        "email": "employee@example.test",
        "account_number": "DEMO-123456"
    }
}


def access_sensitive_data(record_id: str):

    record = SENSITIVE_RECORDS.get(record_id)

    if not record:
        return {
            "success": False,
            "message": "Record not found"
        }

    return {
        "success": True,
        "record": record
    }
