import asyncio
from app.services.argocd_service import ArgoCDService

async def main():
    s = ArgoCDService()
    conn = await s.get_connection_status()
    apps = await s.list_applications() if conn.get("connected") else []
    print("CONNECTED", conn)
    print("APPS", len(apps))
    if apps:
        print("SAMPLE", apps[0].get("name"), apps[0].get("health"))

asyncio.run(main())
