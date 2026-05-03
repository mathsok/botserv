from aiohttp import web
import json
import os
import random

STATIC_DIR = os.path.join(os.path.dirname(__file__), "miniapp")
DATA_FILE = os.path.join(os.path.dirname(__file__), "database.json")

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"teachers": {}}

def save_db(db):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

def new_code(existing):
    while True:
        code = str(random.randint(1000, 9999))
        if code not in existing:
            return code

def get_existing_codes(db):
    codes = set()
    for t in db["teachers"].values():
        for s in t.get("students", {}).values():
            for k in ("u_code","p_code","su_code"):
                if s.get(k): codes.add(s[k])
    return codes

def teacher_to_response(tid, tdata):
    students = []
    for sname, sdata in tdata.get("students", {}).items():
        students.append({**sdata, "name": sname})
    return {
        "tid": tid,
        "name": tdata.get("name",""),
        "subject": tdata.get("subject",""),
        "students": students,
        "links": tdata.get("links",{})
    }

cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS", "Access-Control-Allow-Headers": "Content-Type"}

async def options_handler(request):
    return web.Response(headers=cors)

async def handle_index(request):
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def register_teacher(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    if tid not in db["teachers"]:
        db["teachers"][tid] = {"name": body["name"], "subject": body["subject"], "students": {}, "links": {}}
        save_db(db)
    return web.Response(text=json.dumps({"ok": True}), content_type="application/json", headers=cors)

async def get_teacher(request):
    tid = request.match_info["tid"]
    db = load_db()
    t = db["teachers"].get(tid)
    if not t:
        return web.Response(text=json.dumps({"error": "not found"}), status=404, content_type="application/json", headers=cors)
    return web.Response(text=json.dumps(teacher_to_response(tid, t), ensure_ascii=False), content_type="application/json", headers=cors)

async def get_student(request):
    tid = request.match_info["tid"]
    name = request.match_info["name"]
    db = load_db()
    t = db["teachers"].get(tid, {})
    s = t.get("students", {}).get(name)
    if not s:
        return web.Response(text=json.dumps({"error": "not found"}), status=404, content_type="application/json", headers=cors)
    return web.Response(text=json.dumps({**s, "name": name}, ensure_ascii=False), content_type="application/json", headers=cors)

async def auth_handler(request):
    body = await request.json()
    code = str(body.get("code","")).strip()
    uid = body.get("uid", 0)
    db = load_db()
    for tid, tdata in db["teachers"].items():
        for sname, sdata in tdata.get("students", {}).items():
            for role_code, role_key, role in [("su_code","su_id","super"),("u_code","u_id","student"),("p_code","p_id","parent")]:
                if sdata.get(role_code) == code:
                    sdata[role_key] = uid
                    save_db(db)
                    return web.Response(text=json.dumps({"ok":True,"tid":tid,"name":sname,"role":role,"student":{**sdata,"name":sname}}, ensure_ascii=False), content_type="application/json", headers=cors)
    return web.Response(text=json.dumps({"ok":False}), content_type="application/json", headers=cors)

async def add_student(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    if tid not in db["teachers"]:
        return web.Response(text=json.dumps({"error":"teacher not found"}), status=404, content_type="application/json", headers=cors)
    codes = get_existing_codes(db)
    u_code = new_code(codes); codes.add(u_code)
    p_code = new_code(codes); codes.add(p_code)
    su_code = new_code(codes)
    student = {"price": body.get("price",0), "balance": 0, "sessions": body.get("sessions",[]), "homework": [], "journal": [], "links": {}, "u_code": u_code, "u_id": None, "p_code": p_code, "p_id": None, "su_code": su_code, "su_id": None}
    db["teachers"][tid]["students"][name] = student
    save_db(db)
    return web.Response(text=json.dumps({"ok":True,"student":{**student,"name":name},"u_code":u_code,"p_code":p_code,"su_code":su_code}), content_type="application/json", headers=cors)

async def edit_student(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if not s:
        return web.Response(text=json.dumps({"error":"not found"}), status=404, content_type="application/json", headers=cors)
    if "price" in body: s["price"] = body["price"]
    if "sessions" in body: s["sessions"] = body["sessions"]
    save_db(db)
    return web.Response(text=json.dumps({"ok":True}), content_type="application/json", headers=cors)

async def delete_student(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    if name in db["teachers"].get(tid,{}).get("students",{}):
        del db["teachers"][tid]["students"][name]
        save_db(db)
    return web.Response(text=json.dumps({"ok":True}), content_type="application/json", headers=cors)

async def update_balance(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    amount = body["amount"]
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if s:
        s["balance"] += amount
        save_db(db)
        return web.Response(text=json.dumps({"ok":True,"balance":s["balance"]}), content_type="application/json", headers=cors)
    return web.Response(text=json.dumps({"error":"not found"}), status=404, content_type="application/json", headers=cors)

async def mark_lesson(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    topic = body.get("topic","")
    action = body.get("action","done")
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if not s:
        return web.Response(text=json.dumps({"error":"not found"}), status=404, content_type="application/json", headers=cors)
    from datetime import datetime
    date_str = datetime.now().strftime("%d.%m.%Y")
    if action == "done":
        s["balance"] -= s["price"]
        s.setdefault("journal",[]).append({"date":date_str,"topic":topic,"materials":[]})
    save_db(db)
    return web.Response(text=json.dumps({"ok":True,"balance":s.get("balance",0)}), content_type="application/json", headers=cors)

async def send_hw(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    text = body.get("text","")
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if not s:
        return web.Response(text=json.dumps({"error":"not found"}), status=404, content_type="application/json", headers=cors)
    from datetime import datetime
    import random as rnd
    hw_id = str(rnd.randint(10000,99999))
    s.setdefault("homework",[]).append({"id":hw_id,"text":text,"photo_id":None,"date":datetime.now().strftime("%d.%m.%Y"),"status":"new"})
    save_db(db)
    return web.Response(text=json.dumps({"ok":True}), content_type="application/json", headers=cors)

async def mark_hw(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    hw_id = body["hw_id"]
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if s:
        for hw in s.get("homework",[]):
            if hw["id"] == hw_id:
                hw["status"] = "done"
                break
        save_db(db)
    return web.Response(text=json.dumps({"ok":True}), content_type="application/json", headers=cors)

async def reset_codes(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if s:
        codes = get_existing_codes(db)
        u_code = new_code(codes); codes.add(u_code)
        p_code = new_code(codes); codes.add(p_code)
        su_code = new_code(codes)
        s.update({"u_code":u_code,"u_id":None,"p_code":p_code,"p_id":None,"su_code":su_code,"su_id":None})
        save_db(db)
        return web.Response(text=json.dumps({"ok":True,"u_code":u_code,"p_code":p_code,"su_code":su_code}), content_type="application/json", headers=cors)
    return web.Response(text=json.dumps({"error":"not found"}), status=404, content_type="application/json", headers=cors)

async def add_student_link(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if s:
        s.setdefault("links",{})[body["label"]] = body["url"]
        save_db(db)
        return web.Response(text=json.dumps({"ok":True}), content_type="application/json", headers=cors)
    return web.Response(text=json.dumps({"error":"not found"}), status=404, content_type="application/json", headers=cors)

async def delete_student_link(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if s and body["label"] in s.get("links",{}):
        del s["links"][body["label"]]
        save_db(db)
    return web.Response(text=json.dumps({"ok":True}), content_type="application/json", headers=cors)

# ── APP ──
app = web.Application()
app.router.add_route("OPTIONS", "/{path_info:.*}", options_handler)
app.router.add_get("/", handle_index)
app.router.add_post("/api/register-teacher", register_teacher)
app.router.add_get("/api/teacher/{tid}", get_teacher)
app.router.add_get("/api/student/{tid}/{name}", get_student)
app.router.add_post("/api/auth", auth_handler)
app.router.add_post("/api/add-student", add_student)
app.router.add_post("/api/edit-student", edit_student)
app.router.add_post("/api/delete-student", delete_student)
app.router.add_post("/api/update-balance", update_balance)
app.router.add_post("/api/mark-lesson", mark_lesson)
app.router.add_post("/api/send-hw", send_hw)
app.router.add_post("/api/mark-hw", mark_hw)
app.router.add_post("/api/reset-codes", reset_codes)
app.router.add_post("/api/add-student-link", add_student_link)
app.router.add_post("/api/delete-student-link", delete_student_link)
app.router.add_static("/miniapp", STATIC_DIR)

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8080))
    print(f"API сервер запущено на порту {port}")
    web.run_app(app, host="0.0.0.0", port=port)
