from aiohttp import web
from dotenv import load_dotenv
import json
import os
import random
import aiohttp as aiohttp_client

load_dotenv()

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.json")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

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
    return {"tid": tid, "name": tdata.get("name",""), "subject": tdata.get("subject",""), "students": students, "links": tdata.get("links",{})}

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
    role = request.rel_url.query.get("role", "student")
    db = load_db()
    s = db["teachers"].get(tid, {}).get("students", {}).get(name)
    if not s:
        return web.Response(text=json.dumps({"error": "not found"}), status=404, content_type="application/json", headers=cors)
    key = {"student": "u_own_links", "parent": "p_own_links", "super": "su_own_links"}.get(role, "u_own_links")
    data = {**s, "name": name, "own_links": s.get(key, [])}
    return web.Response(text=json.dumps(data, ensure_ascii=False), content_type="application/json", headers=cors)

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
    student = {"price": body.get("price",0), "currency": body.get("currency","UAH"), "balance": 0, "sessions": body.get("sessions",[]), "homework": [], "journal": [], "links": {}, "u_code": u_code, "u_id": None, "p_code": p_code, "p_id": None, "su_code": su_code, "su_id": None}
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
    custom_date = body.get("date","")
    reschedule = body.get("reschedule",None)
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if not s:
        return web.Response(text=json.dumps({"error":"not found"}), status=404, content_type="application/json", headers=cors)
    from datetime import datetime
    date_str = custom_date if custom_date else datetime.now().strftime("%d.%m.%Y")
    if action == "done":
        s["balance"] -= s["price"]
        s.setdefault("journal",[]).append({"date":date_str,"topic":topic,"materials":[]})
    elif action == "cancel":
        s.setdefault("journal",[]).append({"date":date_str,"topic":"❌ Скасовано: "+topic,"materials":[]})
    elif action == "reschedule" and reschedule:
        from_str = reschedule.get("fromDate","")+" "+reschedule.get("fromTime","")
        to_str = reschedule.get("toDate","")+" "+reschedule.get("toTime","")
        s.setdefault("journal",[]).append({
            "date":date_str,
            "topic":"🔄 Перенесено: "+topic,
            "reschedule":{"from":from_str,"to":to_str},
            "materials":[]
        })
    save_db(db)
    # Notify student about lesson date (not mark date)
    u_id = s.get("u_id") or s.get("su_id")
    if u_id and action == "done":
        cur = s.get("currency","UAH")
        sym = "$" if cur=="USD" else "€" if cur=="EUR" else "₴"
        bal = s.get("balance",0)
        bal_str = (sym+str(abs(bal))) if cur in ("USD","EUR") else (str(bal)+sym)
        try:
            async with aiohttp_client.ClientSession() as session:
                msg = "\u2705 \u0417\u0430\u043d\u044f\u0442\u0442\u044f \u0432\u0456\u0434\u043c\u0456\u0447\u0435\u043d\u043e!\n\U0001f4c5 "+date_str+"\n\U0001f4d6 "+topic+"\n\U0001f4b3 \u0411\u0430\u043b\u0430\u043d\u0441: "+bal_str
                await session.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                    json={"chat_id":u_id,"text":msg})
        except Exception as e:
            print("[MARK LESSON] notify error:", e)
    elif u_id and action == "reschedule" and reschedule:
        try:
            async with aiohttp_client.ClientSession() as session:
                msg2 = "\U0001f504 \u0417\u0430\u043d\u044f\u0442\u0442\u044f \u043f\u0435\u0440\u0435\u043d\u0435\u0441\u0435\u043d\u043e!\n\U0001f4c5 \u0417: "+reschedule.get("fromDate","")+" "+reschedule.get("fromTime","")+"\n\U0001f4c5 \u041d\u0430: "+reschedule.get("toDate","")+" "+reschedule.get("toTime","")
                await session.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                    json={"chat_id":u_id,"text":msg2})
        except Exception as e:
            print("[RESCHEDULE] notify error:", e)

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
    date_str = datetime.now().strftime("%d.%m.%Y")
    s.setdefault("homework",[]).append({"id":hw_id,"text":text,"photo_id":None,"date":date_str,"status":"new"})
    save_db(db)
    u_id = s.get("u_id") or s.get("su_id")
    if u_id:
        try:
            async with aiohttp_client.ClientSession() as session:
                await session.post(
                    "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                    json={"chat_id": u_id, "text": "📝 Нове ДЗ!\n📅 " + date_str + "\n\n" + text}
                )
        except Exception as e:
            print("[SEND HW] error:", e)
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

async def delete_journal_entry(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    idx = body["idx"]
    s = db["teachers"].get(tid,{}).get("students",{}).get(name)
    if s and 0 <= idx < len(s.get("journal",[])):
        s["journal"].pop(idx)
        save_db(db)
    return web.Response(text=json.dumps({"ok":True}), content_type="application/json", headers=cors)

async def send_materials(request):
    print("[SEND MATERIALS] Request received")
    try:
        reader = await request.multipart()
        tid = None; name = None; topic = None; files = []
        async for part in reader:
            if part.name == "tid": tid = (await part.read()).decode()
            elif part.name == "name": name = (await part.read()).decode()
            elif part.name == "topic": topic = (await part.read()).decode()
            elif part.name == "files":
                fn = part.filename or "file"
                ct = part.headers.get("Content-Type", "application/octet-stream")
                data = await part.read()
                files.append({"name": fn, "data": data, "ct": ct, "is_photo": ct.startswith("image/")})
        print("[SEND MATERIALS] tid=" + str(tid) + " name=" + str(name) + " files=" + str(len(files)))
        if not all([tid, name]) or not files:
            return web.Response(text=json.dumps({"ok": True, "sent": 0}), content_type="application/json", headers=cors)
        db = load_db()
        sdata = db["teachers"].get(tid, {}).get("students", {}).get(name, {})
        notify = [i for i in [sdata.get("u_id"), sdata.get("su_id")] if i]
        saved_materials = []
        async with aiohttp_client.ClientSession() as session:
            first_id = notify[0] if notify else int(tid)
            for f in files:
                file_id = None
                form = aiohttp_client.FormData()
                form.add_field("chat_id", str(first_id))
                if topic: form.add_field("caption", topic)
                if f["is_photo"]:
                    form.add_field("photo", f["data"], filename=f["name"], content_type=f["ct"])
                    async with session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto", data=form) as resp:
                        result = await resp.json()
                        if result.get("ok"):
                            photo = result["result"].get("photo", [])
                            if photo:
                                file_id = photo[-1]["file_id"]
                                saved_materials.append({"type": "photo", "file_id": file_id, "caption": topic or ""})
                else:
                    form.add_field("document", f["data"], filename=f["name"], content_type=f["ct"])
                    async with session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument", data=form) as resp:
                        result = await resp.json()
                        if result.get("ok"):
                            doc = result["result"].get("document", {})
                            file_id = doc.get("file_id")
                            if file_id:
                                saved_materials.append({"type": "document", "file_id": file_id, "caption": f["name"]})
                if file_id and len(notify) > 1:
                    for nid in notify[1:]:
                        try:
                            f2 = aiohttp_client.FormData()
                            f2.add_field("chat_id", str(nid))
                            if saved_materials[-1]["type"] == "photo":
                                f2.add_field("photo", file_id)
                                await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto", data=f2)
                            else:
                                f2.add_field("document", file_id)
                                await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument", data=f2)
                        except Exception as e:
                            print("[SEND MATERIALS] error:", e)
        if saved_materials and topic:
            db2 = load_db()
            journal = db2["teachers"].get(tid, {}).get("students", {}).get(name, {}).get("journal", [])
            for entry in reversed(journal):
                if entry.get("topic") == topic:
                    entry["materials"] = saved_materials
                    break
            save_db(db2)
        return web.Response(text=json.dumps({"ok": True, "sent": len(saved_materials)}), content_type="application/json", headers=cors)
    except Exception as e:
        import traceback; traceback.print_exc()
        return web.Response(text=json.dumps({"ok": False, "error": str(e)}), content_type="application/json", headers=cors)

async def send_hw_file(request):
    try:
        reader = await request.multipart()
        tid = None; name = None; text = None; files = []
        async for part in reader:
            if part.name == "tid": tid = (await part.read()).decode()
            elif part.name == "name": name = (await part.read()).decode()
            elif part.name == "text": text = (await part.read()).decode()
            elif part.name == "files":
                fn = part.filename or "hw"
                ct = part.headers.get("Content-Type", "application/octet-stream")
                data = await part.read()
                files.append({"name": fn, "data": data, "ct": ct, "is_photo": ct.startswith("image/")})
        if not all([tid, name]) or not files:
            return web.Response(text=json.dumps({"ok": False, "error": "missing fields"}), content_type="application/json", headers=cors)
        from datetime import datetime
        import random as rnd
        hw_id = str(rnd.randint(10000, 99999))
        date_str = datetime.now().strftime("%d.%m.%Y")
        db = load_db()
        s = db["teachers"].get(tid, {}).get("students", {}).get(name)
        if not s:
            return web.Response(text=json.dumps({"ok": False, "error": "not found"}), content_type="application/json", headers=cors)
        s.setdefault("homework", []).append({"id": hw_id, "text": text or "Дивись файли", "photo_id": None, "date": date_str, "status": "new"})
        save_db(db)
        u_id = s.get("u_id") or s.get("su_id")
        if u_id:
            async with aiohttp_client.ClientSession() as session:
                await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                    json={"chat_id": str(u_id), "text": "📝 Нове ДЗ!\n📅 " + date_str + "\n\n" + (text or "")})
                for f in files:
                    form = aiohttp_client.FormData()
                    form.add_field("chat_id", str(u_id))
                    if f["is_photo"]:
                        form.add_field("photo", f["data"], filename=f["name"], content_type=f["ct"])
                        await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto", data=form)
                    else:
                        form.add_field("document", f["data"], filename=f["name"], content_type=f["ct"])
                        await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument", data=form)
        return web.Response(text=json.dumps({"ok": True}), content_type="application/json", headers=cors)
    except Exception as e:
        import traceback; traceback.print_exc()
        return web.Response(text=json.dumps({"ok": False, "error": str(e)}), content_type="application/json", headers=cors)

async def submit_hw_reply(request):
    print("[HW REPLY] Request received")
    try:
        reader = await request.multipart()
        tid = None; name = None; hw_id = None; text = None; files = []
        async for part in reader:
            if part.name == "tid": tid = (await part.read()).decode()
            elif part.name == "name": name = (await part.read()).decode()
            elif part.name == "hw_id": hw_id = (await part.read()).decode()
            elif part.name == "text": text = (await part.read()).decode()
            elif part.name == "files":
                fn = part.filename or "reply"
                ct = part.headers.get("Content-Type", "application/octet-stream")
                data = await part.read()
                files.append({"name": fn, "data": data, "ct": ct, "is_photo": ct.startswith("image/")})
        print("[HW REPLY] tid=" + str(tid) + " name=" + str(name) + " hw_id=" + str(hw_id) + " files=" + str(len(files)))
        if not all([tid, name, hw_id]):
            return web.Response(text=json.dumps({"ok": False, "error": "missing fields"}), content_type="application/json", headers=cors)
        db = load_db()
        s = db["teachers"].get(tid, {}).get("students", {}).get(name)
        if not s:
            return web.Response(text=json.dumps({"ok": False, "error": "not found"}), content_type="application/json", headers=cors)
        for hw in s.get("homework", []):
            if hw["id"] == hw_id:
                hw["status"] = "done"
                if text: hw["reply"] = text
                break
        save_db(db)
        msg_text = "📝 " + name + " відповів на ДЗ!"
        if text: msg_text += "\n\n" + text
        kb = json.dumps({"inline_keyboard": [[{"text": "💬 Відповісти", "callback_data": "hw_feedback_" + hw_id + "_" + tid + "_" + name}]]})
        async with aiohttp_client.ClientSession() as session:
            await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                json={"chat_id": tid, "text": msg_text, "reply_markup": kb})
            for f in files:
                form = aiohttp_client.FormData()
                form.add_field("chat_id", tid)
                if f["is_photo"]:
                    form.add_field("photo", f["data"], filename=f["name"], content_type=f["ct"])
                    await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto", data=form)
                else:
                    form.add_field("document", f["data"], filename=f["name"], content_type=f["ct"])
                    await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument", data=form)
        return web.Response(text=json.dumps({"ok": True}), content_type="application/json", headers=cors)
    except Exception as e:
        import traceback; traceback.print_exc()
        return web.Response(text=json.dumps({"ok": False, "error": str(e)}), content_type="application/json", headers=cors)

async def pay_request(request):
    try:
        reader = await request.multipart()
        amount = None; tid = None; name = None
        file_data = None; file_name = "check"; file_ct = "image/jpeg"; is_photo = True
        async for part in reader:
            if part.name == "amount": amount = int(await part.read())
            elif part.name == "tid": tid = (await part.read()).decode()
            elif part.name == "name": name = (await part.read()).decode()
            elif part.name == "file":
                file_name = part.filename or "check"
                file_ct = part.headers.get("Content-Type", "image/jpeg")
                is_photo = file_ct.startswith("image/")
                file_data = await part.read()
        if not all([amount, tid, name, file_data]):
            return web.Response(text=json.dumps({"ok": False, "error": "missing fields"}), content_type="application/json", headers=cors)
        caption = "💰 Заявка на поповнення!\nВід: " + name + "\nСума: " + str(amount) + "₴"
        kb = json.dumps({"inline_keyboard": [[
            {"text": "✅ Підтвердити", "callback_data": "confirm_webapp_" + str(amount) + "_" + tid + "_" + name},
            {"text": "❌ Відхилити", "callback_data": "reject_webapp_" + name + "_" + tid}
        ]]})
        async with aiohttp_client.ClientSession() as session:
            form = aiohttp_client.FormData()
            form.add_field("chat_id", tid)
            form.add_field("caption", caption)
            form.add_field("reply_markup", kb)
            if is_photo:
                form.add_field("photo", file_data, filename=file_name, content_type=file_ct)
                async with session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto", data=form) as resp:
                    result = await resp.json()
            else:
                form.add_field("document", file_data, filename=file_name, content_type=file_ct)
                async with session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument", data=form) as resp:
                    result = await resp.json()
        if result.get("ok"):
            return web.Response(text=json.dumps({"ok": True}), content_type="application/json", headers=cors)
        print("[PAY] Telegram error:", result)
        return web.Response(text=json.dumps({"ok": False, "error": result.get("description","error")}), content_type="application/json", headers=cors)
    except Exception as e:
        import traceback; traceback.print_exc()
        return web.Response(text=json.dumps({"ok": False, "error": str(e)}), content_type="application/json", headers=cors)

async def get_file_url(request):
    try:
        body = await request.json()
        file_id = body.get("file_id")
        if not file_id:
            return web.Response(text=json.dumps({"ok": False}), content_type="application/json", headers=cors)
        async with aiohttp_client.ClientSession() as session:
            async with session.get("https://api.telegram.org/bot" + BOT_TOKEN + "/getFile?file_id=" + file_id) as resp:
                result = await resp.json()
        if not result.get("ok"):
            return web.Response(text=json.dumps({"ok": False}), content_type="application/json", headers=cors)
        file_path = result["result"]["file_path"]
        url = "https://api.telegram.org/file/bot" + BOT_TOKEN + "/" + file_path
        return web.Response(text=json.dumps({"ok": True, "url": url}), content_type="application/json", headers=cors)
    except Exception as e:
        return web.Response(text=json.dumps({"ok": False, "error": str(e)}), content_type="application/json", headers=cors)

async def resend_materials(request):
    try:
        body = await request.json()
        tid = str(body["tid"]); name = body["name"]; idx = int(body["idx"]); uid = body.get("uid")
        db = load_db()
        journal = db["teachers"].get(tid, {}).get("students", {}).get(name, {}).get("journal", [])
        if not (0 <= idx < len(journal)):
            return web.Response(text=json.dumps({"ok": False, "error": "not found"}), content_type="application/json", headers=cors)
        entry = journal[idx]; materials = entry.get("materials", [])
        topic = entry.get("topic", ""); date = entry.get("date", "")
        if not materials:
            return web.Response(text=json.dumps({"ok": False, "error": "no materials"}), content_type="application/json", headers=cors)
        if not uid:
            sdata = db["teachers"].get(tid, {}).get("students", {}).get(name, {})
            uid = sdata.get("u_id") or sdata.get("su_id")
        if not uid:
            return web.Response(text=json.dumps({"ok": False, "error": "no uid"}), content_type="application/json", headers=cors)
        async with aiohttp_client.ClientSession() as session:
            await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                json={"chat_id": uid, "text": "📚 " + topic + "\n📅 " + date})
            for mat in materials:
                form = aiohttp_client.FormData(); form.add_field("chat_id", str(uid))
                if mat["type"] == "photo":
                    form.add_field("photo", mat["file_id"])
                    await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendPhoto", data=form)
                else:
                    form.add_field("document", mat["file_id"])
                    await session.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendDocument", data=form)
        return web.Response(text=json.dumps({"ok": True}), content_type="application/json", headers=cors)
    except Exception as e:
        return web.Response(text=json.dumps({"ok": False, "error": str(e)}), content_type="application/json", headers=cors)



async def get_notes(request):
    tid = request.match_info["tid"]
    role = request.rel_url.query.get("role", "teacher")
    name = request.rel_url.query.get("name", "")
    db = load_db()
    if role == "teacher":
        notes = db["teachers"].get(tid, {}).get("notes", [])
    else:
        key = {"student": "u_notes", "parent": "p_notes", "super": "su_notes"}.get(role, "u_notes")
        notes = db["teachers"].get(tid, {}).get("students", {}).get(name, {}).get(key, [])
    return web.Response(text=json.dumps({"ok": True, "notes": notes}, ensure_ascii=False), content_type="application/json", headers=cors)

async def add_note(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    role = body.get("role", "teacher")
    name = body.get("name", "")
    text = body.get("text", "").strip()
    if not text:
        return web.Response(text=json.dumps({"ok": False, "error": "empty"}), content_type="application/json", headers=cors)
    import random as rnd
    note = {"id": str(rnd.randint(10000, 99999)), "text": text}
    if role == "teacher":
        db["teachers"].get(tid, {}).setdefault("notes", []).append(note)
    else:
        key = {"student": "u_notes", "parent": "p_notes", "super": "su_notes"}.get(role, "u_notes")
        db["teachers"].get(tid, {}).get("students", {}).get(name, {}).setdefault(key, []).append(note)
    save_db(db)
    return web.Response(text=json.dumps({"ok": True, "note": note}), content_type="application/json", headers=cors)

async def delete_note(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    role = body.get("role", "teacher")
    name = body.get("name", "")
    note_id = body.get("note_id", "")
    if role == "teacher":
        notes = db["teachers"].get(tid, {}).get("notes", [])
        db["teachers"][tid]["notes"] = [n for n in notes if n["id"] != note_id]
    else:
        key = {"student": "u_notes", "parent": "p_notes", "super": "su_notes"}.get(role, "u_notes")
        s = db["teachers"].get(tid, {}).get("students", {}).get(name, {})
        s[key] = [n for n in s.get(key, []) if n["id"] != note_id]
    save_db(db)
    return web.Response(text=json.dumps({"ok": True}), content_type="application/json", headers=cors)


async def add_student_own_link(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    role = body.get("role", "student")
    label = body.get("label", "").strip()
    url = body.get("url", "").strip()
    if not label or not url:
        return web.Response(text=json.dumps({"ok": False, "error": "empty"}), content_type="application/json", headers=cors)
    import random as rnd
    link = {"id": str(rnd.randint(10000, 99999)), "label": label, "url": url}
    key = {"student": "u_own_links", "parent": "p_own_links", "super": "su_own_links"}.get(role, "u_own_links")
    s = db["teachers"].get(tid, {}).get("students", {}).get(name)
    if not s:
        return web.Response(text=json.dumps({"ok": False, "error": "not found"}), content_type="application/json", headers=cors)
    s.setdefault(key, []).append(link)
    save_db(db)
    return web.Response(text=json.dumps({"ok": True, "link": link}), content_type="application/json", headers=cors)

async def delete_student_own_link(request):
    body = await request.json()
    db = load_db()
    tid = str(body["tid"])
    name = body["name"]
    role = body.get("role", "student")
    link_id = body.get("link_id", "")
    key = {"student": "u_own_links", "parent": "p_own_links", "super": "su_own_links"}.get(role, "u_own_links")
    s = db["teachers"].get(tid, {}).get("students", {}).get(name)
    if s:
        s[key] = [l for l in s.get(key, []) if l["id"] != link_id]
        save_db(db)
    return web.Response(text=json.dumps({"ok": True}), content_type="application/json", headers=cors)

app = web.Application(client_max_size=50*1024*1024)
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
app.router.add_post("/api/delete-journal-entry", delete_journal_entry)
app.router.add_post("/api/send-materials", send_materials)
app.router.add_post("/api/send-hw-file", send_hw_file)
app.router.add_post("/api/submit-hw-reply", submit_hw_reply)
app.router.add_post("/api/pay-request", pay_request)
app.router.add_post("/api/get-file-url", get_file_url)
app.router.add_post("/api/resend-materials", resend_materials)
app.router.add_get("/api/notes/{tid}", get_notes)
app.router.add_post("/api/add-note", add_note)
app.router.add_post("/api/delete-note", delete_note)
app.router.add_post("/api/add-student-own-link", add_student_own_link)
app.router.add_post("/api/delete-student-own-link", delete_student_own_link)
app.router.add_static("/miniapp", STATIC_DIR)

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8080))
    print("API сервер запущено на порту " + str(port))
    web.run_app(app, host="0.0.0.0", port=port)
