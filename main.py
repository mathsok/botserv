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
        [KeyboardButton(text="➕ Додати учня"), KeyboardButton(text="📋 Список учнів")],
        [KeyboardButton(text="📅 Мій розклад"), KeyboardButton(text="✔️ Відмітити заняття")],
        [KeyboardButton(text="💳 Баланси")],
    ], resize_keyboard=True
)

menu_student = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Мій розклад"), KeyboardButton(text="💳 Мій баланс")]
    ], resize_keyboard=True
)

menu_parent = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Розклад дитини"), KeyboardButton(text="💳 Баланс дитини")],
        [KeyboardButton(text="💰 Поповнити баланс")]
    ], resize_keyboard=True
)

def get_menu(uid):
    if uid == ADMIN_ID:
        return menu_teacher
    for name, data in students.items():
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

def new_code():
    existing = set()
    for d in students.values():
        if d.get("u_code"):
            existing.add(d["u_code"])
        if d.get("p_code"):
            existing.add(d["p_code"])
    while True:
        code = str(random.randint(1000, 9999))
        if code not in existing:
            return code


# ─── НАГАДУВАННЯ ───────────────────────────────────────────────────────────────

async def send_reminders():
    """Кожну хвилину перевіряє: чи є заняття рівно через 4 години"""
    while True:
        try:
            now = datetime.now()
            target = now + timedelta(hours=4)
            target_day = days[target.weekday()]
            target_time = target.strftime("%H:%M")

            for name, data in students.items():
                for session in data.get("sessions", []):
                    if session["day"] == target_day and session["time"] == target_time:

                        u_id = data.get("u_id")
                        if u_id:
                            try:
                                await bot.send_message(
                                    u_id,
                                    f"🔔 Нагадування!\n"
                                    f"Сьогодні о {target_time} у тебе заняття.\n"
                                    f"Не забудь підготуватись! 📚"
                                )
                            except Exception:
                                pass

                        p_id = data.get("p_id")
                        if p_id:
                            try:
                                await bot.send_message(
                                    p_id,
                                    f"🔔 Нагадування!\n"
                                    f"Сьогодні о {target_time} заняття у {name}.\n"
                                    f"Не забудьте нагадати дитині! 📚"
                                )
                            except Exception:
                                pass

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

    u_status = "✅ Прив'язано" if s.get("u_id") else f"🔑 Код учня: {s.get('u_code')}"
    p_status = "✅ Прив'язано" if s.get("p_id") else f"🔑 Код батьків: {s.get('p_code')}"

    text = (
        f"👤 {name}\n"
        f"💰 Ціна: {s['price']}₴ | Баланс: {bal_str}\n"
        f"📅 {sessions_text or 'Розклад не встановлено'}\n"
        f"📱 {u_status}\n"
        f"👨‍👩‍👦 {p_status}"
    )

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"💰 Поповнити {name}"), KeyboardButton(text=f"➖ Списати {name}")],
        [KeyboardButton(text=f"❌ Видалити {name}"), KeyboardButton(text=f"🔑 Оновити коди {name}")],
        [KeyboardButton(text="⬅️ Назад")]
    ], resize_keyboard=True)

    user_state[message.from_user.id] = {"state": "managing_student", "name": name}
    await message.answer(text, reply_markup=kb)


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

    kb = [[KeyboardButton(text=f"Проведено: {n}")] for n in students]
    kb.append([KeyboardButton(text="⬅️ Назад")])
    await message.answer(
        "Оберіть учня, який відвідав заняття:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )


@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text.startswith("Проведено: "))
async def mark_lesson_confirm(message: types.Message):
    name = message.text.replace("Проведено: ", "")
    if name not in students:
        await message.answer("Учня не знайдено.", reply_markup=menu_teacher)
        return

    price = students[name]["price"]
    students[name]["balance"] -= price
    save_data()

    new_balance = students[name]["balance"]
    await message.answer(
        f"✅ Відмічено! З балансу {name} списано {price}₴.\nЗалишок: {new_balance}₴",
        reply_markup=menu_teacher
    )

    p_id = students[name].get("p_id")
    if p_id:
        try:
            await bot.send_message(
                p_id,
                f"🔔 Заняття проведено.\nЗ балансу списано: {price}₴\nПоточний баланс: {new_balance}₴"
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
        text += f"\nОбща заборгованість: {total_debt}₴"

    await message.answer(text, parse_mode="Markdown")


# ─── УЧЕНЬ: БАЛАНС ─────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text == "💳 Мій баланс")
async def student_balance(message: types.Message):
    name, data = find_by_uid(message.from_user.id)
    if data:
        bal = data["balance"]
        status = "✅" if bal >= 0 else "⚠️ (заборгованість)"
        await message.answer(f"👤 {name}, твій баланс: {bal}₴ {status}")


# ─── УЧЕНЬ: РОЗКЛАД ────────────────────────────────────────────────────────────

@dp.message(lambda m: m.text == "📅 Мій розклад")
async def student_schedule(message: types.Message):
    name, data = find_by_uid(message.from_user.id)
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
    p_id, amount = int(parts[1]), int(parts[2])

    for name, data in students.items():
        if data.get("p_id") == p_id:
            data["balance"] += amount
            save_data()
            await bot.send_message(
                p_id,
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
            u_code = new_code()
            p_code = new_code()
            students[name] = {
                "price": state["price"],
                "balance": 0,
                "sessions": state["sessions"],
                "u_code": u_code,
                "u_id": None,
                "p_code": p_code,
                "p_id": None
            }
            save_data()
            user_state[uid] = None
            sessions_text = "\n".join([f"  {s['day']} {s['time']}" for s in state["sessions"]])
            await message.answer(
                f"✅ {name} доданий\n"
                f"💰 {state['price']}₴\n"
                f"📅 Розклад:\n{sessions_text}\n\n"
                f"🔑 Код учня: {u_code}\n"
                f"👨‍👩‍👦 Код батьків: {p_code}",
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
            save_data()
            await message.answer(
                f"🔑 Нові коди для {name}:\n"
                f"Учень: {students[name]['u_code']}\n"
                f"Батьки: {students[name]['p_code']}"
            )
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
