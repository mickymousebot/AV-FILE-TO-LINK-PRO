import asyncio
import os
import time
from datetime import datetime, timedelta
from database.users_db import db
from web.utils.file_properties import get_hash
from pyrogram import Client, filters, enums, idle
from info import URL, BOT_USERNAME, BIN_CHANNEL, BAN_ALERT, FSUB, CHANNEL, ADMINS
from utils import get_size
from Script import script
from pyrogram.errors import FloodWait
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.avbot import is_user_joined, is_user_allowed

# Professional Premium Plans Configuration
PLANS = {
    "trial": {
        "name": "1-Day Trial",
        "duration": 1,  # 1 day
        "files": 50,
        "price": "FREE"
    },
    "1month": {
        "name": "1 Month Plan",
        "duration": 30,
        "files": 150,
        "price": "₹99"
    },
    "3months": {
        "name": "3 Months Plan",
        "duration": 90,
        "files": 350,
        "price": "₹249"
    },
    "1year": {
        "name": "1 Year Plan",
        "duration": 365,
        "files": "Unlimited",
        "price": "₹799"
    }
}

# Background task for checking expired plans
async def check_expired_plans(client):
    while True:
        try:
            current_time = datetime.now()
            print(f"Checking for expired plans at {current_time}")
            
            expired_users = await db.premiumUsers.find({
                "expiry_date": {"$lt": current_time}
            }).to_list(length=None)
            
            print(f"Found {len(expired_users)} expired plans")
            
            for user in expired_users:
                user_id = user['user_id']
                plan_name = user.get('plan_name', 'Unknown Plan')
                
                # Remove premium status
                success = await db.remove_premium(user_id)
                if success:
                    print(f"Removed expired plan for user {user_id} ({plan_name})")
                    
                    # Notify user
                    try:
                        await client.send_message(
                            chat_id=user_id,
                            text="⏳ Your premium plan has expired\n\n"
                                 "To continue enjoying premium features:\n"
                                 "1. View available plans: /plans\n"
                                 "2. Contact @BOT_OWNER26 to renew"
                        )
                    except Exception as e:
                        print(f"Could not notify user {user_id}: {str(e)}")
                else:
                    print(f"Failed to remove expired plan for user {user_id}")
                
        except Exception as e:
            print(f"Error in expired plans check: {str(e)}")
        
        # Check every 6 hours (21600 seconds)
        await asyncio.sleep(21600)

# Startup handler
async def startup(client):
    # Start the background task
    asyncio.create_task(check_expired_plans(client))
    print("✅ Bot started successfully")
    print("🔍 Premium plan expiry checker is running")

@Client.on_message((filters.private) & (filters.document | filters.video | filters.audio), group=4)
async def private_receive_handler(c: Client, m: Message):
    if FSUB:
        if not await is_user_joined(c, m):
            return
                
    ban_chk = await db.is_banned(int(m.from_user.id))
    if ban_chk == True:
        return await m.reply(BAN_ALERT)
    
    user_id = m.from_user.id

    # Check premium status with expiry validation
    premium = await db.is_premium(user_id)
    if premium:
        expiry_date = await db.get_expiry_date(user_id)
        if expiry_date and datetime.now() > expiry_date:
            await db.remove_premium(user_id)
            await m.reply_text(
                "⏳ Your premium subscription has expired.\n\n"
                "To continue enjoying premium benefits, please renew your plan.\n"
                "Use /plans to view available subscription options.",
                quote=True
            )
            premium = False
    
    if not premium:
        is_allowed, remaining_time = await is_user_allowed(user_id)
        if not is_allowed:
            await m.reply_text(
                "📊 **Daily Upload Limit Reached**\n\n"
                "Free users are limited to 10 uploads per day.\n\n"
                "Consider our premium plans for:\n"
                "• Higher upload limits\n"
                "• Priority processing\n"
                "• Extended file retention\n\n"
                "Explore plans: /plans",
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
            text=f"📤 New File Upload\n\n"
                 f"👤 User: [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n"
                 f"🆔 ID: {m.from_user.id}\n"
                 f"💎 Premium: {'✅ Active' if premium else '❌ Inactive'}\n"
                 f"🔗 Stream: {stream}",
            disable_web_page_preview=True, 
            quote=True
        )

        if file_name:
            await m.reply_text(
                text=script.CAPTION_TXT.format(CHANNEL, file_name, file_size, stream, download),
                quote=True,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📺 Stream", url=stream),
                        InlineKeyboardButton("⬇️ Download", url=download)
                    ],
                    [
                        InlineKeyboardButton('📂 Get File', url=file_link),
                        InlineKeyboardButton('🔗 Share', url=share_link)
                    ],
                    [
                        InlineKeyboardButton('❌ Close', callback_data='close_data')
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
                        InlineKeyboardButton("⬇️ Download", url=download),
                        InlineKeyboardButton('📂 Get File', url=file_link)
                    ],
                    [
                        InlineKeyboardButton('🔗 Share', url=share_link)
                    ],
                    [
                        InlineKeyboardButton('❌ Close', callback_data='close_data')
                    ]
                ])
            )

    except FloodWait as e:
        print(f"⏳ FloodWait: Sleeping for {e.value}s")
        await asyncio.sleep(e.value)
        await c.send_message(
            chat_id=BIN_CHANNEL,
            text=f"⚠️ FloodWait Detected\n\n"
                 f"⏱ Duration: {e.value} seconds\n"
                 f"👤 User: [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n"
                 f"🆔 ID: `{m.from_user.id}`",
            disable_web_page_preview=True
        )

@Client.on_message(filters.command(["planinfo", "plans"]) & filters.private)
async def plan_info(c: Client, m: Message):
    text = "✨ **Premium Subscription Plans** ✨\n\n"
    for plan_id, details in PLANS.items():
        duration_text = "1 day" if details["duration"] == 1 else f"{details['duration']} days"
        text += (
            f"🌟 **{details['name']}**\n"
            f"⏳ Duration: {duration_text}\n"
            f"📁 File Limit: {details['files']}\n"
            f"💵 Price: {details['price']}\n\n"
        )
    
    text += (
        "🔹 To subscribe:\n"
        "1. Contact @BOT_OWNER26\n"
        "2. Make payment\n"
        "3. Send receipt with command:\n"
        "<code>/approve &lt;user_id&gt; &lt;plan&gt; &lt;payment_details&gt;</code>\n\n"
        "Try our free 1-day trial with 50 file uploads!"
    )
    
    await m.reply_text(text, quote=True)

@Client.on_message(filters.command("myplan") & filters.private)
async def my_plan(c: Client, m: Message):
    user_id = m.from_user.id
    premium = await db.is_premium(user_id)
    
    if not premium:
        await m.reply_text(
            "🔹 **Account Status: Free Tier**\n\n"
            "• Daily upload limit: 10 files\n"
            "• No expiration date\n\n"
            "Upgrade to premium for enhanced features:\n"
            "/plans",
            quote=True
        )
        return
    
    expiry_date = await db.get_expiry_date(user_id)
    plan_details = await db.get_premium_plan(user_id)
    
    if expiry_date and datetime.now() > expiry_date:
        await db.remove_premium(user_id)
        await m.reply_text(
            "⏳ Your premium subscription has expired.\n\n"
            "To renew your plan, please visit:\n"
            "/plans",
            quote=True
        )
        return
    
    remaining_days = (expiry_date - datetime.now()).days if expiry_date else 0
    
    await m.reply_text(
        "✨ **Your Premium Subscription** ✨\n\n"
        f"🔹 Plan: {plan_details.get('plan_name', 'Premium')}\n"
        f"📅 Expiry: {expiry_date.strftime('%d %B %Y') if expiry_date else 'Lifetime'}\n"
        f"⏳ Remaining: {remaining_days} days\n"
        f"📁 File Limit: {plan_details.get('files_allowed', 'Unlimited')}\n\n"
        "Thank you for being a valued subscriber!",
        quote=True
    )

@Client.on_message(filters.command("approve") & filters.user(ADMINS))
async def approve_user(c: Client, m: Message):
    if len(m.command) < 4:
        await m.reply_text(
            "🛠 **Usage:**\n"
            "<code>/approve &lt;user_id&gt; &lt;plan&gt; &lt;payment_details&gt;</code>\n\n"
            "📋 Available plans:\n"
            "- trial (1 day, 50 files)\n"
            "- 1month (30 days, 150 files)\n"
            "- 3months (90 days, 350 files)\n"
            "- 1year (365 days, Unlimited files)",
            quote=True
        )
        return
    
    try:
        user_id = int(m.command[1])
        plan = m.command[2].lower()
        payment_details = " ".join(m.command[3:])
        
        if plan not in PLANS:
            await m.reply_text(
                "❌ Invalid plan specified.\n\n"
                "Available plans:\n"
                "- trial\n"
                "- 1month\n"
                "- 3months\n"
                "- 1year",
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
            f"✅ Successfully activated {plan_details['name']} for user {user_id}\n"
            f"📅 Expires on: {expiry_date.strftime('%d %B %Y')}\n"
            f"📁 File Limit: {plan_details['files']}",
            quote=True
        )
        
        try:
            await c.send_message(
                chat_id=user_id,
                text=f"🎉 **Premium Plan Activated!** 🎉\n\n"
                     f"🔹 Plan: {plan_details['name']}\n"
                     f"📅 Expiry: {expiry_date.strftime('%d %B %Y')}\n"
                     f"📁 Files: {plan_details['files']}\n\n"
                     f"Thank you for subscribing! Enjoy your premium benefits."
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")

    except Exception as e:
        await m.reply_text(
            f"❌ Error processing request:\n<code>{str(e)}</code>",
            quote=True
        )

@Client.on_message(filters.command("unapprove") & filters.user(ADMINS))
async def unapprove_user(c: Client, m: Message):
    if len(m.command) < 2:
        await m.reply_text(
            "🛠 **Usage:**\n"
            "<code>/unapprove &lt;user_id&gt;</code>",
            quote=True
        )
        return
    
    try:
        user_id = int(m.command[1])
        await db.remove_premium(user_id)
        await m.reply_text(
            f"✅ Removed premium status from user {user_id}",
            quote=True
        )
        
        try:
            await c.send_message(
                chat_id=user_id,
                text="ℹ️ Your premium subscription has been removed by admin.\n\n"
                     "You now have free account limitations."
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")
            
    except Exception as e:
        await m.reply_text(
            f"❌ Error processing request:\n<code>{str(e)}</code>",
            quote=True
        )

@Client.on_message(filters.command("approvedusers") & filters.user(ADMINS))
async def approved_users(c: Client, m: Message):
    users = await db.get_all_premium_users()
    if not users:
        await m.reply_text("ℹ️ No active premium subscribers found.", quote=True)
        return
    
    text = "✨ **Premium Subscribers List** ✨\n\n"
    for user in users:
        expiry_date = user.get("expiry_date")
        if isinstance(expiry_date, datetime):
            expiry_str = expiry_date.strftime('%d %B %Y')
            remaining_days = (expiry_date - datetime.now()).days
            status = "✅ Active" if remaining_days > 0 else "❌ Expired"
        else:
            expiry_str = "Lifetime"
            remaining_days = "∞"
            status = "✅ Active"
        
        text += (
            f"👤 User ID: <code>{user['user_id']}</code>\n"
            f"📝 Plan: {user.get('plan_name', 'Premium')}\n"
            f"📅 Expiry: {expiry_str}\n"
            f"⏳ Status: {status}\n\n"
        )
    
    await m.reply_text(text, quote=True)

# Main bot runner
async def main():
    await Client.start()
    await startup(Client)
    await idle()
    await Client.stop()

if __name__ == "__main__":
    Client.run(main())

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP
