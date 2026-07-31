#!/usr/bin/env python3
"""Pasa consola/API/agente a exposición pública y republica infra-gitops."""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "installer"))

import gitops_publish  # noqa: E402
import gitops_render  # noqa: E402
from server import (  # noqa: E402
    detect_ingress_class,
    kubectl,
    load_credentials,
    parse_env_text,
    run,
    save_credentials,
)


def log(msg, level="info"):
    print(f"[{level}] {msg}", flush=True)


def image_tag(deploy):
    rc, out = kubectl(
        f"-n prod get deploy {deploy} -o jsonpath='{{.spec.template.spec.containers[0].image}}'"
    )
    if rc != 0 or not (out or "").strip():
        return "bootstrap"
    image = out.strip().strip("'")
    return image.rsplit(":", 1)[-1] if ":" in image else "bootstrap"


def main():
    env_path = sys.argv[1] if len(sys.argv) > 1 else "/etc/kaanbal/installer.env"
    with open(env_path, encoding="utf-8") as fh:
        cfg = parse_env_text(fh.read())

    # Forzar público (Cloudflare + Traefik Ingress)
    cfg["console_exposure"] = "public"
    cfg["api_exposure"] = "public"
    cfg["agent_exposure"] = "public"
    cfg["mode"] = cfg.get("mode") or "cloud"
    cfg["gitops_repo"] = "infra-gitops"
    cfg["ingress_class"] = detect_ingress_class()
    cfg["tailscale_ready"] = bool(cfg.get("tailscale_id") and cfg.get("tailscale_secret"))
    cfg["api_tag"] = image_tag("kaanbal-api")
    cfg["console_tag"] = image_tag("kaanbal-console")
    cfg["agent_tag"] = image_tag("kaanbal-agent")

    token = (cfg.get("gitops_token") or "").strip()
    org = (cfg.get("github_org") or "").strip()
    if not token or not org:
        raise SystemExit("Faltan github_org / gitops_token en installer.env")

    log(f"Renderizando baseline público para {cfg.get('domain')} "
        f"(api={cfg['api_tag']} console={cfg['console_tag']} agent={cfg['agent_tag']})")

    context, flags = gitops_render.build_context(cfg)
    assert flags["CONSOLE_PUBLIC"] and flags["API_PUBLIC"] and flags["AGENT_PUBLIC"]

    infra_src = os.path.join(ROOT, "infra-gitops")
    render_rules = gitops_render.load_baseline(infra_src, flags)
    owned_rules = gitops_render.load_baseline(infra_src)
    rendered = "/tmp/kaanbal-baseline-public"
    written = gitops_render.render_tree(
        infra_src, rendered, context, flags, render_rules)
    log(f"Render OK: {len(written)} archivos")

    failures = gitops_render.validate_rendered(rendered)
    if failures:
        detail = "; ".join(f"{t}: {e}" for t, e in failures[:3])
        raise SystemExit(f"kustomize falló: {detail}")

    sha, err = gitops_publish.publish_baseline(
        run, token, org, "infra-gitops", rendered, owned_rules, log_fn=log)
    if err:
        raise SystemExit(err)
    log(f"infra-gitops publicado: {sha[:12] if sha else '?'}")

    # Persistir exposición pública para futuras reinstals
    try:
        save_credentials({
            **load_credentials(),
            "console_exposure": "public",
            "api_exposure": "public",
            "agent_exposure": "public",
            "mode": "cloud",
        })
        log("Credenciales actualizadas: console/api/agent = public")
    except Exception as exc:
        log(f"No pude guardar installer.env: {exc}", "warn")

    # Forzar sync ArgoCD de apps core
    for app in (
        "kaanbal-console-prod",
        "kaanbal-api-prod",
        "kaanbal-agent-prod",
        "applicationsets",
        "core-config",
    ):
        kubectl(
            f"-n argocd patch application {app} --type merge "
            f"-p '{{\"metadata\":{{\"annotations\":{{\"argocd.argoproj.io/refresh\":\"hard\"}}}}}}'"
        )
        kubectl(
            f"-n argocd annotate application {app} "
            "argocd.argoproj.io/refresh=hard --overwrite"
        )

    log("Esperando Ingress de consola…")
    for i in range(36):
        rc, out = kubectl("-n prod get ingress kaanbal-console -o name")
        if rc == 0 and out.strip():
            log(f"Ingress presente: {out.strip()}", "ok")
            break
        time.sleep(5)
    else:
        log("Ingress aún no aparece — revisa ArgoCD sync", "warn")

    domain = cfg.get("domain") or ""
    for host in (f"https://kaanbal-console.{domain}/",
                 f"https://kaanbal.{domain}/",
                 f"https://kaanbal-api.{domain}/api/v1/health"):
        rc, out = run(f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time 20 '{host}'",
                      timeout=30)
        log(f"probe {host} → {(out or '').strip()} (rc={rc})")

    print("DONE_PUBLIC_CORE", flush=True)


if __name__ == "__main__":
    main()
