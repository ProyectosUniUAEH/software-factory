/* Kaanbal Installer v2 — AcuaBot framework player + wizard + SSE
   AcuaBot es la implementación de referencia del Acuaponsito Framework
   (ver animacion/ACUAPONSITO_FRAMEWORK.md) — reutilizable en otros proyectos. */
(() => {
  const TOKEN = new URLSearchParams(location.search).get("token") || "";
  const api = (p) => `${p}${p.includes("?") ? "&" : "?"}token=${encodeURIComponent(TOKEN)}`;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];

  /* ═══ El agente es el Acuaponsito Runtime (:4600) — el flotante es SU embed ═══ */
  const RT = `${location.protocol}//${location.hostname}:4600`;
  const rt = (p) => `${RT}${p}${p.includes("?") ? "&" : "?"}token=${encodeURIComponent(TOKEN)}`;
  (() => {
    const s = document.createElement("script");
    s.src = `${RT}/embed.js`;
    s.dataset.token = TOKEN;
    document.body.appendChild(s);
  })();
  /* el estado del personaje lo gobierna el runtime; el instalador ya no actúa clips */
  const bot = { async load() {}, setState() {}, speak() {}, applyLLM() {}, awake() {}, playClip() {} };

  /* ═══════════════ wizard ═══════════════ */
  function show(id) {
    $$(".screen").forEach((s) => s.classList.remove("active"));
    $(`#screen-${id}`).classList.add("active");
  }
  const setPhaseChip = (t) => ($("#chip-phase").textContent = t);

  /* chequeo de sistema */
  const CHECKS = [
    ["ram_gb", (v) => [v >= 4, `${v} GB RAM`, "mínimo 4 GB"]],
    ["cpus", (v) => [v >= 2, `${v} CPUs`, "mínimo 2"]],
    ["disk_free_gb", (v) => [v >= 15, `${v} GB libres`, "recomendado 20+"]],
    ["systemd", (v) => [v, "systemd activo", "requerido"]],
    ["wsl", (v) => [true, v ? "WSL2 detectado" : "Linux nativo", ""]],
    ["k3s_installed", (v) => [true, v ? "k3s ya presente" : "k3s se instalará", ""]],
    ["argocd_present", (v) => [true, v ? "ArgoCD ya presente" : "ArgoCD se instalará", ""]],
  ];
  async function systemCheck() {
    try {
      const r = await fetch(api("/api/system-check"));
      if (r.status === 401) { alert("Token inválido — usa la URL completa impresa en la terminal."); return; }
      const info = await r.json();
      $("#chip-host").textContent = info.hostname || "célula";
      const grid = $("#check-grid"); grid.innerHTML = "";
      let allOk = true;
      for (const [key, fn] of CHECKS) {
        const [ok, label, hint] = fn(info[key]);
        if (!ok) allOk = false;
        grid.insertAdjacentHTML("beforeend",
          `<div class="check"><span class="${ok ? "ok" : "bad"}">${ok ? "✓" : "✕"}</span>
           <span>${label} ${hint && !ok ? `<small>· ${hint}</small>` : ""}</span></div>`);
      }
      $("#sys-spin").classList.add("hidden");
      $("#btn-start").disabled = !allOk;
      setPhaseChip(allOk ? "sistema listo" : "revisa requisitos");
    } catch {
      $("#check-grid").innerHTML = `<div class="check"><span class="bad">✕</span><span>Sin conexión con el backend</span></div>`;
    }
  }

  /* ═══ Paso 1: el agente se configura EN SU PROPIO panel (runtime :4600) ═══ */
  const aiProviders = [];   // el paso "ia" del despliegue lee providers del runtime en el backend
  let aiAwake = false;
  async function pollRuntime() {
    try {
      const b = await (await fetch(rt("/api/boot"))).json();
      $("#rt-status").innerHTML =
        `<span class="ok">✓</span><span>${b.agent.name} en línea <small>· servicio :4600</small></span>`;
      $("#rt-guardian").innerHTML = b.needs_admin
        ? `<span class="info">—</span><span>Guardián (admin): pendiente — créalo en el panel</span>`
        : `<span class="ok">✓</span><span>Guardián creado</span>`;
      if (b.agent.has_provider) {
        const p = b.agent.providers[0] || {};
        $("#rt-provider").innerHTML =
          `<span class="ok">✓</span><span>Despierto 🌱 · ${p.provider} <small>${p.model}</small></span>`;
        if (!aiAwake) {
          aiAwake = true;
          $("#btn-ia-next").disabled = false;
          setPhaseChip("agente despierto");
          $("#msg-ai").className = "val-msg ok";
          $("#msg-ai").textContent = "✓ Tu agente está listo — te acompañará en toda la plataforma";
        }
      } else {
        $("#rt-provider").innerHTML =
          `<span class="info">—</span><span>Proveedor IA: dormido 💤 — despiértalo en el panel</span>`;
      }
    } catch {
      $("#rt-status").innerHTML =
        `<span class="bad">✕</span><span>El agente no responde en :4600 — revisa la terminal del instalador</span>`;
    }
  }
  setInterval(pollRuntime, 3000);
  $("#btn-ia-open").addEventListener("click", () => {
    window.postMessage({ acua: true, kind: "open" }, "*");
    $("#msg-ai").className = "val-msg wait";
    $("#msg-ai").textContent = "Panel abierto → crea al guardián y conéctale su proveedor";
  });

  /* modo + validaciones infra */
  let mode = "cloud";
  $$(".mode-card").forEach((card) => card.addEventListener("click", () => {
    $$(".mode-card").forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");
    mode = card.dataset.mode;
    $("#cloud-fields").style.opacity = mode === "cloud" ? "1" : ".35";
  }));
  const validated = {};   // proveedores confirmados en esta sesión
  async function validate(kind, payload, msgEl, stateEl) {
    msgEl.className = "val-msg wait"; msgEl.textContent = "Validando…";
    try {
      const r = await fetch(api("/api/validate"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, ...payload }),
      });
      const res = await r.json();
      msgEl.className = `val-msg ${res.valid ? "ok" : "bad"}`;
      msgEl.textContent = (res.valid ? "✓ " : "✕ ") + res.message;
      validated[kind] = !!res.valid;
      if (stateEl) {
        stateEl.className = `cred-state ${res.valid ? "ok" : "bad"}`;
        stateEl.textContent = res.valid ? "✓ conectado" : "✕ revisar";
      }
    } catch {
      msgEl.className = "val-msg bad"; msgEl.textContent = "✕ Error de conexión";
      if (stateEl) { stateEl.className = "cred-state bad"; stateEl.textContent = "✕ sin conexión"; }
    }
  }
  $("#btn-val-cf").addEventListener("click", () =>
    validate("cloudflare", { token: $("#f-cf-token").value, account_id: $("#f-cf-account").value }, $("#msg-cf")));
  $("#btn-val-gh").addEventListener("click", () =>
    validate("github", { token: $("#f-git-token").value }, $("#msg-gh"), $("#st-gh")));
  $("#btn-val-dk").addEventListener("click", () =>
    validate("docker", { username: $("#f-dk-user").value, token: $("#f-dk-token").value }, $("#msg-dk"), $("#st-dk")));
  $("#btn-val-ts").addEventListener("click", () =>
    validate("tailscale", { client_id: $("#f-ts-id").value, client_secret: $("#f-ts-secret").value,
      dns_suffix: $("#f-ts-dns").value }, $("#msg-ts"), $("#st-ts")));

  /* despliegue: SSE + pasos + terminal */
  const term = $("#term");
  function termLine(line, level) {
    const div = document.createElement("div");
    div.className = `l-${level || "info"}`;
    div.textContent = line;
    term.appendChild(div);
    term.scrollTop = term.scrollHeight;
  }
  function applyStep(step, status, detail) {
    const li = $(`.steps li[data-step="${step}"]`);
    if (!li) return;
    li.className = status;
    if (detail) li.querySelector("small").textContent = detail;
  }
  function connectStream() {
    const es = new EventSource(api("/api/stream"));
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.kind === "log") termLine(ev.line, ev.level);
      if (ev.kind === "step") applyStep(ev.step, ev.status, ev.detail);
      if (ev.kind === "phase") {
        setPhaseChip(ev.phase === "installing" ? "desplegando…" : ev.phase === "done" ? "operativa" : ev.phase);
        if (ev.phase === "error") {
          bot.setState("error");
          bot.speak("Algo detuvo el cultivo… revisa la bitácora, corrige y reintenta. No se pierde el progreso.");
          $("#deploy-title").textContent = "Algo detuvo el cultivo — revisa la bitácora";
        }
      }
      if (ev.kind === "handoff") finish(ev);
    };
    return es;
  }
  function finish(h) {
    $("#done-node").textContent = h.node || "kaanbal";
    $("#h-url").textContent = h.argocd_url; $("#h-url").href = h.argocd_url;
    $("#btn-open-argo").href = h.argocd_url;
    $("#h-pass").textContent = h.argocd_password;
    $("#h-kube").textContent = h.kubeconfig;
    if (h.tunnel_live && h.console_url) {
      $("#h-domain-row").style.display = "";
      $("#h-console").textContent = h.console_url; $("#h-console").href = h.console_url;
      $("#btn-open-argo").href = h.console_url;
      if (h.dns && h.dns.length) { $("#h-dns-row").style.display = ""; $("#h-dns").textContent = h.dns.join("  ·  "); }
      bot.speak(`¡Tu plataforma está EN VIVO en ${h.domain}! 🌐 HTTPS por Cloudflare, sin abrir puertos.`);
    } else if (h.domain) {
      bot.speak("Célula viva 🎉 — el túnel no activó del todo; revisa el paso Túnel en la bitácora.");
    } else {
      bot.speak("¡Tu célula está viva! 🎉 Para salir a internet, configura tu dominio en Conectividad.");
    }
    bot.setState("celebrate");
    setPhaseChip("operativa");
    setTimeout(() => show("done"), 900);
  }
  $("#btn-copy-pass").addEventListener("click", () => {
    navigator.clipboard.writeText($("#h-pass").textContent);
    $("#btn-copy-pass").textContent = "✓ copiado";
    setTimeout(() => ($("#btn-copy-pass").textContent = "copiar"), 1600);
  });

  /* navegación */
  $("#btn-start").addEventListener("click", () => { show("ia"); pollRuntime(); });
  $("#btn-back-welcome").addEventListener("click", () => show("welcome"));
  $("#btn-ia-next").addEventListener("click", () => { show("mode"); bot.setState("listen"); });
  $("#btn-ia-skip").addEventListener("click", () => { show("mode"); });
  $("#btn-back-ia").addEventListener("click", () => show("ia"));
  $("#btn-deploy").addEventListener("click", async () => {
    const cfg = {
      mode,
      domain: $("#f-domain").value,
      cf_token: $("#f-cf-token").value,
      cf_account: $("#f-cf-account").value,
      tunnel_token: $("#f-tunnel").value,
      gitops_url: $("#f-git-url").value,
      gitops_token: $("#f-git-token").value,
      docker_user: $("#f-dk-user").value,
      docker_token: $("#f-dk-token").value,
      tailscale_id: $("#f-ts-id").value,
      tailscale_secret: $("#f-ts-secret").value,
      tailscale_dns: $("#f-ts-dns").value,
      ai_providers: aiProviders,
    };
    show("deploy");
    bot.setState("think");
    setPhaseChip("desplegando…");
    connectStream();
    const r = await fetch(api("/api/install"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    });
    if (r.status === 409) termLine("Instalación ya en curso — mostrando progreso actual", "info");
  });

  /* arranque: Acuaponsito duerme hasta que el agente IA exista */
  (async function boot() {
    pollRuntime();
    await systemCheck();
    try {
      const st = await (await fetch(api("/api/state"))).json();
      if (st.phase === "installing") {
        show("deploy"); bot.setState("think"); setPhaseChip("desplegando…");
        for (const [sid, s] of Object.entries(st.steps)) applyStep(sid, s.status, s.detail);
        connectStream();
      } else if (st.phase === "done" && st.handoff.argocd_url) {
        for (const [sid, s] of Object.entries(st.steps)) applyStep(sid, s.status, s.detail);
        finish(st.handoff); show("done");
      }
    } catch {}
  })();
})();
