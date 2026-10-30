
from app.tools.document_reader import DOCUMENTS


def search_files(keyword: str):

    results = []

    for document_id, document in DOCUMENTS.items():

        if keyword.lower() in document["content"].lower():

            results.append({
                "document_id": document_id,
                "title": document["title"]
            })

    return {
        "success": True,
        "results": results
    }
