import asyncio
import os
import json
import random
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramAPIError

load_dotenv()

# ─── КОНФІГУРАЦІЯ ──────────────────────────────────────────────────────────────

TOKEN = os.environ["BOT_TOKEN"]
DATA_FILE = "database.json"
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://mathkyrylo.com")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = {"teachers": {}}
user_state = {}

days = ["Понеділок", "Вівторок", "Середа", "Четвер", "Пʼятниця", "Субота", "Неділя"]


# ─── БАЗА ДАНИХ ────────────────────────────────────────────────────────────────

def load_db():
    global db
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    if "teachers" not in db:
        db["teachers"] = {}

def save_db():
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

def get_teacher(tid):
    return db["teachers"].get(str(tid))

def get_students(tid):
    t = get_teacher(tid)
    return t["students"] if t else {}

def save_teacher(tid, data):
    db["teachers"][str(tid)] = data
    save_db()


# ─── ДОПОМІЖНІ ФУНКЦІЇ ─────────────────────────────────────────────────────────

def new_code(tid):
    existing = set()
    students = get_students(tid)
    for d in students.values():
        for key in ("u_code", "p_code", "su_code"):
            if d.get(key):
                existing.add(d[key])
    while True:
        code = str(random.randint(1000, 9999))
        if code not in existing:
            return code

def new_hw_id():
    return str(random.randint(10000, 99999))

def find_teacher_by_code(code):
    """Шукає вчителя і учня по коду входу"""
    for tid, tdata in db["teachers"].items():
        for sname, sdata in tdata.get("students", {}).items():
            for role_code, role_key, role_menu in [
                ("su_code", "su_id", "super"),
                ("u_code", "u_id", "student"),
                ("p_code", "p_id", "parent")
            ]:
                if sdata.get(role_code) == code:
                    return tid, sname, role_key, role_menu
    return None, None, None, None

def find_student_by_uid(uid):
    """Шукає учня по його Telegram ID"""
    for tid, tdata in db["teachers"].items():
        for sname, sdata in tdata.get("students", {}).items():
            for role_key, role_menu in [("su_id", "super"), ("u_id", "student"), ("p_id", "parent")]:
                if sdata.get(role_key) == uid:
                    return tid, sname, sdata, role_menu
    return None, None, None, None


# ─── КЛАВІАТУРИ ────────────────────────────────────────────────────────────────

menu_teacher = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👥 Керування учнями")],
        [KeyboardButton(text="📖 Заняття і матеріали")],
        [KeyboardButton(text="📅 Мій розклад"), KeyboardButton(text="🗓 Розклад на тиждень")],
        [KeyboardButton(text="🔗 Корисні посилання")],
    ], resize_keyboard=True
)

menu_teacher_students = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Додати учня"), KeyboardButton(text="📋 Список учнів")],
        [KeyboardButton(text="💳 Баланси")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True
)

menu_teacher_lessons = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✔️ Відмітити заняття")],
        [KeyboardButton(text="📝 Відправити домашнє завдання")],
        [KeyboardButton(text="📒 Журнал занять")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True
)

menu_student = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Мій розклад"), KeyboardButton(text="💳 Мій баланс")],
        [KeyboardButton(text="📖 Заняття і матеріали")],
        [KeyboardButton(text="🔗 Корисні посилання")],
        [KeyboardButton(text="🚪 Вийти з кабінета")]
    ], resize_keyboard=True
)

menu_student_lessons = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Домашні завдання")],
        [KeyboardButton(text="📒 Журнал занять")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True
)

menu_parent = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Розклад дитини"), KeyboardButton(text="💳 Баланс дитини")],
        [KeyboardButton(text="💰 Поповнити баланс")],
        [KeyboardButton(text="🔗 Корисні посилання")],
        [KeyboardButton(text="🚪 Вийти з кабінета")]
    ], resize_keyboard=True
)

menu_super = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Мій розклад"), KeyboardButton(text="💳 Мій баланс")],
        [KeyboardButton(text="📖 Заняття і матеріали"), KeyboardButton(text="💰 Поповнити баланс")],
        [KeyboardButton(text="🔗 Корисні посилання")],
        [KeyboardButton(text="🚪 Вийти з кабінета")]
    ], resize_keyboard=True
)

def get_student_menu(role):
    if role == "super": return menu_super
    if role == "parent": return menu_parent
    return menu_student

def get_webapp_menu(base_menu, url):
    return ReplyKeyboardMarkup(
        keyboard=[*base_menu.keyboard, [KeyboardButton(text="📱 Відкрити кабінет", web_app=WebAppInfo(url=url))]],
        resize_keyboard=True
    )


# ─── НАГАДУВАННЯ ───────────────────────────────────────────────────────────────

async def send_reminders():
    while True:
        try:
            now = datetime.now()
            target = now + timedelta(hours=4)
            target_day = days[target.weekday()]
            target_time = target.strftime("%H:%M")

            print(f"[{now.strftime('%H:%M')}] Нагадування: шукаю заняття на {target_day} {target_time}")

            for tid, tdata in db["teachers"].items():
                for sname, sdata in tdata.get("students", {}).items():
                    for session in sdata.get("sessions", []):
                        match = session["day"] == target_day and session["time"] == target_time
                        if match:
                            u_id = sdata.get("u_id") or sdata.get("su_id")
                            if u_id:
                                try:
                                    await bot.send_message(u_id,
                                        f"🔔 Нагадування!\n"
                                        f"Сьогодні о {target_time} у тебе заняття.\n"
                                        f"Не забудь підготуватись! 📚")
                                except Exception:
                                    pass
        except Exception as e:
            print(f"Помилка в нагадуваннях: {e}")

        await asyncio.sleep(60)


# ─── СТАРТ ─────────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def start(message: types.Message):
    load_db()
    uid = message.from_user.id
    tid_str = str(uid)

    # Вчитель вже зареєстрований
    if tid_str in db["teachers"]:
        t = db["teachers"][tid_str]
        url = f"{WEBAPP_URL}?role=admin&tid={tid_str}"
        kb = get_webapp_menu(menu_teacher, url)
        await message.answer(
            f"Вітаю, {t['name']}! Ваша панель керування:",
            reply_markup=kb
        )
        return

    # Учень/батьки/супер
    tid, sname, role_key, role_menu = find_student_by_uid(uid)
    if tid:
        sdata = db["teachers"][tid]["students"][sname]
        url = f"{WEBAPP_URL}?role={role_menu}&tid={tid}&name={sname}"
        kb = get_webapp_menu(get_student_menu(role_menu), url)
        greeting = f"Привіт, {sname}!" if role_menu != "parent" else f"Привіт! Кабінет учня {sname}:"
        await message.answer(greeting, reply_markup=kb)
        return

    # Новий користувач — запитуємо хто він
    user_state[uid] = "waiting_role"
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👨‍🏫 Я вчитель")],
        [KeyboardButton(text="🎓 Я учень / батьки")]
    ], resize_keyboard=True)
    await message.answer(
        "Привіт! Ласкаво просимо до TutorBot 👋\n\nОберіть свою роль:",
        reply_markup=kb
    )


# ─── РЕЄСТРАЦІЯ ВЧИТЕЛЯ ────────────────────────────────────────────────────────

@dp.message(lambda m: user_state.get(m.from_user.id) == "waiting_role")
async def choose_role(message: types.Message):
    uid = message.from_user.id
    if message.text == "👨‍🏫 Я вчитель":
        user_state[uid] = "teacher_waiting_name"
        await message.answer(
            "Чудово! Як вас звати? (Введіть ім'я та по батькові):",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
        )
    elif message.text == "🎓 Я учень / батьки":
        user_state[uid] = "waiting_auth_code"
        await message.answer(
            "Введіть код доступу, який надав вчитель:",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
        )

@dp.message(lambda m: user_state.get(m.from_user.id) == "teacher_waiting_name")
async def teacher_enter_name(message: types.Message):
    uid = message.from_user.id
    user_state[uid] = {"state": "teacher_waiting_subject", "name": message.text.strip()}
    await message.answer("Який предмет ви викладаєте?")

@dp.message(lambda m: isinstance(user_state.get(m.from_user.id), dict) and user_state[m.from_user.id].get("state") == "teacher_waiting_subject")
async def teacher_enter_subject(message: types.Message):
    uid = message.from_user.id
    name = user_state[uid]["name"]
    subject = message.text.strip()

    db["teachers"][str(uid)] = {
        "name": name,
        "subject": subject,
        "students": {},
        "links": {}
    }
    save_db()
    user_state[uid] = None

    url = f"{WEBAPP_URL}?role=admin&tid={uid}"
    kb = get_webapp_menu(menu_teacher, url)
    await message.answer(
        f"✅ Вітаємо, {name}!\n"
        f"Предмет: {subject}\n\n"
        f"Ваш кабінет готовий. Починайте додавати учнів!",
        reply_markup=kb
    )


# ─── АВТОРИЗАЦІЯ УЧНЯ ──────────────────────────────────────────────────────────

@dp.message(lambda m: user_state.get(m.from_user.id) == "waiting_auth_code")
async def auth(message: types.Message):
    code = message.text.strip()
    uid = message.from_user.id

    tid, sname, role_key, role_menu = find_teacher_by_code(code)
    if tid:
        db["teachers"][tid]["students"][sname][role_key] = uid
        save_db()
        user_state[uid] = None

        url = f"{WEBAPP_URL}?role={role_menu}&tid={tid}&name={sname}"
        kb = get_webapp_menu(get_student_menu(role_menu), url)

        if role_menu == "parent":
            await message.answer(f"✅ Вітаємо! Ви зайшли як батько/мати учня {sname}.", reply_markup=kb)
        else:
            await message.answer(f"✅ Вітаємо, {sname}! Ти зайшов як учень.", reply_markup=kb)
        return

    await message.answer("❌ Код не знайдено. Спробуй ще раз або зверніться до вчителя.")


# ─── ВЧИТЕЛЬ: РОЗДІЛИ МЕНЮ ────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "👥 Керування учнями" and str(m.from_user.id) in db["teachers"])
async def teacher_section_students(message: types.Message):
    await message.answer("👥 Керування учнями:", reply_markup=menu_teacher_students)

@dp.message(lambda m: m.text and m.text == "📖 Заняття і матеріали" and str(m.from_user.id) in db["teachers"])
async def teacher_section_lessons(message: types.Message):
    await message.answer("📖 Заняття і матеріали:", reply_markup=menu_teacher_lessons)

@dp.message(lambda m: m.text and m.text == "📖 Заняття і матеріали")
async def student_section_lessons(message: types.Message):
    await message.answer("📖 Заняття і матеріали:", reply_markup=menu_student_lessons)


# ─── ВЧИТЕЛЬ: ДОДАТИ УЧНЯ ──────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "➕ Додати учня" and str(m.from_user.id) in db["teachers"])
async def add_student(message: types.Message):
    user_state[message.from_user.id] = {"state": "waiting_name", "tid": str(message.from_user.id)}
    await message.answer("Введи ім'я учня:")

@dp.message(lambda m: m.text and m.text == "📋 Список учнів" and str(m.from_user.id) in db["teachers"])
async def teacher_list(message: types.Message):
    tid = str(message.from_user.id)
    students = get_students(tid)
    if not students:
        await message.answer("Учнів поки немає.", reply_markup=menu_teacher)
        return
    kb = [[KeyboardButton(text=f"Учень: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer("Обери учня:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(lambda m: m.text and m.text.startswith("Учень: ") and str(m.from_user.id) in db["teachers"])
async def manage_student(message: types.Message):
    tid = str(message.from_user.id)
    name = message.text.replace("Учень: ", "")
    students = get_students(tid)
    if name not in students:
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return

    s = students[name]
    if not s.get("u_id") and not s.get("u_code"):
        s["u_code"] = new_code(tid)
    if not s.get("p_id") and not s.get("p_code"):
        s["p_code"] = new_code(tid)
    if not s.get("su_id") and not s.get("su_code"):
        s["su_code"] = new_code(tid)
    save_db()

    bal = s["balance"]
    bal_str = f"+{bal}₴" if bal > 0 else f"{bal}₴"
    u_status = "✅" if s.get("u_id") else f"🔑 {s.get('u_code','—')}"
    p_status = "✅" if s.get("p_id") else f"🔑 {s.get('p_code','—')}"
    su_status = "✅" if s.get("su_id") else f"🔑 {s.get('su_code','—')}"

    text = (
        f"👤 *{name}*\n"
        f"💰 Ціна: {s['price']}₴ | Баланс: {bal_str}\n"
        f"📱 Учень: {u_status} | 👨‍👩‍👦 Батьки: {p_status} | ⭐ Супер: {su_status}"
    )

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"💳 Керування балансом {name}"), KeyboardButton(text=f"📅 Розклад {name}")],
        [KeyboardButton(text=f"⚙️ Редагування {name}"), KeyboardButton(text=f"🔗 Посилання {name}")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True)

    user_state[message.from_user.id] = {"state": "managing_student", "name": name, "tid": tid}
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)


# ─── ВЧИТЕЛЬ: РОЗКЛАД ──────────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "📅 Мій розклад" and str(m.from_user.id) in db["teachers"])
async def teacher_schedule(message: types.Message):
    tid = str(message.from_user.id)
    students = get_students(tid)
    today = days[datetime.today().weekday()]
    today_sessions = []
    for name, data in students.items():
        for s in data.get("sessions", []):
            if s["day"] == today:
                today_sessions.append((s["time"], name))
    today_sessions.sort(key=lambda x: x[0])
    text = f"📅 Сьогодні ({today}):\n\n"
    text += "\n".join([f"{name} — {t}" for t, name in today_sessions]) if today_sessions else "Немає занять"
    await message.answer(text)

@dp.message(lambda m: m.text and m.text == "🗓 Розклад на тиждень" and str(m.from_user.id) in db["teachers"])
async def teacher_week_schedule(message: types.Message):
    tid = str(message.from_user.id)
    students = get_students(tid)
    today = days[datetime.today().weekday()]
    text = "🗓 *Розклад на тиждень:*\n"
    for day in days:
        day_sessions = []
        for name, data in students.items():
            for s in data.get("sessions", []):
                if s["day"] == day:
                    day_sessions.append((s["time"], name))
        day_sessions.sort(key=lambda x: x[0])
        marker = " ← сьогодні" if day == today else ""
        text += f"\n*{day}*{marker}\n─────────────\n"
        text += "\n".join([f"  {t} — {n}" for t, n in day_sessions]) if day_sessions else "  Немає занять"
        text += "\n"
    await message.answer(text, parse_mode="Markdown")


# ─── ВЧИТЕЛЬ: БАЛАНСИ ──────────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "💳 Баланси" and str(m.from_user.id) in db["teachers"])
async def teacher_balances(message: types.Message):
    tid = str(message.from_user.id)
    students = get_students(tid)
    if not students:
        await message.answer("Список учнів порожній.")
        return
    text = "💳 *Поточні баланси учнів:*\n\n"
    total_debt = 0
    for name, data in students.items():
        bal = data.get("balance", 0)
        status = "✅" if bal >= 0 else "⚠️ (борг)"
        text += f"👤 {name}: {bal}₴ {status}\n"
        if bal < 0:
            total_debt += bal
    if total_debt < 0:
        text += f"\nЗагальна заборгованість: {total_debt}₴"
    await message.answer(text, parse_mode="Markdown")


# ─── ВЧИТЕЛЬ: ВІДМІТИТИ ЗАНЯТТЯ ────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "✔️ Відмітити заняття" and str(m.from_user.id) in db["teachers"])
async def mark_lesson(message: types.Message):
    tid = str(message.from_user.id)
    students = get_students(tid)
    if not students:
        await message.answer("Учнів немає.")
        return
    kb = [[KeyboardButton(text=f"Заняття: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer("Оберіть учня:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(lambda m: m.text and m.text.startswith("Заняття: ") and str(m.from_user.id) in db["teachers"])
async def mark_lesson_choose_action(message: types.Message):
    tid = str(message.from_user.id)
    name = message.text.replace("Заняття: ", "")
    if name not in get_students(tid):
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return
    user_state[message.from_user.id] = {"state": "mark_lesson_action", "name": name, "tid": tid}
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✅ Проведено"), KeyboardButton(text="❌ Скасовано")],
        [KeyboardButton(text="🔄 Перенести заняття")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True)
    await message.answer(f"Що сталось із заняттям у {name}?", reply_markup=kb)


# ─── ВЧИТЕЛЬ: ДЗ ───────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "📝 Відправити домашнє завдання" and str(m.from_user.id) in db["teachers"])
async def hw_choose_student(message: types.Message):
    tid = str(message.from_user.id)
    students = get_students(tid)
    if not students:
        await message.answer("Учнів немає.", reply_markup=menu_teacher)
        return
    kb = [[KeyboardButton(text=f"ДЗ для: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer("Обери учня:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(lambda m: m.text and m.text.startswith("ДЗ для: ") and str(m.from_user.id) in db["teachers"])
async def hw_enter_text(message: types.Message):
    tid = str(message.from_user.id)
    name = message.text.replace("ДЗ для: ", "")
    if name not in get_students(tid):
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return
    user_state[message.from_user.id] = {"state": "hw_waiting_text", "name": name, "tid": tid}
    await message.answer(
        f"📝 Введи текст ДЗ для {name} або надішли фото:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
    )


# ─── ВЧИТЕЛЬ: ЖУРНАЛ ───────────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "📒 Журнал занять" and str(m.from_user.id) in db["teachers"])
async def teacher_journal_choose_student(message: types.Message):
    tid = str(message.from_user.id)
    students = get_students(tid)
    if not students:
        await message.answer("Учнів немає.")
        return
    kb = [[KeyboardButton(text=f"Журнал: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer("Обери учня:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(lambda m: m.text and m.text.startswith("Журнал: ") and str(m.from_user.id) in db["teachers"])
async def teacher_journal_list(message: types.Message):
    tid = str(message.from_user.id)
    name = message.text.replace("Журнал: ", "").strip()
    students = get_students(tid)
    if name not in students:
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return
    journal = students[name].get("journal", [])
    if not journal:
        await message.answer(f"📒 У {name} ще немає занять.", reply_markup=menu_teacher)
        return
    kb = []
    for i, entry in enumerate(reversed(journal)):
        kb.append([KeyboardButton(text=f"Т.Журнал {name} #{len(journal)-i}: {entry['date']}")])
    kb.append([KeyboardButton(text="⬅️ Назад")])
    text = f"📒 *Журнал — {name}:*\n\n"
    for entry in reversed(journal):
        mat_count = len(entry.get("materials", []))
        text += f"📅 {entry['date']} — *{entry['topic']}*{f' | 📎{mat_count}' if mat_count else ''}\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(lambda m: m.text and m.text.startswith("Т.Журнал ") and str(m.from_user.id) in db["teachers"])
async def teacher_journal_detail(message: types.Message):
    tid = str(message.from_user.id)
    try:
        part = message.text.replace("Т.Журнал ", "")
        name, rest = part.split(" #", 1)
        idx = int(rest.split(":")[0].strip()) - 1
        journal = get_students(tid)[name].get("journal", [])
        entry = journal[idx]
    except (ValueError, IndexError, KeyError):
        await message.answer("Заняття не знайдено.")
        return
    materials = entry.get("materials", [])
    await message.answer(
        f"📒 *Заняття {idx+1} — {name}*\n📅 {entry['date']}\n📖 {entry['topic']}\n"
        f"{'📎 ' + str(len(materials)) + ' файл(ів)' if materials else '📎 Матеріалів немає'}",
        parse_mode="Markdown"
    )
    for mat in materials:
        try:
            if mat["type"] == "photo":
                await message.answer_photo(mat["file_id"], caption=mat.get("caption") or None)
            elif mat["type"] == "document":
                await message.answer_document(mat["file_id"], caption=mat.get("caption") or None)
        except Exception:
            pass


# ─── ВЧИТЕЛЬ: КОРИСНІ ПОСИЛАННЯ ───────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "🔗 Корисні посилання" and str(m.from_user.id) in db["teachers"])
async def teacher_links(message: types.Message):
    tid = str(message.from_user.id)
    links = db["teachers"][tid].get("links", {})
    if not links:
        user_state[message.from_user.id] = {"state": "teacher_links_waiting_label", "tid": tid}
        await message.answer(
            "🔗 Посилань поки немає.\nЯк назвемо перше?",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
        )
    else:
        text = "🔗 *Корисні посилання:*\n\n"
        for label, url in links.items():
            text += f"• {label}: {url}\n"
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="➕ Додати посилання")],
            [KeyboardButton(text="🗑 Видалити посилання")],
            [KeyboardButton(text="⬅️ Назад")]
        ], resize_keyboard=True)
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)


# ─── УЧЕНЬ: БАЛАНС ─────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text and ("Мій баланс" in m.text or "Баланс дитини" in m.text))
async def student_balance(message: types.Message):
    uid = message.from_user.id
    tid, sname, sdata, role = find_student_by_uid(uid)
    if sdata:
        bal = sdata["balance"]
        status = "✅" if bal >= 0 else "⚠️ (заборгованість)"
        await message.answer(f"👤 {sname}, баланс: {bal}₴ {status}")

@dp.message(lambda m: m.text and ("Мій розклад" in m.text or "Розклад дитини" in m.text))
async def student_schedule(message: types.Message):
    uid = message.from_user.id
    # Перевіряємо чи не вчитель
    if str(uid) in db["teachers"]:
        return
    tid, sname, sdata, role = find_student_by_uid(uid)
    if sdata:
        sessions = "\n".join([f"🔹 {s['day']} {s['time']}" for s in sdata.get("sessions", [])])
        await message.answer(f"📅 Твій розклад:\n{sessions or 'Розклад ще не встановлено'}")

@dp.message(lambda m: m.text and "Домашні завдання" in m.text)
async def student_hw_list(message: types.Message):
    uid = message.from_user.id
    tid, sname, sdata, role = find_student_by_uid(uid)
    if not sdata:
        return
    homework = (sdata.get("homework") or []).copy()
    homework.reverse()
    if not homework:
        await message.answer("📚 Домашніх завдань немає.")
        return
    kb = []
    for i, hw in enumerate(homework):
        status_icon = "✅" if hw["status"] == "done" else "🔴"
        kb.append([KeyboardButton(text=f"ДЗ {len(homework)-i}: {hw['date']} {status_icon}")])
    kb.append([KeyboardButton(text="⬅️ Назад")])
    text = "📚 *Домашні завдання:*\n\n"
    for hw in homework:
        status = "✅ Виконано" if hw["status"] == "done" else "🔴 Не виконано"
        text += f"📅 {hw['date']} — {hw['text'][:40]}{'…' if len(hw['text'])>40 else ''}\n{status}\n\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(lambda m: m.text and m.text.startswith("ДЗ ") and ":" in (m.text or ""))
async def student_hw_detail(message: types.Message):
    uid = message.from_user.id
    tid, sname, sdata, role = find_student_by_uid(uid)
    if not sdata:
        return
    try:
        part = message.text.split(":")[0].replace("ДЗ ", "").strip()
        idx = int(part) - 1
        hw = sdata.get("homework", [])[idx]
    except (ValueError, IndexError):
        await message.answer("ДЗ не знайдено.")
        return
    status_text = "✅ Виконано" if hw["status"] == "done" else "🔴 Не виконано"
    text = f"📝 *ДЗ від {hw['date']}*\n\n{hw['text']}\n\nСтатус: {status_text}"
    user_state[uid] = {"state": "viewing_hw", "hw_id": hw["id"], "tid": tid, "sname": sname}
    if hw["status"] == "done":
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
    else:
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="✅ Відмітити як виконане")],
            [KeyboardButton(text="📸 Надіслати фото виконання")],
            [KeyboardButton(text="⬅️ Назад")]
        ], resize_keyboard=True)
    if hw.get("photo_id"):
        await message.answer_photo(hw["photo_id"], caption=text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.message(lambda m: m.text and m.text == "📒 Журнал занять")
async def student_journal(message: types.Message):
    uid = message.from_user.id
    if str(uid) in db["teachers"]:
        return
    tid, sname, sdata, role = find_student_by_uid(uid)
    if not sdata:
        return
    journal = (sdata.get("journal") or []).copy()
    journal.reverse()
    if not journal:
        await message.answer("📒 Журнал порожній.")
        return
    kb = []
    for i, entry in enumerate(journal):
        kb.append([KeyboardButton(text=f"📒 Заняття {len(journal)-i}: {entry['date']}")])
    kb.append([KeyboardButton(text="⬅️ Назад")])
    text = "📒 *Журнал занять:*\n\n"
    for entry in journal:
        mat_count = len(entry.get("materials", []))
        text += f"📅 {entry['date']} — *{entry['topic']}*{f' | 📎{mat_count}' if mat_count else ''}\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(lambda m: m.text and m.text.startswith("📒 Заняття "))
async def student_journal_detail(message: types.Message):
    uid = message.from_user.id
    tid, sname, sdata, role = find_student_by_uid(uid)
    if not sdata:
        return
    try:
        part = message.text.replace("📒 Заняття ", "")
        idx = int(part.split(":")[0].strip()) - 1
        entry = sdata.get("journal", [])[idx]
    except (ValueError, IndexError):
        await message.answer("Заняття не знайдено.")
        return
    materials = entry.get("materials", [])
    await message.answer(
        f"📒 *Заняття {idx+1}*\n📅 {entry['date']}\n📖 {entry['topic']}\n"
        f"{'📎 ' + str(len(materials)) + ' файл(ів)' if materials else '📎 Матеріалів немає'}",
        parse_mode="Markdown"
    )
    for mat in materials:
        try:
            if mat["type"] == "photo":
                await message.answer_photo(mat["file_id"], caption=mat.get("caption") or None)
            elif mat["type"] == "document":
                await message.answer_document(mat["file_id"], caption=mat.get("caption") or None)
        except Exception:
            pass


# ─── УЧЕНЬ: КОРИСНІ ПОСИЛАННЯ ──────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "🔗 Корисні посилання")
async def student_links(message: types.Message):
    uid = message.from_user.id
    if str(uid) in db["teachers"]:
        return
    tid, sname, sdata, role = find_student_by_uid(uid)
    if not sdata:
        return
    links = sdata.get("links", {})
    if not links:
        await message.answer("🔗 Посилань поки немає. Зверніться до вчителя.")
        return
    text = "🔗 *Корисні посилання:*\n\n"
    for label, url in links.items():
        text += f"• [{label}]({url})\n"
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)


# ─── УЧЕНЬ: ВИХІД ──────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "🚪 Вийти з кабінета")
async def logout(message: types.Message):
    uid = message.from_user.id
    tid, sname, sdata, role = find_student_by_uid(uid)
    if sdata:
        for key in ("u_id", "p_id", "su_id"):
            if sdata.get(key) == uid:
                sdata[key] = None
        save_db()
        user_state[uid] = None
        await message.answer(
            f"👋 Ти вийшов з кабінету {sname}.\nЩоб увійти знову — введи свій код після /start.",
            reply_markup=types.ReplyKeyboardRemove()
        )


# ─── ОПЛАТА ────────────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text and m.text == "💰 Поповнити баланс")
async def pay_start(message: types.Message):
    uid = message.from_user.id
    tid, sname, sdata, role = find_student_by_uid(uid)
    if not sdata or role not in ("parent", "super"):
        await message.answer("Доступ заборонено.")
        return
    user_state[uid] = {"state": "pay_sum", "tid": tid, "sname": sname}
    await message.answer("Введіть суму поповнення (₴):")

@dp.message(lambda m: isinstance(user_state.get(m.from_user.id), dict) and user_state[m.from_user.id].get("state") == "pay_sum")
async def pay_sum(message: types.Message):
    if not message.text or not message.text.isdigit():
        await message.answer("Будь ласка, введіть число.")
        return
    uid = message.from_user.id
    state = user_state[uid]
    state["sum"] = int(message.text)
    state["state"] = "pay_check"
    await message.answer(f"Сума: {message.text}₴. Надішліть фото чеку:")

@dp.message(
    lambda m: isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "pay_check"
    and m.photo is not None
)
async def pay_photo(message: types.Message):
    uid = message.from_user.id
    state = user_state[uid]
    amount = state["sum"]
    tid = state["tid"]
    sname = state["sname"]

    teacher = db["teachers"].get(tid, {})
    tid_int = int(tid)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_{uid}_{amount}_{tid}_{sname}")],
        [InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{uid}")]
    ])

    await bot.send_photo(
        tid_int,
        message.photo[-1].file_id,
        caption=f"💰 Заявка на поповнення!\nВід: {sname}\nСума: {amount}₴",
        reply_markup=kb
    )
    user_state[uid] = None
    await message.answer("Дякуємо! Чек надіслано вчителю.")


# ─── CALLBACKS ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_pay(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    payer_id = int(parts[1])
    amount = int(parts[2])
    tid = parts[3]
    sname = "_".join(parts[4:])

    if tid in db["teachers"] and sname in db["teachers"][tid]["students"]:
        sdata = db["teachers"][tid]["students"][sname]
        sdata["balance"] += amount
        save_db()
        await bot.send_message(payer_id, f"✅ Поповнення {amount}₴ підтверджено!\n💳 Баланс: {sdata['balance']}₴")
        await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n✅ ПІДТВЕРДЖЕНО")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_pay(callback: types.CallbackQuery):
    payer_id = int(callback.data.split("_")[1])
    await bot.send_message(payer_id, "❌ Поповнення відхилено. Зверніться до вчителя.")
    await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n❌ ВІДХИЛЕНО")
    await callback.answer()


# ─── ОБРОБНИК ПОМИЛОК ─────────────────────────────────────────────────────────

@dp.errors()
async def error_handler(event: types.ErrorEvent):
    print(f"[ERROR] {event.exception.__class__.__name__}: {event.exception}")
    import traceback
    traceback.print_exc()


# ─── ЗАГАЛЬНИЙ ХЕНДЛЕР ─────────────────────────────────────────────────────────

@dp.message()
async def handle(message: types.Message):
    uid = message.from_user.id
    state = user_state.get(uid)
    tid_str = str(uid)
    is_teacher = tid_str in db["teachers"]

    print(f"[HANDLE] uid={uid} state={state} text={message.text!r} photo={bool(message.photo)} doc={bool(message.document)}")

    # ── Матеріали до заняття ──
    if isinstance(state, dict) and state.get("state") == "lesson_send_materials":
        tid = state["tid"]
        if message.photo:
            state["materials"].append({"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""})
            await message.answer(f"🖼 Фото {len(state['materials'])} додано. Ще або *Готово*.", parse_mode="Markdown")
            return
        if message.document:
            mime = message.document.mime_type or ""
            icon = "📄" if "pdf" in mime else "📎"
            state["materials"].append({"type": "document", "file_id": message.document.file_id, "caption": message.caption or "", "name": message.document.file_name or "файл"})
            await message.answer(f"{icon} {message.document.file_name} ({len(state['materials'])}) додано. Ще або *Готово*.", parse_mode="Markdown")
            return

    # ── Назад ──
    if message.text == "⬅️ Назад":
        user_state[uid] = None
        if is_teacher:
            url = f"{WEBAPP_URL}?role=admin&tid={tid_str}"
            await message.answer("Головне меню", reply_markup=get_webapp_menu(menu_teacher, url))
        else:
            ftid, sname, sdata, role = find_student_by_uid(uid)
            if sdata:
                url = f"{WEBAPP_URL}?role={role}&tid={ftid}&name={sname}"
                await message.answer("Головне меню", reply_markup=get_webapp_menu(get_student_menu(role), url))
        return

    # ── Журнал занять ──
    if message.text == "📒 Журнал занять":
        if is_teacher:
            await teacher_journal_choose_student(message)
        else:
            await student_journal(message)
        return

    if message.text and message.text.startswith("Журнал: ") and is_teacher:
        await teacher_journal_list(message)
        return

    if message.text and message.text.startswith("Т.Журнал ") and is_teacher:
        await teacher_journal_detail(message)
        return

    if message.text and message.text.startswith("📒 Заняття "):
        await student_journal_detail(message)
        return

    if message.text and message.text.startswith("ДЗ ") and ":" in message.text:
        await student_hw_detail(message)
        return

    if message.text and message.text.startswith("Заняття: ") and is_teacher:
        await mark_lesson_choose_action(message)
        return

    if message.text == "🚪 Вийти з кабінета":
        await logout(message)
        return

    if message.text == "🔗 Корисні посилання":
        if is_teacher:
            await teacher_links(message)
        else:
            await student_links(message)
        return

    if message.text in ("➕ Додати посилання", "🗑 Видалити посилання") and is_teacher:
        tid = tid_str
        links = db["teachers"][tid].get("links", {})
        if message.text == "➕ Додати посилання":
            user_state[uid] = {"state": "teacher_links_waiting_label", "tid": tid}
            await message.answer("Як назвемо посилання?", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True))
        else:
            if not links:
                await message.answer("Посилань немає.")
                return
            kb = [[KeyboardButton(text=f"🗑 {label}")] for label in links]
            kb.append([KeyboardButton(text="⬅️ Назад")])
            user_state[uid] = {"state": "teacher_links_waiting_delete", "tid": tid}
            await message.answer("Оберіть для видалення:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
        return

    if message.text == "🗓 Розклад на тиждень" and is_teacher:
        await teacher_week_schedule(message)
        return

    # ── Стани ──

    # Додавання учня
    if isinstance(state, dict) and state.get("state") == "waiting_name":
        tid = state["tid"]
        user_state[uid] = {"state": "waiting_price", "name": message.text, "tid": tid}
        await message.answer("Введи ціну заняття (₴):")
        return

    if isinstance(state, dict) and state.get("state") == "waiting_price":
        try:
            price = int(message.text)
            user_state[uid] = {"state": "waiting_day", "name": state["name"], "price": price, "sessions": [], "tid": state["tid"]}
            await message.answer("Обери день:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=d)] for d in days], resize_keyboard=True))
        except ValueError:
            await message.answer("Введи число")
        return

    if isinstance(state, dict) and state.get("state") == "waiting_day":
        if message.text not in days:
            await message.answer("Обери день кнопкою")
            return
        state["current_day"] = message.text
        state["state"] = "waiting_time"
        user_state[uid] = state
        await message.answer(f"Введи час для {message.text} (наприклад 18:00):")
        return

    if isinstance(state, dict) and state.get("state") == "waiting_time":
        if not re.match(r"^\d{1,2}:\d{2}$", message.text):
            await message.answer("Формат: 18:00")
            return
        state["sessions"].append({"day": state["current_day"], "time": message.text})
        state["state"] = "confirm_more_days"
        user_state[uid] = state
        await message.answer(
            f"Додано: {state['current_day']} {message.text}\nДодати ще день?",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➕ Додати ще день")], [KeyboardButton(text="✅ Готово")]], resize_keyboard=True)
        )
        return

    if isinstance(state, dict) and state.get("state") == "confirm_more_days":
        if message.text == "➕ Додати ще день":
            state["state"] = "waiting_day"
            user_state[uid] = state
            await message.answer("Обери ще один день:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=d)] for d in days], resize_keyboard=True))
        elif message.text == "✅ Готово":
            tid = state["tid"]
            name = state["name"]
            u_code = new_code(tid)
            p_code = new_code(tid)
            su_code = new_code(tid)
            db["teachers"][tid]["students"][name] = {
                "price": state["price"], "balance": 0,
                "sessions": state["sessions"], "homework": [], "journal": [], "links": {},
                "u_code": u_code, "u_id": None,
                "p_code": p_code, "p_id": None,
                "su_code": su_code, "su_id": None
            }
            save_db()
            user_state[uid] = None
            sessions_text = "\n".join([f"  {s['day']} {s['time']}" for s in state["sessions"]])
            await message.answer(
                f"✅ {name} доданий!\n💰 {state['price']}₴\n📅\n{sessions_text}\n\n"
                f"🔑 Код учня: {u_code}\n👨‍👩‍👦 Код батьків: {p_code}\n⭐ Код супер-учня: {su_code}",
                reply_markup=menu_teacher
            )
        return

    # Керування учнем
    if isinstance(state, dict) and state.get("state") == "managing_student":
        tid = state["tid"]
        name = state["name"]
        students = get_students(tid)

        if message.text == f"💳 Керування балансом {name}":
            bal = students[name]["balance"]
            bal_str = f"+{bal}₴" if bal > 0 else f"{bal}₴"
            await message.answer(f"💳 Баланс {name}: *{bal_str}*", parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(keyboard=[
                    [KeyboardButton(text=f"💰 Поповнити {name}"), KeyboardButton(text=f"➖ Списати {name}")],
                    [KeyboardButton(text=f"👁 Баланс {name}")],
                    [KeyboardButton(text="⬅️ Назад")]
                ], resize_keyboard=True))
            return

        if message.text == f"💰 Поповнити {name}":
            user_state[uid] = {"state": "balance_add", "name": name, "tid": tid}
            await message.answer("Введи суму поповнення (₴):")
            return

        if message.text == f"➖ Списати {name}":
            user_state[uid] = {"state": "balance_sub", "name": name, "tid": tid}
            await message.answer("Введи суму для списання (₴):")
            return

        if message.text == f"👁 Баланс {name}":
            bal = students[name]["balance"]
            bal_str = f"+{bal}₴" if bal > 0 else f"{bal}₴"
            await message.answer(f"💳 {name}: *{bal_str}*\n💲 Ціна: {students[name]['price']}₴", parse_mode="Markdown")
            return

        if message.text == f"📅 Розклад {name}":
            sessions = students[name].get("sessions", [])
            text = f"📅 *Розклад {name}:*\n\n" + "\n".join([f"🔹 {s['day']} {s['time']}" for s in sessions]) if sessions else "Розклад не встановлено"
            await message.answer(text, parse_mode="Markdown")
            return

        if message.text == f"⚙️ Редагування {name}":
            await message.answer(f"⚙️ Редагування {name}:", reply_markup=ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text=f"📅 Змінити розклад {name}"), KeyboardButton(text=f"💲 Змінити ціну {name}")],
                [KeyboardButton(text=f"🔑 Оновити коди {name}"), KeyboardButton(text=f"❌ Видалити {name}")],
                [KeyboardButton(text="⬅️ Назад")]
            ], resize_keyboard=True))
            return

        if message.text == f"💲 Змінити ціну {name}":
            user_state[uid] = {"state": "edit_price", "name": name, "tid": tid}
            await message.answer(f"Поточна ціна: {students[name]['price']}₴\nВведи нову:")
            return

        if message.text == f"📅 Змінити розклад {name}":
            user_state[uid] = {"state": "waiting_day", "name": name, "price": students[name]["price"], "sessions": [], "tid": tid, "editing": True}
            await message.answer("Обери новий перший день:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=d)] for d in days], resize_keyboard=True))
            return

        if message.text == f"❌ Видалити {name}":
            del db["teachers"][tid]["students"][name]
            save_db()
            user_state[uid] = None
            await message.answer(f"🗑 {name} видалений.", reply_markup=menu_teacher)
            return

        if message.text == f"🔑 Оновити коди {name}":
            s = students[name]
            s["u_code"] = new_code(tid); s["u_id"] = None
            s["p_code"] = new_code(tid); s["p_id"] = None
            s["su_code"] = new_code(tid); s["su_id"] = None
            save_db()
            await message.answer(f"🔑 Нові коди для {name}:\nУчень: {s['u_code']}\nБатьки: {s['p_code']}\n⭐ Супер: {s['su_code']}")
            return

        if message.text == f"🔗 Посилання {name}":
            links = students[name].get("links", {})
            text = f"🔗 *Посилання {name}:*\n\n" + "\n".join([f"• {k}: {v}" for k, v in links.items()]) if links else f"🔗 У {name} посилань немає."
            await message.answer(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text=f"➕ Посилання учню {name}")],
                [KeyboardButton(text=f"🗑л Посилання учня {name}")],
                [KeyboardButton(text="⬅️ Назад")]
            ], resize_keyboard=True))
            user_state[uid] = {"state": "managing_student", "name": name, "tid": tid}
            return

        if message.text == f"➕ Посилання учню {name}":
            user_state[uid] = {"state": "student_links_label", "name": name, "tid": tid}
            await message.answer("Як назвемо посилання?")
            return

        if message.text == f"🗑л Посилання учня {name}":
            links = students[name].get("links", {})
            if not links:
                await message.answer("Посилань немає.")
                return
            kb = [[KeyboardButton(text=f"🗑л {k}")] for k in links]
            kb.append([KeyboardButton(text="⬅️ Назад")])
            user_state[uid] = {"state": "student_links_delete", "name": name, "tid": tid}
            await message.answer("Оберіть для видалення:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
            return

    # Баланс
    if isinstance(state, dict) and state.get("state") == "balance_add":
        try:
            amount = int(message.text)
            tid = state["tid"]
            name = state["name"]
            db["teachers"][tid]["students"][name]["balance"] += amount
            save_db()
            bal = db["teachers"][tid]["students"][name]["balance"]
            user_state[uid] = None
            await message.answer(f"✅ +{amount}₴ до балансу {name}\n💳 Баланс: {'+' if bal>=0 else ''}{bal}₴", reply_markup=menu_teacher)
        except ValueError:
            await message.answer("Введи число")
        return

    if isinstance(state, dict) and state.get("state") == "balance_sub":
        try:
            amount = int(message.text)
            tid = state["tid"]
            name = state["name"]
            db["teachers"][tid]["students"][name]["balance"] -= amount
            save_db()
            bal = db["teachers"][tid]["students"][name]["balance"]
            user_state[uid] = None
            await message.answer(f"✅ -{amount}₴ з балансу {name}\n💳 Баланс: {'+' if bal>=0 else ''}{bal}₴", reply_markup=menu_teacher)
            if bal < 0:
                sdata = db["teachers"][tid]["students"][name]
                notify = [i for i in [sdata.get("p_id"), sdata.get("su_id")] if i]
                for nid in notify:
                    try:
                        await bot.send_message(nid, f"⚠️ Баланс від'ємний!\n💳 {bal}₴\nПоповніть баланс.")
                    except Exception:
                        pass
        except ValueError:
            await message.answer("Введи число")
        return

    if isinstance(state, dict) and state.get("state") == "edit_price":
        try:
            price = int(message.text)
            tid = state["tid"]
            name = state["name"]
            old = db["teachers"][tid]["students"][name]["price"]
            db["teachers"][tid]["students"][name]["price"] = price
            save_db()
            user_state[uid] = None
            await message.answer(f"✅ Ціна {name}: {old}₴ → {price}₴", reply_markup=menu_teacher)
        except ValueError:
            await message.answer("Введи число")
        return

    # Відмітити заняття
    if isinstance(state, dict) and state.get("state") == "mark_lesson_action":
        tid = state["tid"]
        name = state["name"]
        sdata = db["teachers"][tid]["students"][name]

        if message.text == "✅ Проведено":
            user_state[uid] = {"state": "lesson_enter_topic", "name": name, "tid": tid}
            await message.answer("Введіть тему заняття:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True))
            return

        if message.text == "❌ Скасовано":
            user_state[uid] = {"state": "cancel_enter_date", "name": name, "tid": tid}
            await message.answer("Введіть дату заняття, яке скасовуєте:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True))
            return

        if message.text == "🔄 Перенести заняття":
            user_state[uid] = {"state": "reschedule_enter_date", "name": name, "tid": tid}
            await message.answer("Введіть дату заняття, яке переносите:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True))
            return

    if isinstance(state, dict) and state.get("state") == "lesson_enter_topic":
        topic = message.text.strip()
        user_state[uid] = {"state": "lesson_send_materials", "name": state["name"], "tid": state["tid"], "topic": topic, "date": datetime.now().strftime("%d.%m.%Y"), "materials": []}
        await message.answer(
            f"✏️ Тема: *{topic}*\n\nНадішліть матеріали або натисніть Готово.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Готово")], [KeyboardButton(text="✅ Готово (без матеріалів)")]], resize_keyboard=True)
        )
        return

    if isinstance(state, dict) and state.get("state") == "lesson_send_materials" and message.text in ("✅ Готово", "✅ Готово (без матеріалів)"):
        tid = state["tid"]
        name = state["name"]
        topic = state["topic"]
        date_str = state["date"]
        materials = state["materials"]
        user_state[uid] = None

        sdata = db["teachers"][tid]["students"][name]
        price = sdata["price"]
        sdata["balance"] -= price
        if "journal" not in sdata:
            sdata["journal"] = []
        sdata["journal"].append({"date": date_str, "topic": topic, "materials": materials})
        save_db()

        new_balance = sdata["balance"]
        await message.answer(
            f"✅ Заняття відмічено!\n👤 {name} | 📖 {topic}\nСписано {price}₴. Залишок: {new_balance}₴",
            reply_markup=menu_teacher
        )

        notify_pay = [i for i in [sdata.get("p_id"), sdata.get("su_id")] if i]
        notify_student = [i for i in [sdata.get("u_id"), sdata.get("su_id")] if i]

        for nid in notify_pay:
            try:
                await bot.send_message(nid, f"🔔 Заняття проведено.\n📖 Тема: {topic}\nСписано: {price}₴\nБаланс: {new_balance}₴")
            except Exception:
                pass

        if new_balance < 0:
            for nid in notify_pay:
                try:
                    await bot.send_message(nid, f"⚠️ Баланс від'ємний!\n💳 {new_balance}₴\nПоповніть баланс.")
                except Exception:
                    pass

        if materials:
            for nid in notify_student:
                try:
                    await bot.send_message(nid, f"📚 Матеріали до заняття *{topic}* ({date_str}):", parse_mode="Markdown")
                    for mat in materials:
                        if mat["type"] == "photo":
                            await bot.send_photo(nid, mat["file_id"], caption=mat.get("caption") or None)
                        elif mat["type"] == "document":
                            await bot.send_document(nid, mat["file_id"], caption=mat.get("caption") or None)
                except Exception:
                    pass
        return

    if isinstance(state, dict) and state.get("state") == "cancel_enter_date":
        date = message.text.strip()
        name = state["name"]
        tid = state["tid"]
        user_state[uid] = None
        await message.answer(f"❌ Заняття {name} {date} скасовано.", reply_markup=menu_teacher)
        sdata = db["teachers"][tid]["students"][name]
        for nid in [i for i in [sdata.get("u_id"), sdata.get("su_id"), sdata.get("p_id")] if i]:
            try:
                await bot.send_message(nid, f"❌ Заняття {date} скасовано. Баланс не змінювався.")
            except Exception:
                pass
        return

    if isinstance(state, dict) and state.get("state") == "reschedule_enter_date":
        state["old_date"] = message.text.strip()
        state["state"] = "reschedule_enter_new_date"
        user_state[uid] = state
        await message.answer("На яку дату переносимо?")
        return

    if isinstance(state, dict) and state.get("state") == "reschedule_enter_new_date":
        new_date = message.text.strip()
        old_date = state["old_date"]
        name = state["name"]
        tid = state["tid"]
        user_state[uid] = None
        await message.answer(f"🔄 Заняття {name} перенесено з {old_date} на {new_date}.", reply_markup=menu_teacher)
        sdata = db["teachers"][tid]["students"][name]
        for nid in [i for i in [sdata.get("u_id"), sdata.get("su_id"), sdata.get("p_id")] if i]:
            try:
                await bot.send_message(nid, f"🔄 Заняття перенесено!\nБуло: {old_date}\nСтало: {new_date}")
            except Exception:
                pass
        return

    # ДЗ від вчителя
    if isinstance(state, dict) and state.get("state") == "hw_waiting_text":
        tid = state["tid"]
        name = state["name"]
        date_str = datetime.now().strftime("%d.%m.%Y")
        hw_id = new_hw_id()
        sdata = db["teachers"][tid]["students"][name]

        if message.photo:
            sdata.setdefault("homework", []).append({"id": hw_id, "text": message.caption or "Дивись фото", "photo_id": message.photo[-1].file_id, "date": date_str, "status": "new"})
            save_db()
            user_state[uid] = None
            await message.answer(f"✅ ДЗ надіслано {name}!", reply_markup=menu_teacher)
            u_id = sdata.get("u_id") or sdata.get("su_id")
            if u_id:
                try:
                    await bot.send_photo(u_id, message.photo[-1].file_id, caption=f"📝 Нове ДЗ!\n📅 {date_str}\n{message.caption or ''}")
                except Exception:
                    pass
        elif message.text:
            sdata.setdefault("homework", []).append({"id": hw_id, "text": message.text, "photo_id": None, "date": date_str, "status": "new"})
            save_db()
            user_state[uid] = None
            await message.answer(f"✅ ДЗ надіслано {name}!", reply_markup=menu_teacher)
            u_id = sdata.get("u_id") or sdata.get("su_id")
            if u_id:
                try:
                    await bot.send_message(u_id, f"📝 Нове ДЗ!\n📅 {date_str}\n\n{message.text}")
                except Exception:
                    pass
        return

    # Виконання ДЗ учнем
    if isinstance(state, dict) and state.get("state") == "viewing_hw":
        tid = state["tid"]
        sname = state["sname"]
        hw_id = state["hw_id"]
        sdata = db["teachers"][tid]["students"][sname]

        if message.text == "✅ Відмітити як виконане":
            for hw in sdata.get("homework", []):
                if hw["id"] == hw_id:
                    hw["status"] = "done"
                    hw_date = hw["date"]
                    break
            save_db()
            user_state[uid] = None
            await message.answer("✅ ДЗ відмічено як виконане!", reply_markup=get_student_menu("student"))
            try:
                await bot.send_message(int(tid), f"✅ {sname} відмітив ДЗ як виконане.")
            except Exception:
                pass
            return

        if message.text == "📸 Надіслати фото виконання":
            user_state[uid] = {"state": "hw_done_photo", "hw_id": hw_id, "tid": tid, "sname": sname}
            await message.answer("📸 Надішли фото виконаного ДЗ:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True))
            return

    if isinstance(state, dict) and state.get("state") == "hw_done_photo" and message.photo:
        tid = state["tid"]
        sname = state["sname"]
        hw_id = state["hw_id"]
        sdata = db["teachers"][tid]["students"][sname]
        hw_date = "?"
        for hw in sdata.get("homework", []):
            if hw["id"] == hw_id:
                hw["status"] = "done"
                hw_date = hw["date"]
                break
        save_db()
        user_state[uid] = None
        await message.answer("✅ Фото надіслано! ДЗ виконане.", reply_markup=get_student_menu("student"))
        try:
            await bot.send_photo(int(tid), message.photo[-1].file_id, caption=f"📸 {sname} виконав ДЗ від {hw_date}\n{message.caption or ''}")
        except Exception:
            pass
        return

    # Посилання вчителя
    if isinstance(state, dict) and state.get("state") == "teacher_links_waiting_label":
        user_state[uid] = {"state": "teacher_links_waiting_url", "tid": state["tid"], "label": message.text.strip()}
        await message.answer(f"Вставте посилання для *{message.text.strip()}*:", parse_mode="Markdown")
        return

    if isinstance(state, dict) and state.get("state") == "teacher_links_waiting_url":
        url = message.text.strip()
        if not url.startswith("http"):
            await message.answer("Посилання повинно починатись з http://")
            return
        tid = state["tid"]
        label = state["label"]
        db["teachers"][tid].setdefault("links", {})[label] = url
        save_db()
        user_state[uid] = None
        await message.answer(f"✅ Посилання *{label}* збережено!", parse_mode="Markdown", reply_markup=menu_teacher)
        return

    if isinstance(state, dict) and state.get("state") == "teacher_links_waiting_delete" and message.text and message.text.startswith("🗑 "):
        label = message.text.replace("🗑 ", "").strip()
        tid = state["tid"]
        links = db["teachers"][tid].get("links", {})
        if label in links:
            del links[label]
            save_db()
            await message.answer(f"🗑 Посилання *{label}* видалено.", parse_mode="Markdown", reply_markup=menu_teacher)
        user_state[uid] = None
        return

    # Посилання учня
    if isinstance(state, dict) and state.get("state") == "student_links_label":
        user_state[uid] = {"state": "student_links_url", "name": state["name"], "tid": state["tid"], "label": message.text.strip()}
        await message.answer(f"Вставте посилання для *{message.text.strip()}*:", parse_mode="Markdown")
        return

    if isinstance(state, dict) and state.get("state") == "student_links_url":
        url = message.text.strip()
        if not url.startswith("http"):
            await message.answer("Посилання повинно починатись з http://")
            return
        tid = state["tid"]
        name = state["name"]
        db["teachers"][tid]["students"][name].setdefault("links", {})[state["label"]] = url
        save_db()
        user_state[uid] = None
        await message.answer(f"✅ Посилання додано для {name}!", reply_markup=menu_teacher)
        return

    if isinstance(state, dict) and state.get("state") == "student_links_delete" and message.text and message.text.startswith("🗑л "):
        label = message.text.replace("🗑л ", "").strip()
        tid = state["tid"]
        name = state["name"]
        links = db["teachers"][tid]["students"][name].get("links", {})
        if label in links:
            del links[label]
            save_db()
            await message.answer(f"🗑 Посилання *{label}* видалено.", parse_mode="Markdown", reply_markup=menu_teacher)
        user_state[uid] = None
        return

    # Редагування розкладу (editing=True)
    if isinstance(state, dict) and state.get("state") == "confirm_more_days" and state.get("editing"):
        if message.text == "✅ Готово":
            tid = state["tid"]
            name = state["name"]
            db["teachers"][tid]["students"][name]["sessions"] = state["sessions"]
            save_db()
            user_state[uid] = None
            sessions_text = "\n".join([f"  {s['day']} {s['time']}" for s in state["sessions"]])
            await message.answer(f"✅ Розклад {name} оновлено!\n{sessions_text}", reply_markup=menu_teacher)
            u_id = db["teachers"][tid]["students"][name].get("u_id") or db["teachers"][tid]["students"][name].get("su_id")
            if u_id:
                try:
                    await bot.send_message(u_id, f"📅 Твій розклад оновлено!\n{sessions_text}")
                except Exception:
                    pass
        return


# ─── ЗАПУСК ────────────────────────────────────────────────────────────────────

async def main():
    load_db()
    print("Бот запущено...")
    asyncio.create_task(send_reminders())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
