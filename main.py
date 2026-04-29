import asyncio
import os
import json
import random
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

load_dotenv()

# ─── КОНФІГУРАЦІЯ ──────────────────────────────────────────────────────────────

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
DATA_FILE = "students_db.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

students = {}
user_state = {}

days = ["Понеділок", "Вівторок", "Середа", "Четвер", "Пʼятниця", "Субота", "Неділя"]


# ─── БАЗА ДАНИХ ────────────────────────────────────────────────────────────────

def load_data():
    global students
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            students = json.load(f)

def save_data():
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=4)
    os.replace(tmp, DATA_FILE)


# ─── КЛАВІАТУРИ ────────────────────────────────────────────────────────────────

menu_teacher = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👥 Керування учнями")],
        [KeyboardButton(text="📖 Заняття і матеріали")],
        [KeyboardButton(text="📅 Мій розклад")],
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
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True
)

menu_student = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Мій розклад"), KeyboardButton(text="💳 Мій баланс")],
        [KeyboardButton(text="📖 Заняття і матеріали")],
        [KeyboardButton(text="🚪 Вийти з кабінета")]
    ], resize_keyboard=True
)

menu_student_lessons = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Домашні завдання")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True
)

menu_parent = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Розклад дитини"), KeyboardButton(text="💳 Баланс дитини")],
        [KeyboardButton(text="💰 Поповнити баланс")],
        [KeyboardButton(text="🚪 Вийти з кабінета")]
    ], resize_keyboard=True
)

menu_super = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Мій розклад"), KeyboardButton(text="💳 Мій баланс")],
        [KeyboardButton(text="📖 Заняття і матеріали"), KeyboardButton(text="💰 Поповнити баланс")],
        [KeyboardButton(text="🚪 Вийти з кабінета")]
    ], resize_keyboard=True
)

def get_menu(uid):
    if uid == ADMIN_ID:
        return menu_teacher
    for name, data in students.items():
        if data.get("su_id") == uid:
            return menu_super
        if data.get("u_id") == uid:
            return menu_student
        if data.get("p_id") == uid:
            return menu_parent
    return None


# ─── ДОПОМІЖНІ ФУНКЦІЇ ─────────────────────────────────────────────────────────

def find_by_uid(uid):
    for name, data in students.items():
        if data.get("u_id") == uid:
            return name, data
    return None, None

def find_by_pid(pid):
    for name, data in students.items():
        if data.get("p_id") == pid:
            return name, data
    return None, None

def find_by_suid(uid):
    for name, data in students.items():
        if data.get("su_id") == uid:
            return name, data
    return None, None

def new_code():
    existing = set()
    for d in students.values():
        for key in ("u_code", "p_code", "su_code"):
            if d.get(key):
                existing.add(d[key])
    while True:
        code = str(random.randint(1000, 9999))
        if code not in existing:
            return code

def new_hw_id():
    """Генерує унікальний ID для домашнього завдання"""
    all_ids = set()
    for d in students.values():
        for hw in d.get("homework", []):
            all_ids.add(hw.get("id", ""))
    while True:
        hw_id = str(random.randint(10000, 99999))
        if hw_id not in all_ids:
            return hw_id


# ─── НАГАДУВАННЯ ───────────────────────────────────────────────────────────────

async def send_reminders():
    """Кожну хвилину перевіряє: чи є заняття рівно через 4 години"""
    while True:
        try:
            now = datetime.now()
            target = now + timedelta(hours=4)
            target_day = days[target.weekday()]
            target_time = target.strftime("%H:%M")

            print(f"[{now.strftime('%H:%M')}] Нагадування: шукаю заняття на {target_day} {target_time}")

            for name, data in students.items():
                for session in data.get("sessions", []):
                    match = session["day"] == target_day and session["time"] == target_time
                    print(f"  {name}: '{session['day']} {session['time']}' → {'✅ збіг!' if match else '—'}")
                    if match:
                        u_id = data.get("u_id") or data.get("su_id")
                        print(f"  → u_id = {u_id}")
                        if u_id:
                            try:
                                await bot.send_message(
                                    u_id,
                                    f"🔔 Нагадування!\n"
                                    f"Сьогодні о {target_time} у тебе заняття.\n"
                                    f"Не забудь підготуватись! 📚"
                                )
                                print(f"  → Нагадування надіслано {name}")
                            except Exception as e:
                                print(f"  → Помилка надсилання: {e}")
                        else:
                            print(f"  → u_id не прив'язано, пропускаємо")

        except Exception as e:
            print(f"Помилка в нагадуваннях: {e}")

        await asyncio.sleep(60)


# ─── СТАРТ ─────────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def start(message: types.Message):
    load_data()
    uid = message.from_user.id

    if uid == ADMIN_ID:
        await message.answer("Вітаю, Вчителю! Ваша панель керування:", reply_markup=menu_teacher)
        return

    su_name, _ = find_by_suid(uid)
    if su_name:
        await message.answer(f"Привіт, {su_name}! Твій кабінет:", reply_markup=menu_super)
        return
    s_name, _ = find_by_uid(uid)
    if s_name:
        await message.answer(f"Привіт, {s_name}! Твій кабінет:", reply_markup=menu_student)
        return

    p_name, _ = find_by_pid(uid)
    if p_name:
        await message.answer(f"Привіт! Кабінет учня {p_name}:", reply_markup=menu_parent)
        return

    user_state[uid] = "waiting_auth_code"
    await message.answer("Привіт! Ви ще не зареєстровані. Введіть код доступу, який надав вчитель:")


# ─── АВТОРИЗАЦІЯ ───────────────────────────────────────────────────────────────

@dp.message(lambda m: user_state.get(m.from_user.id) == "waiting_auth_code")
async def auth(message: types.Message):
    code = message.text.strip()
    uid = message.from_user.id

    for name, data in students.items():
        if data.get("su_code") == code:
            data["su_id"] = uid
            data["su_code"] = None
            save_data()
            user_state[uid] = None
            await message.answer(f"✅ Вітаю, {name}! Ти зайшов як учень.", reply_markup=menu_super)
            return
        if data.get("u_code") == code:
            data["u_id"] = uid
            data["u_code"] = None
            save_data()
            user_state[uid] = None
            await message.answer(f"✅ Вітаю, {name}! Ти зайшов як учень.", reply_markup=menu_student)
            return
        if data.get("p_code") == code:
            data["p_id"] = uid
            data["p_code"] = None
            save_data()
            user_state[uid] = None
            await message.answer(f"✅ Вітаю! Ви зайшли як батько/мати учня {name}.", reply_markup=menu_parent)
            return

    await message.answer("❌ Код не знайдено. Спробуй ще раз або звернись до вчителя.")


# ─── ВЧИТЕЛЬ: СПИСОК УЧНІВ ─────────────────────────────────────────────────────

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "📋 Список учнів")
async def teacher_list(message: types.Message):
    if not students:
        await message.answer("Учнів поки немає.", reply_markup=menu_teacher)
        return
    kb = [[KeyboardButton(text=f"Учень: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer("Обери учня для керування:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))


@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text.startswith("Учень: "))
async def manage_student(message: types.Message):
    name = message.text.replace("Учень: ", "")
    if name not in students:
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return

    s = students[name]

    if not s.get("u_id") and not s.get("u_code"):
        s["u_code"] = new_code()
    if not s.get("p_id") and not s.get("p_code"):
        s["p_code"] = new_code()
    save_data()

    sessions_text = " | ".join([f"{x['day']} {x['time']}" for x in s.get("sessions", [])])
    bal = s["balance"]
    bal_str = f"+{bal}₴" if bal > 0 else f"{bal}₴"

    u_status = "✅ Прив'язано" if s.get("u_id") else f"🔑 Код учня: {s.get('u_code') or '—'}"
    p_status = "✅ Прив'язано" if s.get("p_id") else f"🔑 Код батьків: {s.get('p_code') or '—'}"
    su_status = "✅ Прив'язано" if s.get("su_id") else f"🔑 Код супер-учня: {s.get('su_code') or '—'}"

    text = (
        f"👤 {name}\n"
        f"💰 Ціна: {s['price']}₴ | Баланс: {bal_str}\n"
        f"📅 {sessions_text or 'Розклад не встановлено'}\n"
        f"📱 {u_status}\n"
        f"👨‍👩‍👦 {p_status}\n"
        f"⭐ {su_status}"
    )

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"💰 Поповнити {name}"), KeyboardButton(text=f"➖ Списати {name}")],
        [KeyboardButton(text=f"📅 Змінити розклад {name}"), KeyboardButton(text=f"💲 Змінити ціну {name}")],
        [KeyboardButton(text=f"❌ Видалити {name}"), KeyboardButton(text=f"🔑 Оновити коди {name}")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True)

    user_state[message.from_user.id] = {"state": "managing_student", "name": name}
    await message.answer(text, reply_markup=kb)


# ─── ВЧИТЕЛЬ: РОЗДІЛИ МЕНЮ ────────────────────────────────────────────────────

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "👥 Керування учнями")
async def teacher_section_students(message: types.Message):
    await message.answer("👥 Керування учнями:", reply_markup=menu_teacher_students)


@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "📖 Заняття і матеріали")
async def teacher_section_lessons(message: types.Message):
    await message.answer("📖 Заняття і матеріали:", reply_markup=menu_teacher_lessons)


# ─── ВЧИТЕЛЬ: ДОДАТИ УЧНЯ ──────────────────────────────────────────────────────

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "➕ Додати учня")
async def add_student(message: types.Message):
    user_state[message.from_user.id] = "waiting_name"
    await message.answer("Введи ім'я учня:")


# ─── ВЧИТЕЛЬ: РОЗКЛАД ──────────────────────────────────────────────────────────

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "📅 Мій розклад")
async def teacher_schedule(message: types.Message):
    if not students:
        await message.answer("Немає учнів.")
        return

    today = days[datetime.today().weekday()]
    text = f"📅 Сьогодні ({today}):\n\n"

    today_sessions = []
    for name, data in students.items():
        for s in data.get("sessions", []):
            if s["day"] == today:
                today_sessions.append((s["time"], name))

    today_sessions.sort(key=lambda x: x[0])
    text += "\n".join([f"{name} — {time}" for time, name in today_sessions]) if today_sessions else "Немає занять"
    await message.answer(text)


# ─── ВЧИТЕЛЬ: ВІДМІТИТИ ЗАНЯТТЯ ────────────────────────────────────────────────

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "✔️ Відмітити заняття")
async def mark_lesson(message: types.Message):
    if not students:
        await message.answer("Учнів немає.")
        return

    kb = [[KeyboardButton(text=f"Заняття: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer(
        "Оберіть учня:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )


@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text.startswith("Заняття: "))
async def mark_lesson_choose_action(message: types.Message):
    name = message.text.replace("Заняття: ", "")
    if name not in students:
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return

    user_state[message.from_user.id] = {"state": "mark_lesson_action", "name": name}
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✅ Проведено"), KeyboardButton(text="❌ Скасовано")],
        [KeyboardButton(text="🔄 Перенести заняття")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True)
    await message.answer(f"Що сталось із заняттям у {name}?", reply_markup=kb)


@dp.message(
    lambda m: m.from_user.id == ADMIN_ID
    and isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "mark_lesson_action"
    and m.text in ["✅ Проведено", "❌ Скасовано", "🔄 Перенести заняття"]
)
async def mark_lesson_confirm(message: types.Message):
    uid = message.from_user.id
    name = user_state[uid]["name"]

    if name not in students:
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        user_state[uid] = None
        return

    if message.text == "✅ Проведено":
        user_state[uid] = None
        price = students[name]["price"]
        students[name]["balance"] -= price
        save_data()

        new_balance = students[name]["balance"]
        await message.answer(
            f"✅ Відмічено! З балансу {name} списано {price}₴.\nЗалишок: {new_balance}₴",
            reply_markup=menu_teacher
        )

        p_id = students[name].get("p_id")
        su_id = students[name].get("su_id")
        notify_ids = [i for i in [p_id, su_id] if i]
        for nid in notify_ids:
            try:
                await bot.send_message(
                    nid,
                    f"🔔 Заняття проведено.\nЗ балансу списано: {price}₴\nПоточний баланс: {new_balance}₴"
                )
            except Exception:
                pass

        if new_balance < 0:
            for nid in notify_ids:
                try:
                    await bot.send_message(
                        nid,
                        f"⚠️ Увага! Баланс став від'ємним.\n"
                        f"💳 Поточний баланс: {new_balance}₴\n"
                        f"Будь ласка, поповніть баланс."
                    )
                except Exception:
                    pass

    elif message.text == "❌ Скасовано":
        user_state[uid] = {"state": "cancel_enter_date", "name": name}
        await message.answer(
            f"Введіть дату заняття, яке бажаєте скасувати (наприклад 05.05):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )

    elif message.text == "🔄 Перенести заняття":
        user_state[uid] = {"state": "reschedule_enter_date", "name": name}
        await message.answer(
            f"Введіть дату заняття, яке переносите (наприклад 05.05):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Назад")]],
                resize_keyboard=True
            )
        )


@dp.message(
    lambda m: m.from_user.id == ADMIN_ID
    and isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "cancel_enter_date"
)
async def cancel_enter_date(message: types.Message):
    uid = message.from_user.id
    name = user_state[uid]["name"]
    date = message.text.strip()
    user_state[uid] = None

    await message.answer(
        f"❌ Заняття з {name} {date} скасовано. Баланс не змінено.",
        reply_markup=menu_teacher
    )

    # Сповіщення всім
    notify_ids = [i for i in [
        students[name].get("u_id"),
        students[name].get("su_id"),
        students[name].get("p_id")
    ] if i]
    for nid in notify_ids:
        try:
            await bot.send_message(
                nid,
                f"❌ Заняття {date} скасовано.\nБаланс не змінювався."
            )
        except Exception:
            pass


@dp.message(
    lambda m: m.from_user.id == ADMIN_ID
    and isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "reschedule_enter_date"
)
async def reschedule_enter_date(message: types.Message):
    uid = message.from_user.id
    name = user_state[uid]["name"]
    old_date = message.text.strip()
    user_state[uid] = {"state": "reschedule_enter_new_date", "name": name, "old_date": old_date}
    await message.answer(
        f"На яку дату переносимо? (наприклад 10.05, можна також вказати час: 10.05 о 18:00):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )


@dp.message(
    lambda m: m.from_user.id == ADMIN_ID
    and isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "reschedule_enter_new_date"
)
async def reschedule_enter_new_date(message: types.Message):
    uid = message.from_user.id
    name = user_state[uid]["name"]
    old_date = user_state[uid]["old_date"]
    new_date = message.text.strip()
    user_state[uid] = None

    await message.answer(
        f"🔄 Заняття з {name} перенесено з {old_date} на {new_date}.",
        reply_markup=menu_teacher
    )

    # Сповіщення всім
    notify_ids = [i for i in [
        students[name].get("u_id"),
        students[name].get("su_id"),
        students[name].get("p_id")
    ] if i]
    for nid in notify_ids:
        try:
            await bot.send_message(
                nid,
                f"🔄 Заняття перенесено!\n"
                f"Було: {old_date}\n"
                f"Стало: {new_date}"
            )
        except Exception:
            pass


# ─── ВЧИТЕЛЬ: БАЛАНСИ ──────────────────────────────────────────────────────────

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "💳 Баланси")
async def teacher_balances(message: types.Message):
    load_data()
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


# ─── ВЧИТЕЛЬ: ДОМАШНЄ ЗАВДАННЯ — ВИБІР УЧНЯ ───────────────────────────────────

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "📝 Відправити домашнє завдання")
async def hw_choose_student(message: types.Message):
    if not students:
        await message.answer("Учнів немає.", reply_markup=menu_teacher)
        return

    kb = [[KeyboardButton(text=f"ДЗ для: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer(
        "Обери учня, якому хочеш надіслати домашнє завдання:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )


@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text.startswith("ДЗ для: "))
async def hw_enter_text(message: types.Message):
    name = message.text.replace("ДЗ для: ", "")
    if name not in students:
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return

    user_state[message.from_user.id] = {"state": "hw_waiting_text", "name": name}
    await message.answer(
        f"📝 Введи текст домашнього завдання для {name}:\n"
        f"(або надішли фото із підписом)",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )


# ─── ВЧИТЕЛЬ: ДОМАШНЄ ЗАВДАННЯ — ОТРИМАННЯ ТЕКСТУ АБО ФОТО ───────────────────

@dp.message(
    lambda m: m.from_user.id == ADMIN_ID
    and isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "hw_waiting_text",
    F.photo
)
async def hw_receive_photo(message: types.Message):
    """Учитель надсилає ДЗ у вигляді фото"""
    uid = message.from_user.id
    state = user_state[uid]
    name = state["name"]

    caption = message.caption or ""
    hw_id = new_hw_id()
    date_str = datetime.now().strftime("%d.%m.%Y")

    if "homework" not in students[name]:
        students[name]["homework"] = []

    students[name]["homework"].append({
        "id": hw_id,
        "text": caption or "Дивись фото",
        "photo_id": message.photo[-1].file_id,
        "date": date_str,
        "status": "new"  # new | done
    })
    save_data()
    user_state[uid] = None

    await message.answer(
        f"✅ Домашнє завдання надіслано учню {name}!",
        reply_markup=menu_teacher
    )

    # Сповіщення учню
    u_id = students[name].get("u_id")
    if u_id:
        try:
            await bot.send_photo(
                u_id,
                message.photo[-1].file_id,
                caption=(
                    f"📝 Нове домашнє завдання!\n"
                    f"📅 {date_str}\n"
                    f"{caption}\n\n"
                    f"Перейди у розділ 📚 *Домашні завдання*, щоб відмітити виконання."
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass


@dp.message(
    lambda m: m.from_user.id == ADMIN_ID
    and isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "hw_waiting_text"
)
async def hw_receive_text(message: types.Message):
    """Учитель надсилає ДЗ у вигляді тексту"""
    uid = message.from_user.id
    state = user_state[uid]
    name = state["name"]

    hw_id = new_hw_id()
    date_str = datetime.now().strftime("%d.%m.%Y")

    if "homework" not in students[name]:
        students[name]["homework"] = []

    students[name]["homework"].append({
        "id": hw_id,
        "text": message.text,
        "photo_id": None,
        "date": date_str,
        "status": "new"
    })
    save_data()
    user_state[uid] = None

    await message.answer(
        f"✅ Домашнє завдання надіслано учню {name}!",
        reply_markup=menu_teacher
    )

    # Сповіщення учню
    u_id = students[name].get("u_id")
    if u_id:
        try:
            await bot.send_message(
                u_id,
                f"📝 Нове домашнє завдання!\n"
                f"📅 {date_str}\n\n"
                f"{message.text}\n\n"
                f"Перейди у розділ 📚 *Домашні завдання*, щоб відмітити виконання.",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ─── УЧЕНЬ: РОЗДІЛ ЗАНЯТТЯ І МАТЕРІАЛИ ────────────────────────────────────────

@dp.message(lambda m: m.text == "📖 Заняття і матеріали")
async def student_section_lessons(message: types.Message):
    uid = message.from_user.id
    # Перевіряємо чи це учень або супер-учень (не вчитель)
    if uid == ADMIN_ID:
        return
    await message.answer("📖 Заняття і матеріали:", reply_markup=menu_student_lessons)


# ─── УЧЕНЬ: ДОМАШНІ ЗАВДАННЯ — СПИСОК ─────────────────────────────────────────

@dp.message(lambda m: m.text == "📚 Домашні завдання")
async def student_hw_list(message: types.Message):
    uid = message.from_user.id
    name, data = find_by_uid(uid)
    if not data:
        name, data = find_by_suid(uid)
    if not data:
        return

    homework = data.get("homework", [])
    if not homework:
        await message.answer("📚 Домашніх завдань немає.")
        return

    # Показуємо кнопки для кожного ДЗ
    kb = []
    for hw in homework:
        status_icon = "✅" if hw["status"] == "done" else "🔴"
        label = f"{status_icon} ДЗ від {hw['date']}: {hw['text'][:25]}{'…' if len(hw['text']) > 25 else ''}"
        kb.append([KeyboardButton(text=f"ДЗ#{hw['id']}")])

    kb.append([KeyboardButton(text="⬅️ Назад")])

    # Формуємо текстовий список
    text = "📚 *Твої домашні завдання:*\n\n"
    for hw in homework:
        status_icon = "✅ Виконано" if hw["status"] == "done" else "🔴 Не виконано"
        text += f"*ДЗ від {hw['date']}* (#{hw['id']})\n{hw['text'][:60]}{'…' if len(hw['text']) > 60 else ''}\nСтатус: {status_icon}\n\n"

    text += "Натисни на номер ДЗ нижче, щоб відкрити його:"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )


# ─── УЧЕНЬ: ДОМАШНЄ ЗАВДАННЯ — ДЕТАЛІ ─────────────────────────────────────────

@dp.message(lambda m: m.text and m.text.startswith("ДЗ#"))
async def student_hw_detail(message: types.Message):
    uid = message.from_user.id
    name, data = find_by_uid(uid)
    if not data:
        name, data = find_by_suid(uid)
    if not data:
        return

    hw_id = message.text.replace("ДЗ#", "").strip()
    homework = data.get("homework", [])
    hw = next((h for h in homework if h["id"] == hw_id), None)

    if not hw:
        await message.answer("Домашнє завдання не знайдено.")
        return

    status_text = "✅ Виконано" if hw["status"] == "done" else "🔴 Не виконано"
    text = (
        f"📝 *Домашнє завдання від {hw['date']}*\n\n"
        f"{hw['text']}\n\n"
        f"Статус: {status_text}"
    )

    # Зберігаємо поточне ДЗ у стані
    user_state[uid] = {"state": "viewing_hw", "hw_id": hw_id}

    # Кнопки залежать від статусу
    if hw["status"] == "done":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="⬅️ Назад")]
        ], resize_keyboard=True)
    else:
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="✅ Відмітити як виконане")],
            [KeyboardButton(text="📸 Надіслати фото виконання")],
            [KeyboardButton(text="⬅️ Назад")]
        ], resize_keyboard=True)

    # Якщо є фото — надсилаємо фото з підписом
    if hw.get("photo_id"):
        await message.answer_photo(
            hw["photo_id"],
            caption=text,
            parse_mode="Markdown",
            reply_markup=kb
        )
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)


# ─── УЧЕНЬ: ВІДМІТИТИ ДЗ ЯК ВИКОНАНЕ ─────────────────────────────────────────

@dp.message(
    lambda m: isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "viewing_hw"
    and m.text == "✅ Відмітити як виконане"
)
async def hw_mark_done(message: types.Message):
    uid = message.from_user.id
    name, data = find_by_uid(uid)
    if not data:
        return

    hw_id = user_state[uid]["hw_id"]
    for hw in data.get("homework", []):
        if hw["id"] == hw_id:
            hw["status"] = "done"
            break

    save_data()
    user_state[uid] = None

    await message.answer("✅ Чудово! Домашнє завдання відмічено як виконане.", reply_markup=menu_student)

    # Сповіщення вчителю
    try:
        await bot.send_message(
            ADMIN_ID,
            f"✅ {name} відмітив домашнє завдання як виконане.\n"
            f"📅 ДЗ від {next((h['date'] for h in data['homework'] if h['id'] == hw_id), '?')}"
        )
    except Exception:
        pass


# ─── УЧЕНЬ: НАДІСЛАТИ ФОТО ВИКОНАННЯ ──────────────────────────────────────────

@dp.message(
    lambda m: isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "viewing_hw"
    and m.text == "📸 Надіслати фото виконання"
)
async def hw_request_photo(message: types.Message):
    uid = message.from_user.id
    hw_id = user_state[uid]["hw_id"]
    user_state[uid] = {"state": "hw_sending_photo", "hw_id": hw_id}
    await message.answer(
        "📸 Надішли фото виконаного домашнього завдання:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )


@dp.message(
    lambda m: isinstance(user_state.get(m.from_user.id), dict)
    and user_state[m.from_user.id].get("state") == "hw_sending_photo",
    F.photo
)
async def hw_receive_done_photo(message: types.Message):
    uid = message.from_user.id
    name, data = find_by_uid(uid)
    if not data:
        return

    hw_id = user_state[uid]["hw_id"]
    hw_date = "?"
    for hw in data.get("homework", []):
        if hw["id"] == hw_id:
            hw["status"] = "done"
            hw_date = hw["date"]
            break

    save_data()
    user_state[uid] = None

    await message.answer("✅ Фото надіслано вчителю! Домашнє завдання відмічено як виконане.", reply_markup=menu_student)

    # Пересилаємо фото вчителю
    try:
        await bot.send_photo(
            ADMIN_ID,
            message.photo[-1].file_id,
            caption=(
                f"📸 {name} надіслав виконане домашнє завдання!\n"
                f"📅 ДЗ від {hw_date}\n"
                f"Коментар: {message.caption or '—'}"
            )
        )
    except Exception:
        pass


# ─── ВИХІД З КАБІНЕТУ ─────────────────────────────────────────────────────────

@dp.message(lambda m: m.text == "🚪 Вийти з кабінета")
async def logout(message: types.Message):
    uid = message.from_user.id

    # Визначаємо хто виходить і скидаємо прив'язку
    for name, data in students.items():
        if data.get("u_id") == uid:
            data["u_id"] = None
            save_data()
            user_state[uid] = None
            await message.answer(
                f"👋 Ти вийшов з кабінету {name}.\n"
                f"Щоб увійти знову — введи свій код після /start.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return

        if data.get("p_id") == uid:
            data["p_id"] = None
            save_data()
            user_state[uid] = None
            await message.answer(
                f"👋 Ви вийшли з кабінету {name}.\n"
                f"Щоб увійти знову — введіть свій код після /start.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return

        if data.get("su_id") == uid:
            data["su_id"] = None
            save_data()
            user_state[uid] = None
            await message.answer(
                f"👋 Ти вийшов з кабінету {name}.\n"
                f"Щоб увійти знову — введи свій код після /start.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            return


# ─── УЧЕНЬ: БАЛАНС ─────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text == "💳 Мій баланс")
async def student_balance(message: types.Message):
    uid = message.from_user.id
    name, data = find_by_uid(uid)
    if not data:
        name, data = find_by_suid(uid)
    if data:
        bal = data["balance"]
        status = "✅" if bal >= 0 else "⚠️ (заборгованість)"
        await message.answer(f"👤 {name}, твій баланс: {bal}₴ {status}")


# ─── УЧЕНЬ: РОЗКЛАД ────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text == "📅 Мій розклад")
async def student_schedule(message: types.Message):
    uid = message.from_user.id
    name, data = find_by_uid(uid)
    if not data:
        name, data = find_by_suid(uid)
    if data:
        sessions = "\n".join([f"🔹 {s['day']} {s['time']}" for s in data.get("sessions", [])])
        await message.answer(f"📅 Твій розклад:\n{sessions or 'Розклад ще не встановлено'}")


# ─── БАТЬКИ: БАЛАНС ────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text == "💳 Баланс дитини")
async def parent_balance(message: types.Message):
    name, data = find_by_pid(message.from_user.id)
    if data:
        bal = data["balance"]
        status = "✅" if bal >= 0 else "⚠️ (заборгованість)"
        await message.answer(f"👤 {name}, поточний баланс: {bal}₴ {status}")


# ─── БАТЬКИ: РОЗКЛАД ───────────────────────────────────────────────────────────

@dp.message(lambda m: m.text == "📅 Розклад дитини")
async def parent_schedule(message: types.Message):
    name, data = find_by_pid(message.from_user.id)
    if data:
        sessions = "\n".join([f"🔹 {s['day']} {s['time']}" for s in data.get("sessions", [])])
        await message.answer(f"📅 Розклад {name}:\n{sessions or 'Розклад ще не встановлено'}")


# ─── БАТЬКИ: ПОПОВНЕННЯ ЧЕРЕЗ ФОТО ────────────────────────────────────────────

@dp.message(lambda m: m.text == "💰 Поповнити баланс")
async def pay_start(message: types.Message):
    uid = message.from_user.id
    name, data = find_by_pid(uid)
    if not data:
        name, data = find_by_suid(uid)
    if not data:
        await message.answer("Доступ заборонено.")
        return
    user_state[uid] = "pay_sum"
    await message.answer("Введіть суму поповнення (₴):")


@dp.message(lambda m: user_state.get(m.from_user.id) == "pay_sum")
async def pay_sum(message: types.Message):
    if not message.text.isdigit():
        await message.answer("Будь ласка, введіть число.")
        return
    user_state[message.from_user.id] = {"state": "pay_check", "sum": int(message.text)}
    await message.answer(f"Сума: {message.text}₴. Тепер надішліть фото чеку для підтвердження:")


@dp.message(
    lambda m: isinstance(user_state.get(m.from_user.id), dict) and user_state[m.from_user.id].get("state") == "pay_check",
    F.photo
)
async def pay_photo(message: types.Message):
    uid = message.from_user.id
    state_data = user_state[uid]
    amount = state_data["sum"]

    child_name, _ = find_by_pid(uid)
    if not child_name:
        child_name, _ = find_by_suid(uid)
    child_name = child_name or "Учень"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_{uid}_{amount}")],
        [InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{uid}")]
    ])

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"💰 Заявка на поповнення!\nВід: {child_name} (батьки)\nСума: {amount}₴",
        reply_markup=kb
    )

    user_state[uid] = None
    await message.answer("Дякуємо! Чек надіслано вчителю на підтвердження.")


# ─── ПІДТВЕРДЖЕННЯ / ВІДХИЛЕННЯ ОПЛАТИ ────────────────────────────────────────

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_pay(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    payer_id, amount = int(parts[1]), int(parts[2])

    for name, data in students.items():
        if data.get("p_id") == payer_id or data.get("su_id") == payer_id:
            data["balance"] += amount
            save_data()
            await bot.send_message(
                payer_id,
                f"✅ Поповнення на {amount}₴ підтверджено!\n💳 Новий баланс: {data['balance']}₴"
            )
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n✅ ПІДТВЕРДЖЕНО"
            )
            await callback.answer()
            return

    await callback.answer("Учня не знайдено.")


@dp.callback_query(F.data.startswith("reject_"))
async def reject_pay(callback: types.CallbackQuery):
    p_id = int(callback.data.split("_")[1])
    await bot.send_message(p_id, "❌ Ваше поповнення відхилено. Зверніться до вчителя.")
    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n❌ ВІДХИЛЕНО"
    )
    await callback.answer()


# ─── ЗАГАЛЬНИЙ ХЕНДЛЕР ─────────────────────────────────────────────────────────

@dp.message()
async def handle(message: types.Message):
    uid = message.from_user.id
    state = user_state.get(uid)

    if message.text == "⬅️ Назад":
        user_state[uid] = None
        kb = get_menu(uid) or menu_teacher
        await message.answer("Головне меню", reply_markup=kb)
        return

    if state == "waiting_name":
        user_state[uid] = {"state": "waiting_price", "name": message.text}
        await message.answer("Введи ціну заняття (₴):")
        return

    if isinstance(state, dict) and state.get("state") == "waiting_price":
        try:
            price = int(message.text)
            user_state[uid] = {"state": "waiting_day", "name": state["name"], "price": price, "sessions": []}
            buttons = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=day)] for day in days],
                resize_keyboard=True
            )
            await message.answer("Обери день:", reply_markup=buttons)
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
            await message.answer("Введи час у форматі ГГ:ХХ, наприклад 18:00")
            return
        state["sessions"].append({"day": state["current_day"], "time": message.text})
        state["state"] = "confirm_more_days"
        user_state[uid] = state
        buttons = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="➕ Додати ще день")],
                [KeyboardButton(text="✅ Готово")]
            ],
            resize_keyboard=True
        )
        await message.answer(f"Додано: {state['current_day']} {message.text}\n\nДодати ще день?", reply_markup=buttons)
        return

    if isinstance(state, dict) and state.get("state") == "confirm_more_days":
        if message.text == "➕ Додати ще день":
            state["state"] = "waiting_day"
            user_state[uid] = state
            buttons = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=day)] for day in days],
                resize_keyboard=True
            )
            await message.answer("Обери ще один день:", reply_markup=buttons)
        elif message.text == "✅ Готово":
            name = state["name"]

            # ── Редагування розкладу існуючого учня ──
            if state.get("editing"):
                students[name]["sessions"] = state["sessions"]
                save_data()
                user_state[uid] = None
                sessions_text = "\n".join([f"  {s['day']} {s['time']}" for s in state["sessions"]])
                await message.answer(
                    f"✅ Розклад {name} оновлено!\n📅\n{sessions_text}",
                    reply_markup=menu_teacher
                )
                # Сповіщення учню про зміну розкладу
                u_id = students[name].get("u_id")
                if u_id:
                    try:
                        await bot.send_message(
                            u_id,
                            f"📅 Твій розклад було оновлено!\n\n{sessions_text}"
                        )
                    except Exception:
                        pass

            # ── Додавання нового учня ──
            else:
                u_code = new_code()
                p_code = new_code()
                su_code = new_code()
                students[name] = {
                    "price": state["price"],
                    "balance": 0,
                    "sessions": state["sessions"],
                    "homework": [],
                    "u_code": u_code,
                    "u_id": None,
                    "p_code": p_code,
                    "p_id": None,
                    "su_code": su_code,
                    "su_id": None
                }
                save_data()
                user_state[uid] = None
                sessions_text = "\n".join([f"  {s['day']} {s['time']}" for s in state["sessions"]])
                await message.answer(
                    f"✅ {name} доданий\n"
                    f"💰 {state['price']}₴\n"
                    f"📅 Розклад:\n{sessions_text}\n\n"
                    f"🔑 Код учня: {u_code}\n"
                    f"👨‍👩‍👦 Код батьків: {p_code}\n"
                    f"⭐ Код супер-учня: {su_code}",
                    reply_markup=menu_teacher
                )
        return

    if isinstance(state, dict) and state.get("state") == "managing_student":
        name = state["name"]

        if message.text == f"💰 Поповнити {name}":
            user_state[uid] = {"state": "balance_add", "name": name}
            await message.answer("Введи суму поповнення (₴):")
            return

        if message.text == f"➖ Списати {name}":
            user_state[uid] = {"state": "balance_sub", "name": name}
            await message.answer("Введи суму для списання (₴):")
            return

        if message.text == f"💲 Змінити ціну {name}":
            user_state[uid] = {"state": "edit_price", "name": name}
            await message.answer(
                f"Поточна ціна заняття для {name}: {students[name]['price']}₴\n"
                f"Введи нову ціну (₴):"
            )
            return

        if message.text == f"📅 Змінити розклад {name}":
            current = " | ".join([f"{s['day']} {s['time']}" for s in students[name].get("sessions", [])])
            user_state[uid] = {"state": "waiting_day", "name": name, "price": students[name]["price"], "sessions": [], "editing": True}
            buttons = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=day)] for day in days],
                resize_keyboard=True
            )
            await message.answer(
                f"📅 Поточний розклад {name}: {current or 'не встановлено'}\n\n"
                f"Обери новий перший день (старий розклад буде замінено):",
                reply_markup=buttons
            )
            return

        if message.text == f"❌ Видалити {name}":
            students.pop(name, None)
            save_data()
            user_state[uid] = None
            await message.answer(f"🗑 {name} видалений.", reply_markup=menu_teacher)
            return

        if message.text == f"🔑 Оновити коди {name}":
            students[name]["u_code"] = new_code()
            students[name]["u_id"] = None
            students[name]["p_code"] = new_code()
            students[name]["p_id"] = None
            students[name]["su_code"] = new_code()
            students[name]["su_id"] = None
            save_data()
            await message.answer(
                f"🔑 Нові коди для {name}:\n"
                f"Учень: {students[name]['u_code']}\n"
                f"Батьки: {students[name]['p_code']}\n"
                f"⭐ Супер-учень: {students[name]['su_code']}"
            )
            return

    if isinstance(state, dict) and state.get("state") == "edit_price":
        try:
            new_price = int(message.text)
            name = state["name"]
            old_price = students[name]["price"]
            students[name]["price"] = new_price
            save_data()
            user_state[uid] = None
            await message.answer(
                f"✅ Ціна для {name} змінена: {old_price}₴ → {new_price}₴",
                reply_markup=menu_teacher
            )
        except ValueError:
            await message.answer("Введи число")
        return

    if isinstance(state, dict) and state.get("state") == "balance_add":
        try:
            amount = int(message.text)
            name = state["name"]
            students[name]["balance"] += amount
            save_data()
            bal = students[name]["balance"]
            bal_str = f"+{bal}₴" if bal > 0 else f"{bal}₴"
            user_state[uid] = None
            await message.answer(f"✅ Баланс {name} поповнено на +{amount}₴\n💳 Новий баланс: {bal_str}", reply_markup=menu_teacher)
        except ValueError:
            await message.answer("Введи число")
        return

    if isinstance(state, dict) and state.get("state") == "balance_sub":
        try:
            amount = int(message.text)
            name = state["name"]
            students[name]["balance"] -= amount
            save_data()
            bal = students[name]["balance"]
            bal_str = f"+{bal}₴" if bal > 0 else f"{bal}₴"
            user_state[uid] = None
            await message.answer(f"✅ З балансу {name} списано −{amount}₴\n💳 Новий баланс: {bal_str}", reply_markup=menu_teacher)
            if bal < 0:
                notify_ids = [i for i in [students[name].get("p_id"), students[name].get("su_id")] if i]
                for nid in notify_ids:
                    try:
                        await bot.send_message(
                            nid,
                            f"⚠️ Увага! Баланс став від'ємним.\n"
                            f"💳 Поточний баланс: {bal}₴\n"
                            f"Будь ласка, поповніть баланс."
                        )
                    except Exception:
                        pass
        except ValueError:
            await message.answer("Введи число")
        return


# ─── ЗАПУСК ────────────────────────────────────────────────────────────────────

async def main():
    load_data()
    print("Бот запущено...")
    asyncio.create_task(send_reminders())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
