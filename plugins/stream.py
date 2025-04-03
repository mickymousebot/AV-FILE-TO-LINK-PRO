import asyncio
import os
import time
from datetime import datetime, timedelta
from database.users_db import db
from web.utils.file_properties import get_hash
from pyrogram import Client, filters, enums
from info import URL, BOT_USERNAME, BIN_CHANNEL, BAN_ALERT, FSUB, CHANNEL, ADMINS
from utils import get_size
from Script import script
from pyrogram.errors import FloodWait
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.avbot import is_user_joined, is_user_allowed

# Premium Plans Configuration
PLANS = {
    "bronze": {
        "name": "Bronze Plan",
        "duration": 30,  # days
        "files": 150,
        "price": "₹99"
    },
    "silver": {
        "name": "Silver Plan",
        "duration": 90,  # days
        "files": 350,
        "price": "₹249"
    },
    "gold": {
        "name": "Gold Plan",
        "duration": 365,  # days
        "files": "Unlimited",
        "price": "₹799"
    }
}

@Client.on_message((filters.private) & (filters.document | filters.video | filters.audio), group=4)
async def private_receive_handler(c: Client, m: Message):
    if FSUB:
        if not await is_user_joined(c, m):
            return
                
    ban_chk = await db.is_banned(int(m.from_user.id))
    if ban_chk == True:
        return await m.reply(BAN_ALERT)
    
    user_id = m.from_user.id

    # Check if user is premium
    premium = await db.is_premium(user_id)
    if premium:
        expiry_date = await db.get_expiry_date(user_id)
        if expiry_date and datetime.now() > expiry_date:
            await db.remove_premium(user_id)
            await m.reply_text("⚠️ Your premium plan has expired! Renew to continue enjoying premium benefits.")
            premium = False
    
    if not premium:
        is_allowed, remaining_time = await is_user_allowed(user_id)
        if not is_allowed:
            await m.reply_text(
                f"🚫 **Daily Limit Reached!**\n\n"
                f"You can only upload 10 files per day for free.\n"
                f"Upgrade to premium for more uploads!\n\n"
                f"Use /planinfo to see premium plans",
                quote=True
            )
            return

    file_id = m.document or m.video or m.audio
    file_name = file_id.file_name if file_id.file_name else None
    file_size = get_size(file_id.file_size)

    try:
        msg = await m.forward(chat_id=BIN_CHANNEL)
        
        stream = f"{URL}watch/{msg.id}?hash={get_hash(msg)}"
        download = f"{URL}{msg.id}?hash={get_hash(msg)}"
        file_link = f"https://t.me/{BOT_USERNAME}?start=file_{msg.id}"
        share_link = f"https://t.me/share/url?url={file_link}"
        
        await msg.reply_text(
            text=f"Requested By: [{m.from_user.first_name}](tg://user?id={m.from_user.id})\nUser ID: {m.from_user.id}\nPremium: {'✅' if premium else '❌'}\nStream Link: {stream}",
            disable_web_page_preview=True, quote=True
        )

        if file_name:
            await m.reply_text(
                text=script.CAPTION_TXT.format(CHANNEL, file_name, file_size, stream, download),
                quote=True,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(" Stream ", url=stream),
                        InlineKeyboardButton(" Download ", url=download)
                    ],
                    [
                        InlineKeyboardButton('Get File', url=file_link),
                        InlineKeyboardButton('Share', url=share_link)
                    ],
                    [
                        InlineKeyboardButton('Upgrade Plan', callback_data='premium_plan')
                    ],
                    [
                        InlineKeyboardButton('Close', callback_data='close_data')
                    ]
                ])
            )
        else:
            await m.reply_text(
                text=script.CAPTION2_TXT.format(CHANNEL, file_name, file_size, download),
                quote=True,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(" Download ", url=download),
                        InlineKeyboardButton('Get File', url=file_link)
                    ],
                    [
                        InlineKeyboardButton('Share', url=share_link)
                    ],
                    [
                        InlineKeyboardButton('Upgrade Plan', callback_data='premium_plan')
                    ],
                    [
                        InlineKeyboardButton('Close', callback_data='close_data')
                    ]
                ])
            )

    except FloodWait as e:
        print(f"Sleeping for {e.value}s")
        await asyncio.sleep(e.value)
        await c.send_message(
            chat_id=BIN_CHANNEL,
            text=f"Gᴏᴛ FʟᴏᴏᴅWᴀɪᴛ ᴏғ {e.value}s from [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n\n**𝚄𝚜𝚎𝚛 𝙸𝙳 :** `{m.from_user.id}`",
            disable_web_page_preview=True
        )

@Client.on_message(filters.command("planinfo") & filters.private)
async def plan_info(c: Client, m: Message):
    text = "🌟 **Premium Plans Available** 🌟\n\n"
    for plan_id, details in PLANS.items():
        text += (
            f"🔹 **{details['name']}**\n"
            f"📅 Duration: {details['duration']} days\n"
            f"📁 Files: {details['files']}\n"
            f"💰 Price: {details['price']}\n\n"
        )
    text += (
        "To purchase a plan, contact @BOT_OWNER26\n\n"
        "After payment, send receipt to admin with command:\n"
        "/approve <user_id> <plan> <payment_details>"
    )
    await m.reply_text(text, quote=True)

@Client.on_message(filters.command("myplan") & filters.private)
async def my_plan(c: Client, m: Message):
    user_id = m.from_user.id
    premium = await db.is_premium(user_id)
    
    if not premium:
        await m.reply_text(
            "You don't have an active premium plan.\n\n"
            "Free users can upload 10 files per day.\n"
            "Use /planinfo to see premium plans.",
            quote=True
        )
        return
    
    expiry_date = await db.get_expiry_date(user_id)
    plan_details = await db.get_premium_plan(user_id)
    
    if expiry_date and datetime.now() > expiry_date:
        await db.remove_premium(user_id)
        await m.reply_text(
            "⚠️ Your premium plan has expired! Renew to continue enjoying premium benefits.",
            quote=True
        )
        return
    
    remaining_days = (expiry_date - datetime.now()).days if expiry_date else 0
    
    await m.reply_text(
        f"🌟 **Your Premium Plan Details** 🌟\n\n"
        f"🔹 Plan: {plan_details.get('plan_name', 'Premium')}\n"
        f"📅 Expiry Date: {expiry_date.strftime('%d %B %Y') if expiry_date else 'Lifetime'}\n"
        f"⏳ Remaining Days: {remaining_days}\n"
        f"📁 Files Allowed: {plan_details.get('files_allowed', 'Unlimited')}",
        quote=True
    )

@Client.on_message(filters.command("approve") & filters.user(ADMINS))
async def approve_user(c: Client, m: Message):
    if len(m.command) < 4:
        await m.reply_text(
            "Usage: /approve <user_id> <plan> <payment_details>\n\n"
            "Available plans: bronze, silver, gold",
            quote=True
        )
        return
    
    try:
        user_id = int(m.command[1])
        plan = m.command[2].lower()
        payment_details = " ".join(m.command[3:])
        
        if plan not in PLANS:
            await m.reply_text(
                "Invalid plan! Available plans: bronze, silver, gold",
                quote=True
            )
            return
        
        plan_details = PLANS[plan]
        expiry_date = datetime.now() + timedelta(days=plan_details["duration"])
        
        await db.add_premium(
            user_id=user_id,
            plan_name=plan_details["name"],
            files_allowed=plan_details["files"],
            expiry_date=expiry_date,
            payment_details=payment_details
        )
        
        await m.reply_text(
            f"✅ Successfully approved user {user_id} for {plan_details['name']}\n"
            f"Expiry Date: {expiry_date.strftime('%d %B %Y')}",
            quote=True
        )
        
        try:
            await c.send_message(
                chat_id=user_id,
                text=f"🎉 Congratulations! Your premium plan has been activated!\n\n"
                     f"🔹 Plan: {plan_details['name']}\n"
                     f"📅 Expiry Date: {expiry_date.strftime('%d %B %Y')}\n"
                     f"📁 Files Allowed: {plan_details['files']}\n\n"
                     f"Thank you for your purchase!"
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")

    except Exception as e:
        await m.reply_text(f"Error: {str(e)}", quote=True)

@Client.on_message(filters.command("unapprove") & filters.user(ADMINS))
async def unapprove_user(c: Client, m: Message):
    if len(m.command) < 2:
        await m.reply_text("Usage: /unapprove <user_id>", quote=True)
        return
    
    try:
        user_id = int(m.command[1])
        await db.remove_premium(user_id)
        await m.reply_text(f"✅ Successfully removed premium status from user {user_id}", quote=True)
        
        try:
            await c.send_message(
                chat_id=user_id,
                text="⚠️ Your premium plan has been removed by admin."
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")
            
    except Exception as e:
        await m.reply_text(f"Error: {str(e)}", quote=True)

@Client.on_message(filters.command("approvedusers") & filters.user(ADMINS))
async def approved_users(c: Client, m: Message):
    users = await db.get_all_premium_users()
    if not users:
        await m.reply_text("No premium users found.", quote=True)
        return
    
    text = "🌟 **Premium Users List** 🌟\n\n"
    for user in users:
        expiry_date = user.get("expiry_date", "Lifetime")
        if isinstance(expiry_date, datetime):
            expiry_date = expiry_date.strftime('%d %B %Y')
            remaining_days = (user['expiry_date'] - datetime.now()).days
            status = "✅ Active" if remaining_days > 0 else "❌ Expired"
        else:
            status = "✅ Active"
            remaining_days = "∞"
        
        text += (
            f"👤 User ID: {user['user_id']}\n"
            f"🔹 Plan: {user.get('plan_name', 'Premium')}\n"
            f"📅 Expiry: {expiry_date}\n"
            f"⏳ Days Left: {remaining_days}\n"
            f"Status: {status}\n\n"
        )
    
    await m.reply_text(text, quote=True)

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP
