import motor.motor_asyncio
from datetime import datetime, timedelta
import asyncio  # Added this import
from info import DATABASE_NAME, DATABASE_URI

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.bannedList = self.db.bannedList
        self.premiumUsers = self.db.premiumUsers
        
        # Initialize indexes without creating a task
        self._init_task = asyncio.create_task(self._initialize())

    async def _initialize(self):
        """Initialize database indexes"""
        try:
            await self.create_indexes()
            print("✅ Database indexes created successfully")
        except Exception as e:
            print(f"❌ Error creating indexes: {e}")

    async def create_indexes(self):
        """Create database indexes for better performance"""
        await asyncio.gather(
            self.premiumUsers.create_index("user_id", unique=True),
            self.premiumUsers.create_index("expiry_date"),
            self.bannedList.create_index("banId", unique=True),
            self.col.create_index("id", unique=True)
        )

    def new_user(self, id, name):
        return {
            "id": id,
            "name": name,
            "join_date": datetime.now(),
            "last_used": datetime.now(),
            "daily_uploads": 0,
            "last_upload_date": datetime.now().date(),
            "is_premium": False,
            "total_uploads": 0
        }
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        return await self.col.find_one({'id': int(id)}) is not None
    
    async def total_users_count(self):
        return await self.col.count_documents({})

    async def get_all_users(self):
        return self.col.find({})
    
    async def delete_user(self, user_id):
        await asyncio.gather(
            self.col.delete_many({'id': int(user_id)}),
            self.premiumUsers.delete_many({'user_id': int(user_id)})
        )

    async def ban_user(self, user_id):
        if await self.bannedList.find_one({'banId': int(user_id)}):
            return False
        await asyncio.gather(
            self.bannedList.insert_one({'banId': int(user_id)}),
            self.remove_premium(user_id)
        )
        return True
        
    async def is_banned(self, user_id):
        return await self.bannedList.find_one({'banId': int(user_id)}) is not None
    
    async def is_unbanned(self, user_id):
        result = await self.bannedList.delete_one({'banId': int(user_id)})
        return result.deleted_count > 0

    # Premium User Methods
    async def add_premium(self, user_id, plan_name, files_allowed, expiry_date, payment_details):
        try:
            premium_data = {
                'user_id': int(user_id),
                'plan_name': plan_name,
                'files_allowed': files_allowed,
                'expiry_date': expiry_date,
                'payment_details': payment_details,
                'purchase_date': datetime.now(),
                'last_updated': datetime.now()
            }
            await asyncio.gather(
                self.premiumUsers.replace_one(
                    {'user_id': int(user_id)},
                    premium_data,
                    upsert=True
                ),
                self.col.update_one(
                    {'id': int(user_id)},
                    {'$set': {'is_premium': True}}
                )
            )
            return True
        except Exception as e:
            print(f"Error adding premium user: {e}")
            return False

    async def remove_premium(self, user_id):
        try:
            await asyncio.gather(
                self.premiumUsers.delete_many({'user_id': int(user_id)}),
                self.col.update_one(
                    {'id': int(user_id)},
                    {'$set': {'is_premium': False}}
                )
            )
            return True
        except Exception as e:
            print(f"Error removing premium user: {e}")
            return False

    async def is_premium(self, user_id):
        try:
            user = await self.premiumUsers.find_one({'user_id': int(user_id)})
            if user and user.get('expiry_date', datetime.max) > datetime.now():
                return True
            if user:  # Expired user
                await self.remove_premium(user_id)
            return False
        except Exception as e:
            print(f"Error checking premium status: {e}")
            return False

    async def get_expiry_date(self, user_id):
        user = await self.premiumUsers.find_one({'user_id': int(user_id)})
        return user.get('expiry_date') if user else None

    async def get_premium_plan(self, user_id):
        user = await self.premiumUsers.find_one({'user_id': int(user_id)})
        return {
            'plan_name': user.get('plan_name'),
            'files_allowed': user.get('files_allowed'),
            'expiry_date': user.get('expiry_date'),
            'purchase_date': user.get('purchase_date')
        } if user else None

    async def get_all_premium_users(self, filter_expired=False):
        query = {"expiry_date": {"$gt": datetime.now()}} if filter_expired else {}
        return [{
            'user_id': user.get('user_id'),
            'plan_name': user.get('plan_name'),
            'expiry_date': user.get('expiry_date'),
            'remaining_days': (user['expiry_date'] - datetime.now()).days 
                if user.get('expiry_date') else None
        } async for user in self.premiumUsers.find(query)]

    async def bulk_remove_expired(self):
        """Remove all expired premium users at once"""
        expired = await self.premiumUsers.find({
            "expiry_date": {"$lt": datetime.now()}
        }).to_list(length=None)
        
        if not expired:
            return 0
            
        user_ids = [user['user_id'] for user in expired]
        await asyncio.gather(
            self.premiumUsers.delete_many({
                "expiry_date": {"$lt": datetime.now()}
            }),
            self.col.update_many(
                {'id': {'$in': user_ids}},
                {'$set': {'is_premium': False}}
            )
        )
        return len(expired)

    # Upload Tracking Methods
    async def update_upload_stats(self, user_id):
        today = datetime.now().date()
        update_result = await self.col.update_one(
            {
                'id': int(user_id),
                'last_upload_date': today
            },
            {'$inc': {'daily_uploads': 1, 'total_uploads': 1}}
        )
        
        if update_result.matched_count == 0:
            await self.col.update_one(
                {'id': int(user_id)},
                {
                    '$set': {
                        'daily_uploads': 1,
                        'last_upload_date': today
                    },
                    '$inc': {'total_uploads': 1}
                }
            )

    async def get_daily_uploads(self, user_id):
        user = await self.col.find_one({'id': int(user_id)})
        if user and user.get('last_upload_date') == datetime.now().date():
            return user.get('daily_uploads', 0)
        return 0

    async def get_user_stats(self, user_id):
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return None
            
        premium = await self.is_premium(user_id)
        expiry_date = await self.get_expiry_date(user_id) if premium else None
        
        return {
            'user_id': user_id,
            'name': user.get('name'),
            'join_date': user.get('join_date'),
            'last_used': user.get('last_used'),
            'daily_uploads': user.get('daily_uploads', 0),
            'total_uploads': user.get('total_uploads', 0),
            'is_premium': premium,
            'expiry_date': expiry_date,
            'remaining_days': (expiry_date - datetime.now()).days 
                if expiry_date else None
        }

db = Database(DATABASE_URI, DATABASE_NAME)
