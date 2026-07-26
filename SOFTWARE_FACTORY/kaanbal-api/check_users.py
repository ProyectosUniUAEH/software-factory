import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017/forge')
    db = client.forge
    users = await db.users.find().to_list(None)
    for u in users:
        print(f"User: {u.get('username')}")

asyncio.run(main())
