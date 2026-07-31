import asyncio
from app.services.template_service import TemplateService

async def main():
    s = TemplateService()
    s._last_sync = None
    ok = await s.refresh_cache()
    print("cache_ok", ok)
    tpls = await s.get_templates()
    print("templates", [t["id"] for t in tpls[:5]])

asyncio.run(main())
