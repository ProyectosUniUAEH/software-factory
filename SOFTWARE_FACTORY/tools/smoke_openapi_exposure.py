import urllib.request, json
d = json.load(urllib.request.urlopen("http://127.0.0.1:8000/openapi.json"))
paths = [p for p in d.get("paths", {}) if "environments" in p or "exposure" in p]
print("PATHS:")
for p in sorted(paths):
    methods = ",".join(d["paths"][p].keys())
    print(f"  {methods.upper():12} {p}")
# also check ensure_env methods exist on switch
from app.services.exposure.switch_service import ExposureSwitchService
print("HAS_ENSURE", hasattr(ExposureSwitchService, "ensure_env"))
print("HAS_REMOVE", hasattr(ExposureSwitchService, "remove_env"))
