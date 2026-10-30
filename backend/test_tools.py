
from app.tools.document_reader import read_document
from app.tools.file_search import search_files
from app.tools.sensitive_data import access_sensitive_data
from app.tools.communication import send_external_message


def test_document_reader():
    result = read_document("report_01")
    assert result["success"] is True


def test_file_search():
    result = search_files("security")
    assert result["success"] is True
    assert len(result["results"]) > 0


def test_sensitive_data():
    result = access_sensitive_data("employee_01")
    assert result["success"] is True


def test_communication():
    result = send_external_message(
        "demo@example.test",
        "Test message"
    )

    assert result["simulated"] is True


if __name__ == "__main__":
    test_document_reader()
    test_file_search()
    test_sensitive_data()
    test_communication()

    print("All simulated tool tests passed!")
