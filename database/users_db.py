import re
import motor.motor_asyncio
from datetime import datetime, timedelta
from info import DATABASE_NAME, DATABASE_URI
from typing import Optional, Dict, List, Union

class Database:
    def __init__(self, uri: str, database_name: str):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.banned_users = self.db.banned_users
        self.premium_users = self.db.premium_users
        self.trial_users = self.db.trial_users

    @staticmethod
    def _create_user_dict(user_id: int, name: str) -> Dict:
        """Create a new user document structure"""
        return {
            "id": user_id,
            "name": name,
            "join_date": datetime.now(),
            "last_used": datetime.now(),
            "daily_uploads": 0,
            "total_uploads": 0,
            "last_upload_date": datetime.now().date(),
            "is_premium": False,
            "is_trial": False
        }

    async def add_user(self, user_id: int, name: str) -> bool:
        """Add a new user to the database"""
        try:
            if not await self.is_user_exist(user_id):
                user_data = self._create_user_dict(user_id, name)
                await self.users.insert_one(user_data)
                return True
            return False
        except Exception as e:
            print(f"Error adding user: {e}")
            return False

    async def is_user_exist(self, user_id: int) -> bool:
        """Check if user exists in database"""
        try:
            user = await self.users.find_one({"id": int(user_id)})
            return bool(user)
        except Exception as e:
            print(f"Error checking user existence: {e}")
            return False

    async def total_users_count(self) -> int:
        """Get total count of users"""
        try:
            return await self.users.count_documents({})
        except Exception as e:
            print(f"Error counting users: {e}")
            return 0

    async def get_all_users(self):
        """Get all users from database"""
        try:
            return self.users.find({})
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []

    async def delete_user(self, user_id: int) -> bool:
        """Delete a user from all collections"""
        try:
            await self.users.delete_many({"id": int(user_id)})
            await self.premium_users.delete_many({"user_id": int(user_id)})
            await self.trial_users.delete_many({"user_id": int(user_id)})
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    async def ban_user(self, user_id: int) -> bool:
        """Ban a user and remove premium status"""
        try:
            if await self.is_banned(user_id):
                return False
                
            await self.banned_users.insert_one({
                "user_id": int(user_id),
                "ban_date": datetime.now()
            })
            await self.remove_premium(user_id)
            return True
        except Exception as e:
            print(f"Error banning user: {e}")
            return False

    async def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        try:
            user = await self.banned_users.find_one({"user_id": int(user_id)})
            return bool(user)
        except Exception as e:
            print(f"Error checking ban status: {e}")
            return False

    async def unban_user(self, user_id: int) -> bool:
        """Unban a user"""
        try:
            result = await self.banned_users.delete_one({"user_id": int(user_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error unbanning user: {e}")
            return False

    # Premium User Management
    async def add_premium(
        self,
        user_id: int,
        plan_name: str,
        files_allowed: Union[int, str],
        expiry_date: datetime,
        payment_details: str,
        is_trial: bool = False
    ) -> bool:
        """Add premium subscription for a user"""
        try:
            premium_data = {
                "user_id": int(user_id),
                "plan_name": plan_name,
                "files_allowed": files_allowed,
                "expiry_date": expiry_date,
                "payment_details": payment_details,
                "purchase_date": datetime.now(),
                "is_trial": is_trial
            }

            # Add to appropriate collection
            if is_trial:
                await self.trial_users.insert_one(premium_data)
            else:
                await self.premium_users.insert_one(premium_data)

            # Update user document
            await self.users.update_one(
                {"id": int(user_id)},
                {"$set": {
                    "is_premium": True,
                    "is_trial": is_trial
                }}
            )
            return True
        except Exception as e:
            print(f"Error adding premium: {e}")
            return False

    async def remove_premium(self, user_id: int) -> bool:
        """Remove premium status from user"""
        try:
            # Remove from both premium and trial collections
            await self.premium_users.delete_many({"user_id": int(user_id)})
            await self.trial_users.delete_many({"user_id": int(user_id)})

            # Update user document
            await self.users.update_one(
                {"id": int(user_id)},
                {"$set": {
                    "is_premium": False,
                    "is_trial": False
                }}
            )
            return True
        except Exception as e:
            print(f"Error removing premium: {e}")
            return False

    async def is_premium(self, user_id: int) -> bool:
        """Check if user has active premium subscription"""
        try:
            # Check premium users first
            premium_user = await self.premium_users.find_one({"user_id": int(user_id)})
            if premium_user:
                if premium_user.get("expiry_date", datetime.max) > datetime.now():
                    return True
                await self.remove_premium(user_id)
                return False

            # Check trial users
            trial_user = await self.trial_users.find_one({"user_id": int(user_id)})
            if trial_user:
                if trial_user.get("expiry_date", datetime.max) > datetime.now():
                    return True
                await self.remove_premium(user_id)
                return False

            return False
        except Exception as e:
            print(f"Error checking premium status: {e}")
            return False

    async def check_trial_used(self, user_id: int) -> bool:
        """Check if user has used trial before"""
        try:
            return await self.trial_users.find_one({"user_id": int(user_id)}) is not None
        except Exception as e:
            print(f"Error checking trial status: {e}")
            return True  # Assume trial used if error occurs

    async def get_expiry_date(self, user_id: int) -> Optional[datetime]:
        """Get user's premium expiry date"""
        try:
            # Check premium users first
            premium_user = await self.premium_users.find_one({"user_id": int(user_id)})
            if premium_user:
                return premium_user.get("expiry_date")

            # Check trial users
            trial_user = await self.trial_users.find_one({"user_id": int(user_id)})
            if trial_user:
                return trial_user.get("expiry_date")

            return None
        except Exception as e:
            print(f"Error getting expiry date: {e}")
            return None

    async def get_premium_plan(self, user_id: int) -> Optional[Dict]:
        """Get user's premium plan details"""
        try:
            # Check premium users first
            premium_user = await self.premium_users.find_one({"user_id": int(user_id)})
            if premium_user:
                return {
                    "plan_name": premium_user.get("plan_name"),
                    "files_allowed": premium_user.get("files_allowed"),
                    "expiry_date": premium_user.get("expiry_date"),
                    "purchase_date": premium_user.get("purchase_date"),
                    "is_trial": False
                }

            # Check trial users
            trial_user = await self.trial_users.find_one({"user_id": int(user_id)})
            if trial_user:
                return {
                    "plan_name": trial_user.get("plan_name"),
                    "files_allowed": trial_user.get("files_allowed"),
                    "expiry_date": trial_user.get("expiry_date"),
                    "purchase_date": trial_user.get("purchase_date"),
                    "is_trial": True
                }

            return None
        except Exception as e:
            print(f"Error getting premium plan: {e}")
            return None

    async def get_all_premium_users(self) -> List[Dict]:
        """Get all premium users including trial users"""
        try:
            premium_users = []
            
            # Add premium users
            async for user in self.premium_users.find({}):
                premium_users.append({
                    "user_id": user.get("user_id"),
                    "plan_name": user.get("plan_name"),
                    "files_allowed": user.get("files_allowed"),
                    "expiry_date": user.get("expiry_date"),
                    "purchase_date": user.get("purchase_date"),
                    "is_trial": False
                })
            
            # Add trial users
            async for user in self.trial_users.find({}):
                premium_users.append({
                    "user_id": user.get("user_id"),
                    "plan_name": user.get("plan_name"),
                    "files_allowed": user.get("files_allowed"),
                    "expiry_date": user.get("expiry_date"),
                    "purchase_date": user.get("purchase_date"),
                    "is_trial": True
                })
            
            return premium_users
        except Exception as e:
            print(f"Error getting all premium users: {e}")
            return []

    # Upload tracking methods
    async def update_upload_stats(self, user_id: int) -> bool:
        """Update user's upload statistics"""
        try:
            current_date = datetime.now().date()
            
            update_data = {
                "$inc": {"daily_uploads": 1, "total_uploads": 1},
                "$set": {"last_upload_date": current_date, "last_used": datetime.now()}
            }
            
            result = await self.users.update_one(
                {"id": int(user_id)},
                update_data,
                upsert=True
            )
            
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating upload stats: {e}")
            return False

    async def get_daily_uploads(self, user_id: int) -> int:
        """Get user's daily upload count"""
        try:
            user = await self.users.find_one({"id": int(user_id)})
            if user:
                current_date = datetime.now().date()
                last_upload_date = user.get("last_upload_date")
                
                if last_upload_date == current_date:
                    return user.get("daily_uploads", 0)
            return 0
        except Exception as e:
            print(f"Error getting daily uploads: {e}")
            return 0

    async def get_total_uploads(self, user_id: int) -> int:
        """Get user's total upload count"""
        try:
            user = await self.users.find_one({"id": int(user_id)})
            return user.get("total_uploads", 0) if user else 0
        except Exception as e:
            print(f"Error getting total uploads: {e}")
            return 0

# Initialize database connection
db = Database(DATABASE_URI, DATABASE_NAME)
