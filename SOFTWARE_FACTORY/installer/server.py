#!/usr/bin/env python3
"""
Kaanbal Web Installer — backend (BLUEPRINT RFC-0001 §8, experiencia guiada)
===========================================================================
Cero dependencias: solo stdlib. Un comando lo levanta en VPS o laptop:

    python3 installer/server.py            # puerto 3000, imprime URL con token

Seguridad estilo Contabo: token de sesión impreso en la terminal; toda la
API lo exige. Los pasos son idempotentes: detectan k3s/ArgoCD ya instalados
y los marcan completados, así el instalador también funciona como panel de
verificación del estado real de la célula.
"""
import json
import os
import queue
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("KAANBAL_INSTALLER_PORT", "3000"))
TOKEN = os.environ.get("KAANBAL_INSTALLER_TOKEN") or secrets.token_urlsafe(18)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Carpeta del Framework Acuaponsito (catálogo + clips). El repertorio crece
# sin redeploy: tirar un mp4 + editar catalog.json ya lo hace disponible.
_ANIM_CANDIDATES = [
    os.environ.get("KAANBAL_ANIM_DIR", ""),
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "animacion")),
]
ANIM_DIR = next((p for p in _ANIM_CANDIDATES if p and os.path.isdir(p)), None)

# Fallback si no existe carpeta animacion: los 3 clips empacados en static/media
_BUILTIN_CATALOG = {
    "version": 0, "character": "Acuaponsito",
    "states": {
        "sleep": {"desc": "dormido", "fallback": "greet"},
        "greet": {"desc": "saluda", "fallback": "idle"},
        "idle": {"desc": "neutral", "fallback": "greet"},
        "listen": {"desc": "escucha", "fallback": "idle"},
        "think": {"desc": "procesa", "fallback": "listen"},
    },
    "clips": [
        {"id": "greet__saludo", "file": "media/clip_welcome.mp4", "state": "greet",
         "description": "Saluda con la mano, bienvenida", "loop": True},
        {"id": "listen__atento", "file": "media/clip_listening.mp4", "state": "listen",
         "description": "Escucha con mano al oído", "loop": True},
        {"id": "think__proceso", "file": "media/clip_processing.mp4", "state": "think",
         "description": "Procesa información", "loop": True},
    ],
}


def load_catalog():
    """Catálogo del framework: animacion/catalog.json, o el built-in de respaldo."""
    if ANIM_DIR:
        try:
            with open(os.path.join(ANIM_DIR, "catalog.json"), encoding="utf-8") as f:
                cat = json.load(f)
            for clip in cat.get("clips", []):
                clip["url"] = "/anim/" + urllib.parse.quote(clip["file"])
            cat["source"] = "animacion"
            return cat
        except Exception as e:
            print(f"[catalog] error leyendo animacion/catalog.json: {e}")
    cat = json.loads(json.dumps(_BUILTIN_CATALOG))
    for clip in cat["clips"]:
        clip["url"] = "/" + clip["file"]
    cat["source"] = "builtin"
    return cat

# ------------------------------------------------- memoria del agente ------
# Bitácora local en formato amigable para IA: JSONL, un evento por línea.
# {ts, source, kind, ...}. Base de conocimiento que crece con TODO lo que
# pasa en el sistema (instalación, consola, acciones del usuario).
MEMORY_FILE = os.path.expanduser("~/.kaanbal/memory.jsonl")
os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
MEMORY_LOCK = threading.Lock()


def remember(source, kind, **detail):
    event = {"ts": round(time.time(), 2), "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
             "source": source, "kind": kind, **detail}
    try:
        with MEMORY_LOCK, open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return event


def recall(limit=120):
    try:
        with MEMORY_LOCK, open(MEMORY_FILE, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        return [json.loads(l) for l in lines if l.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []


# ----------------------------------------------------------------- estado ---
STATE_LOCK = threading.Lock()
EVENTS = []           # historial de eventos SSE (replay con ?since=)
EVENT_Q = queue.Queue()
INSTALLING = False
PORT_FORWARD_PROC = None

STEP_IDS = ["sistema", "k3s", "nodo", "argocd", "ia", "cloudflared", "gitops", "acceso"]
STATE = {
    "steps": {sid: {"status": "pending", "detail": ""} for sid in STEP_IDS},
    "phase": "idle",          # idle | installing | done | error
    "handoff": {},            # argocd_url, password, kubeconfig, node
    "sysinfo": {},
}


def emit(kind, **payload):
    """Registrar evento para SSE (log de terminal o cambio de paso)."""
    event = {"kind": kind, "ts": round(time.time(), 2), **payload}
    with STATE_LOCK:
        EVENTS.append(event)
    EVENT_Q.put(event)
    # persistir en la memoria del agente (sin el ruido de stdout crudo)
    if not (kind == "log" and payload.get("level") in ("out", "cmd")):
        remember("installer", kind, **payload)


def log(line, level="info"):
    emit("log", line=line, level=level)


def set_step(step_id, status, detail=""):
    with STATE_LOCK:
        STATE["steps"][step_id] = {"status": status, "detail": detail}
    emit("step", step=step_id, status=status, detail=detail)


def set_phase(phase):
    with STATE_LOCK:
        STATE["phase"] = phase
    emit("phase", phase=phase)


# ------------------------------------------------------------ shell helpers ---
def run(cmd, timeout=120, stream=False):
    """Ejecutar comando; si stream=True, mandar stdout línea a línea al log."""
    log(f"$ {cmd}", "cmd")
    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    lines = []
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line:
                lines.append(line)
                if stream:
                    log(line, "out")
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Timeout ({timeout}s): {cmd}")
    return proc.returncode, "\n".join(lines)


def kubectl(args, timeout=60, stream=False):
    return run(f"k3s kubectl {args}", timeout=timeout, stream=stream)


# ------------------------------------------------------------- validaciones ---
def http_json(url, headers=None, data=None, auth=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    if auth:
        import base64
        cred = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
    if data is not None:
        req.data = data.encode() if isinstance(data, str) else data
        req.method = "POST"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def validate_cloudflare(token, account_id):
    """Mismas comprobaciones que kaanbal-api /setup/validate/cloudflare."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    status, acc = http_json(f"https://api.cloudflare.com/client/v4/accounts/{account_id}", headers)
    if status == 0:
        return {"valid": False, "message": f"Sin conexión a Cloudflare: {acc.get('error')}"}
    if status in (401, 403):
        return {"valid": False, "message": "Token inválido o sin permiso 'Account Settings: Read'."}
    if status != 200:
        return {"valid": False, "message": f"Cuenta '{account_id}' no accesible (HTTP {status}). Verifica el Account ID."}
    name = acc.get("result", {}).get("name", account_id)
    t_status, _ = http_json(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/cfd_tunnel?is_deleted=false&per_page=1", headers)
    z_status, zones = http_json(
        f"https://api.cloudflare.com/client/v4/zones?account.id={account_id}&per_page=5", headers)
    zone_names = [z.get("name", "") for z in zones.get("result", [])] if z_status == 200 else []
    if t_status == 200 and z_status == 200:
        zonas = ", ".join(zone_names) if zone_names else "sin zonas aún"
        return {"valid": True, "message": f"Cuenta '{name}' OK. Túneles ✓ DNS ✓. Zonas: {zonas}.", "zones": zone_names}
    if t_status == 200:
        return {"valid": True, "message": f"Cuenta '{name}' OK. Túneles ✓. Falta confirmar permiso DNS."}
    return {"valid": False, "message": f"Cuenta '{name}' encontrada pero faltan permisos Tunnel/DNS en el token."}


# ── Cloudflare CONTROL PLANE: crear túnel + ingress + DNS (portado de setup.py) ──
# Ésta es la pieza que hace que el DOMINIO cobre vida. El túnel abre una conexión
# SALIENTE al edge de Cloudflare (sin IP pública, sin abrir puertos): mientras la
# máquina esté encendida, Cloudflare enruta *.dominio hacia el Traefik de k3s.
def _cf(method, url, token, body=None, timeout=30):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers, method=method)
    if body is not None:
        req.data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def create_cloudflare_tunnel(token, account_id, domain, hostname, log_fn=None):
    """Crea (o reutiliza) el túnel, configura ingress y DNS wildcard.
    Devuelve {tunnel_id, tunnel_token, dns:[...], zone_id} o {error}."""
    import base64 as _b64
    say = log_fn or (lambda *a, **k: None)
    cf = "https://api.cloudflare.com/client/v4"
    tunnel_name = f"kaanbal-{hostname}".lower().replace(" ", "-")[:60]

    # ¿ya existe un túnel con ese nombre? reutilizar (idempotente en re-instalación)
    st, lst = _cf("GET", f"{cf}/accounts/{account_id}/cfd_tunnel?name={urllib.parse.quote(tunnel_name)}&is_deleted=false", token)
    tunnel_id = tunnel_token = None
    if st == 200 and lst.get("result"):
        tunnel_id = lst["result"][0]["id"]
        stt, tk = _cf("GET", f"{cf}/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token", token)
        tunnel_token = tk.get("result") if stt == 200 else None
        say(f"Túnel existente reutilizado: {tunnel_name}", "info")
    if not tunnel_id:
        secret = _b64.b64encode(secrets.token_bytes(32)).decode()
        st, cr = _cf("POST", f"{cf}/accounts/{account_id}/cfd_tunnel", token,
                     {"name": tunnel_name, "tunnel_secret": secret})
        if st != 200:
            errs = cr.get("errors", [])
            return {"error": errs[0].get("message") if errs else f"HTTP {st} al crear el túnel"}
        tunnel_id = cr["result"]["id"]
        tunnel_token = cr["result"].get("token")
        say(f"Túnel creado en Cloudflare: {tunnel_name}", "ok")

    # ingress: argocd → server TLS; wildcard + raíz → Traefik de k3s (:80)
    traefik = "http://traefik.kube-system.svc.cluster.local:80"
    ingress = [
        {"hostname": f"argocd.{domain}",
         "service": "https://argocd-server.argocd.svc.cluster.local:443",
         "originRequest": {"noTLSVerify": True}},
        {"hostname": f"*.{domain}", "service": traefik},
        {"hostname": domain, "service": traefik},
        {"service": "http_status:404"},
    ]
    st, _ = _cf("PUT", f"{cf}/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations", token,
                {"config": {"ingress": ingress}})
    if st == 200:
        say("Reglas de ingress configuradas (*.dominio → Traefik, argocd.dominio → ArgoCD)", "ok")

    # DNS: wildcard + raíz + argocd como CNAME al túnel (proxied → HTTPS de Cloudflare)
    st, zr = _cf("GET", f"{cf}/zones?name={domain}", token)
    zone_id = (zr.get("result") or [{}])[0].get("id") if st == 200 else None
    dns = []
    if zone_id:
        target = f"{tunnel_id}.cfargotunnel.com"
        for name in [f"*.{domain}", domain, f"argocd.{domain}"]:
            ste, ex = _cf("GET", f"{cf}/zones/{zone_id}/dns_records?type=CNAME&name={urllib.parse.quote(name)}", token)
            recs = ex.get("result", []) if ste == 200 else []
            rec = {"type": "CNAME", "name": name, "content": target, "proxied": True}
            if recs:
                _cf("PUT", f"{cf}/zones/{zone_id}/dns_records/{recs[0]['id']}", token, rec)
            else:
                _cf("POST", f"{cf}/zones/{zone_id}/dns_records", token, rec)
            dns.append(name)
        say(f"DNS apuntado a tu célula: {', '.join(dns)}", "ok")
    else:
        say(f"⚠ No encontré la zona '{domain}' en Cloudflare — ¿ya la agregaste y está Active?", "warn")
    return {"tunnel_id": tunnel_id, "tunnel_token": tunnel_token, "dns": dns, "zone_id": zone_id}


CLOUDFLARED_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudflared
  namespace: prod
  labels: {{app: cloudflared, app.kubernetes.io/part-of: kaanbal}}
spec:
  replicas: 1
  selector:
    matchLabels: {{app: cloudflared}}
  template:
    metadata:
      labels: {{app: cloudflared}}
    spec:
      containers:
        - name: cloudflared
          image: cloudflare/cloudflared:latest
          args: [tunnel, --no-autoupdate, --metrics, "0.0.0.0:2000", run]
          env:
            - name: TUNNEL_TOKEN
              valueFrom:
                secretKeyRef: {{name: cloudflared-secrets, key: TUNNEL_TOKEN}}
          ports:
            - {{containerPort: 2000, name: metrics}}
          resources:
            requests: {{cpu: 10m, memory: 64Mi}}
            limits: {{cpu: 200m, memory: 128Mi}}
          livenessProbe:
            httpGet: {{path: /ready, port: 2000}}
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
"""


def validate_github(token):
    status, user = http_json("https://api.github.com/user",
                             {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"})
    if status != 200:
        return {"valid": False, "message": f"GitHub rechazó el token (HTTP {status})."}
    login = user.get("login", "?")
    # el email público puede venir vacío si el usuario lo oculta en su perfil;
    # en ese caso consultamos /user/emails (requiere scope user:email o read:user)
    email = user.get("email")
    if not email:
        st2, emails = http_json("https://api.github.com/user/emails",
                                {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"})
        if st2 == 200 and isinstance(emails, list):
            primary = next((e["email"] for e in emails if e.get("primary")), None)
            email = primary or (emails[0]["email"] if emails else None)
    detail = f"'{login}'" + (f" · {email}" if email else " (sin email público — agrega scope 'user:email' si lo necesitas)")
    return {"valid": True, "message": f"Conectado a GitHub como {detail}.", "login": login, "email": email}


# ── Agent Studio: flujos de trabajo y roles (replicables en cualquier app) ──
WORKFLOWS = {
    "general": {
        "name": "Asistente general", "icon": "🌱",
        "instructions": "Ayuda al usuario con su plataforma. Sé claro, breve y práctico.",
    },
    "ciencia": {
        "name": "Validación científica", "icon": "🔬",
        "instructions": ("Modo científico riguroso: exige evidencia, distingue hecho de hipótesis, "
                         "sugiere validar afirmaciones con DOI/fuentes primarias y di explícitamente "
                         "cuando NO tengas certeza. Nivel de conservadurismo: {conservadurismo}/10 "
                         "(a mayor nivel, más escéptico y más pedirás fuentes)."),
    },
    "infra": {
        "name": "Vigilancia de infraestructura", "icon": "📡",
        "instructions": ("Analiza el estado del cluster (nodos, pods, fases) del contexto adjunto. "
                         "Detecta anomalías (restarts, pods no Ready) y propone diagnóstico y siguiente paso."),
    },
    "dev": {
        "name": "Desarrollo asistido", "icon": "⚙️",
        "instructions": ("Modo dev estilo pair-programming: propone cambios concretos con criterios de "
                         "aceptación. NUNCA asumas que puedes aplicar cambios: tu modo de operación actual "
                         "es {modo}; si no es 'dev' o superior, solo propones."),
    },
    "mejora": {
        "name": "Registrar mejora", "icon": "📋",
        "instructions": ("Skill de automejora de la plataforma: convierte la idea del usuario en una ficha "
                         "de desarrollo. Tu 'say' DEBE tener este formato con saltos de línea:\n"
                         "IDEA: <resumen 1 línea>\nIMPACTO: <quién se beneficia>\n"
                         "TAREAS:\n1. ...\n2. ...\n3. ...\nRIESGOS: <1 línea>\n"
                         "ROLES: <subagentes sugeridos>\nACEPTACIÓN: <criterio verificable>"),
    },
}

ROLES = {
    "orquestador": {"name": "Orquestador", "icon": "🧠", "desc": "Contexto completo; decide y delega. No ejecuta directo."},
    "arquitecto": {"name": "Arquitecto", "icon": "🏗️", "desc": "Diseño de sistema, trade-offs, deuda técnica."},
    "seguridad": {"name": "Seguridad", "icon": "🛡️", "desc": "Amenazas, secretos, permisos, superficies expuestas."},
    "qa": {"name": "QA / Tester", "icon": "🧪", "desc": "Casos de prueba, criterios de aceptación, regresiones."},
    "frontend": {"name": "Dev Frontend", "icon": "🎨", "desc": "UI/UX, componentes, accesibilidad."},
    "backend": {"name": "Dev Backend", "icon": "🔌", "desc": "APIs, datos, contratos, rendimiento."},
    "devops": {"name": "DevOps", "icon": "☸️", "desc": "Pipelines, GitOps, clusters, observabilidad."},
    "datos": {"name": "Data / ML", "icon": "📊", "desc": "Datos, features, entrenamientos, métricas de modelos."},
    "cientifico": {"name": "Científico", "icon": "🔬", "desc": "Rigor metodológico, DOI, reproducibilidad."},
}

# ── Agente IA: proveedores LLM (parte del instalador Y del sistema) ──────────
AI_PROVIDERS = {
    "deepseek": {
        "base": "https://api.deepseek.com", "models_path": "/models",
        "chat_path": "/chat/completions", "default_model": "deepseek-chat", "style": "openai",
    },
    "openai": {
        "base": "https://api.openai.com", "models_path": "/v1/models",
        "chat_path": "/v1/chat/completions", "default_model": "gpt-4o-mini", "style": "openai",
    },
    "anthropic": {
        "base": "https://api.anthropic.com", "models_path": "/v1/models",
        "chat_path": "/v1/messages", "default_model": "claude-haiku-4-5-20251001", "style": "anthropic",
    },
}


def _ai_headers(provider, api_key):
    if AI_PROVIDERS[provider]["style"] == "anthropic":
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def validate_ai(provider, api_key):
    """Valida la API key listando modelos del proveedor."""
    if provider not in AI_PROVIDERS:
        return {"valid": False, "message": f"Proveedor desconocido: {provider}"}
    p = AI_PROVIDERS[provider]
    status, resp = http_json(p["base"] + p["models_path"], _ai_headers(provider, api_key))
    if status == 200:
        models = [m.get("id", "") for m in resp.get("data", [])][:6]
        with STATE_LOCK:
            existing = [x for x in STATE.setdefault("ai_providers", []) if x["provider"] != provider]
            STATE["ai_providers"] = existing + [{"provider": provider, "api_key": api_key,
                                                 "model": p["default_model"]}]
        return {"valid": True, "message": f"✓ {provider} conectado. Modelos: {', '.join(models[:4])}…",
                "models": models, "default_model": p["default_model"]}
    if status in (401, 403):
        return {"valid": False, "message": f"API key de {provider} inválida (HTTP {status})."}
    return {"valid": False, "message": f"{provider} respondió HTTP {status}: {str(resp)[:140]}"}


def _catalog_for_llm():
    """Catálogo compacto para el system prompt (id + descripción)."""
    cat = load_catalog()
    states = ", ".join(cat.get("states", {}).keys())
    lines = [f'- {c["id"]}: {c.get("description", c.get("title", ""))[:140]}' for c in cat.get("clips", [])]
    return states, "\n".join(lines)


def _ai_call(provider, api_key, model, system, messages, max_tokens=700):
    """Llamada genérica de chat a cualquier proveedor. Devuelve (texto, error)."""
    p = AI_PROVIDERS[provider]
    model = model or p["default_model"]
    if p["style"] == "anthropic":
        body = json.dumps({"model": model, "max_tokens": max_tokens, "system": system,
                           "messages": messages})
        status, resp = http_json(p["base"] + p["chat_path"], _ai_headers(provider, api_key), data=body, timeout=60)
        if status != 200:
            return None, f"{provider} HTTP {status}: {str(resp)[:200]}"
        return resp.get("content", [{}])[0].get("text", ""), None
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "messages": [{"role": "system", "content": system}] + messages})
    status, resp = http_json(p["base"] + p["chat_path"], _ai_headers(provider, api_key), data=body, timeout=60)
    if status != 200:
        return None, f"{provider} HTTP {status}: {str(resp)[:200]}"
    return resp.get("choices", [{}])[0].get("message", {}).get("content", ""), None


def _parse_contract(text):
    """Extrae el contrato JSON {say, state, clip} de la respuesta del LLM."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if match:
        try:
            out = json.loads(match.group(0))
            return {"say": out.get("say", text), "state": out.get("state", "idle"),
                    "clip": out.get("clip"), "raw": text}
        except json.JSONDecodeError:
            pass
    return {"say": (text or "").strip(), "state": "speak", "clip": None, "raw": text}


def _observe_cache():
    return getattr(_observe_cache, "data", None)


def observe():
    """Snapshot REAL del sistema para el agente: nodos, pods, fases. Cache 6s."""
    cached = getattr(observe, "_cache", None)
    if cached and time.time() - cached[0] < 6:
        return cached[1]
    snap = {"ts": round(time.time(), 2), "nodes": [], "namespaces": {}, "totals": {}}
    rc, out = run("k3s kubectl get nodes -o json 2>/dev/null", timeout=25)
    if rc == 0 and out.strip().startswith("{"):
        try:
            for n in json.loads(out).get("items", []):
                conds = {c["type"]: c["status"] for c in n["status"].get("conditions", [])}
                snap["nodes"].append({
                    "name": n["metadata"]["name"],
                    "ready": conds.get("Ready") == "True",
                    "cpu": n["status"].get("capacity", {}).get("cpu"),
                    "memory": n["status"].get("capacity", {}).get("memory"),
                    "version": n["status"].get("nodeInfo", {}).get("kubeletVersion"),
                })
        except Exception:
            pass
    rc, out = run("k3s kubectl get pods -A -o json 2>/dev/null", timeout=30)
    running = total = 0
    if rc == 0 and out.strip().startswith("{"):
        try:
            for p in json.loads(out).get("items", []):
                ns = p["metadata"]["namespace"]
                phase = p["status"].get("phase", "?")
                restarts = sum(cs.get("restartCount", 0) for cs in p["status"].get("containerStatuses", []))
                snap["namespaces"].setdefault(ns, []).append({
                    "name": p["metadata"]["name"], "phase": phase, "restarts": restarts,
                })
                total += 1
                running += phase == "Running"
        except Exception:
            pass
    snap["totals"] = {"pods": total, "running": running, "namespaces": len(snap["namespaces"])}
    with STATE_LOCK:
        snap["phase"] = STATE["phase"]
    observe._cache = (time.time(), snap)
    return snap


def _observe_summary():
    s = observe()
    nodes = "; ".join(f'{n["name"]} Ready={n["ready"]} cpu={n["cpu"]} {n["version"]}' for n in s["nodes"]) or "sin nodos"
    ns_lines = []
    for ns, pods in s["namespaces"].items():
        bad = [p for p in pods if p["phase"] != "Running" or p["restarts"] > 3]
        line = f"{ns}: {len(pods)} pods"
        if bad:
            line += " (atención: " + ", ".join(f'{p["name"]}={p["phase"]}/r{p["restarts"]}' for p in bad[:4]) + ")"
        ns_lines.append(line)
    return f"Nodos: {nodes}. Pods {s['totals']['running']}/{s['totals']['pods']} Running. " + " | ".join(ns_lines)


def ai_chat(body):
    """Chat del agente con flujo de trabajo, rol, scopes y contexto real."""
    providers = STATE.get("ai_providers") or []
    entry = None
    if body.get("provider") and body.get("api_key"):
        entry = {"provider": body["provider"], "api_key": body["api_key"], "model": body.get("model", "")}
    elif providers:
        entry = providers[0]
    if not entry:
        return {"error": "sin-proveedor", "message": "Conecta un proveedor de IA primero (paso Agente IA del instalador)."}

    wf = WORKFLOWS.get(body.get("workflow", "general"), WORKFLOWS["general"])
    role = ROLES.get(body.get("role", "orquestador"), ROLES["orquestador"])
    scopes = body.get("scopes", {})
    modo = body.get("modo", "asistido")
    conservadurismo = body.get("conservadurismo", 7)

    states, clips = _catalog_for_llm()
    context_blocks = []
    if scopes.get("infra", True):
        context_blocks.append("INFRAESTRUCTURA REAL AHORA: " + _observe_summary())
    if scopes.get("actividad", True):
        tail = recall(25)
        acts = "; ".join(f'{e.get("iso", "?")[-8:]} {e.get("source")}/{e.get("kind")} {e.get("step", e.get("line", ""))[:60]}'
                         for e in tail[-12:])
        context_blocks.append("ACTIVIDAD RECIENTE (memoria JSONL): " + (acts or "sin eventos"))
    context_blocks.append(f"CONTEXTO DE UBICACIÓN: consola del agente Kaanbal, célula '{socket.gethostname().lower()}', "
                          f"modo de operación '{modo}' (asistido=solo propones; dev=puedes proponer cambios aplicables en dev; "
                          f"staging/prod requieren aprobación explícita).")

    system = (
        f"Eres Acuaponsito, el agente de plataforma de Kaanbal (open source, para científicos y makers). "
        f"Rol activo: {role['name']} — {role['desc']}\n"
        f"Flujo de trabajo: {wf['name']}. Instrucciones del flujo: "
        + wf["instructions"].format(conservadurismo=conservadurismo, modo=modo) + "\n\n"
        + "\n".join(context_blocks) + "\n\n"
        "Respondes SIEMPRE un único JSON válido sin markdown:\n"
        '{"say": "<respuesta útil en español; puede ser multilínea>", "state": "<estado>", "clip": "<id opcional>"}\n'
        f"Estados: {states}.\nRepertorio de clips:\n{clips}\n"
        "Elige state/clip acorde a tu respuesta (think si analizas, warn si alertas, celebrate si hay éxito)."
    )
    messages = [{"role": m["role"], "content": m["content"]} for m in body.get("messages", [])][-12:]
    if not messages:
        return {"error": "sin-mensajes", "message": "Envía al menos un mensaje."}
    text, err = _ai_call(entry["provider"], entry["api_key"], entry.get("model", ""), system, messages)
    if err:
        return {"error": "proveedor", "message": err}
    result = _parse_contract(text)
    result["provider"] = entry["provider"]
    remember("console", "chat", workflow=body.get("workflow", "general"), role=body.get("role", "orquestador"),
             user=messages[-1]["content"][:160], agent=str(result.get("say", ""))[:160])
    return result


def ai_greet(provider, api_key, model, hostname):
    """Primera interacción: el LLM saluda Y elige su clip (contrato del framework)."""
    if provider not in AI_PROVIDERS:
        return {"error": f"Proveedor desconocido: {provider}"}
    p = AI_PROVIDERS[provider]
    model = model or p["default_model"]
    states, clips = _catalog_for_llm()
    system = (
        "Eres Acuaponsito, asistente robótico tierno de Kaanbal, una plataforma open source "
        "de DevOps/MLOps/IoT. Acabas de ser despertado por primera vez.\n"
        "Respondes SIEMPRE un único JSON válido, sin markdown ni texto extra, con esta forma:\n"
        '{"say": "<texto breve y cálido en español, máximo 2 frases>", "state": "<estado>", "clip": "<id opcional>"}\n'
        f"Estados disponibles: {states}.\n"
        f"Repertorio de clips (elige 'clip' SOLO de aquí, u omítelo):\n{clips}\n"
        "El repertorio crece con el tiempo; si dudas, indica solo 'state'."
    )
    user_msg = (
        f"El usuario acaba de activarte dentro del instalador de Kaanbal en la máquina '{hostname}'. "
        "Salúdalo por primera vez: di que ya despertaste y que lo acompañarás a cultivar su plataforma."
    )
    try:
        if p["style"] == "anthropic":
            body = json.dumps({"model": model, "max_tokens": 300, "system": system,
                               "messages": [{"role": "user", "content": user_msg}]})
            status, resp = http_json(p["base"] + p["chat_path"], _ai_headers(provider, api_key), data=body, timeout=45)
            text = resp.get("content", [{}])[0].get("text", "") if status == 200 else ""
        else:
            body = json.dumps({"model": model, "max_tokens": 300,
                               "messages": [{"role": "system", "content": system},
                                            {"role": "user", "content": user_msg}]})
            status, resp = http_json(p["base"] + p["chat_path"], _ai_headers(provider, api_key), data=body, timeout=45)
            text = resp.get("choices", [{}])[0].get("message", {}).get("content", "") if status == 200 else ""
        if status != 200:
            return {"error": f"{provider} HTTP {status}: {str(resp)[:200]}"}
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                out = json.loads(match.group(0))
                return {"say": out.get("say", text), "state": out.get("state", "greet"),
                        "clip": out.get("clip"), "model": model, "raw": text}
            except json.JSONDecodeError:
                pass
        return {"say": text.strip() or "¡Hola! Ya desperté 🌱", "state": "greet", "clip": None, "model": model}
    except Exception as e:
        return {"error": str(e)}


def validate_tailscale(client_id, client_secret, dns_suffix=""):
    suffix = (dns_suffix or "").strip().lower()
    if suffix and not suffix.endswith(".ts.net"):
        return {"valid": False, "message": "El DNS suffix debe terminar en .ts.net (ej. tailXXXX.ts.net)."}
    status, resp = http_json("https://api.tailscale.com/api/v2/oauth/token",
                             {"Content-Type": "application/x-www-form-urlencoded"},
                             data="grant_type=client_credentials", auth=(client_id, client_secret))
    if status == 200 and resp.get("access_token"):
        extra = f" DNS suffix '{suffix}' aceptado." if suffix else ""
        return {"valid": True, "message": f"OAuth de Tailscale válido. VPN lista para el tier privado.{extra}"}
    if status == 401:
        return {"valid": False, "message": "Client ID/Secret inválidos. Regenera el OAuth client en Tailscale."}
    return {"valid": False, "message": f"Tailscale respondió HTTP {status}."}


def validate_docker(username, token):
    """Autentica contra Docker Hub v2 (usuario + Access Token)."""
    status, resp = http_json("https://hub.docker.com/v2/users/login/", {"Content-Type": "application/json"},
                             data=json.dumps({"username": username, "password": token}))
    if status == 200 and resp.get("token"):
        return {"valid": True, "message": f"Autenticado en Docker Hub como '{username}'."}
    if status == 401:
        return {"valid": False, "message": "Usuario o Access Token inválidos. Crea uno en hub.docker.com/settings/security."}
    return {"valid": False, "message": f"Docker Hub respondió HTTP {status}."}


# ------------------------------------------------------------ system checks ---
def system_info():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            mem_kb = int(re.search(r"MemTotal:\s+(\d+)", f.read()).group(1))
        info["ram_gb"] = round(mem_kb / 1024 / 1024, 1)
    except Exception:
        info["ram_gb"] = None
    info["cpus"] = os.cpu_count()
    try:
        disk = shutil.disk_usage("/")
        info["disk_free_gb"] = round(disk.free / 1024**3)
    except Exception:
        info["disk_free_gb"] = None
    rc, out = run("systemctl is-system-running 2>/dev/null || true", timeout=10)
    info["systemd"] = out.strip() in ("running", "degraded")
    info["wsl"] = "microsoft" in open("/proc/version").read().lower() if os.path.exists("/proc/version") else False
    info["k3s_installed"] = shutil.which("k3s") is not None
    rc, _ = run("k3s kubectl get node --no-headers 2>/dev/null | grep -q ' Ready'", timeout=20)
    info["node_ready"] = rc == 0
    rc, _ = run("k3s kubectl get ns argocd 2>/dev/null", timeout=20)
    info["argocd_present"] = rc == 0
    info["hostname"] = socket.gethostname().lower()
    with STATE_LOCK:
        STATE["sysinfo"] = info
    return info


# --------------------------------------------------------------- instalación ---
def do_install(cfg):
    global INSTALLING, PORT_FORWARD_PROC
    try:
        set_phase("installing")
        mode = cfg.get("mode", "local")
        log(f"Iniciando instalación — modo: {'dominio público (Cloudflare)' if mode == 'cloud' else 'local / VPN'}")

        # 1. Sistema
        set_step("sistema", "running")
        info = system_info()
        if not info["systemd"]:
            raise RuntimeError("systemd no está activo. En WSL2: agrega [boot] systemd=true a /etc/wsl.conf y ejecuta wsl --shutdown")
        if (info["ram_gb"] or 0) < 3.5:
            raise RuntimeError(f"RAM insuficiente: {info['ram_gb']}GB (mínimo 4GB)")
        set_step("sistema", "done", f"{info['ram_gb']}GB RAM · {info['cpus']} CPUs · {info['disk_free_gb']}GB libres · systemd ✓")

        # 2. k3s
        set_step("k3s", "running")
        if info["k3s_installed"]:
            set_step("k3s", "done", "k3s ya instalado — detectado")
            log("k3s ya presente, se omite descarga", "ok")
        else:
            log("Descargando e instalando k3s (~60s)...")
            rc, out = run(
                f"curl -sfL https://get.k3s.io | sudo INSTALL_K3S_EXEC='--write-kubeconfig-mode 644 --node-name {info['hostname']}' sh -",
                timeout=420, stream=True)
            if rc != 0:
                raise RuntimeError("La instalación de k3s falló — revisa el log")
            set_step("k3s", "done", "k3s instalado")

        # 3. Nodo Ready
        set_step("nodo", "running")
        for i in range(60):
            rc, _ = run("k3s kubectl get node --no-headers 2>/dev/null | grep -q ' Ready'", timeout=15)
            if rc == 0:
                break
            time.sleep(5)
        else:
            raise RuntimeError("El nodo no llegó a Ready en 5 minutos")
        rc, node = kubectl("get node --no-headers")
        set_step("nodo", "done", node.split()[0] if node else "Ready")
        log(f"Nodo Kubernetes Ready: {node}", "ok")

        # 4. ArgoCD (server-side apply: evita el error del CRD de 262KB)
        set_step("argocd", "running")
        rc, _ = kubectl("get ns argocd")
        if rc != 0:
            kubectl("create namespace argocd")
        log("Aplicando manifiestos de ArgoCD (server-side)...")
        rc, out = kubectl(
            "apply --server-side --force-conflicts -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml",
            timeout=180)
        if rc != 0:
            raise RuntimeError(f"ArgoCD apply falló: {out[-400:]}")
        log("Esperando a que ArgoCD esté listo (puede tardar en la primera descarga de imágenes)...")
        rc, _ = kubectl("-n argocd rollout status deployment/argocd-server --timeout=420s", timeout=440, stream=False)
        if rc != 0:
            raise RuntimeError("argocd-server no llegó a Ready")
        rc, _ = kubectl("get crd applicationsets.argoproj.io")
        crd_ok = "✓ ApplicationSets" if rc == 0 else "sin ApplicationSets"
        set_step("argocd", "done", f"ArgoCD Ready · {crd_ok}")
        log("ArgoCD desplegado y saludable", "ok")

        # 5. Agente IA — los proveedores validados se vuelven parte del SISTEMA
        set_step("ia", "running")
        providers = cfg.get("ai_providers") or STATE.get("ai_providers") or []
        if not providers:
            # el agente ahora se configura en el Acuaponsito Runtime — leer su config
            try:
                with open(os.path.expanduser("~/.acuaponsito/agent.config.json"), encoding="utf-8") as f:
                    providers = json.load(f).get("providers", [])
            except Exception:
                providers = []
        if providers:
            payload = json.dumps(providers)
            tmp_ai = "/tmp/kaanbal-ai-secret.json"
            with open(tmp_ai, "w") as f:
                f.write(payload)
            kubectl("get ns prod || k3s kubectl create namespace prod", timeout=30)
            rc, _ = run(
                "k3s kubectl -n prod create secret generic kaanbal-ai-providers "
                f"--from-file=providers.json={tmp_ai} --dry-run=client -o yaml | k3s kubectl apply -f -",
                timeout=30)
            os.remove(tmp_ai)
            if rc != 0:
                raise RuntimeError("No se pudo guardar el secret de proveedores IA")
            names = ", ".join(p["provider"] for p in providers)
            set_step("ia", "done", f"Proveedores en el cluster: {names} — los agentes del sistema ya pueden usarlos")
            log(f"Agente(s) IA integrados al sistema: {names}", "ok")
        else:
            set_step("ia", "skipped", "Sin proveedor IA — configúralo después en la consola")
            log("Paso IA omitido (sin proveedores validados)")

        # 5b. Credenciales base de la plataforma (Docker registry + Tailscale VPN)
        kubectl("get ns prod || k3s kubectl create namespace prod", timeout=30)
        dk_user = (cfg.get("docker_user") or "").strip()
        dk_token = (cfg.get("docker_token") or "").strip()
        if dk_user and dk_token:
            import base64 as _b64
            auth = _b64.b64encode(f"{dk_user}:{dk_token}".encode()).decode()
            dockercfg = _b64.b64encode(json.dumps({"auths": {"https://index.docker.io/v1/":
                {"username": dk_user, "password": dk_token, "auth": auth}}}).encode()).decode()
            secret_yaml = ("apiVersion: v1\nkind: Secret\nmetadata:\n  name: regcred\n  namespace: prod\n"
                           "type: kubernetes.io/dockerconfigjson\ndata:\n"
                           f"  .dockerconfigjson: {dockercfg}\n")
            tmp = "/tmp/kaanbal-regcred.yaml"
            with open(tmp, "w") as f:
                f.write(secret_yaml)
            kubectl(f"apply -f {tmp}", timeout=30)
            os.remove(tmp)
            log(f"Docker Hub conectado: secret 'regcred' listo (pull/push como {dk_user})", "ok")

        ts_id = (cfg.get("tailscale_id") or "").strip()
        ts_secret = (cfg.get("tailscale_secret") or "").strip()
        if ts_id and ts_secret:
            kubectl("get ns tailscale || k3s kubectl create namespace tailscale", timeout=30)
            rc, _ = run(
                "k3s kubectl -n tailscale create secret generic operator-oauth "
                f"--from-literal=client_id='{ts_id}' --from-literal=client_secret='{ts_secret}' "
                "--dry-run=client -o yaml | k3s kubectl apply -f -", timeout=30)
            if rc == 0:
                log("Tailscale conectado: secret 'operator-oauth' listo — el tier privado/VPN queda disponible", "ok")

        # 6. Cloudflare Tunnel (tier público) — AQUÍ el dominio cobra vida
        set_step("cloudflared", "running")
        domain = (cfg.get("domain") or "").strip().lower().lstrip("*.").rstrip("/")
        cf_token = (cfg.get("cf_token") or cfg.get("cloudflare_token") or "").strip()
        cf_account = (cfg.get("cf_account") or cfg.get("cloudflare_account_id") or "").strip()
        tunnel_token = (cfg.get("tunnel_token") or "").strip()
        if mode != "cloud":
            set_step("cloudflared", "skipped", "Modo local sin dominio — actívalo después desde la consola")
            log("Tier público omitido (modo local)")
        elif not domain:
            set_step("cloudflared", "failed", "Falta el dominio — la célula quedó lista, sin salida pública")
            log("⚠ Sin dominio: no puedo publicar a internet. Vuelve a Conectividad y pon tu dominio.", "warn")
        else:
            hostname = socket.gethostname().lower()
            with STATE_LOCK:
                STATE["domain"] = domain
            # 1) obtener el tunnel_token: creándolo vía API (ideal) o el que pegó el usuario
            if not tunnel_token and cf_token and cf_account:
                log(f"Creando túnel Cloudflare para {domain} (control plane vía API)...")
                res = create_cloudflare_tunnel(cf_token, cf_account, domain, hostname, log_fn=log)
                if res.get("error"):
                    set_step("cloudflared", "failed", f"Cloudflare: {res['error']} — célula lista igual")
                    log(f"⚠ No se pudo crear el túnel: {res['error']}. Revisa scopes del token.", "warn")
                    tunnel_token = None
                else:
                    tunnel_token = res.get("tunnel_token")
                    with STATE_LOCK:
                        STATE["tunnel_dns"] = res.get("dns", [])
            if tunnel_token:
                # 2) secret + 3) correr cloudflared (data plane: conexión saliente al edge)
                kubectl("get ns prod || k3s kubectl create namespace prod", timeout=30)
                rc, _ = run(
                    "k3s kubectl -n prod create secret generic cloudflared-secrets "
                    f"--from-literal=TUNNEL_TOKEN='{tunnel_token}' --dry-run=client -o yaml | k3s kubectl apply -f -",
                    timeout=30)
                if rc != 0:
                    raise RuntimeError("No se pudo crear el secret del túnel")
                tmp_cf = "/tmp/kaanbal-cloudflared.yaml"
                with open(tmp_cf, "w") as f:
                    f.write(CLOUDFLARED_DEPLOYMENT)
                kubectl(f"apply -f {tmp_cf}", timeout=40)
                os.remove(tmp_cf)
                kubectl("-n prod rollout status deployment/cloudflared --timeout=120s", timeout=130, stream=False)
                set_step("cloudflared", "done", f"Túnel activo — {domain} servido desde esta máquina 🌐")
                log(f"🌐 Tier público EN VIVO: https://{domain} y *.{domain} salen por Cloudflare (sin IP pública)", "ok")
            elif not cf_token:
                set_step("cloudflared", "skipped", "Sin credenciales Cloudflare — pega tu token en Conectividad")
                log("Túnel omitido: faltó token de Cloudflare para crearlo.", "warn")

        # 6. Bootstrap GitOps (OPCIONAL — su fallo nunca aborta la instalación)
        set_step("gitops", "running")
        repo_url = (cfg.get("gitops_url") or "").strip()
        repo_token = (cfg.get("gitops_token") or "").strip()
        if not repo_url:
            set_step("gitops", "skipped", "Sin repo — conéctalo después desde la consola")
            log("Bootstrap GitOps omitido (sin repo configurado)")
        else:
            # normalizar/validar la URL: debe ser un REPO, no una página de org/usuario
            norm = repo_url
            if norm.endswith("/"):
                norm = norm[:-1]
            bad = None
            m = re.match(r"https?://github\.com/(orgs|users)/([^/]+)/?$", norm)
            if m:
                bad = (f"'{norm}' es la página de {'organización' if m.group(1)=='orgs' else 'usuario'} "
                       f"'{m.group(2)}', no un repositorio. Usa la URL del repo: "
                       f"https://github.com/{m.group(2)}/infra-gitops.git")
            elif re.match(r"https?://github\.com/[^/]+/?$", norm):
                bad = f"'{norm}' parece un perfil, no un repo. Falta el nombre del repositorio (…/infra-gitops.git)."
            if bad:
                set_step("gitops", "failed", "URL de repo inválida — la célula quedó lista igual")
                log("⚠ GitOps: " + bad, "warn")
                log("Puedes conectar el repo después desde la consola; sigo con el despliegue.", "info")
            else:
                if not norm.endswith(".git"):
                    norm += ".git"
                try:
                    if repo_token:
                        secret_yaml = f"""apiVersion: v1
kind: Secret
metadata:
  name: kaanbal-infra-gitops-repo
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
stringData:
  type: git
  url: {norm}
  username: kaanbal
  password: {repo_token}
"""
                        tmp = "/tmp/kaanbal-repo-secret.yaml"
                        with open(tmp, "w") as f:
                            f.write(secret_yaml)
                        kubectl(f"apply -f {tmp}", timeout=30)
                        os.remove(tmp)
                    clone_url = norm if not repo_token else norm.replace("https://", f"https://kaanbal:{repo_token}@")
                    rc, out = run(f"rm -rf /tmp/kaanbal-gitops && git clone --depth 1 '{clone_url}' /tmp/kaanbal-gitops", timeout=120)
                    if rc == 0 and os.path.exists("/tmp/kaanbal-gitops/argocd/bootstrap/app-of-apps.yaml"):
                        kubectl("apply -f /tmp/kaanbal-gitops/argocd/bootstrap/app-of-apps.yaml", timeout=30)
                        set_step("gitops", "done", "app-of-apps aplicado — la célula reconcilia tu repo")
                        log("GitOps conectado: ArgoCD desplegará la plataforma completa", "ok")
                    elif rc == 0:
                        set_step("gitops", "done", "Repo clonado; sin app-of-apps — aplica tus Applications luego")
                    else:
                        set_step("gitops", "failed", "No se pudo clonar — la célula quedó lista igual")
                        log(f"⚠ GitOps: no se pudo clonar '{norm}'. ¿Existe el repo y el token tiene acceso?", "warn")
                        log("Sigo con el despliegue; conecta el repo después desde la consola.", "info")
                except Exception as ge:
                    set_step("gitops", "failed", "Error en GitOps — la célula quedó lista igual")
                    log(f"⚠ GitOps falló: {ge}. Continúo con el despliegue.", "warn")

        # 7. Acceso operativo
        set_step("acceso", "running")
        rc, pwd = kubectl("-n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}'")
        password = ""
        if rc == 0 and pwd.strip():
            import base64
            password = base64.b64decode(pwd.strip()).decode()
        if PORT_FORWARD_PROC is None or PORT_FORWARD_PROC.poll() is not None:
            PORT_FORWARD_PROC = subprocess.Popen(
                "k3s kubectl -n argocd port-forward svc/argocd-server 8080:443 --address 0.0.0.0",
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
        rc, node = kubectl("get node --no-headers")
        with STATE_LOCK:
            dom = STATE.get("domain", "")
            live = bool(dom) and STATE.get("steps", {}).get("cloudflared", {}).get("status") == "done"
            # si el túnel quedó en vivo, el acceso primario es por dominio + HTTPS de Cloudflare
            argocd_url = f"https://argocd.{dom}" if live else "https://localhost:8080"
            if not live and dom:
                # dominio configurado pero túnel no activó: seguimos dando acceso local + aviso
                argocd_url = "https://localhost:8080"
            STATE["handoff"] = {
                "domain": dom,
                "tunnel_live": live,
                "console_url": f"https://{dom}" if live else "",
                "argocd_url": argocd_url,
                "argocd_user": "admin",
                "argocd_password": password or "(rotado — usa argocd admin initial-password)",
                "kubeconfig": "/etc/rancher/k3s/k3s.yaml",
                "node": node.split()[0] if node else "",
                "dns": STATE.get("tunnel_dns", []),
            }
        if live:
            set_step("acceso", "done", f"En vivo: https://{dom} · ArgoCD en https://argocd.{dom}")
            log(f"🎉 Célula EN LA NUBE: tu dominio {dom} ya sirve desde esta máquina (HTTPS por Cloudflare)", "ok")
            log("El DNS puede tardar 1-2 min en propagar la primera vez.", "info")
        else:
            set_step("acceso", "done", "ArgoCD en https://localhost:8080 (túnel no activo — revisa Cloudflare)")
            log("Célula Kaanbal operativa 🎉 (acceso local; para dominio revisa el paso Túnel)", "ok")
        set_phase("done")
        emit("handoff", **STATE["handoff"])

    except Exception as e:
        log(f"ERROR: {e}", "error")
        with STATE_LOCK:
            for sid, s in STATE["steps"].items():
                if s["status"] == "running":
                    STATE["steps"][sid] = {"status": "error", "detail": str(e)}
                    emit("step", step=sid, status="error", detail=str(e))
                    break
        set_phase("error")
    finally:
        INSTALLING = False


# ------------------------------------------------------------------ HTTP ---
MIME = {".html": "text/html", ".css": "text/css", ".js": "application/javascript",
        ".mp4": "video/mp4", ".svg": "image/svg+xml", ".png": "image/png",
        ".json": "application/json", ".woff2": "font/woff2"}


class Handler(BaseHTTPRequestHandler):
    server_version = "KaanbalInstaller/1.0"

    def log_message(self, fmt, *args):
        pass  # silencio: la terminal es para el token y eventos importantes

    def _auth_ok(self):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        token = q.get("token", [None])[0] or self.headers.get("X-Kaanbal-Token")
        return token == TOKEN

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        path = urllib.parse.unquote(path)
        root = STATIC_DIR
        if path.startswith("/anim/") and ANIM_DIR:  # clips servidos DESDE la carpeta animacion
            root = ANIM_DIR
            path = path[len("/anim/"):]
        fpath = os.path.normpath(os.path.join(root, path.lstrip("/")))
        if not fpath.startswith(os.path.normpath(root)) or not os.path.isfile(fpath):
            self.send_error(404)
            return
        ext = os.path.splitext(fpath)[1]
        ctype = MIME.get(ext, "application/octet-stream")
        size = os.path.getsize(fpath)
        range_header = self.headers.get("Range")
        with open(fpath, "rb") as f:
            if range_header:  # soporte Range para los clips de Acuaponsito
                m = re.match(r"bytes=(\d+)-(\d*)", range_header)
                start = int(m.group(1)) if m else 0
                end = int(m.group(2)) if m and m.group(2) else size - 1
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(length))
                self.end_headers()
                f.seek(start)
                self.wfile.write(f.read(length))
            else:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                shutil.copyfileobj(f, self.wfile)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self._serve_static(parsed.path)
        if not self._auth_ok():
            return self._json(401, {"error": "Token inválido. Usa la URL impresa en la terminal."})

        if parsed.path == "/api/state":
            with STATE_LOCK:
                snapshot = json.loads(json.dumps({k: v for k, v in STATE.items() if k != "ai_providers"}))
                snapshot["ai_providers"] = [{"provider": p["provider"], "model": p.get("model", "")}
                                            for p in STATE.get("ai_providers", [])]
            snapshot["installing"] = INSTALLING
            snapshot["hostname"] = socket.gethostname().lower()
            return self._json(200, snapshot)

        if parsed.path == "/api/observe":
            return self._json(200, observe())

        if parsed.path == "/api/memory":
            q = parse_qs(parsed.query)
            limit = int(q.get("limit", ["120"])[0])
            return self._json(200, {"file": MEMORY_FILE, "events": recall(limit)})

        if parsed.path == "/api/agent/config":
            return self._json(200, {"workflows": WORKFLOWS, "roles": ROLES})

        if parsed.path == "/api/system-check":
            return self._json(200, system_info())

        if parsed.path == "/api/catalog":
            return self._json(200, load_catalog())

        if parsed.path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            q = parse_qs(parsed.query)
            since = int(q.get("since", ["0"])[0])
            try:
                with STATE_LOCK:
                    backlog = EVENTS[since:]
                for i, ev in enumerate(backlog, start=since):
                    self.wfile.write(f"id: {i + 1}\ndata: {json.dumps(ev)}\n\n".encode())
                self.wfile.flush()
                idx = since + len(backlog)
                while True:
                    try:
                        ev = EVENT_Q.get(timeout=15)
                        with STATE_LOCK:
                            idx = len(EVENTS)
                        self.wfile.write(f"id: {idx}\ndata: {json.dumps(ev)}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
        self.send_error(404)

    def do_POST(self):
        global INSTALLING
        from urllib.parse import urlparse
        parsed = urlparse(self.path)
        if not self._auth_ok():
            return self._json(401, {"error": "Token inválido"})
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode() or "{}")

        if parsed.path == "/api/validate":
            kind = body.get("kind")
            if kind == "cloudflare":
                return self._json(200, validate_cloudflare(body.get("token", ""), body.get("account_id", "")))
            if kind == "github":
                return self._json(200, validate_github(body.get("token", "")))
            if kind == "tailscale":
                return self._json(200, validate_tailscale(body.get("client_id", ""), body.get("client_secret", ""),
                                                          body.get("dns_suffix", "")))
            if kind == "docker":
                return self._json(200, validate_docker(body.get("username", ""), body.get("token", "")))
            return self._json(400, {"error": f"kind desconocido: {kind}"})

        if parsed.path == "/api/ai/validate":
            return self._json(200, validate_ai(body.get("provider", ""), body.get("api_key", "")))

        if parsed.path == "/api/ai/greet":
            result = ai_greet(body.get("provider", ""), body.get("api_key", ""),
                              body.get("model", ""), socket.gethostname())
            return self._json(200 if "error" not in result else 502, result)

        if parsed.path == "/api/ai/chat":
            result = ai_chat(body)
            return self._json(200 if "error" not in result else 400, result)

        if parsed.path == "/api/memory":
            event = remember(body.get("source", "console"), body.get("kind", "accion"),
                             **{k: v for k, v in body.items() if k not in ("source", "kind")})
            return self._json(201, event)

        if parsed.path == "/api/catalog/clip":
            # Registrar un clip nuevo en la tabla master (animacion/catalog.json)
            if not ANIM_DIR:
                return self._json(400, {"error": "Carpeta animacion no disponible"})
            required = ("id", "file", "state")
            if not all(body.get(k) for k in required):
                return self._json(400, {"error": f"Campos requeridos: {required}"})
            if not os.path.isfile(os.path.join(ANIM_DIR, body["file"])):
                return self._json(400, {"error": f"El archivo '{body['file']}' no existe en la carpeta animacion"})
            cat_path = os.path.join(ANIM_DIR, "catalog.json")
            with open(cat_path, encoding="utf-8") as f:
                cat = json.load(f)
            if any(c["id"] == body["id"] for c in cat["clips"]):
                return self._json(409, {"error": f"Ya existe un clip con id '{body['id']}'"})
            shutil.copyfile(cat_path, cat_path + ".bak")  # respaldo antes de tocar la tabla master
            clip = {
                "id": body["id"], "file": body["file"], "state": body["state"],
                "title": body.get("title", body["id"]),
                "description": body.get("description", ""),
                "energy": body.get("energy", "media"), "loop": body.get("loop", True),
                "tags": body.get("tags", []), "added": time.strftime("%Y-%m-%d"),
            }
            cat["clips"].append(clip)
            if body["state"] not in cat.get("states", {}):
                cat.setdefault("states", {})[body["state"]] = {
                    "desc": body.get("state_desc", body["state"]), "fallback": "idle"}
            with open(cat_path, "w", encoding="utf-8") as f:
                json.dump(cat, f, ensure_ascii=False, indent=2)
            remember("console", "clip-registrado", clip_id=clip["id"], state=clip["state"])
            return self._json(201, {"message": "Clip agregado a la tabla master", "clip": clip})

        if parsed.path == "/api/install":
            if INSTALLING:
                return self._json(409, {"error": "Instalación ya en curso"})
            INSTALLING = True
            threading.Thread(target=do_install, args=(body,), daemon=True).start()
            return self._json(202, {"message": "Instalación iniciada", "stream": "/api/stream"})

        self.send_error(404)


def _launch_agent_runtime():
    """El agente (Acuaponsito Runtime) arranca JUNTO con el instalador,
    compartiendo token. Es un servicio aparte: el instalador solo lo embebe."""
    runtime = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "acuaponsito", "server.py"))
    if not os.path.isfile(runtime):
        return None
    try:  # ¿ya está corriendo?
        socket.create_connection(("127.0.0.1", 4600), timeout=1).close()
        return "existente"
    except OSError:
        pass
    env = {**os.environ, "ACUA_TOKEN": TOKEN}
    if ANIM_DIR:
        env["KAANBAL_ANIM_DIR"] = ANIM_DIR
    subprocess.Popen([sys.executable, runtime], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "lanzado"


def main():
    os.chdir(STATIC_DIR)
    agent = _launch_agent_runtime()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    url = f"http://localhost:{PORT}/?token={TOKEN}"
    print("=" * 62)
    print("  🌱 Kaanbal Web Installer")
    print("=" * 62)
    print(f"  URL de acceso (incluye tu token de sesión):\n")
    print(f"    {url}\n")
    print("  En un VPS: http://<IP-DEL-SERVIDOR>:%d/?token=%s" % (PORT, TOKEN))
    if agent:
        print(f"  Agente  : Acuaponsito Runtime {agent} en :4600 (mismo token)")
    print("=" * 62, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
