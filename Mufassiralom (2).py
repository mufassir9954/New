# -*- coding: utf-8 -*-
"""P2P FOUND EXCHANGE BOT"""

import telebot
from telebot import types
import json
import os
import random
import string
import requests
import threading
import time
import csv
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
	return datetime.now(IST)

BOT_TOKEN = "8610388673:AAHvsmrQvRozIVXQk-OPoM7kV59FNupLznY"
ADMIN_ID = 7276285414

BOT_NAME = "P2P FOUND EXCHANGE BOT"

DB_FILE = "database.json"
DB_LOCK = threading.Lock()

DEFAULT_SETTINGS = {
	"tax_percent": 2,
	"ultra_deposit_number": "2233556696",
	"upi_qr_image": "https://i.ibb.co/F4FtLVgW/IMG-20260619-145746.jpg",
	"ultra_api_token": "daT324jwv1sqWHvDHJxdr5wPdgQ65MmnxuD72leX",
	"ultra_api_key": "mZ4ABlka66XDtlF",
	"ultra_api_base_url": "https://ultra-pay.store/APIs/api",
	"support_username": "@GLPAY_AGENT",
	"force_channels": [
		{"name": "Channel 1", "username": "P2P_FUND_EXCHANGE_OFFICIAL", "url": "https://t.me/P2P_FUND_EXCHANGE_OFFICIAL"},
		{"name": "Channel 2", "username": "P2B_WALLET", "url": "https://t.me/P2B_WALLET"},
	],
	"log_channel": "@P2B_WALLET",
	"maintenance_mode": False,
	"min_deposit": 1,
	"max_deposit": 100000,
	"min_withdraw": 1,
	"max_withdraw": 100000,
	"support_message": "Send your message describing your issue. It will be forwarded to support.\nFor More Support Contact {support_username}",
	"pin_announcement": "",
	"big_action_threshold": 1000,
}

PERMISSIONS = {
	"dashboard": "📊 Dashboard",
	"user_mgmt": "👥 User Management",
	"payment_control": "💰 Payment Control",
	"channel_mgmt": "⚙️ Channel Management",
	"broadcast": "📢 Broadcast",
	"gift_control": "🎁 Gift Code Control",
	"payment_settings": "⚙️ Payment Settings",
	"reports": "📈 Reports",
	"maintenance": "🔧 Maintenance Mode",
	"limits": "💵 Min/Max Limits",
	"activity_log": "🗒️ Admin Activity Log",
	"backup": "💾 Auto Backup",
	"export": "📤 Export Data",
}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

def _blank_db():
	return {
		"users": {},
		"gift_codes": {},
		"pending": {},
		"settings": dict(DEFAULT_SETTINGS),
		"sub_admins": {},
		"activity_log": [],
		"broadcast_history": [],
		"scheduled_broadcasts": [],
	}

def load_db():
	if not os.path.exists(DB_FILE):
		return _blank_db()
	with open(DB_FILE, "r", encoding="utf-8") as f:
		try:
			db = json.load(f)
		except Exception:
			return _blank_db()

	changed = False
	for key, default_val in [("users", {}), ("gift_codes", {}), ("pending", {}),
                              ("settings", dict(DEFAULT_SETTINGS)), ("sub_admins", {}), ("activity_log", []),
                              ("broadcast_history", []), ("scheduled_broadcasts", [])]:
		if key not in db:
			db[key] = default_val
			changed = True
	for key, default_val in DEFAULT_SETTINGS.items():
		if key not in db["settings"]:
			db["settings"][key] = default_val
			changed = True
	if changed:
		with open(DB_FILE, "w", encoding="utf-8") as f:
			json.dump(db, f, indent=2, ensure_ascii=False)
	return db

def save_db(data):
	with open(DB_FILE, "w", encoding="utf-8") as f:
		json.dump(data, f, indent=2, ensure_ascii=False)

def get_setting(key):
	db = load_db()
	return db["settings"].get(key, DEFAULT_SETTINGS.get(key))

def set_setting(key, value):
	with DB_LOCK:
		db = load_db()
		db["settings"][key] = value
		save_db(db)

def log_admin_action(admin_id, action, details=""):
	with DB_LOCK:
		db = load_db()
		db["activity_log"].append({
			"admin_id": admin_id,
			"action": action,
			"details": details,
			"date": now_ist().strftime("%d-%m-%Y"),
			"time": now_ist().strftime("%I:%M %p"),
		})
		db["activity_log"] = db["activity_log"][-500:]  # keep last 500 entries
		save_db(db)

def get_admin_permissions(user_id):
	"""Returns list of permission keys the user has, or None if not an admin at all."""
	if user_id == ADMIN_ID:
		return list(PERMISSIONS.keys())
	db = load_db()
	sub = db["sub_admins"].get(str(user_id))
	if sub:
		return sub.get("permissions", [])
	return None

def is_any_admin(user_id):
	if user_id == ADMIN_ID:
		return True
	db = load_db()
	return str(user_id) in db["sub_admins"]

def get_user(user_id):
	with DB_LOCK:
		db = load_db()
		return db["users"].get(str(user_id))

def ensure_user(message_from):
	"""Create user record if not exists. Returns (user_dict, is_new)."""
	uid = str(message_from.id)
	with DB_LOCK:
		db = load_db()
		is_new = uid not in db["users"]
		if is_new:
			db["users"][uid] = {
				"name": message_from.first_name or "",
				"username": message_from.username or "N/A",
				"balance": 0.0,
				"upi_id": None,
				"ultra_pay": None,
				"banned": False,
				"joined_date": now_ist().strftime("%d-%m-%Y"),
				"joined_time": now_ist().strftime("%I:%M %p"),
				"transactions": [],
				"add_fund_history": [],
				"withdraw_history": [],
				"notes": [],
			}
			save_db(db)
		return db["users"][uid], is_new

def update_user(user_id, key, value):
	with DB_LOCK:
		db = load_db()
		uid = str(user_id)
		if uid not in db["users"]:
			return
		db["users"][uid][key] = value
		save_db(db)

def add_balance(user_id, amount):
	with DB_LOCK:
		db = load_db()
		uid = str(user_id)
		if uid not in db["users"]:
			return
		db["users"][uid]["balance"] = round(db["users"][uid]["balance"] + amount, 2)
		save_db(db)

def deduct_balance(user_id, amount):
	with DB_LOCK:
		db = load_db()
		uid = str(user_id)
		if uid not in db["users"]:
			return
		db["users"][uid]["balance"] = round(db["users"][uid]["balance"] - amount, 2)
		save_db(db)

def add_history(user_id, section, entry):
	"""section: transactions / add_fund_history / withdraw_history"""
	with DB_LOCK:
		db = load_db()
		uid = str(user_id)
		if uid not in db["users"]:
			return
		db["users"][uid][section].append(entry)
		save_db(db)

def update_history_status(user_id, section, entry_id, new_status, extra_fields=None):
	"""Find a history entry by its 'id' field and update its status (used for Pending -> Approved/Rejected)."""
	with DB_LOCK:
		db = load_db()
		uid = str(user_id)
		if uid not in db["users"]:
			return
		for entry in db["users"][uid][section]:
			if entry.get("id") == entry_id:
				entry["status"] = new_status
				if extra_fields:
					entry.update(extra_fields)
				break
		save_db(db)

def new_pending_id():
	with DB_LOCK:
		db = load_db()
		pid = str(len(db["pending"]) + 1) + "_" + str(random.randint(1000, 9999))
		return pid

def save_pending(pid, data):
	with DB_LOCK:
		db = load_db()
		db["pending"][pid] = data
		save_db(db)

def get_pending(pid):
	db = load_db()
	return db["pending"].get(pid)

def delete_pending(pid):
	with DB_LOCK:
		db = load_db()
		if pid in db["pending"]:
			del db["pending"][pid]
			save_db(db)

def save_gift_code(code, data):
	with DB_LOCK:
		db = load_db()
		db["gift_codes"][code] = data
		save_db(db)

def get_gift_code(code):
	db = load_db()
	return db["gift_codes"].get(code)

USER_STATE = {}  # user_id -> dict with temp data

def set_state(user_id, **kwargs):
	USER_STATE.setdefault(user_id, {})
	USER_STATE[user_id].update(kwargs)

def get_state(user_id):
	return USER_STATE.get(user_id, {})

def clear_state(user_id):
	USER_STATE.pop(user_id, None)

MENU_BUTTON_TEXTS = {
	"➕ ADD FUND",
	"👤 Account",
	"💵 Pay to User",
	"🎁 Gift Code",
	"🏦 Withdraw",
	"🔗 Link UPI/Wallet",
	"🎧 Support",
}

def is_menu_button(text):
	return text is not None and text.strip() in MENU_BUTTON_TEXTS

def redirect_to_menu(message):
	"""If the user clicked a menu button while a next_step_handler was pending,
	clear any pending state and let the normal menu handlers process it."""
	clear_state(message.from_user.id)
	bot.process_new_messages([message])

def is_blocked_for_call(call):
	"""For inline-button (callback) handlers: checks maintenance mode / ban.
	Sends an alert and returns True if the user should be blocked, admins are exempt."""
	uid = call.from_user.id
	if get_setting("maintenance_mode") and not is_any_admin(uid):
		bot.answer_callback_query(call.id, "🔧 Bot is currently under maintenance. Please wait, or contact admin for support.", show_alert=True)
		return True
	user = get_user(uid)
	if user and user.get("banned"):
		bot.answer_callback_query(call.id, "🚫 You have been banned from using this bot.", show_alert=True)
		return True
	return False

def is_user_joined(user_id):
	for ch in get_setting('force_channels'):
		try:
			member = bot.get_chat_member("@" + ch["username"], user_id)
			if member.status in ["left", "kicked"]:
				return False
		except Exception:
			return False
	return True

def send_join_message(chat_id):
	markup = types.InlineKeyboardMarkup()
	for ch in get_setting('force_channels'):
		markup.add(types.InlineKeyboardButton("Join Channel", url=ch["url"]))
	markup.add(types.InlineKeyboardButton("✅ Verify", callback_data="verify_join"))
	bot.send_message(
		chat_id,
		"Please join our channels to use the bot.",
		reply_markup=markup,
	)

def main_menu_keyboard():
	markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
	markup.add(types.KeyboardButton("➕ ADD FUND"))
	markup.add(types.KeyboardButton("👤 Account"), types.KeyboardButton("💵 Pay to User"))
	markup.add(types.KeyboardButton("🎁 Gift Code"), types.KeyboardButton("🏦 Withdraw"))
	markup.add(types.KeyboardButton("🔗 Link UPI/Wallet"), types.KeyboardButton("🎧 Support"))
	return markup

def send_welcome(chat_id):
	bot.send_message(
		chat_id,
		f"✦ <b>WELCOME TO {BOT_NAME}!</b> ✦",
		reply_markup=main_menu_keyboard(),
	)

@bot.message_handler(commands=["start"])
def handle_start(message):
	uid = message.from_user.id

	if get_setting("maintenance_mode") and not is_any_admin(uid):
		bot.send_message(message.chat.id, "🔧 Bot is currently under maintenance. Please wait, or contact admin for support.")
		return

	existing_user = get_user(uid)
	if existing_user and existing_user.get("banned"):
		bot.send_message(message.chat.id, "🚫 You have been banned from using this bot. Contact support for more info.")
		return

	user, is_new = ensure_user(message.from_user)

	if is_new:
		try:
			bot.send_message(
				ADMIN_ID,
				"🆕 <b>New User Started Bot</b>\n\n"
				f"👤 Name: {message.from_user.first_name or ''}\n"
				f"🆔 Username: @{message.from_user.username or 'N/A'}\n"
				f"🆔 User ID: <code>{message.from_user.id}</code>\n"
				f"📅 Date: {now_ist().strftime('%d-%m-%Y')}\n"
				f"⏰ Time: {now_ist().strftime('%I:%M %p')}",
			)
		except Exception as e:
			print("Admin notify error:", e)

	if not is_user_joined(message.from_user.id):
		send_join_message(message.chat.id)
		return

	send_welcome(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def handle_verify(call):
	if is_blocked_for_call(call):
		return
	if is_user_joined(call.from_user.id):
		bot.answer_callback_query(call.id, "Verified!")
		bot.delete_message(call.message.chat.id, call.message.message_id)
		send_welcome(call.message.chat.id)
	else:
		bot.answer_callback_query(call.id, "Please join the channel(s) first.", show_alert=True)

def require_join(func):
	"""Decorator: block action if user hasn't joined force channels, is banned, or bot is under maintenance."""
	def wrapper(message_or_call):
		uid = message_or_call.from_user.id
		chat_id = message_or_call.message.chat.id if hasattr(message_or_call, "message") else message_or_call.chat.id
		if get_setting("maintenance_mode") and not is_any_admin(uid):
			bot.send_message(chat_id, "🔧 Bot is currently under maintenance. Please try again later.")
			return
		user = get_user(uid)
		if user and user.get("banned"):
			bot.send_message(chat_id, "🚫 You have been banned from using this bot. Contact support for more info.")
			return
		if not is_user_joined(uid):
			send_join_message(chat_id)
			return
		return func(message_or_call)
	return wrapper

@bot.message_handler(func=lambda m: m.text == "➕ ADD FUND")
@require_join
def add_fund_start(message):
	markup = types.InlineKeyboardMarkup()
	markup.add(
		types.InlineKeyboardButton("Ultra Pay", callback_data="addfund_ultra"),
		types.InlineKeyboardButton("UPI", callback_data="addfund_upi"),
	)
	bot.send_message(message.chat.id, "Select a method to add fund:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["addfund_ultra", "addfund_upi"])
def add_fund_method(call):
	if is_blocked_for_call(call):
		return
	method = "ultra" if call.data == "addfund_ultra" else "upi"
	set_state(call.from_user.id, flow="add_fund", method=method)
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, f"Enter amount to deposit (Note: {get_setting('tax_percent')}% tax applicable):")
	bot.register_next_step_handler(msg, add_fund_amount_step)

def add_fund_amount_step(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	state = get_state(message.from_user.id)
	if state.get("flow") != "add_fund":
		return
	try:
		amount = float(message.text.strip())
		if amount <= 0:
			raise ValueError
	except ValueError:
		msg = bot.send_message(message.chat.id, "Invalid amount. Enter a valid number:")
		bot.register_next_step_handler(msg, add_fund_amount_step)
		return

	min_dep = get_setting("min_deposit")
	max_dep = get_setting("max_deposit")
	if amount < min_dep or amount > max_dep:
		msg = bot.send_message(message.chat.id, f"Amount must be between ₹{min_dep} and ₹{max_dep}. Enter a valid amount:")
		bot.register_next_step_handler(msg, add_fund_amount_step)
		return

	tax = round(amount * get_setting('tax_percent') / 100, 2)
	final_amount = round(amount - tax, 2)
	set_state(message.from_user.id, amount=amount, tax=tax, final_amount=final_amount)

	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="addfund_cancel"))

	if state.get("method") == "ultra":
		bot.send_message(
			message.chat.id,
			f"Send ₹{amount} to this number:\n<code>{get_setting('ultra_deposit_number')}</code>\n\nSend the screenshot of payment below:",
			reply_markup=markup,
		)
	else:
		bot.send_photo(
			message.chat.id,
			get_setting('upi_qr_image'),
			caption=f"Send ₹{amount} to this QR.\n\nSend screenshot below:",
			reply_markup=markup,
		)
	set_state(message.from_user.id, awaiting_screenshot=True)

@bot.callback_query_handler(func=lambda call: call.data == "addfund_cancel")
def add_fund_cancel(call):
	if is_blocked_for_call(call):
		return
	clear_state(call.from_user.id)
	bot.answer_callback_query(call.id, "Cancelled")
	bot.send_message(call.message.chat.id, "❌ Add fund cancelled.", reply_markup=main_menu_keyboard())

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
	state = get_state(message.from_user.id)

	if state.get("flow") == "add_fund" and state.get("awaiting_screenshot"):
		handle_add_fund_screenshot(message, state)
		return

	return

def handle_add_fund_screenshot(message, state):
	uid = message.from_user.id
	user = get_user(uid)
	amount = state["amount"]
	tax = state["tax"]
	final_amount = state["final_amount"]
	method = state["method"]
	file_id = message.photo[-1].file_id

	pid = new_pending_id()
	date_str = now_ist().strftime("%d-%m-%Y")
	time_str = now_ist().strftime("%I:%M %p")
	save_pending(pid, {
		"type": "deposit",
		"method": method,
		"user_id": uid,
		"amount": amount,
		"tax": tax,
		"final_amount": final_amount,
		"date": date_str,
		"time": time_str,
		"file_id": file_id,
	})

	add_history(uid, "add_fund_history", {
		"id": pid,
		"amount": amount,
		"tax": tax,
		"final_amount": final_amount,
		"method": method,
		"date": date_str,
		"time": time_str,
		"status": "Pending",
	})

	markup = types.InlineKeyboardMarkup()
	markup.add(
		types.InlineKeyboardButton("✅ Approved", callback_data=f"dep_approve_{pid}"),
		types.InlineKeyboardButton("❌ Rejected", callback_data=f"dep_reject_{pid}"),
	)

	caption = (
		"🔔 <b>New Deposit Request</b>\n\n"
		f"👤 Name: {user['name']}\n"
		f"🆔 Username: @{user['username']}\n"
		f"🆔 User ID: <code>{uid}</code>\n"
		f"📅 Date: {now_ist().strftime('%d-%m-%Y')}\n"
		f"⏰ Time: {now_ist().strftime('%I:%M %p')}\n\n"
		f"💰 Amount: ₹{amount}\n"
		f"📉 Tax ({get_setting('tax_percent')}%): ₹{tax}\n"
		f"✅ Final Amount: ₹{final_amount}\n"
		f"💳 Method: {method.upper()}"
	)

	try:
		bot.send_photo(get_setting('log_channel'), file_id, caption=caption, reply_markup=markup)
	except Exception as e:
		print("Error sending to log channel:", e)

	bot.send_message(message.chat.id, "✅ Successful! Your request has been sent to admin for approval.", reply_markup=main_menu_keyboard())
	clear_state(uid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dep_approve_") or call.data.startswith("dep_reject_"))
def deposit_admin_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "payment_control" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return

	approve = call.data.startswith("dep_approve_")
	pid = call.data.split("_", 2)[2]
	pending = get_pending(pid)

	if not pending:
		bot.answer_callback_query(call.id, "Request already processed.", show_alert=True)
		return

	uid = pending["user_id"]

	if approve:
		add_balance(uid, pending["final_amount"])
		update_history_status(uid, "add_fund_history", pid, "Approved")
		log_admin_action(call.from_user.id, "Approved Deposit", f"User {uid}, ₹{pending['amount']}")
		try:
			bot.send_message(uid, f"✅ Your deposit request of ₹{pending['amount']} has been approved!\nBalance added: ₹{pending['final_amount']}")
		except Exception:
			pass
		bot.answer_callback_query(call.id, "Approved")
	else:
		update_history_status(uid, "add_fund_history", pid, "Rejected")
		log_admin_action(call.from_user.id, "Rejected Deposit", f"User {uid}, ₹{pending['amount']}")
		try:
			bot.send_message(uid, "❌ Your deposit request has been rejected.")
		except Exception:
			pass
		bot.answer_callback_query(call.id, "Rejected")

	delete_pending(pid)
	try:
		bot.edit_message_caption(
			chat_id=call.message.chat.id,
			message_id=call.message.message_id,
			caption=call.message.caption + f"\n\n{'✅ APPROVED' if approve else '❌ REJECTED'}",
		)
	except Exception:
		pass

@bot.message_handler(func=lambda m: m.text == "👤 Account")
@require_join
def account_menu(message):
	user, _ = ensure_user(message.from_user)
	upi = user.get("upi_id") or "Not Set"
	ultra = user.get("ultra_pay") or "Not Set"

	announcement = get_setting("pin_announcement")
	prefix = f"📌 <b>{announcement}</b>\n\n" if announcement else ""

	text = (
		prefix +
		f"🆔 <b>USER ID:</b> <code>{message.from_user.id}</code>\n\n"
		f"💰 <b>BALANCE:</b> ₹{user['balance']}\n\n"
		f"🏛️ <b>UPI ID:</b> {upi}\n\n"
		f"💳 <b>ULTRA PAY:</b> {ultra}"
	)
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("Transaction History", callback_data="hist_transactions"))
	markup.add(types.InlineKeyboardButton("Add Fund History", callback_data="hist_add_fund_history"))
	markup.add(types.InlineKeyboardButton("Withdrawal History", callback_data="hist_withdraw_history"))
	bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("hist_"))
def history_menu(call):
	if is_blocked_for_call(call):
		return
	section = call.data.replace("hist_", "")
	markup = types.InlineKeyboardMarkup()
	markup.add(
		types.InlineKeyboardButton("5", callback_data=f"showhist_{section}_5"),
		types.InlineKeyboardButton("10", callback_data=f"showhist_{section}_10"),
		types.InlineKeyboardButton("20", callback_data=f"showhist_{section}_20"),
	)
	markup.add(types.InlineKeyboardButton("ALL", callback_data=f"showhist_{section}_all"))
	bot.answer_callback_query(call.id)
	bot.send_message(call.message.chat.id, "Select how many records to view:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("showhist_"))
def show_history(call):
	if is_blocked_for_call(call):
		return
	rest = call.data[len("showhist_"):]
	section, count = rest.rsplit("_", 1)
	user = get_user(call.from_user.id)
	records = user.get(section, [])

	bot.answer_callback_query(call.id)

	if not records:
		bot.send_message(call.message.chat.id, "No history found.")
		return

	if count != "all":
		records = records[-int(count):]

	lines = []
	for r in reversed(records):
		if section == "transactions":
			lines.append(f"➡️ {r}")
		elif section == "add_fund_history":
			lines.append(
				f"💰 ₹{r['amount']} | Tax: ₹{r['tax']} | Final: ₹{r['final_amount']} | "
				f"{r['method'].upper()} | {r['status']} | {r['date']} {r['time']}"
			)
		elif section == "withdraw_history":
			lines.append(
				f"🏦 ₹{r['amount']} | Tax: ₹{r['tax']} | Final: ₹{r['final_amount']} | "
				f"{r['method'].upper()} | {r['status']} | {r['date']} {r['time']}"
			)

	text = "\n\n".join(lines)
	bot.send_message(call.message.chat.id, text[:4000])

@bot.message_handler(func=lambda m: m.text == "💵 Pay to User")
@require_join
def pay_to_user_start(message):
	text = (
		"Send transfer details.\n"
		"Format 1: UserID:Amount\n"
		"Format 2: ID1,ID2:Amount\n"
		"Format 3:\n"
		"ID1:Amount\n"
		"ID2:Amount"
	)
	msg = bot.send_message(message.chat.id, text)
	bot.register_next_step_handler(msg, pay_to_user_process)

def _split_id_amount(line):
	"""Split a single line into (ids_part, amount_str), accepting ':' or space as separator."""
	line = line.strip()
	if ":" in line:
		left, right = line.rsplit(":", 1)
		return left.strip(), right.strip()
	parts = line.split()
	if len(parts) < 2:
		raise ValueError("Not enough parts")
	amount_str = parts[-1]
	ids_part = " ".join(parts[:-1])
	return ids_part.strip(), amount_str.strip()

def parse_pay_input(text):
	"""Returns list of (user_id, amount) tuples, or None if invalid format.
	Accepts ':' or space as the separator between ID(s) and amount, e.g.:
      7610388580:20   OR   7610388580 20
      ID1,ID2:20       OR  ID1,ID2 20
      ID1:20 / ID1 20  (one per line)
	"""
	text = text.strip()
	results = []
	try:
		lines = [l for l in text.split("\n") if l.strip()]
		if len(lines) > 1:
			for line in lines:
				uid, amt = _split_id_amount(line)
				results.append((uid.strip(), float(amt)))
		else:
			single_line = lines[0]
			ids_part, amt = _split_id_amount(single_line)
			amt = float(amt)
			if "," in ids_part:
				for uid in ids_part.split(","):
					results.append((uid.strip(), amt))
			else:
				results.append((ids_part.strip(), amt))
	except Exception:
		return None

	if not results:
		return None
	return results

def pay_to_user_process(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	parsed = parse_pay_input(message.text)
	if not parsed:
		bot.send_message(message.chat.id, "Invalid format. Please try again from the Pay to User menu.", reply_markup=main_menu_keyboard())
		return

	sender_id = message.from_user.id
	sender = get_user(sender_id)
	total_needed = sum(amt for _, amt in parsed)

	if sender["balance"] < total_needed:
		bot.send_message(message.chat.id, "Insufficient balance.", reply_markup=main_menu_keyboard())
		return

	for uid, amt in parsed:
		if not uid.isdigit():
			bot.send_message(message.chat.id, f"Invalid User ID: {uid}", reply_markup=main_menu_keyboard())
			return
		if not get_user(uid):
			bot.send_message(message.chat.id, f"User {uid} not found (they must have started the bot).", reply_markup=main_menu_keyboard())
			return
		if int(uid) == sender_id:
			bot.send_message(message.chat.id, "You cannot pay yourself.", reply_markup=main_menu_keyboard())
			return

	deduct_balance(sender_id, total_needed)
	failed_notify = []
	for uid, amt in parsed:
		add_balance(uid, amt)
		add_history(uid, "transactions", f"Received ₹{amt} from {sender_id} on {now_ist().strftime('%d-%m-%Y %I:%M %p')}")
		try:
			bot.send_message(int(uid), f"💵 You received ₹{amt} from user {sender_id}.")
		except Exception as e:
			print(f"Failed to notify user {uid}: {e}")
			failed_notify.append(uid)

	add_history(sender_id, "transactions", f"Sent ₹{total_needed} to {', '.join(u for u,_ in parsed)} on {now_ist().strftime('%d-%m-%Y %I:%M %p')}")

	result_text = f"✅ Successfully sent ₹{total_needed}."
	if failed_notify:
		result_text += f"\n\n⚠️ Note: could not notify user(s) {', '.join(failed_notify)} (they may have blocked the bot), but the transfer was completed."
	bot.send_message(message.chat.id, result_text, reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "🎁 Gift Code")
@require_join
def gift_code_menu(message):
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("Create a Code", callback_data="gift_create"))
	markup.add(types.InlineKeyboardButton("Claim Code", callback_data="gift_claim"))
	bot.send_message(message.chat.id, "Gift Code Menu:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "gift_create")
def gift_create_start(call):
	if is_blocked_for_call(call):
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Enter amount for the gift code:")
	bot.register_next_step_handler(msg, gift_create_amount)

def gift_create_amount(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	try:
		amount = float(message.text.strip())
		if amount <= 0:
			raise ValueError
	except ValueError:
		msg = bot.send_message(message.chat.id, "Invalid amount. Enter a valid number:")
		bot.register_next_step_handler(msg, gift_create_amount)
		return

	set_state(message.from_user.id, gift_amount=amount)
	msg = bot.send_message(message.chat.id, "Enter number of users who can claim this code:")
	bot.register_next_step_handler(msg, gift_create_users)

def gift_create_users(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	try:
		num_users = int(message.text.strip())
		if num_users <= 0:
			raise ValueError
	except ValueError:
		msg = bot.send_message(message.chat.id, "Invalid number. Enter a valid whole number:")
		bot.register_next_step_handler(msg, gift_create_users)
		return

	state = get_state(message.from_user.id)
	amount = state["gift_amount"]
	total_cost = round(amount * num_users, 2)

	user = get_user(message.from_user.id)
	if user["balance"] < total_cost:
		bot.send_message(message.chat.id, "Insufficient balance.", reply_markup=main_menu_keyboard())
		clear_state(message.from_user.id)
		return

	deduct_balance(message.from_user.id, total_cost)
	code = "".join(random.choices(string.ascii_letters, k=12))

	save_gift_code(code, {
		"amount": amount,
		"max_claims": num_users,
		"claimed_by": [],
		"creator": message.from_user.id,
		"created_date": now_ist().strftime("%d-%m-%Y %I:%M %p"),
	})

	add_history(message.from_user.id, "transactions", f"Created gift code {code} (₹{amount} x {num_users}) on {now_ist().strftime('%d-%m-%Y %I:%M %p')}")

	bot.send_message(
		message.chat.id,
		f"✅ Gift code created successfully!\n\n🎁 Code: <code>{code}</code>\n💰 Amount per claim: ₹{amount}\n👥 Max claims: {num_users}",
		reply_markup=main_menu_keyboard(),
	)
	clear_state(message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "gift_claim")
def gift_claim_start(call):
	if is_blocked_for_call(call):
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Send the 12-letter code:")
	bot.register_next_step_handler(msg, gift_claim_process)

def gift_claim_process(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	code = message.text.strip()
	data = get_gift_code(code)

	if not data:
		bot.send_message(message.chat.id, "❌ Invalid or expired code.", reply_markup=main_menu_keyboard())
		return

	if len(data["claimed_by"]) >= data["max_claims"]:
		bot.send_message(message.chat.id, "❌ Invalid or expired code.", reply_markup=main_menu_keyboard())
		return

	if message.from_user.id in data["claimed_by"]:
		bot.send_message(message.chat.id, "❌ You have already claimed this code.", reply_markup=main_menu_keyboard())
		return

	data["claimed_by"].append(message.from_user.id)
	save_gift_code(code, data)

	add_balance(message.from_user.id, data["amount"])
	add_history(message.from_user.id, "transactions", f"Claimed gift code {code} (+₹{data['amount']}) on {now_ist().strftime('%d-%m-%Y %I:%M %p')}")

	bot.send_message(
		message.chat.id,
		f"✅ Code claimed successfully! ₹{data['amount']} added to your balance.",
		reply_markup=main_menu_keyboard(),
	)

@bot.message_handler(func=lambda m: m.text == "🏦 Withdraw")
@require_join
def withdraw_start(message):
	markup = types.InlineKeyboardMarkup()
	markup.add(
		types.InlineKeyboardButton("Ultra Pay", callback_data="wd_ultra"),
		types.InlineKeyboardButton("UPI", callback_data="wd_upi"),
	)
	bot.send_message(message.chat.id, "Select withdrawal method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["wd_ultra", "wd_upi"])
def withdraw_method(call):
	if is_blocked_for_call(call):
		return
	method = "ultra" if call.data == "wd_ultra" else "upi"
	set_state(call.from_user.id, flow="withdraw", method=method)
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, f"Enter amount to withdraw (Note: {get_setting('tax_percent')}% tax applicable):")
	bot.register_next_step_handler(msg, withdraw_amount_step)

def withdraw_amount_step(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	state = get_state(message.from_user.id)
	if state.get("flow") != "withdraw":
		return
	try:
		amount = float(message.text.strip())
		if amount <= 0:
			raise ValueError
	except ValueError:
		msg = bot.send_message(message.chat.id, "Invalid amount. Enter a valid number:")
		bot.register_next_step_handler(msg, withdraw_amount_step)
		return

	min_wd = get_setting("min_withdraw")
	max_wd = get_setting("max_withdraw")
	if amount < min_wd or amount > max_wd:
		msg = bot.send_message(message.chat.id, f"Amount must be between ₹{min_wd} and ₹{max_wd}. Enter a valid amount:")
		bot.register_next_step_handler(msg, withdraw_amount_step)
		return

	user = get_user(message.from_user.id)
	if user["balance"] < amount:
		bot.send_message(message.chat.id, "Insufficient balance.", reply_markup=main_menu_keyboard())
		clear_state(message.from_user.id)
		return

	tax = round(amount * get_setting('tax_percent') / 100, 2)
	final_amount = round(amount - tax, 2)
	set_state(message.from_user.id, amount=amount, tax=tax, final_amount=final_amount)

	if state["method"] == "upi":
		upi_id = user.get("upi_id")
		if upi_id:
			set_state(message.from_user.id, number=upi_id)
			show_withdraw_confirmation(message.chat.id, message.from_user.id)
		else:
			bot.send_message(
				message.chat.id,
				"⚠️ You haven't linked a UPI ID yet. Please set it first from 🔗 Link UPI/Wallet, then try withdrawing again.",
				reply_markup=main_menu_keyboard(),
			)
			clear_state(message.from_user.id)
	else:
		ultra_number = user.get("ultra_pay")
		if ultra_number:
			set_state(message.from_user.id, number=ultra_number)
			show_withdraw_confirmation(message.chat.id, message.from_user.id)
		else:
			msg = bot.send_message(message.chat.id, "Enter your Ultra Pay number (10 digits):")
			bot.register_next_step_handler(msg, withdraw_number_step)

def show_withdraw_confirmation(chat_id, user_id):
	state = get_state(user_id)
	text = (
		f"Number: {state['number']}\n"
		f"Amount: ₹{state['amount']}\n"
		f"Tax ({get_setting('tax_percent')}%): ₹{state['tax']}\n"
		f"Final Amount: ₹{state['final_amount']}"
	)
	markup = types.InlineKeyboardMarkup()
	markup.add(
		types.InlineKeyboardButton("Process", callback_data="wd_process"),
		types.InlineKeyboardButton("Cancel", callback_data="wd_cancel"),
	)
	bot.send_message(chat_id, text, reply_markup=markup)

def withdraw_number_step(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	number = message.text.strip()
	if not (number.isdigit() and len(number) == 10):
		msg = bot.send_message(message.chat.id, "Invalid number. Please enter a valid 10-digit Ultra Pay number:")
		bot.register_next_step_handler(msg, withdraw_number_step)
		return
	set_state(message.from_user.id, number=number)
	show_withdraw_confirmation(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "wd_cancel")
def withdraw_cancel(call):
	if is_blocked_for_call(call):
		return
	clear_state(call.from_user.id)
	bot.answer_callback_query(call.id, "Cancelled")
	bot.send_message(call.message.chat.id, "❌ Withdrawal cancelled.", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "wd_process")
def withdraw_process(call):
	if is_blocked_for_call(call):
		return
	state = get_state(call.from_user.id)
	if not state or state.get("flow") != "withdraw":
		bot.answer_callback_query(call.id, "Session expired. Please start again.", show_alert=True)
		return

	uid = call.from_user.id
	user = get_user(uid)
	amount = state["amount"]
	tax = state["tax"]
	final_amount = state["final_amount"]
	number = state["number"]
	method = state["method"]

	if user["balance"] < amount:
		bot.answer_callback_query(call.id, "Insufficient balance.", show_alert=True)
		clear_state(uid)
		return

	bot.answer_callback_query(call.id)
	deduct_balance(uid, amount)

	if method == "ultra":
		success = False
		txn_id = None
		fail_reason = ""
		try:
			resp = requests.get(
				get_setting('ultra_api_base_url'),
				params={
					"token": get_setting('ultra_api_token'),
					"key": get_setting('ultra_api_key'),
					"paytoNumber": number,
					"amount": final_amount,
					"comment": "Withdraw",
				},
				timeout=15,
			)
			data = resp.json()
			if data.get("status") == "success":
				success = True
				txn_id = data.get("transaction_id")
			else:
				fail_reason = data.get("message", "Unknown error")
		except Exception as e:
			fail_reason = str(e)
			print("Ultra API error:", e)

		status = "Approved" if success else "Failed"
		add_history(uid, "withdraw_history", {
			"amount": amount, "tax": tax, "final_amount": final_amount,
			"method": "ultra", "date": now_ist().strftime("%d-%m-%Y"),
			"time": now_ist().strftime("%I:%M %p"), "status": status,
		})

		if success:
			bot.send_message(
				call.message.chat.id,
				f"✅ Withdrawal successful! ₹{final_amount} sent to {number}.\nTXN ID: {txn_id}",
				reply_markup=main_menu_keyboard(),
			)
			try:
				bot.send_message(
					get_setting('log_channel'),
					"🏦 <b>New Ultra Withdraw Request</b>\n\n"
					f"👤 Name: {user['name']}\n"
					f"🆔 Username: @{user['username']}\n"
					f"🆔 User ID: <code>{uid}</code>\n"
					f"📱 Number: <code>{number}</code>\n"
					f"💰 Amount: ₹{amount}\n"
					f"📉 Tax: ₹{tax}\n"
					f"✅ Final Amount: ₹{final_amount}\n"
					f"⚙️ Method: Ultra Pay (Auto via API)\n"
					f"🧾 TXN ID: {txn_id}\n"
					f"✅ Status: Success",
				)
			except Exception:
				pass
		else:
			add_balance(uid, amount)
			bot.send_message(
				call.message.chat.id,
				f"❌ Withdrawal failed ({fail_reason}). Amount refunded to your balance. Please try again or contact support.",
				reply_markup=main_menu_keyboard(),
			)
			try:
				bot.send_message(
					get_setting('log_channel'),
					"⚠️ <b>Ultra Withdraw Failed</b>\n\n"
					f"👤 Name: {user['name']}\n"
					f"🆔 Username: @{user['username']}\n"
					f"🆔 User ID: <code>{uid}</code>\n"
					f"📱 Number: <code>{number}</code>\n"
					f"💰 Amount: ₹{amount}\n"
					f"❌ Reason: {fail_reason}",
				)
			except Exception:
				pass

	else:
		pid = new_pending_id()
		date_str = now_ist().strftime("%d-%m-%Y")
		time_str = now_ist().strftime("%I:%M %p")
		save_pending(pid, {
			"type": "withdraw", "method": "upi", "user_id": uid,
			"amount": amount, "tax": tax, "final_amount": final_amount,
			"number": number,
			"date": date_str,
			"time": time_str,
		})

		add_history(uid, "withdraw_history", {
			"id": pid,
			"amount": amount, "tax": tax, "final_amount": final_amount,
			"method": "upi", "date": date_str, "time": time_str, "status": "Pending",
		})

		markup = types.InlineKeyboardMarkup()
		markup.add(
			types.InlineKeyboardButton("✅ Approved", callback_data=f"wdupi_approve_{pid}"),
			types.InlineKeyboardButton("❌ Rejected", callback_data=f"wdupi_reject_{pid}"),
		)
		try:
			bot.send_message(
				get_setting('log_channel'),
				"🏦 <b>New UPI Withdraw Request</b>\n\n"
				f"👤 Name: {user['name']}\n"
				f"🆔 Username: @{user['username']}\n"
				f"🆔 User ID: <code>{uid}</code>\n"
				f"📱 UPI: <code>{number}</code>\n"
				f"💰 Amount: ₹{amount}\n"
				f"📉 Tax: ₹{tax}\n"
				f"✅ Final Amount: ₹{final_amount}",
				reply_markup=markup,
			)
		except Exception:
			pass
		bot.send_message(call.message.chat.id, "✅ Your withdrawal request has been sent to admin for approval.", reply_markup=main_menu_keyboard())

	clear_state(uid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wdupi_approve_") or call.data.startswith("wdupi_reject_"))
def withdraw_upi_admin_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "payment_control" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return

	approve = call.data.startswith("wdupi_approve_")
	pid = call.data.split("_", 2)[2]
	pending = get_pending(pid)

	if not pending:
		bot.answer_callback_query(call.id, "Request already processed.", show_alert=True)
		return

	uid = pending["user_id"]

	if approve:
		update_history_status(uid, "withdraw_history", pid, "Approved")
		log_admin_action(call.from_user.id, "Approved UPI Withdraw", f"User {uid}, ₹{pending['amount']}")
		try:
			bot.send_message(uid, f"✅ Your withdrawal of ₹{pending['final_amount']} has been approved and processed.")
		except Exception:
			pass
		bot.answer_callback_query(call.id, "Approved")
	else:
		add_balance(uid, pending["amount"])  # refund
		update_history_status(uid, "withdraw_history", pid, "Rejected")
		log_admin_action(call.from_user.id, "Rejected UPI Withdraw", f"User {uid}, ₹{pending['amount']}")
		try:
			bot.send_message(uid, "❌ Your withdrawal request has been rejected. Amount refunded to your balance.")
		except Exception:
			pass
		bot.answer_callback_query(call.id, "Rejected")

	delete_pending(pid)
	try:
		bot.edit_message_text(
			chat_id=call.message.chat.id,
			message_id=call.message.message_id,
			text=call.message.text + f"\n\n{'✅ APPROVED' if approve else '❌ REJECTED'}",
		)
	except Exception:
		pass

@bot.message_handler(func=lambda m: m.text == "🔗 Link UPI/Wallet")
@require_join
def link_menu(message):
	user, _ = ensure_user(message.from_user)
	text = f"Current Wallet: {user.get('ultra_pay') or 'None'}\nCurrent UPI: {user.get('upi_id') or 'None'}"
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("Set Wallet Number", callback_data="link_wallet"))
	markup.add(types.InlineKeyboardButton("Set UPI ID", callback_data="link_upi"))
	bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "link_wallet")
def link_wallet_start(call):
	if is_blocked_for_call(call):
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Send your new wallet:")
	bot.register_next_step_handler(msg, link_wallet_save)

def link_wallet_save(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	number = message.text.strip()
	if not (number.isdigit() and len(number) == 10):
		msg = bot.send_message(message.chat.id, "Invalid number. Please enter a valid 10-digit wallet number:")
		bot.register_next_step_handler(msg, link_wallet_save)
		return
	update_user(message.from_user.id, "ultra_pay", number)
	bot.send_message(message.chat.id, "Successfully linked wallet!", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "link_upi")
def link_upi_start(call):
	if is_blocked_for_call(call):
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Send your new UPI ID:")
	bot.register_next_step_handler(msg, link_upi_save)

def link_upi_save(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	update_user(message.from_user.id, "upi_id", message.text.strip())
	bot.send_message(message.chat.id, "Successfully linked UPI!", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "🎧 Support")
@require_join
def support_start(message):
	template = get_setting("support_message")
	try:
		text = template.format(support_username=get_setting("support_username"))
	except Exception:
		text = template
	msg = bot.send_message(message.chat.id, text)
	bot.register_next_step_handler(msg, support_forward)

def support_forward(message):
	if is_menu_button(message.text):
		redirect_to_menu(message)
		return
	user = get_user(message.from_user.id)
	try:
		bot.send_message(
			get_setting('log_channel'),
			"🎧 <b>New Support Message</b>\n\n"
			f"👤 Name: {user['name']}\n"
			f"🆔 Username: @{user['username']}\n"
			f"🆔 User ID: <code>{message.from_user.id}</code>\n\n"
			f"💬 Message:\n{message.text}",
		)
	except Exception:
		pass
	bot.send_message(message.chat.id, "✅ Your message has been sent to support.", reply_markup=main_menu_keyboard())

@bot.message_handler(
	content_types=["text", "document", "sticker", "video", "audio", "voice", "animation", "video_note", "location", "contact"],
	func=lambda m: get_state(m.from_user.id).get("awaiting_screenshot") and not is_menu_button(getattr(m, "text", None)),
)
def reject_non_screenshot(message):
	try:
		bot.delete_message(message.chat.id, message.message_id)
	except Exception:
		pass
	bot.send_message(message.chat.id, "⚠️ Please send only the screenshot (photo) of your payment.")

def admin_back_button():
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="adm_dashboard"))
	return markup

def ask_confirmation(chat_id, admin_uid, action_key, description):
	"""Two-factor confirmation for sensitive/big admin actions.
	The caller must set_state(admin_uid, ...) with any data the action needs BEFORE calling this."""
	set_state(admin_uid, pending_confirm_action=action_key)
	markup = types.InlineKeyboardMarkup()
	markup.add(
		types.InlineKeyboardButton("✅ Confirm", callback_data="confirm_yes"),
		types.InlineKeyboardButton("❌ Cancel", callback_data="confirm_no"),
	)
	bot.send_message(chat_id, f"⚠️ {description}\n\nAre you sure?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_yes", "confirm_no"])
def confirm_action_handler(call):
	uid = call.from_user.id
	state = get_state(uid)
	action = state.get("pending_confirm_action")

	if call.data == "confirm_no" or not action:
		bot.answer_callback_query(call.id, "Cancelled")
		bot.send_message(call.message.chat.id, "❌ Action cancelled.")
		set_state(uid, pending_confirm_action=None)
		return

	bot.answer_callback_query(call.id, "Confirmed")
	perms = get_admin_permissions(uid)

	if action == "ban_user":
		if perms is None or "user_mgmt" not in perms:
			bot.send_message(call.message.chat.id, "Not authorized.")
			return
		target_id = state["confirm_target"]
		update_user(target_id, "banned", True)
		log_admin_action(uid, "Banned User", f"User {target_id}")
		bot.send_message(call.message.chat.id, "🚫 User banned.")

	elif action == "remove_subadmin":
		if uid != ADMIN_ID:
			bot.send_message(call.message.chat.id, "Not authorized.")
			return
		target_id = state["confirm_target"]
		with DB_LOCK:
			db = load_db()
			found = target_id in db["sub_admins"]
			if found:
				del db["sub_admins"][target_id]
				save_db(db)
		if found:
			log_admin_action(uid, "Removed Sub-Admin", target_id)
			bot.send_message(call.message.chat.id, f"✅ Sub-admin {target_id} removed.")
		else:
			bot.send_message(call.message.chat.id, "Sub-admin not found.")

	elif action == "big_balance":
		if perms is None or "user_mgmt" not in perms:
			bot.send_message(call.message.chat.id, "Not authorized.")
			return
		target_id = state["confirm_target"]
		amount = state["confirm_amount"]
		is_add = state["confirm_is_add"]
		if is_add:
			add_balance(target_id, amount)
			log_admin_action(uid, "Added Balance", f"User {target_id}, +₹{amount}")
			bot.send_message(call.message.chat.id, f"✅ ₹{amount} added to user {target_id}.")
			try:
				bot.send_message(int(target_id), f"💰 ₹{amount} has been added to your balance by admin.")
			except Exception:
				pass
		else:
			deduct_balance(target_id, amount)
			log_admin_action(uid, "Deducted Balance", f"User {target_id}, -₹{amount}")
			bot.send_message(call.message.chat.id, f"✅ ₹{amount} deducted from user {target_id}.")
			try:
				bot.send_message(int(target_id), f"⚠️ ₹{amount} has been deducted from your balance by admin.")
			except Exception:
				pass

	elif action == "broadcast_all":
		if perms is None or "broadcast" not in perms:
			bot.send_message(call.message.chat.id, "Not authorized.")
			return
		execute_broadcast(call.message.chat.id, uid, target="all")

	set_state(uid, pending_confirm_action=None)

@bot.message_handler(commands=["adminpanel"])
def admin_panel_cmd(message):
	uid = message.from_user.id
	perms = get_admin_permissions(uid)
	if perms is None:
		bot.send_message(message.chat.id, "❌ You are not admin.")
		try:
			bot.send_message(
				ADMIN_ID,
				"⚠️ <b>Unauthorized /adminpanel Attempt</b>\n\n"
				f"👤 Name: {message.from_user.first_name or ''}\n"
				f"🆔 Username: @{message.from_user.username or 'N/A'}\n"
				f"🆔 User ID: <code>{uid}</code>",
			)
		except Exception:
			pass
		return
	show_admin_panel(message.chat.id, uid, perms)

def show_admin_panel(chat_id, uid, perms):
	db = load_db()
	total_users = len(db["users"])
	total_balance = round(sum(u.get("balance", 0) for u in db["users"].values()), 2)
	pending_count = len(db["pending"])
	maintenance = get_setting("maintenance_mode")

	text = (
		"╔══════════════════════════╗\n"
		f"║  💎 {BOT_NAME}\n"
		"║      ADMIN DASHBOARD\n"
		"╚══════════════════════════╝\n\n"
		"👋 Welcome, Admin\n"
		f"🕐 {now_ist().strftime('%d %b %Y · %I:%M %p')} IST\n"
		f"{'🔧 Bot Status: Maintenance' if maintenance else '🟢 Bot Status: Online'}\n\n"
		"┌─────────────────────────┐\n"
		"│ 📊 OVERVIEW\n"
		"├─────────────────────────┤\n"
		f"│ 👥 Total Users: {total_users}\n"
		f"│ 💰 Total Balance: ₹{total_balance}\n"
		f"│ ⏳ Pending Actions: {pending_count}\n"
		"└─────────────────────────┘\n\n"
		"🔒 Admin-only access · Secured"
	)

	markup = types.InlineKeyboardMarkup(row_width=2)
	if pending_count > 0 and "payment_control" in perms:
		markup.add(types.InlineKeyboardButton(f"⏳ View {pending_count} Pending Action(s)", callback_data="adm_payment_control"))
	buttons = []
	for key, label in PERMISSIONS.items():
		if key in perms:
			buttons.append(types.InlineKeyboardButton(label, callback_data=f"adm_{key}"))
	for i in range(0, len(buttons), 2):
		markup.add(*buttons[i:i + 2])
	if uid == ADMIN_ID:
		markup.add(types.InlineKeyboardButton("👥 Manage Sub-Admins", callback_data="adm_subadmins"))
	bot.send_message(chat_id, text, reply_markup=markup)

ADMIN_TOP_LEVEL_CALLBACKS = set(["adm_" + k for k in PERMISSIONS.keys()] + ["adm_subadmins"])

@bot.callback_query_handler(func=lambda call: call.data in ADMIN_TOP_LEVEL_CALLBACKS)
def admin_panel_callback(call):
	uid = call.from_user.id
	action = call.data[len("adm_"):]

	if action == "subadmins":
		if uid != ADMIN_ID:
			bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
			return
		bot.answer_callback_query(call.id)
		show_subadmin_menu(call.message.chat.id)
		return

	perms = get_admin_permissions(uid)
	if perms is None or action not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return

	bot.answer_callback_query(call.id)

	if action == "dashboard":
		show_admin_panel(call.message.chat.id, uid, perms)
	elif action == "user_mgmt":
		show_user_mgmt_menu(call.message.chat.id)
	elif action == "payment_control":
		show_payment_control(call.message.chat.id)
	elif action == "channel_mgmt":
		show_channel_mgmt(call.message.chat.id)
	elif action == "broadcast":
		start_broadcast(call.message.chat.id, uid)
	elif action == "gift_control":
		show_gift_control(call.message.chat.id)
	elif action == "payment_settings":
		show_payment_settings(call.message.chat.id)
	elif action == "reports":
		show_reports(call.message.chat.id)
	elif action == "maintenance":
		show_maintenance_menu(call.message.chat.id)
	elif action == "limits":
		show_limits_menu(call.message.chat.id)
	elif action == "activity_log":
		show_activity_log(call.message.chat.id)
	elif action == "backup":
		show_backup_menu(call.message.chat.id)
	elif action == "export":
		show_export_import_menu(call.message.chat.id)

def show_user_mgmt_menu(chat_id):
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("🔍 Search User", callback_data="admu_search"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, "👥 <b>User Management</b>\n\nSelect an option:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admu_search")
def admu_search_start(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "user_mgmt" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Send the User ID to search:")
	bot.register_next_step_handler(msg, admu_search_process)

def admu_search_process(message):
	query = message.text.strip()
	db = load_db()

	if query.isdigit():
		target_id = query
		user = get_user(target_id)
		if not user:
			bot.send_message(message.chat.id, "User not found.")
			return
	else:
		uname = query.lstrip("@").lower()
		matches = [(uid_key, u) for uid_key, u in db["users"].items() if (u.get("username") or "").lower() == uname]
		if not matches:
			bot.send_message(message.chat.id, "No user found with that username.")
			return
		if len(matches) > 1:
			lines = [f"🆔 <code>{uid_key}</code> — {u['name']}" for uid_key, u in matches]
			bot.send_message(message.chat.id, "Multiple users found, search by exact User ID instead:\n\n" + "\n".join(lines))
			return
		target_id, user = matches[0]

	text = (
		f"👤 Name: {user['name']}\n"
		f"🆔 Username: @{user['username']}\n"
		f"🆔 ID: <code>{target_id}</code>\n"
		f"💰 Balance: ₹{user['balance']}\n"
		f"📅 Joined: {user.get('joined_date', 'N/A')}\n"
		f"🚫 Status: {'Banned' if user.get('banned') else 'Active'}"
	)
	notes = user.get("notes", [])
	if notes:
		note_lines = [f"📝 {n['note']} — {n['date']} (by {n['admin_id']})" for n in notes[-3:]]
		text += "\n\n<b>Recent Notes:</b>\n" + "\n".join(note_lines)

	markup = types.InlineKeyboardMarkup()
	markup.add(
		types.InlineKeyboardButton("💰 Add Balance", callback_data=f"admu_add_{target_id}"),
		types.InlineKeyboardButton("➖ Deduct Balance", callback_data=f"admu_deduct_{target_id}"),
	)
	if user.get("banned"):
		markup.add(types.InlineKeyboardButton("✅ Unban", callback_data=f"admu_unban_{target_id}"))
	else:
		markup.add(types.InlineKeyboardButton("🚫 Ban", callback_data=f"admu_ban_{target_id}"))
	markup.add(types.InlineKeyboardButton("📝 Add Note", callback_data=f"admu_note_{target_id}"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_user_mgmt"))
	bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admu_note_"))
def admu_note_start(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "user_mgmt" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	target_id = call.data.split("_", 2)[2]
	bot.answer_callback_query(call.id)
	set_state(call.from_user.id, note_target=target_id)
	msg = bot.send_message(call.message.chat.id, "Send the note text:")
	bot.register_next_step_handler(msg, admu_note_save)

def admu_note_save(message):
	uid = message.from_user.id
	state = get_state(uid)
	target_id = state.get("note_target")
	if not target_id:
		return
	with DB_LOCK:
		db = load_db()
		target_key = str(target_id)
		if target_key in db["users"]:
			db["users"][target_key].setdefault("notes", []).append({
				"admin_id": uid,
				"note": message.text.strip(),
				"date": now_ist().strftime("%d-%m-%Y"),
				"time": now_ist().strftime("%I:%M %p"),
			})
			save_db(db)
	log_admin_action(uid, "Added Note", f"User {target_id}: {message.text.strip()[:40]}")
	bot.send_message(message.chat.id, "✅ Note saved.")
	clear_state(uid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admu_add_") or call.data.startswith("admu_deduct_"))
def admu_balance_start(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "user_mgmt" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	is_add = call.data.startswith("admu_add_")
	target_id = call.data.split("_", 2)[2]
	bot.answer_callback_query(call.id)
	set_state(call.from_user.id, admin_action="add_balance" if is_add else "deduct_balance", admin_target=target_id)
	msg = bot.send_message(call.message.chat.id, f"Enter amount to {'add' if is_add else 'deduct'}:")
	bot.register_next_step_handler(msg, admu_balance_process)

def admu_balance_process(message):
	uid = message.from_user.id
	state = get_state(uid)
	if state.get("admin_action") not in ["add_balance", "deduct_balance"]:
		return
	try:
		amount = float(message.text.strip())
		if amount <= 0:
			raise ValueError
	except ValueError:
		bot.send_message(message.chat.id, "Invalid amount.")
		return

	target_id = state["admin_target"]
	is_add = state["admin_action"] == "add_balance"
	threshold = get_setting("big_action_threshold")

	if amount > threshold:
		set_state(uid, confirm_target=target_id, confirm_amount=amount, confirm_is_add=is_add)
		action_word = "add" if is_add else "deduct"
		ask_confirmation(
			message.chat.id, uid, "big_balance",
			f"You are about to {action_word} ₹{amount} {'to' if is_add else 'from'} user {target_id} (above ₹{threshold} threshold).",
		)
		return

	if is_add:
		add_balance(target_id, amount)
		log_admin_action(uid, "Added Balance", f"User {target_id}, +₹{amount}")
		bot.send_message(message.chat.id, f"✅ ₹{amount} added to user {target_id}.")
		try:
			bot.send_message(int(target_id), f"💰 ₹{amount} has been added to your balance by admin.")
		except Exception:
			pass
	else:
		deduct_balance(target_id, amount)
		log_admin_action(uid, "Deducted Balance", f"User {target_id}, -₹{amount}")
		bot.send_message(message.chat.id, f"✅ ₹{amount} deducted from user {target_id}.")
		try:
			bot.send_message(int(target_id), f"⚠️ ₹{amount} has been deducted from your balance by admin.")
		except Exception:
			pass
	clear_state(uid)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admu_ban_") or call.data.startswith("admu_unban_"))
def admu_ban_toggle(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "user_mgmt" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	ban = call.data.startswith("admu_ban_")
	target_id = call.data.split("_", 2)[2]

	if ban:
		bot.answer_callback_query(call.id)
		set_state(call.from_user.id, confirm_target=target_id)
		ask_confirmation(call.message.chat.id, call.from_user.id, "ban_user", f"You are about to BAN user {target_id}.")
		return

	update_user(target_id, "banned", False)
	log_admin_action(call.from_user.id, "Unbanned User", f"User {target_id}")
	bot.answer_callback_query(call.id, "Unbanned")
	bot.send_message(call.message.chat.id, "✅ User unbanned.")

def show_payment_control(chat_id):
	db = load_db()
	pending = db["pending"]
	if not pending:
		bot.send_message(chat_id, "💰 <b>Payment Control</b>\n\nNo pending requests.", reply_markup=admin_back_button())
		return

	for pid, data in list(pending.items()):
		try:
			if data["type"] == "deposit":
				caption = (
					"🔔 <b>Pending Deposit</b>\n\n"
					f"🆔 User ID: <code>{data['user_id']}</code>\n"
					f"💰 Amount: ₹{data['amount']}\n"
					f"📉 Tax: ₹{data['tax']}\n"
					f"✅ Final: ₹{data['final_amount']}\n"
					f"💳 Method: {data['method'].upper()}\n"
					f"📅 {data['date']} {data['time']}"
				)
				markup = types.InlineKeyboardMarkup()
				markup.add(
					types.InlineKeyboardButton("✅ Approved", callback_data=f"dep_approve_{pid}"),
					types.InlineKeyboardButton("❌ Rejected", callback_data=f"dep_reject_{pid}"),
				)
				if data.get("file_id"):
					bot.send_photo(chat_id, data["file_id"], caption=caption, reply_markup=markup)
				else:
					bot.send_message(chat_id, caption, reply_markup=markup)
			elif data["type"] == "withdraw":
				caption = (
					"🏦 <b>Pending UPI Withdraw</b>\n\n"
					f"🆔 User ID: <code>{data['user_id']}</code>\n"
					f"📱 UPI: <code>{data['number']}</code>\n"
					f"💰 Amount: ₹{data['amount']}\n"
					f"📉 Tax: ₹{data['tax']}\n"
					f"✅ Final: ₹{data['final_amount']}\n"
					f"📅 {data['date']} {data['time']}"
				)
				markup = types.InlineKeyboardMarkup()
				markup.add(
					types.InlineKeyboardButton("✅ Approved", callback_data=f"wdupi_approve_{pid}"),
					types.InlineKeyboardButton("❌ Rejected", callback_data=f"wdupi_reject_{pid}"),
				)
				bot.send_message(chat_id, caption, reply_markup=markup)
		except Exception as e:
			print("Payment control display error:", e)

	bot.send_message(chat_id, "👆 All pending requests shown above.", reply_markup=admin_back_button())

def show_channel_mgmt(chat_id):
	channels = get_setting("force_channels")
	log_ch = get_setting("log_channel")
	lines = [f"{i + 1}. {ch['url']}" for i, ch in enumerate(channels)]
	text = (
		"⚙️ <b>Channel Management</b>\n\n"
		"Current Force-Join Channels:\n" + "\n".join(lines) +
		f"\n\nCurrent Log Channel: {log_ch}"
	)
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("➕ Add Channel", callback_data="admc_add"))
	markup.add(types.InlineKeyboardButton("➖ Remove Channel", callback_data="admc_remove"))
	markup.add(types.InlineKeyboardButton("✏️ Change Log Channel", callback_data="admc_logch"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["admc_add", "admc_remove", "admc_logch"])
def admc_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "channel_mgmt" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)

	if call.data == "admc_add":
		msg = bot.send_message(call.message.chat.id, "Send the new channel username (without @), e.g. MyChannel:")
		bot.register_next_step_handler(msg, admc_add_process)
	elif call.data == "admc_remove":
		msg = bot.send_message(call.message.chat.id, "Send the channel username to remove (without @):")
		bot.register_next_step_handler(msg, admc_remove_process)
	else:
		msg = bot.send_message(call.message.chat.id, "Send the new log channel username (with @), e.g. @MyLogChannel:")
		bot.register_next_step_handler(msg, admc_logch_process)

def admc_add_process(message):
	uid = message.from_user.id
	username = message.text.strip().lstrip("@")
	channels = get_setting("force_channels")
	channels.append({"name": f"Channel {len(channels) + 1}", "username": username, "url": f"https://t.me/{username}"})
	set_setting("force_channels", channels)
	log_admin_action(uid, "Added Force-Join Channel", username)
	bot.send_message(message.chat.id, f"✅ Channel @{username} added.")

def admc_remove_process(message):
	uid = message.from_user.id
	username = message.text.strip().lstrip("@")
	channels = get_setting("force_channels")
	new_channels = [ch for ch in channels if ch["username"] != username]
	set_setting("force_channels", new_channels)
	log_admin_action(uid, "Removed Force-Join Channel", username)
	bot.send_message(message.chat.id, f"✅ Channel @{username} removed (if it existed).")

def admc_logch_process(message):
	uid = message.from_user.id
	new_channel = message.text.strip()
	if not new_channel.startswith("@"):
		new_channel = "@" + new_channel
	set_setting("log_channel", new_channel)
	log_admin_action(uid, "Changed Log Channel", new_channel)
	bot.send_message(message.chat.id, f"✅ Log channel updated to {new_channel}.")

def start_broadcast(chat_id, uid):
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("👤 One User", callback_data="admbc_one"))
	markup.add(types.InlineKeyboardButton("👥 All Users", callback_data="admbc_all"))
	markup.add(types.InlineKeyboardButton("🕐 Schedule Broadcast", callback_data="admbc_schedule"))
	markup.add(types.InlineKeyboardButton("📊 Broadcast Statistics", callback_data="admbc_stats"))
	markup.add(types.InlineKeyboardButton("📌 Pin/Announcement", callback_data="admbc_pin"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, "📢 <b>Broadcast</b>\n\nSend a message (text or photo) to one user or all users.\nYou can also schedule a broadcast for later.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["admbc_one", "admbc_all", "admbc_schedule", "admbc_stats", "admbc_pin"])
def admbc_menu_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "broadcast" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	uid = call.from_user.id

	if call.data == "admbc_stats":
		show_broadcast_stats(call.message.chat.id)
		return

	if call.data == "admbc_pin":
		show_pin_announcement_menu(call.message.chat.id)
		return

	if call.data == "admbc_one":
		set_state(uid, admin_action="broadcast_one")
		msg = bot.send_message(call.message.chat.id, "Send the User ID to message:")
		bot.register_next_step_handler(msg, admbc_one_get_id)
		return

	if call.data == "admbc_all":
		set_state(uid, admin_action="broadcast_all")
		msg = bot.send_message(call.message.chat.id, "Send the message (text or photo with caption) to broadcast to ALL users:")
		bot.register_next_step_handler(msg, admbc_content_step)
		return

	if call.data == "admbc_schedule":
		markup = types.InlineKeyboardMarkup()
		markup.add(types.InlineKeyboardButton("👤 One User", callback_data="admbcs_one"))
		markup.add(types.InlineKeyboardButton("👥 All Users", callback_data="admbcs_all"))
		bot.send_message(call.message.chat.id, "Who should receive the scheduled broadcast?", reply_markup=markup)

def admbc_one_get_id(message):
	uid = message.from_user.id
	target_id = message.text.strip()
	if not target_id.isdigit() or not get_user(target_id):
		bot.send_message(message.chat.id, "Invalid or unknown User ID.")
		return
	set_state(uid, admin_action="broadcast_one", broadcast_target=target_id)
	msg = bot.send_message(message.chat.id, "Send the message (text or photo with caption) to send to this user:")
	bot.register_next_step_handler(msg, admbc_content_step)

def admbc_content_step(message):
	"""Captures the broadcast content (text or photo). Routes to instant send for
	one-user broadcasts, or to a 2FA confirmation for all-user broadcasts."""
	uid = message.from_user.id
	state = get_state(uid)
	action = state.get("admin_action")
	if action not in ["broadcast_one", "broadcast_all"]:
		return

	if message.content_type == "photo":
		file_id = message.photo[-1].file_id
		caption = message.caption or ""
		set_state(uid, broadcast_file_id=file_id, broadcast_text=caption)
	else:
		set_state(uid, broadcast_file_id=None, broadcast_text=message.text or "")

	if action == "broadcast_one":
		execute_broadcast(message.chat.id, uid, target="one")
	else:
		db = load_db()
		total = len(db["users"])
		ask_confirmation(message.chat.id, uid, "broadcast_all", f"This will send a message to ALL {total} users.")

def execute_broadcast(chat_id, uid, target):
	"""target: 'one' or 'all'. Reads content from admin's state."""
	state = get_state(uid)
	file_id = state.get("broadcast_file_id")
	text = state.get("broadcast_text", "")

	if target == "one":
		target_id = state.get("broadcast_target")
		success, failed = 0, 0
		try:
			if file_id:
				bot.send_photo(int(target_id), file_id, caption=text)
			else:
				bot.send_message(int(target_id), text)
			success = 1
		except Exception:
			failed = 1
		recipient_count = 1
	else:
		db = load_db()
		user_ids = list(db["users"].keys())
		success, failed = 0, 0
		for tid in user_ids:
			try:
				if file_id:
					bot.send_photo(int(tid), file_id, caption=text)
				else:
					bot.send_message(int(tid), text)
				success += 1
			except Exception:
				failed += 1
		recipient_count = len(user_ids)

	with DB_LOCK:
		db = load_db()
		db["broadcast_history"].append({
			"admin_id": uid,
			"target": target,
			"recipient_count": recipient_count,
			"success": success,
			"failed": failed,
			"preview": (text[:50] if text else "[photo]"),
			"date": now_ist().strftime("%d-%m-%Y"),
			"time": now_ist().strftime("%I:%M %p"),
		})
		db["broadcast_history"] = db["broadcast_history"][-100:]
		save_db(db)

	log_admin_action(uid, "Broadcast", f"target={target}, sent={success}, failed={failed}")
	bot.send_message(chat_id, f"✅ Broadcast sent to {success}/{success + failed} recipient(s) ({failed} failed/blocked).")
	clear_state(uid)

def show_pin_announcement_menu(chat_id):
	current = get_setting("pin_announcement")
	text = "📌 <b>Pin/Announcement</b>\n\n" + (f"Current: {current}" if current else "No announcement set.")
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("✏️ Set Announcement", callback_data="admpin_set"))
	if current:
		markup.add(types.InlineKeyboardButton("🗑️ Clear Announcement", callback_data="admpin_clear"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["admpin_set", "admpin_clear"])
def admpin_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "broadcast" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	if call.data == "admpin_clear":
		set_setting("pin_announcement", "")
		log_admin_action(call.from_user.id, "Cleared Announcement", "")
		bot.send_message(call.message.chat.id, "✅ Announcement cleared.")
		return
	msg = bot.send_message(call.message.chat.id, "Send the new announcement text:")
	bot.register_next_step_handler(msg, admpin_set_process)

def admpin_set_process(message):
	set_setting("pin_announcement", message.text.strip())
	log_admin_action(message.from_user.id, "Set Announcement", message.text.strip()[:50])
	bot.send_message(message.chat.id, "✅ Announcement set. It will show at the top of the Account section.")

def show_broadcast_stats(chat_id):
	db = load_db()
	history = db["broadcast_history"][-10:]
	if not history:
		bot.send_message(chat_id, "📊 <b>Broadcast Statistics</b>\n\nNo broadcasts sent yet.", reply_markup=admin_back_button())
		return
	lines = []
	for h in reversed(history):
		lines.append(
			f"📅 {h['date']} {h['time']} — {h['target']} — ✅{h['success']} ❌{h['failed']} — \"{h['preview']}\""
		)
	text = "📊 <b>Recent Broadcasts</b>\n\n" + "\n".join(lines)
	bot.send_message(chat_id, text[:4000], reply_markup=admin_back_button())

@bot.callback_query_handler(func=lambda call: call.data in ["admbcs_one", "admbcs_all"])
def admbcs_target_selected(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "broadcast" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	uid = call.from_user.id
	target = "one" if call.data == "admbcs_one" else "all"
	set_state(uid, schedule_target=target)

	if target == "one":
		msg = bot.send_message(call.message.chat.id, "Send the User ID to schedule a message for:")
		bot.register_next_step_handler(msg, admbcs_get_id)
	else:
		msg = bot.send_message(call.message.chat.id, "Send the message (text or photo with caption) to schedule for ALL users:")
		bot.register_next_step_handler(msg, admbcs_content_step)

def admbcs_get_id(message):
	uid = message.from_user.id
	target_id = message.text.strip()
	if not target_id.isdigit() or not get_user(target_id):
		bot.send_message(message.chat.id, "Invalid or unknown User ID.")
		return
	set_state(uid, schedule_user_id=target_id)
	msg = bot.send_message(message.chat.id, "Send the message (text or photo with caption) to schedule:")
	bot.register_next_step_handler(msg, admbcs_content_step)

def admbcs_content_step(message):
	uid = message.from_user.id
	state = get_state(uid)
	if "schedule_target" not in state:
		return

	if message.content_type == "photo":
		file_id = message.photo[-1].file_id
		caption = message.caption or ""
		set_state(uid, schedule_file_id=file_id, schedule_text=caption)
	else:
		set_state(uid, schedule_file_id=None, schedule_text=message.text or "")

	msg = bot.send_message(message.chat.id, "Send the date & time to send this (IST), format: DD-MM-YYYY HH:MM\ne.g. 15-08-2026 09:30")
	bot.register_next_step_handler(msg, admbcs_time_step)

def admbcs_time_step(message):
	uid = message.from_user.id
	state = get_state(uid)
	try:
		naive = datetime.strptime(message.text.strip(), "%d-%m-%Y %H:%M")
		scheduled_dt = naive.replace(tzinfo=IST)
	except Exception:
		msg = bot.send_message(message.chat.id, "Invalid format. Send again as DD-MM-YYYY HH:MM:")
		bot.register_next_step_handler(msg, admbcs_time_step)
		return

	if scheduled_dt <= now_ist():
		msg = bot.send_message(message.chat.id, "That time is in the past. Send a future date/time (DD-MM-YYYY HH:MM):")
		bot.register_next_step_handler(msg, admbcs_time_step)
		return

	with DB_LOCK:
		db = load_db()
		db["scheduled_broadcasts"].append({
			"admin_id": uid,
			"target": state["schedule_target"],
			"user_id": state.get("schedule_user_id"),
			"file_id": state.get("schedule_file_id"),
			"text": state.get("schedule_text", ""),
			"send_at": scheduled_dt.strftime("%d-%m-%Y %H:%M"),
		})
		save_db(db)

	log_admin_action(uid, "Scheduled Broadcast", f"target={state['schedule_target']}, at={scheduled_dt.strftime('%d-%m-%Y %H:%M')}")
	bot.send_message(message.chat.id, f"✅ Broadcast scheduled for {scheduled_dt.strftime('%d-%m-%Y %H:%M')} IST.")
	clear_state(uid)

def scheduled_broadcast_loop():
	while True:
		time.sleep(60)
		try:
			db = load_db()
			due = []
			remaining = []
			now = now_ist()
			for item in db["scheduled_broadcasts"]:
				try:
					send_at = datetime.strptime(item["send_at"], "%d-%m-%Y %H:%M").replace(tzinfo=IST)
				except Exception:
					continue
				if send_at <= now:
					due.append(item)
				else:
					remaining.append(item)

			if due:
				with DB_LOCK:
					db2 = load_db()
					db2["scheduled_broadcasts"] = remaining
					save_db(db2)

				for item in due:
					try:
						if item["target"] == "one":
							tid = item["user_id"]
							if item["file_id"]:
								bot.send_photo(int(tid), item["file_id"], caption=item["text"])
							else:
								bot.send_message(int(tid), item["text"])
						else:
							db3 = load_db()
							for tid in db3["users"].keys():
								try:
									if item["file_id"]:
										bot.send_photo(int(tid), item["file_id"], caption=item["text"])
									else:
										bot.send_message(int(tid), item["text"])
								except Exception:
									pass
					except Exception as e:
						print("Scheduled broadcast send error:", e)
		except Exception as e:
			print("Scheduled broadcast loop error:", e)

def show_gift_control(chat_id):
	db = load_db()
	codes = db["gift_codes"]
	active = {c: d for c, d in codes.items() if len(d["claimed_by"]) < d["max_claims"]}
	if not active:
		bot.send_message(chat_id, "🎁 <b>Gift Code Control</b>\n\nNo active codes.", reply_markup=admin_back_button())
		return
	lines = []
	for code, data in active.items():
		lines.append(f"<code>{code}</code> — ₹{data['amount']} × {data['max_claims']} ({len(data['claimed_by'])} claimed)")
	text = "🎁 <b>Active Gift Codes</b>\n\n" + "\n".join(lines)
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("❌ Disable a Code", callback_data="admg_disable"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admg_disable")
def admg_disable_start(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "gift_control" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Send the gift code to disable:")
	bot.register_next_step_handler(msg, admg_disable_process)

def admg_disable_process(message):
	uid = message.from_user.id
	code = message.text.strip()
	with DB_LOCK:
		db = load_db()
		if code in db["gift_codes"]:
			del db["gift_codes"][code]
			save_db(db)
			found = True
		else:
			found = False
	if found:
		log_admin_action(uid, "Disabled Gift Code", code)
		bot.send_message(message.chat.id, f"✅ Code {code} disabled.")
	else:
		bot.send_message(message.chat.id, "Code not found.")

def show_payment_settings(chat_id):
	token = get_setting("ultra_api_token") or ""
	text = (
		"⚙️ <b>Payment Settings</b>\n\n"
		f"Ultra Number: <code>{get_setting('ultra_deposit_number')}</code>\n"
		f"Tax: {get_setting('tax_percent')}%\n"
		f"Ultra API Token: <code>{token[:10]}...</code>"
	)
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("✏️ Change Ultra Number", callback_data="adms_ultranum"))
	markup.add(types.InlineKeyboardButton("✏️ Change UPI QR", callback_data="adms_qr"))
	markup.add(types.InlineKeyboardButton("✏️ Change Tax %", callback_data="adms_tax"))
	markup.add(types.InlineKeyboardButton("✏️ Change API Token", callback_data="adms_apitoken"))
	markup.add(types.InlineKeyboardButton("✏️ Change API Key", callback_data="adms_apikey"))
	markup.add(types.InlineKeyboardButton("✏️ Change Support Message", callback_data="adms_supportmsg"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adms_"))
def adms_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "payment_settings" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	field_map = {
		"adms_ultranum": ("ultra_deposit_number", "Send the new Ultra Pay deposit number:"),
		"adms_qr": ("upi_qr_image", "Send the new UPI QR image URL:"),
		"adms_tax": ("tax_percent", "Send the new tax percentage (number only):"),
		"adms_apitoken": ("ultra_api_token", "Send the new Ultra API token:"),
		"adms_apikey": ("ultra_api_key", "Send the new Ultra API key:"),
		"adms_supportmsg": ("support_message", "Send the new Support message text.\nYou can use {support_username} as a placeholder:"),
	}
	key, prompt = field_map[call.data]
	set_state(call.from_user.id, admin_setting_key=key)
	msg = bot.send_message(call.message.chat.id, prompt)
	bot.register_next_step_handler(msg, adms_process)

def adms_process(message):
	uid = message.from_user.id
	state = get_state(uid)
	key = state.get("admin_setting_key")
	if not key:
		return
	value = message.text.strip()
	if key == "tax_percent":
		try:
			value = float(value)
		except ValueError:
			bot.send_message(message.chat.id, "Invalid number.")
			return
	set_setting(key, value)
	log_admin_action(uid, "Changed Setting", f"{key} = {value}")
	bot.send_message(message.chat.id, f"✅ {key} updated successfully.")
	clear_state(uid)

def show_reports(chat_id):
	db = load_db()
	total_tax_deposit = 0
	total_tax_withdraw = 0
	for u in db["users"].values():
		for h in u.get("add_fund_history", []):
			if h.get("status") == "Approved":
				total_tax_deposit += h.get("tax", 0)
		for h in u.get("withdraw_history", []):
			if h.get("status") == "Approved":
				total_tax_withdraw += h.get("tax", 0)
	text = (
		"📈 <b>Reports</b>\n\n"
		f"💰 Total Tax Earned (Deposit): ₹{round(total_tax_deposit, 2)}\n"
		f"💰 Total Tax Earned (Withdraw): ₹{round(total_tax_withdraw, 2)}\n"
		f"💎 Total Tax Earned (Overall): ₹{round(total_tax_deposit + total_tax_withdraw, 2)}\n"
		f"👥 Total Users: {len(db['users'])}\n"
		f"🎁 Total Gift Codes Created: {len(db['gift_codes'])}"
	)
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("📈 Growth Chart (7 Days)", callback_data="admr_growth"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admr_growth")
def admr_growth(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "reports" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)

	db = load_db()
	counts = {}
	for u in db["users"].values():
		d = u.get("joined_date")
		if d:
			counts[d] = counts.get(d, 0) + 1

	days = [now_ist() - timedelta(days=i) for i in range(6, -1, -1)]
	day_counts = [counts.get(d.strftime("%d-%m-%Y"), 0) for d in days]
	max_c = max(day_counts) if max(day_counts) > 0 else 1

	lines = []
	for d, c in zip(days, day_counts):
		filled = int((c / max_c) * 8)
		bar = "▓" * filled + "░" * (8 - filled)
		lines.append(f"{d.strftime('%a')} {bar} {c} users")

	text = "📈 <b>Last 7 Days New User Growth</b>\n\n" + "\n".join(lines)
	bot.send_message(call.message.chat.id, text, reply_markup=admin_back_button())

def show_maintenance_menu(chat_id):
	status = get_setting("maintenance_mode")
	text = f"🔧 <b>Maintenance Mode</b>\n\nCurrent status: {'🔴 ON' if status else '🟢 OFF'}"
	markup = types.InlineKeyboardMarkup()
	if status:
		markup.add(types.InlineKeyboardButton("🟢 Turn OFF", callback_data="admm_off"))
	else:
		markup.add(types.InlineKeyboardButton("🔴 Turn ON", callback_data="admm_on"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["admm_on", "admm_off"])
def admm_toggle(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "maintenance" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	new_status = call.data == "admm_on"
	set_setting("maintenance_mode", new_status)
	log_admin_action(call.from_user.id, "Maintenance Mode", "ON" if new_status else "OFF")
	bot.answer_callback_query(call.id, "Updated")
	show_maintenance_menu(call.message.chat.id)

def show_limits_menu(chat_id):
	text = (
		"💵 <b>Min/Max Limits</b>\n\n"
		f"Min Deposit: ₹{get_setting('min_deposit')}\n"
		f"Max Deposit: ₹{get_setting('max_deposit')}\n"
		f"Min Withdraw: ₹{get_setting('min_withdraw')}\n"
		f"Max Withdraw: ₹{get_setting('max_withdraw')}"
	)
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("✏️ Min Deposit", callback_data="admlim_min_deposit"))
	markup.add(types.InlineKeyboardButton("✏️ Max Deposit", callback_data="admlim_max_deposit"))
	markup.add(types.InlineKeyboardButton("✏️ Min Withdraw", callback_data="admlim_min_withdraw"))
	markup.add(types.InlineKeyboardButton("✏️ Max Withdraw", callback_data="admlim_max_withdraw"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admlim_"))
def admlim_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "limits" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	key = call.data[len("admlim_"):]
	set_state(call.from_user.id, admin_limit_key=key)
	msg = bot.send_message(call.message.chat.id, f"Send new value for {key.replace('_', ' ')}:")
	bot.register_next_step_handler(msg, admlim_process)

def admlim_process(message):
	uid = message.from_user.id
	state = get_state(uid)
	key = state.get("admin_limit_key")
	if not key:
		return
	try:
		value = float(message.text.strip())
	except ValueError:
		bot.send_message(message.chat.id, "Invalid number.")
		return
	set_setting(key, value)
	log_admin_action(uid, "Changed Limit", f"{key} = {value}")
	bot.send_message(message.chat.id, f"✅ {key} updated to ₹{value}.")
	clear_state(uid)

def show_activity_log(chat_id):
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("📋 All", callback_data="admlog_all"))
	markup.add(
		types.InlineKeyboardButton("💰 Deposits", callback_data="admlog_deposits"),
		types.InlineKeyboardButton("🏦 Withdraws", callback_data="admlog_withdraws"),
	)
	markup.add(
		types.InlineKeyboardButton("🚫 Bans", callback_data="admlog_bans"),
		types.InlineKeyboardButton("📢 Broadcasts", callback_data="admlog_broadcasts"),
	)
	markup.add(types.InlineKeyboardButton("⚙️ Settings", callback_data="admlog_settings"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, "🗒️ <b>Admin Activity Log</b>\n\nFilter by category:", reply_markup=markup)

ACTIVITY_LOG_KEYWORDS = {
	"all": None,
	"deposits": "deposit",
	"withdraws": "withdraw",
	"bans": "ban",
	"broadcasts": "broadcast",
	"settings": "setting",
}

@bot.callback_query_handler(func=lambda call: call.data.startswith("admlog_"))
def admlog_show(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "activity_log" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)

	cat = call.data[len("admlog_"):]
	keyword = ACTIVITY_LOG_KEYWORDS.get(cat)
	db = load_db()
	logs = db["activity_log"]
	if keyword:
		logs = [l for l in logs if keyword in l["action"].lower()]
	logs = logs[-20:]

	if not logs:
		bot.send_message(call.message.chat.id, "🗒️ No activity found for this category.", reply_markup=admin_back_button())
		return

	lines = []
	for l in reversed(logs):
		lines.append(f"👤 {l['admin_id']} — {l['action']} ({l['details']}) — {l['date']} {l['time']}")
	text = f"🗒️ <b>Activity Log — {cat.title()}</b>\n\n" + "\n".join(lines)
	bot.send_message(call.message.chat.id, text[:4000], reply_markup=admin_back_button())

def show_backup_menu(chat_id):
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("💾 Backup Now", callback_data="admb_now"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(
		chat_id,
		"💾 <b>Auto Backup</b>\n\nThe bot automatically backs up data daily. You can also trigger a manual backup below.",
		reply_markup=markup,
	)

@bot.callback_query_handler(func=lambda call: call.data == "admb_now")
def admb_now(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "backup" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	path = do_backup()
	log_admin_action(call.from_user.id, "Manual Backup", path)
	try:
		with open(path, "rb") as f:
			bot.send_document(call.message.chat.id, f, caption="✅ Backup created.")
	except Exception:
		bot.send_message(call.message.chat.id, f"✅ Backup saved to {path}")

def do_backup():
	os.makedirs("backups", exist_ok=True)
	timestamp = now_ist().strftime("%d-%m-%Y_%H-%M-%S")
	path = f"backups/backup_{timestamp}.json"
	db = load_db()
	with open(path, "w", encoding="utf-8") as f:
		json.dump(db, f, indent=2, ensure_ascii=False)
	return path

def auto_backup_loop():
	while True:
		time.sleep(24 * 60 * 60)  # once a day
		try:
			do_backup()
		except Exception as e:
			print("Auto backup error:", e)

def show_export_import_menu(chat_id):
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("📤 Export Data (CSV)", callback_data="admei_export"))
	markup.add(types.InlineKeyboardButton("📥 Import Data (CSV)", callback_data="admei_import"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, "📤📥 <b>Export / Import Data</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["admei_export", "admei_import"])
def admei_action(call):
	perms = get_admin_permissions(call.from_user.id)
	if perms is None or "export" not in perms:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	if call.data == "admei_export":
		do_export(call.message.chat.id, call.from_user.id)
	else:
		msg = bot.send_message(
			call.message.chat.id,
			"Send a CSV file with rows formatted as: user_id,amount\n(This will ADD the given amount to each user's balance.)",
		)
		bot.register_next_step_handler(msg, do_import)

def do_import(message):
	uid = message.from_user.id
	if message.content_type != "document":
		bot.send_message(message.chat.id, "Please send a valid CSV file.")
		return
	try:
		file_info = bot.get_file(message.document.file_id)
		downloaded = bot.download_file(file_info.file_path)
		text = downloaded.decode("utf-8")
	except Exception as e:
		bot.send_message(message.chat.id, f"Failed to read file: {e}")
		return

	success, failed = 0, 0
	for line in text.strip().split("\n"):
		line = line.strip()
		if not line:
			continue
		try:
			parts = line.split(",")
			target_id = parts[0].strip()
			amount = float(parts[1].strip())
			if get_user(target_id):
				add_balance(target_id, amount)
				success += 1
			else:
				failed += 1
		except Exception:
			failed += 1

	log_admin_action(uid, "Imported Data", f"success={success}, failed={failed}")
	bot.send_message(message.chat.id, f"✅ Import complete. Updated {success} users, {failed} failed/skipped.")

def do_export(chat_id, uid):
	path = "export_users.csv"
	db = load_db()
	with open(path, "w", newline="", encoding="utf-8") as f:
		writer = csv.writer(f)
		writer.writerow(["User ID", "Name", "Username", "Balance", "UPI ID", "Ultra Pay", "Banned", "Joined Date"])
		for uid_key, u in db["users"].items():
			writer.writerow([
				uid_key, u.get("name"), u.get("username"), u.get("balance"),
				u.get("upi_id"), u.get("ultra_pay"), u.get("banned"), u.get("joined_date"),
			])
	log_admin_action(uid, "Exported Data", "users.csv")
	try:
		with open(path, "rb") as f:
			bot.send_document(chat_id, f, caption="📤 User data export.")
	except Exception:
		bot.send_message(chat_id, "Export failed.")

def show_subadmin_menu(chat_id):
	db = load_db()
	subs = db["sub_admins"]
	lines = [f"🆔 {sid} — {len(data['permissions'])} permissions" for sid, data in subs.items()]
	text = "👥 <b>Sub-Admin Management</b>\n\n" + ("\n".join(lines) if lines else "No sub-admins yet.")
	markup = types.InlineKeyboardMarkup()
	markup.add(types.InlineKeyboardButton("➕ Add Sub-Admin", callback_data="adms2_add"))
	if subs:
		markup.add(types.InlineKeyboardButton("➖ Remove Sub-Admin", callback_data="adms2_remove"))
	markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="adm_dashboard"))
	bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "adms2_add")
def adms2_add_start(call):
	if call.from_user.id != ADMIN_ID:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Send the User ID to add as sub-admin:")
	bot.register_next_step_handler(msg, adms2_add_id)

def adms2_add_id(message):
	target_id = message.text.strip()
	if not target_id.isdigit():
		bot.send_message(message.chat.id, "Invalid User ID.")
		return
	set_state(message.from_user.id, new_subadmin_id=target_id, new_subadmin_perms=[])
	show_permission_selector(message.chat.id, message.from_user.id)

def build_permission_markup(selected):
	markup = types.InlineKeyboardMarkup()
	for key, label in PERMISSIONS.items():
		mark = "✅ " if key in selected else "⬜ "
		markup.add(types.InlineKeyboardButton(mark + label, callback_data=f"admperm_{key}"))
	markup.add(types.InlineKeyboardButton("💾 Save", callback_data="admperm_save"))
	return markup

def show_permission_selector(chat_id, admin_uid):
	state = get_state(admin_uid)
	selected = state.get("new_subadmin_perms", [])
	bot.send_message(chat_id, "Select permissions for this sub-admin (tap to toggle):", reply_markup=build_permission_markup(selected))

@bot.callback_query_handler(func=lambda call: call.data.startswith("admperm_"))
def admperm_toggle(call):
	if call.from_user.id != ADMIN_ID:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	key = call.data[len("admperm_"):]
	state = get_state(call.from_user.id)

	if key == "save":
		target_id = state.get("new_subadmin_id")
		perms = state.get("new_subadmin_perms", [])
		if not target_id:
			bot.answer_callback_query(call.id, "Session expired.", show_alert=True)
			return
		with DB_LOCK:
			db = load_db()
			db["sub_admins"][target_id] = {
				"permissions": perms,
				"added_by": call.from_user.id,
				"added_date": now_ist().strftime("%d-%m-%Y"),
			}
			save_db(db)
		log_admin_action(call.from_user.id, "Added Sub-Admin", f"{target_id}, perms: {perms}")
		bot.answer_callback_query(call.id, "Saved!")
		bot.send_message(call.message.chat.id, f"✅ User {target_id} is now a sub-admin with {len(perms)} permissions.")
		try:
			bot.send_message(int(target_id), "🎉 You have been added as a sub-admin! Use /adminpanel to access it.")
		except Exception:
			pass
		clear_state(call.from_user.id)
		return

	selected = state.get("new_subadmin_perms", [])
	if key in selected:
		selected.remove(key)
	else:
		selected.append(key)
	set_state(call.from_user.id, new_subadmin_perms=selected)
	bot.answer_callback_query(call.id)
	try:
		bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=build_permission_markup(selected))
	except Exception:
		pass

@bot.callback_query_handler(func=lambda call: call.data == "adms2_remove")
def adms2_remove_start(call):
	if call.from_user.id != ADMIN_ID:
		bot.answer_callback_query(call.id, "Not authorized.", show_alert=True)
		return
	bot.answer_callback_query(call.id)
	msg = bot.send_message(call.message.chat.id, "Send the User ID of the sub-admin to remove:")
	bot.register_next_step_handler(msg, adms2_remove_process)

def adms2_remove_process(message):
	target_id = message.text.strip()
	db = load_db()
	if target_id not in db["sub_admins"]:
		bot.send_message(message.chat.id, "Sub-admin not found.")
		return
	set_state(message.from_user.id, confirm_target=target_id)
	ask_confirmation(message.chat.id, message.from_user.id, "remove_subadmin", f"You are about to REMOVE sub-admin {target_id}.")

if __name__ == "__main__":
	print(f"{BOT_NAME} is running...")
	threading.Thread(target=auto_backup_loop, daemon=True).start()
	threading.Thread(target=scheduled_broadcast_loop, daemon=True).start()
	bot.infinity_polling(skip_pending=True)
