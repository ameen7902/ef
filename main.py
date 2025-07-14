# === Tournament Bot (Gist Storage Edition) ===
import json
import random
import os
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from telegram import ReplyKeyboardMarkup
from telegram.error import Forbidden
import random
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
GIST_ID = os.getenv("GIST_ID")
GIST_FILENAME = os.getenv("GIST_FILENAME")
GIST_TOKEN = os.getenv("GIST_TOKEN")

REGISTERING_USER = None
REGISTER_LOCK_TASK = None
ADMIN_ID = 7366894756
GROUP_ID = -1002835703789

REGISTER_TEAM, ENTER_PES = range(2)

TEAM_LIST = [
    ("🇧🇷", "Brazil"), ("🇦🇷", "Argentina"), ("🇫🇷", "France"), ("🇩🇪", "Germany"),
    ("🇪🇸", "Spain"), ("🇮🇹", "Italy"), ("🏴", "England"), ("🇵🇹", "Portugal"),
    ("🇳🇱", "Netherlands"), ("🇺🇾", "Uruguay"), ("🇧🇪", "Belgium"), ("🇭🇷", "Croatia"),
    ("🇨🇭", "Switzerland"), ("🇲🇽", "Mexico"), ("🇯🇵", "Japan"), ("🇺🇸", "USA"),
    ("🇸🇪", "Sweden"), ("🇨🇴", "Colombia"), ("🇩🇰", "Denmark"), ("🇷🇸", "Serbia"),
    ("🇵🇱", "Poland"), ("🇨🇲", "Cameroon"), ("🇨🇿", "Czechia"), ("🇷🇴", "Romania"),
    ("🇬🇭", "Ghana"), ("🇨🇱", "Chile"), ("🇰🇷", "South Korea"), ("🇨🇳", "China"),
    ("🇳🇬", "Nigeria"), ("🇲🇦", "Morocco"), ("🇦🇺", "Australia"), ("🇸🇳", "Senegal")
]


def build_team_buttons():
    taken = [p['team'] for p in load_data().get("players", {}).values()]
    available = [(f, n) for f, n in TEAM_LIST if f"{f} {n}" not in taken]
    keyboard = [[f"{f} {n}", f"{f2} {n2}"] for (f, n), (f2, n2) in zip(available[::2], available[1::2])]
    return keyboard

async def unlock_after_timeout():
    global REGISTERING_USER, REGISTER_LOCK_TASK
    await asyncio.sleep(300)  # 5 minutes = 300 seconds
    REGISTERING_USER = None
    REGISTER_LOCK_TASK = None
    print("🔓 Registration unlocked due to timeout.")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REGISTERING_USER, REGISTER_LOCK_TASK
    user = update.effective_user

    # ✅ Only allow /register inside group
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Please use /register in the tournament group.")
        return

    # ✅ Check if someone is registering
    if REGISTERING_USER and REGISTERING_USER != user.id:
        await update.message.reply_text("⚠️ Someone else is registering. Try again in a few minutes.")
        return

    data = load_data()
    players = data.get("players", {})
    if str(user.id) in players:
        await update.message.reply_text("✅ You are already registered.")
        return

    # ✅ Check if all 32 teams are taken
    taken = [p['team'] for p in players.values()]
    available = [(f, n) for f, n in TEAM_LIST if f"{f} {n}" not in taken]
    if not available:
        await update.message.reply_text("Registration is now closed.32/32 qualified for WC 2014")
        return

    try:
        # ✅ Send DM with reply keyboard
        await context.bot.send_message(
            chat_id=user.id,
            text="📝 Let's get you registered!\nPlease select your national team:",
            reply_markup=ReplyKeyboardMarkup(build_team_buttons(), one_time_keyboard=True)
        )
        await update.message.reply_text("📩 Check your DM to complete registration.")
        
        REGISTERING_USER = user.id

        # ✅ Start 5-min timeout task
        if REGISTER_LOCK_TASK:
            REGISTER_LOCK_TASK.cancel()
        REGISTER_LOCK_TASK = asyncio.create_task(unlock_after_timeout())

    except Forbidden:
        await update.message.reply_text("❌ Please start the bot in DM first: @e_tournament_bot")

# === Gist Storage ===
def load_data():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"Bearer {GIST_TOKEN}"}
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        raise Exception(f"Failed to load gist: {res.status_code} - {res.text}")

    res_json = res.json()

    if 'files' not in res_json or GIST_FILENAME not in res_json['files']:
        raise KeyError(f"Gist file '{GIST_FILENAME}' not found in response: {res_json}")

    raw = res_json['files'][GIST_FILENAME]['content']
    return json.loads(raw)


def save_data(data):
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GIST_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "files": {
            GIST_FILENAME: {
                "content": json.dumps(data, indent=2)
            }
        }
    }
    requests.patch(url, headers=headers, data=json.dumps(payload))
# === Registration Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to the eFootball Tournament! Use /register to join.")



async def get_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['team'] = update.message.text
    await update.message.reply_text("Now enter your PES username:")
    return ENTER_PES

async def get_pes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REGISTERING_USER, REGISTER_LOCK_TASK

    user = update.effective_user
    team = context.user_data['team']
    pes_name = update.message.text
    data = load_data()
    players = data.setdefault("players", {})

    # Assign to group with < 4 players
    groups = {g: 0 for g in "ABCDEFGH"}
    for p in players.values():
        if 'group' in p:
            groups[p['group']] += 1
    available_groups = [g for g, count in groups.items() if count < 4]

    if not available_groups:
        await update.message.reply_text("❌ All groups are full.")
        return ConversationHandler.END

    group = random.choice(available_groups)
    players[str(user.id)] = {
        "name": user.first_name,
        "username": user.username or "NoUser",
        "team": team,
        "pes": pes_name,
        "group": group
    }

    data["players"] = players
    save_data(data)

    # 🔓 Clear lock + cancel timeout
    REGISTERING_USER = None
    if REGISTER_LOCK_TASK:
        REGISTER_LOCK_TASK.cancel()

    # ✅ DM confirmation
    await update.message.reply_text(
        f"✅ You are successfully registered!\n\n"
        f"🏳️ Team: {team}\n"
        f"🎮 PES Username: {pes_name}\n"
        f"📍 You have been placed in Group {group}\n\n"
        f"⚔️ Wait for fixtures and get ready!"
    )

    # 📣 Group message (monospace/MarkdownV2)
       

    emojis = ["🎯", "⚽", "🏆", "🔥", "🚀", "📣", "🥅", "🥳"]
    emoji = random.choice(emojis)

    group_msg = f"📝 Registration Update: {user.first_name} ({team}) is allotted to Group {group}! {emoji}"
    await context.bot.send_message(chat_id=GROUP_ID, text=group_msg)


    await context.bot.send_message(chat_id=GROUP_ID, text=group_msg, parse_mode='MarkdownV2')
    return ConversationHandler.END

# === Fixtures Command ===
async def fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    players = data.get("players", {})
    group_fixtures = data.get("group_fixtures", {})

    player = players.get(user_id)
    if not player:
        await update.message.reply_text("❌ You are not registered.")
        return

    group = player['group']
    matches = group_fixtures.get(group, [])
    my_matches = [m for m in matches if user_id in m]

    if not my_matches:
        await update.message.reply_text("📭 No matches assigned yet.")
        return

    for m in my_matches:
        opp_id = m[1] if m[0] == user_id else m[0]
        opp = players.get(opp_id)
        if opp:
            await update.message.reply_text(
                f"📅 Match:\n"
                f"{player['team']} vs {opp['team']}\n"
                f"👤 Opponent: @{opp['username']}\n"
                f"📍 Group {group}"
            )

# === Group Display ===
async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    players = data.get("players", {})
    grouped = {g: [] for g in "ABCDEFGH"}

    for p in players.values():
        grouped[p['group']].append(p)

    for g, plist in grouped.items():
        if plist:
            msg = f"🏆 Group {g} Teams:\n"
            for p in plist:
                msg += f"{p['team']} - @{p['username']}\n"
            await update.message.reply_text(msg)

# === Rules ===
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    rules = data.get("rules", [])
    if not rules:
        await update.message.reply_text("⚠️ No rules added yet.")
    else:
        await update.message.reply_text("📜 Rules:\n" + "\n".join(rules))

async def addrule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    rule_text = ' '.join(context.args)
    if not rule_text:
        await update.message.reply_text("⚠️ Usage: /addrule Your rule text here")
        return

    data = load_data()
    rules = data.setdefault("rules", [])
    rules.append(f"- {rule_text}")
    save_data(data)
    await update.message.reply_text("✅ Rule added.")

# === Add Score + Knockout Generation ===
async def addscore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Usage: /addscore <Group> <MatchNumber> <score> (e.g. A 2 2-1)")
        return

    group, match_num, score = args[0].upper(), int(args[1]), args[2]
    data = load_data()
    players = data["players"]
    fixtures = data["group_fixtures"].get(group, [])
    scores = data.setdefault("scores", {})

    if match_num > len(fixtures):
        await update.message.reply_text("❌ Invalid match number.")
        return

    match = fixtures[match_num - 1]
    scores[f"{group}_{match_num}"] = {
        "teams": match,
        "score": score
    }
    save_data(data)

    home, away = players[match[0]], players[match[1]]
    await update.message.reply_text(f"✅ Recorded: {home['team']} {score} {away['team']}")

    # Knockout logic (auto detect if group done)
    total_group_matches = sum(len(v) for v in data["group_fixtures"].values())
    if len(scores) == total_group_matches:
        await generate_knockouts(context)
# === Knockout Generator ===
async def generate_knockouts(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    scores = data.get("scores", {})
    players = data["players"]

    # Build group standings
    standings = {g: {} for g in "ABCDEFGH"}
    for key, match in scores.items():
        group = key.split("_")[0]
        p1, p2 = match["teams"]
        s1, s2 = map(int, match["score"].split("-"))

        def update(uid, gf, ga, win, draw):
            team = standings[group].setdefault(uid, {"pts": 0, "gf": 0, "ga": 0})
            team["gf"] += gf
            team["ga"] += ga
            team["pts"] += 3 if win else 1 if draw else 0

        if s1 > s2:
            update(p1, s1, s2, win=1, draw=0)
            update(p2, s2, s1, win=0, draw=0)
        elif s2 > s1:
            update(p2, s2, s1, win=1, draw=0)
            update(p1, s1, s2, win=0, draw=0)
        else:
            update(p1, s1, s2, win=0, draw=1)
            update(p2, s2, s1, win=0, draw=1)

    top_16 = []
    for group, table in standings.items():
        if len(table) < 4:
            return
        sorted_teams = sorted(table.items(), key=lambda x: (-x[1]["pts"], -(x[1]["gf"] - x[1]["ga"]), -x[1]["gf"]))
        top_16.extend([sorted_teams[0][0], sorted_teams[1][0]])

    random.shuffle(top_16)
    round_16 = [[top_16[i], top_16[i+1]] for i in range(0, 16, 2)]
    data["knockouts"] = {"round_of_16": round_16}
    save_data(data)

    for p1, p2 in round_16:
        t1 = players[p1]["team"]
        t2 = players[p2]["team"]
        await context.bot.send_message(chat_id=GROUP_ID, text=f"🏆 Knockout Match: {t1} vs {t2}")
        await context.bot.send_message(chat_id=int(p1), text=f"🎯 You qualified for knockouts!")
        await context.bot.send_message(chat_id=int(p2), text=f"🎯 You qualified for knockouts!")

# === Main & Handlers ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register)],
        states={
            REGISTER_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_team)],
            ENTER_PES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pes)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("fixtures", fixtures))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("addrule", addrule))
    app.add_handler(CommandHandler("addscore", addscore))

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
