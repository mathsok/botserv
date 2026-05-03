from aiohttp import web
import json
import os

STATIC_DIR = os.path.join(os.path.dirname(__file__), "miniapp")

BOTS_DIR = {
    "main": "/root/my_bot/botserv/students_db.json",
}
# Автоматично додаємо всі tutor1-11
for i in range(1, 12):
    BOTS_DIR[f"tutor{i}"] = f"/root/my_bots/tutor{i}/students_db.json"

def load_students(bot_id="main"):
    db_path = BOTS_DIR.get(bot_id, BOTS_DIR["main"])
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

async def handle_data(request):
    params = request.rel_url.query
    role = params.get("role", "")
    name = params.get("name", "")
    bot_id = params.get("bot", "main")

    students = load_students(bot_id)

    student_data = None
    for sname, sdata in students.items():
        if sname.startswith("__"):
            continue
        if sname == name:
            student_data = sdata
            break

    if role in ("admin", "teacher"):
        students_list = []
        for sname, sdata in students.items():
            if sname.startswith("__"):
                continue
            students_list.append({
                "name": sname,
                "balance": sdata.get("balance", 0),
                "price": sdata.get("price", 0),
                "sessions": sdata.get("sessions", [])
            })
        result = {"role": "teacher", "students": students_list}

    elif student_data:
        result = {
            "role": role,
            "name": name,
            "balance": student_data.get("balance", 0),
            "price": student_data.get("price", 0),
            "sessions": student_data.get("sessions", []),
            "homework": student_data.get("homework", []),
            "journal": student_data.get("journal", []),
            "links": student_data.get("links", {})
        }
    else:
        result = {"role": "unknown"}

    return web.Response(
        text=json.dumps(result, ensure_ascii=False),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"}
    )

async def handle_index(request):
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
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
