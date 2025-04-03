import re
import motor.motor_asyncio
from datetime import datetime, timedelta
from info import DATABASE_NAME, DATABASE_URI

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.bannedList = self.db.bannedList
        self.premiumUsers = self.db.premiumUsers

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            join_date = datetime.now(),
            last_used = datetime.now(),
            daily_uploads = 0,
            last_upload_date = datetime.now().date(),
            is_premium = False
        )

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        return self.col.find({})
        
#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP
    
    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})
        await self.premiumUsers.delete_many({'user_id': int(user_id)})

    async def ban_user(self, user_id):
        user = await self.bannedList.find_one({'banId': int(user_id)})
        if user:
            return False
        else:
            await self.bannedList.insert_one({'banId': int(user_id)})
            await self.premiumUsers.delete_many({'user_id': int(user_id)})
            return True
        
    async def is_banned(self, user_id):
        user = await self.bannedList.find_one({'banId': int(user_id)})
        return True if user else False

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP
    
    async def is_unbanned(self, user_id):
        try: 
            if await self.bannedList.find_one({'banId': int(user_id)}):
                await self.bannedList.delete_one({'banId': int(user_id)})
                return True
            else:
                return False
        except Exception as e:
            e = f'Failed to unban. Reason: {e}'
            print(e)
            return e

    # Premium User Methods
    async def add_premium(self, user_id, plan_name, files_allowed, expiry_date, payment_details):
        try:
            premium_data = {
                'user_id': int(user_id),
                'plan_name': plan_name,
                'files_allowed': files_allowed,
                'expiry_date': expiry_date,
                'payment_details': payment_details,
                'purchase_date': datetime.now()
            }
            await self.premiumUsers.insert_one(premium_data)
            await self.col.update_one(
                {'id': int(user_id)},
                {'$set': {'is_premium': True}}
            )
            return True
        except Exception as e:
            print(f"Error adding premium user: {e}")
            return False

    async def remove_premium(self, user_id):
        try:
            await self.premiumUsers.delete_many({'user_id': int(user_id)})
            await self.col.update_one(
                {'id': int(user_id)},
                {'$set': {'is_premium': False}}
            )
            return True
        except Exception as e:
            print(f"Error removing premium user: {e}")
            return False

    async def is_premium(self, user_id):
        try:
            # First check if user exists in premium collection
            premium_user = await self.premiumUsers.find_one({'user_id': int(user_id)})
            if premium_user:
                # Check if plan is expired
                if 'expiry_date' in premium_user and premium_user['expiry_date'] < datetime.now():
                    await self.remove_premium(user_id)
                    return False
                return True
            return False
        except Exception as e:
            print(f"Error checking premium status: {e}")
            return False

    async def get_expiry_date(self, user_id):
        try:
            premium_user = await self.premiumUsers.find_one({'user_id': int(user_id)})
            if premium_user:
                return premium_user.get('expiry_date')
            return None
        except Exception as e:
            print(f"Error getting expiry date: {e}")
            return None

    async def get_premium_plan(self, user_id):
        try:
            premium_user = await self.premiumUsers.find_one({'user_id': int(user_id)})
            if premium_user:
                return {
                    'plan_name': premium_user.get('plan_name'),
                    'files_allowed': premium_user.get('files_allowed'),
                    'expiry_date': premium_user.get('expiry_date'),
                    'purchase_date': premium_user.get('purchase_date')
                }
            return None
        except Exception as e:
            print(f"Error getting premium plan: {e}")
            return None

    async def get_all_premium_users(self):
        try:
            premium_users = []
            async for user in self.premiumUsers.find({}):
                premium_users.append({
                    'user_id': user.get('user_id'),
                    'plan_name': user.get('plan_name'),
                    'files_allowed': user.get('files_allowed'),
                    'expiry_date': user.get('expiry_date'),
                    'purchase_date': user.get('purchase_date')
                })
            return premium_users
        except Exception as e:
            print(f"Error getting all premium users: {e}")
            return []

    async def update_daily_uploads(self, user_id):
        try:
            user = await self.col.find_one({'id': int(user_id)})
            if user:
                current_date = datetime.now().date()
                last_upload_date = user.get('last_upload_date')
                
                if last_upload_date and last_upload_date == current_date:
                    await self.col.update_one(
                        {'id': int(user_id)},
                        {'$inc': {'daily_uploads': 1}}
                    )
                else:
                    await self.col.update_one(
                        {'id': int(user_id)},
                        {
                            '$set': {
                                'daily_uploads': 1,
                                'last_upload_date': current_date
                            }
                        }
                    )
                return True
            return False
        except Exception as e:
            print(f"Error updating daily uploads: {e}")
            return False

    async def get_daily_uploads(self, user_id):
        try:
            user = await self.col.find_one({'id': int(user_id)})
            if user:
                current_date = datetime.now().date()
                last_upload_date = user.get('last_upload_date')
                
                if last_upload_date and last_upload_date == current_date:
                    return user.get('daily_uploads', 0)
                else:
                    return 0
            return 0
        except Exception as e:
            print(f"Error getting daily uploads: {e}")
            return 0

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP

db = Database(DATABASE_URI, DATABASE_NAME)

#Dont Remove My Credit @AV_BOTz_UPDATE 
#This Repo Is By @BOT_OWNER26 
# For Any Kind Of Error Ask Us In Support Group @AV_SUPPORT_GROUP
