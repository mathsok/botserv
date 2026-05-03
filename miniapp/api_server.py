from aiohttp import web
import json
import os

STATIC_DIR = os.path.join(os.path.dirname(__file__), "miniapp")
DATA_FILE = os.path.join(os.path.dirname(__file__), "database.json")

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"teachers": {}}

async def handle_data(request):
    params = request.rel_url.query
    role = params.get("role", "")
    name = params.get("name", "")
    tid = params.get("tid", "")

    db = load_db()
    teacher = db["teachers"].get(tid, {})

    if role in ("admin", "teacher"):
        students_list = []
        for sname, sdata in teacher.get("students", {}).items():
            students_list.append({
                "name": sname,
                "balance": sdata.get("balance", 0),
                "price": sdata.get("price", 0),
                "sessions": sdata.get("sessions", [])
            })
        result = {
            "role": "teacher",
            "name": teacher.get("name", ""),
            "subject": teacher.get("subject", ""),
            "students": students_list
        }

    elif name and name in teacher.get("students", {}):
        sdata = teacher["students"][name]
        result = {
            "role": role,
            "name": name,
            "balance": sdata.get("balance", 0),
            "price": sdata.get("price", 0),
            "sessions": sdata.get("sessions", []),
            "homework": sdata.get("homework", []),
            "journal": sdata.get("journal", []),
            "links": sdata.get("links", {})
        }
    else:
        result = {"role": "unknown"}

    return web.Response(
        text=json.dumps(result, ensure_ascii=False),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"}
    )

async def handle_index(request):
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(text=content, content_type="text/html")

app = web.Application()
app.router.add_get("/api/data", handle_data)
app.router.add_get("/", handle_index)
app.router.add_static("/miniapp", STATIC_DIR)

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8080))
    print(f"API сервер запущено на порту {port}")
    web.run_app(app, host="0.0.0.0", port=port)
