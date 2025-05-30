import telebot
from telebot import types
from datetime import datetime, timedelta
from setings import TOKEN, ADMIN_ID
import json

bot = telebot.TeleBot(TOKEN)

# Завантаження користувачів з файлу
try:
    with open("users.json", "r", encoding="utf-8") as file:
        users = json.load(file)
except (FileNotFoundError, json.JSONDecodeError):
    users = {}

orders = {}  # Тимчасове збереження замовлень

def save_users():
    with open("users.json", "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = str(message.chat.id)
    if chat_id not in users:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        phone_button = types.KeyboardButton("📞 Надіслати номер", request_contact=True)
        markup.add(phone_button)
        bot.send_message(chat_id, "Вітаю! Будь ласка, надішліть свій номер телефону для реєстрації:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "Ви вже зареєстровані! Надішліть ваше замовлення (напій).")

@bot.message_handler(content_types=['contact'])
def register_user(message):
    chat_id = str(message.chat.id)
    if message.contact is not None:
        users[chat_id] = {"name": message.contact.first_name, "phone": message.contact.phone_number}
        save_users()
        bot.send_message(chat_id, f"Дякую, {message.contact.first_name}! Ви зареєстровані.\nТепер введіть ваш напій.")

@bot.message_handler(func=lambda message: (
    str(message.chat.id) in users and
    str(message.chat.id) not in orders and
    not message.text.startswith('/')
))
def get_drink(message):
    chat_id = str(message.chat.id)
    orders[chat_id] = {"drink": message.text}
    bot.send_message(chat_id, "Напишіть на котру годину бажаєте у форматі 00:00\n\nАбо виберіть із швидкодоступних на панелі знизу", reply_markup=time_keyboard())

def time_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    now = datetime.now()
    buttons = [
        types.KeyboardButton("Через 15 хв"),
        types.KeyboardButton("Через 30 хв"),
        types.KeyboardButton("На " + (now + timedelta(minutes=60)).strftime("%H:%M"))
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(func=lambda message: str(message.chat.id) in orders and "drink" in orders[str(message.chat.id)] and "time" not in orders[str(message.chat.id)])
def set_time(message):
    chat_id = str(message.chat.id)
    if "Через 15 хв" in message.text:
        order_time = (datetime.now() + timedelta(minutes=15)).strftime("%H:%M")
    elif "Через 30 хв" in message.text:
        order_time = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
    else:
        order_time = message.text.replace("На ", "")

    orders[chat_id]["time"] = order_time
    order_text = f"📝 {orders[chat_id]['drink']}\n🕒 Час: {order_time}"
    bot.send_message(chat_id, f"✅ Ваше замовлення: \n{order_text}\n\nВи можете його змінити, скасувати або підтвердити.\n\n⚠Після відправлення замовлення змінити його не вийде!⚠", 
                     reply_markup=confirm_order_keyboard())

def confirm_order_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("✏️ Редагувати"), types.KeyboardButton("❌ Скасувати"))
    markup.add(types.KeyboardButton("✅ Підтвердити"))
    return markup

@bot.message_handler(func=lambda message: message.text == "✅ Підтвердити")
def confirm_order(message):
    chat_id = str(message.chat.id)
    user_name = users[chat_id]["name"]
    user_phone = users[chat_id]["phone"]
    drink = orders[chat_id]["drink"]
    order_time = orders[chat_id]["time"]
    order_text = f"👤 {user_name} ({user_phone})\n📝 {drink}\n🕒 Час: {order_time}"

    accept_button = types.InlineKeyboardMarkup()
    accept_button.add(types.InlineKeyboardButton("✅ Прийняти замовлення", callback_data=f"accept_{chat_id}"))

    bot.send_message(ADMIN_ID, f"🔀 НОВЕ ЗАМОВЛЕННЯ\n{order_text}", reply_markup=accept_button)
    bot.send_message(chat_id, f"✅ Ваше замовлення надіслано баристі!\n{order_text}\n\n ⚠ Якщо бажаєте скасувати замовлення - зверніться до баристи @andrvsha.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_"))
def accept_order(call):
    chat_id = call.data.split("_")[1]
    if chat_id in orders:
        ready_button = types.InlineKeyboardMarkup()
        ready_button.add(types.InlineKeyboardButton("☕ Замовлення готове", callback_data=f"ready_{chat_id}"))

        bot.send_message(ADMIN_ID, f"✅ Замовлення користувача {users[chat_id]['name']} прийнято.", reply_markup=ready_button)
        bot.send_message(chat_id, "✅ Ваше замовлення прийнято баристою! Очікуйте приготування в зазначений час☕")
        bot.answer_callback_query(call.id, "Замовлення прийнято!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("ready_"))
def ready_order(call):
    chat_id = call.data.split("_")[1]
    if chat_id in orders:
        bot.send_message(chat_id, "☕ Ваше замовлення готове! Можете його забрати.")
        bot.send_message(ADMIN_ID, f"☕ Замовлення користувача {users[chat_id]['name']} готове.")
        del orders[chat_id]
        bot.answer_callback_query(call.id, "Повідомлення про готовність відправлено!")


# Додаємо функцію для отримання графіка роботи
def get_working_hours():
    return (
        "🕒 Графік роботи кав'ярні:\n"
        "Пн-Сб: 8:00 – 21:00\n"
        "Нд: 9:00 – 21:00"
    )

@bot.message_handler(commands=['notify'])
def notify_users(message):
    if str(message.chat.id) != str(ADMIN_ID):
        bot.send_message(message.chat.id, "⛔️ Доступ заборонено.")
        return
    text = "👋 Чи не бажаєте щось замовити сьогодні у нашій кав'ярні?"
    count = 0
    for user_id in users:
        try:
            bot.send_message(user_id, text)
            count += 1
        except Exception as e:
            pass  # Можна додати логування помилок, якщо потрібно
    bot.send_message(message.chat.id, f"✅ Повідомлення надіслано {count} користувачам.")


@bot.message_handler(commands=['hours', 'графік', 'часи'])
def send_working_hours(message):
    bot.send_message(message.chat.id, get_working_hours())

bot.polling(none_stop=True)