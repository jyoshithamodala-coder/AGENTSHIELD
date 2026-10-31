AEGIS AI / AgentShield frontend prototype

RUN:
1. Extract this ZIP and open the folder in VS Code.
2. Start your existing FastAPI backend:
   cd C:\Users\srili\AGENTSHIELD\backend
   & "C:\Users\srili\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --reload
3. Open index.html with VS Code Live Server.

API endpoints used:
GET  http://127.0.0.1:8000/api/health
GET  http://127.0.0.1:8000/api/audit?limit=50
POST http://127.0.0.1:8000/api/tasks
Request body: {"task":"your task","document_id":""}

IMPORTANT:
- This is a separate frontend; it does not replace your backend.
- The /api/tasks response schema is not yet confirmed, so the UI shows common response fields and the raw response in the inspector.
- If the browser reports CORS, add CORS middleware to your EXISTING FastAPI main.py for the Live Server origin (commonly http://127.0.0.1:5500). Do not replace main.py.
- Login is not included as a working feature because no authentication endpoint has been confirmed.
- Approval buttons are not included because the exact approval request-body schemas have not been confirmed.
- Security decisions and risk levels are displayed from backend data; this frontend never decides whether an operation is safe.
- Never place Gemini API keys or database credentials in JavaScript.
