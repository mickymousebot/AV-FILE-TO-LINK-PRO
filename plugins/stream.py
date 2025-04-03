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
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from plugins.avbot import is_user_joined, is_user_allowed

# Premium Plans Configuration
PLANS = {
    "trial": {
        "name": "🌟 Trial Plan",
        "duration": 1,  # day
        "files": 50,
        "price": "FREE",
        "description": "Perfect for testing our premium features"
    },
    "1month": {
        "name": "💎 1 Month Plan",
        "duration": 30,
        "files": 500,
        "price": "₹99",
        "description": "Best for regular users with moderate needs"
    },
    "3months": {
        "name": "🔥 3 Months Plan",
        "duration": 90,
        "files": 1500,
        "price": "₹249",
        "description": "Great value with 3 months of premium access"
    },
    "1year": {
        "name": "✨ 1 Year Plan",
        "duration": 365,
        "files": float('inf'),  # Unlimited
        "price": "₹799",
        "description": "Ultimate plan with maximum benefits"
    }
}

@Client.on_callback_query(filters.regex('^trial_info$'))
async def trial_info_callback(c: Client, query: CallbackQuery):
    await query.answer()
    await my_plan(c, query.message)

@Client.on_callback_query(filters.regex('^premium_plans$'))
async def premium_plans_callback(c: Client, query: CallbackQuery):
    await query.answer()
    await plan_info(c, query.message)

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
            await m.reply_text(
                "⚠️ Your premium subscription has expired!\n\n"
                "You've been reverted to free tier with daily limits.\n"
                "Renew your plan to continue enjoying premium benefits.",
                quote=True
            )
            premium = False
    
    if not premium:
        is_allowed, remaining_time = await is_user_allowed(user_id)
        if not is_allowed:
            await m.reply_text(
                "📊 **Daily Upload Limit Reached**\n\n"
                "Free users can upload 10 files per day.\n\n"
                "🔹 Upgrade to premium for:\n"
                "- Higher daily limits\n"
                "- Priority processing\n"
                "- Extended file retention\n\n"
                "Try our free trial with /trial or see plans with /plans",
                quote=True
            )
            return
    else:
        # Check premium user's file limit
        plan_details = await db.get_premium_plan(user_id)
        files_uploaded = await db.get_user_files_uploaded(user_id)
        files_limit = plan_details.get("files_allowed", 0)
        
        # Convert to int if not unlimited
        if files_limit != float('inf'):
            files_limit = int(files_limit)
            
        if files_uploaded >= files_limit:
            await m.reply_text(
                "⚠️ **Plan Limit Reached**\n\n"
                f"You've reached your plan's limit of {files_limit} files.\n\n"
                "🔹 Options:\n"
                "- Wait for next billing cycle\n"
                "- Upgrade to higher plan with /plans\n"
                "- Contact support for assistance",
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
            text=f"📥 New File Upload\n\n"
                 f"👤 User: [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n"
                 f"🆔 ID: {m.from_user.id}\n"
                 f"💎 Premium: {'✅ Active' if premium else '❌ Inactive'}\n"
                 f"📁 Files Uploaded: {files_uploaded + 1}/{files_limit if files_limit != float('inf') else '∞'}\n"
                 f"🔗 Stream: {stream}",
            disable_web_page_preview=True, quote=True
        )

        # Update user's file count in database
        await db.update_user_files_uploaded(user_id, files_uploaded + 1)

        buttons = [
            [
                InlineKeyboardButton("📺 Stream", url=stream),
                InlineKeyboardButton("📥 Download", url=download)
            ],
            [
                InlineKeyboardButton('🔗 Direct Link', url=file_link),
                InlineKeyboardButton('↗️ Share', url=share_link)
            ]
        ]

        if not premium:
            buttons.append([InlineKeyboardButton('✨ Upgrade Now', callback_data='premium_plans')])
        else:
            # Show remaining files for premium users (except unlimited plans)
            if files_limit != float('inf'):
                remaining_files = files_limit - (files_uploaded + 1)
                if remaining_files <= 10:  # Show warning if few files left
                    buttons.append([InlineKeyboardButton(
                        f'⚠️ {remaining_files} files remaining - Upgrade', 
                        callback_data='premium_plans'
                    )])

        buttons.append([InlineKeyboardButton('❌ Close', callback_data='close_data')])

        if file_name:
            caption = script.CAPTION_TXT.format(
                CHANNEL, 
                file_name, 
                file_size, 
                stream, 
                download
            )
        else:
            caption = script.CAPTION2_TXT.format(
                CHANNEL, 
                "Unnamed File", 
                file_size, 
                download
            )

        await m.reply_text(
            text=caption,
            quote=True,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except FloodWait as e:
        print(f"Sleeping for {e.value}s")
        await asyncio.sleep(e.value)
        await c.send_message(
            chat_id=BIN_CHANNEL,
            text=f"⚠️ FloodWait Detected\n\n"
                 f"⏳ Delay: {e.value}s\n"
                 f"👤 User: [{m.from_user.first_name}](tg://user?id={m.from_user.id})\n"
                 f"🆔 ID: `{m.from_user.id}`",
            disable_web_page_preview=True
        )

@Client.on_message(filters.command(["plans", "planinfo"]) & filters.private)
async def plan_info(c: Client, m: Message):
    text = "🚀 **Premium Subscription Plans** 🚀\n\n"
    text += "Choose the plan that fits your needs:\n\n"
    
    for plan_id, details in PLANS.items():
        if plan_id == "trial":
            continue  # We'll handle trial separately
            
        text += (
            f"{details['name']}\n"
            f"⏳ Duration: {details['duration']} days\n"
            f"📁 Files: {'Unlimited' if details['files'] == float('inf') else details['files']}\n"
            f"💰 Price: {details['price']}\n"
            f"🔹 {details['description']}\n\n"
        )
    
    text += (
        "🎁 Special Offer: Try our FREE trial with /trial\n\n"
        "💳 Payment Methods: UPI, PayTM, PayPal\n"
        "📨 After payment, contact @BOT_OWNER26 with:\n"
        "/approve <user_id> <plan> <transaction_id>"
    )
    
    await m.reply_text(
        text,
        quote=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 View Trial Plan", callback_data="trial_info")]
        ])
    )

@Client.on_message(filters.command("trial") & filters.private)
async def trial_plan(c: Client, m: Message):
    user_id = m.from_user.id
    
    # Check if user already used trial
    trial_used = await db.check_trial_used(user_id)
    if trial_used:
        await m.reply_text(
            "⚠️ You've already used your free trial.\n\n"
            "Explore our affordable premium plans with /plans",
            quote=True
        )
        return
    
    # Activate trial plan
    plan_details = PLANS["trial"]
    expiry_date = datetime.now() + timedelta(days=plan_details["duration"])
    
    await db.add_premium(
        user_id=user_id,
        plan_name=plan_details["name"],
        files_allowed=plan_details["files"],
        expiry_date=expiry_date,
        payment_details="Trial Plan",
        is_trial=True
    )
    
    # Reset file count for new plan
    await db.reset_user_files_uploaded(user_id)
    
    await m.reply_text(
        "🎉 Your Free Trial Has Been Activated!\n\n"
        f"🔹 Plan: {plan_details['name']}\n"
        f"⏳ Duration: {plan_details['duration']} day\n"
        f"📁 Files: {plan_details['files']}\n\n"
        "Start uploading now and experience premium features!\n\n"
        "Upgrade anytime with /plans to continue after trial ends.",
        quote=True
    )

@Client.on_message(filters.command("myplan") & filters.private)
async def my_plan(c: Client, m: Message):
    user_id = m.from_user.id
    premium = await db.is_premium(user_id)
    
    if not premium:
        is_allowed, remaining_time = await is_user_allowed(user_id)
        remaining_files = 10 - await db.get_user_files_uploaded(user_id)
        
        await m.reply_text(
            "🔹 **Your Current Plan: Free Tier**\n\n"
            f"📊 Daily Upload Limit: {remaining_files}/10 files\n"
            f"⏳ Resets in: {remaining_time}\n\n"
            "Upgrade to premium for more benefits with /plans\n"
            "Try our free trial with /trial",
            quote=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 View Plans", callback_data="premium_plans")],
                [InlineKeyboardButton("🎁 Try Free Trial", callback_data="trial_info")]
            ])
        )
        return
    
    expiry_date = await db.get_expiry_date(user_id)
    plan_details = await db.get_premium_plan(user_id)
    is_trial = await db.check_trial_used(user_id)
    files_uploaded = await db.get_user_files_uploaded(user_id)
    files_limit = plan_details.get("files_allowed", 0)
    
    if expiry_date and datetime.now() > expiry_date:
        await db.remove_premium(user_id)
        await m.reply_text(
            "⚠️ Your subscription has expired!\n\n"
            "You've been reverted to free tier with daily limits.\n"
            "Renew your plan to continue premium access with /plans",
            quote=True
        )
        return
    
    remaining_time = expiry_date - datetime.now()
    remaining_days = remaining_time.days
    remaining_hours = remaining_time.seconds // 3600
    
    plan_type = "🎁 Trial" if is_trial else "💎 Premium"
    
    text = (
        f"🔹 **Your Current Plan: {plan_details.get('plan_name', 'Premium')}**\n\n"
        f"📝 Type: {plan_type}\n"
        f"⏳ Remaining: {remaining_days} days, {remaining_hours} hours\n"
        f"📅 Expires on: {expiry_date.strftime('%d %B %Y %H:%M') if expiry_date else 'Lifetime'}\n"
        f"📁 Files: {files_uploaded}/{'Unlimited' if files_limit == float('inf') else files_limit}\n\n"
    )
    
    if is_trial:
        text += "🔄 Your trial will end soon. Upgrade now to continue premium benefits!\n"
    elif files_limit != float('inf') and files_uploaded >= files_limit * 0.9:  # 90% usage warning
        text += "⚠️ You're approaching your plan's file limit. Consider upgrading!\n"
    else:
        text += "🔸 Thank you for being a premium user!\n"
    
    buttons = []
    if is_trial or (files_limit != float('inf') and files_uploaded >= files_limit * 0.8):
        buttons.append([InlineKeyboardButton("💎 Upgrade Plan", callback_data="premium_plans")])
    
    await m.reply_text(
        text,
        quote=True,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )

@Client.on_message(filters.command("approve") & filters.user(ADMINS))
async def approve_user(c: Client, m: Message):
    if len(m.command) < 4:
        await m.reply_text(
            "📝 **Usage:**\n"
            "/approve <user_id> <plan> <transaction_id>\n\n"
            "📋 Available Plans:\n"
            "- trial (1 day, 50 files)\n"
            "- 1month (30 days, 500 files)\n"
            "- 3months (90 days, 1500 files)\n"
            "- 1year (365 days, unlimited)\n\n"
            "Example:\n"
            "/approve 12345678 1month PAYTM1234",
            quote=True
        )
        return
    
    try:
        user_id = int(m.command[1])
        plan = m.command[2].lower()
        transaction_id = " ".join(m.command[3:])
        
        if plan not in PLANS:
            await m.reply_text(
                "❌ Invalid plan! Available plans:\n"
                "trial, 1month, 3months, 1year",
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
            payment_details=transaction_id,
            is_trial=(plan == "trial")
        )
        
        # Reset file count for new plan
        await db.reset_user_files_uploaded(user_id)
        
        await m.reply_text(
            f"✅ Successfully activated {plan_details['name']} for user {user_id}\n\n"
            f"📅 Expiry: {expiry_date.strftime('%d %B %Y %H:%M')}\n"
            f"📝 Transaction: {transaction_id}",
            quote=True
        )
        
        try:
            await c.send_message(
                chat_id=user_id,
                text=f"🎉 **Premium Subscription Activated!**\n\n"
                     f"🔹 Plan: {plan_details['name']}\n"
                     f"⏳ Duration: {plan_details['duration']} days\n"
                     f"📁 Files: {'Unlimited' if plan_details['files'] == float('inf') else plan_details['files']}\n"
                     f"📅 Expires on: {expiry_date.strftime('%d %B %Y')}\n\n"
                     f"Thank you for choosing our service!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 View Plan", callback_data="myplan")]
                ])
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")

    except Exception as e:
        await m.reply_text(f"❌ Error: {str(e)}", quote=True)

@Client.on_message(filters.command("unapprove") & filters.user(ADMINS))
async def unapprove_user(c: Client, m: Message):
    if len(m.command) < 2:
        await m.reply_text("📝 Usage: /unapprove <user_id>", quote=True)
        return
    
    try:
        user_id = int(m.command[1])
        user_data = await db.get_premium_plan(user_id)
        
        if not user_data:
            await m.reply_text(f"ℹ️ User {user_id} doesn't have an active premium plan.", quote=True)
            return
            
        await db.remove_premium(user_id)
        await m.reply_text(
            f"✅ Successfully removed premium status from user {user_id}\n\n"
            f"🔹 Plan: {user_data.get('plan_name', 'Unknown')}\n"
            f"🆔 User ID: {user_id}",
            quote=True
        )
        
        try:
            await c.send_message(
                chat_id=user_id,
                text="⚠️ **Premium Subscription Update**\n\n"
                     "Your premium access has been removed by admin.\n\n"
                     "Contact support if this was a mistake."
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")
            
    except Exception as e:
        await m.reply_text(f"❌ Error: {str(e)}", quote=True)

@Client.on_message(filters.command("approvedusers") & filters.user(ADMINS))
async def approved_users(c: Client, m: Message):
    users = await db.get_all_premium_users()
    if not users:
        await m.reply_text("ℹ️ No premium users found in database.", quote=True)
        return
    
    text = "📊 **Premium Users Report**\n\n"
    text += f"Total Premium Users: {len(users)}\n\n"
    
    active_users = 0
    expired_users = 0
    trial_users = 0
    
    for user in users:
        expiry_date = user.get("expiry_date")
        is_trial = user.get("is_trial", False)
        files_uploaded = await db.get_user_files_uploaded(user['user_id'])
        files_limit = user.get("files_allowed", 0)
        
        if is_trial:
            trial_users += 1
            status = "🎁 Trial"
        elif expiry_date and datetime.now() > expiry_date:
            expired_users += 1
            status = "❌ Expired"
        else:
            active_users += 1
            status = "✅ Active"
        
        if isinstance(expiry_date, datetime):
            remaining_days = (expiry_date - datetime.now()).days
            expiry_str = expiry_date.strftime('%d %b %Y')
        else:
            remaining_days = "∞"
            expiry_str = "Lifetime"
        
        text += (
            f"🆔 {user['user_id']} - {user.get('plan_name', 'Unknown')}\n"
            f"📅 {expiry_str} ({remaining_days} days) - {status}\n"
            f"📁 Files: {files_uploaded}/{'∞' if files_limit == float('inf') else files_limit}\n"
            f"📝 {user.get('payment_details', 'No details')}\n\n"
        )
    
    summary = (
        f"\n📈 **Summary**\n"
        f"✅ Active: {active_users}\n"
        f"🎁 Trial: {trial_users}\n"
        f"❌ Expired: {expired_users}"
    )
    
    # Split message if too long
    if len(text + summary) > 4000:
        part1 = text[:4000]
        await m.reply_text(part1, quote=True)
        await m.reply_text(summary, quote=True)
    else:
        await m.reply_text(text + summary, quote=True)

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP
