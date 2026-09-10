<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent">Updates</h1>
        <p class="mt-2 text-slate-400">La versión del engine que corre esta célula y lo que hay publicado.</p>
      </div>
      <button @click="load" :disabled="loading" class="glass-button text-sm flex items-center gap-2">
        <span :class="{'animate-spin': loading}">🔄</span> Revisar
      </button>
    </div>

    <div v-if="loading && !data" class="text-center py-12 text-slate-400">Consultando upstream...</div>

    <template v-if="data">
      <!-- Versión actual -->
      <div class="glass-panel p-6 rounded-xl">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p class="text-xs uppercase tracking-wider text-slate-500">Versión instalada</p>
            <p class="text-2xl font-bold text-white mt-1">{{ data.current.version }}</p>
            <p v-if="!data.current.known" class="text-sm text-amber-300 mt-2 max-w-xl">
              {{ data.current.reason }}
            </p>
            <p v-else-if="data.current.upstream_sha" class="text-xs font-mono text-slate-500 mt-1">
              {{ data.current.upstream_sha.slice(0, 7) }}
            </p>
          </div>
          <span class="text-xs px-3 py-1 rounded-full" :class="channelClass">
            canal {{ data.channel }}
          </span>
        </div>

        <!-- Componentes -->
        <div v-if="Object.keys(data.current.components || {}).length" class="mt-5 pt-5 border-t border-white/10 grid gap-2 sm:grid-cols-3">
          <div v-for="(info, name) in data.current.components" :key="name" class="text-sm">
            <p class="text-slate-300 font-medium">{{ name }}</p>
            <p class="font-mono text-xs text-slate-500 break-all">{{ info.tag }}</p>
            <p v-if="driftFor(name)?.custom" class="text-xs text-amber-300 mt-1">
              ⚠ modificado localmente
            </p>
          </div>
        </div>
      </div>

      <!-- Estado del upgrade -->
      <div v-if="data.update_available" class="glass-panel p-6 rounded-xl border-amber-500/30 bg-amber-500/5">
        <div class="flex items-start gap-3">
          <span class="text-2xl">⬆️</span>
          <div class="min-w-0 flex-1">
            <h3 class="font-semibold text-amber-300">
              Hay una versión nueva: {{ data.latest?.version }}
            </h3>
            <p v-if="data.latest?.published_at" class="text-xs text-slate-400 mt-1">
              Publicada el {{ new Date(data.latest.published_at).toLocaleDateString() }}
            </p>

            <div v-if="data.blocked_by_drift" class="mt-4 rounded-lg bg-slate-900/60 border border-amber-500/30 p-4 space-y-2">
              <p class="text-sm font-medium text-amber-200">Esta célula tiene cambios locales</p>
              <p class="text-sm text-slate-400">
                Actualizar sobrescribiría el código que modificaste. Elige qué hacer con él antes
                de continuar — nunca se descarta solo.
              </p>
              <ul class="text-sm text-slate-400 list-disc list-inside space-y-1 mt-2">
                <li><span class="text-slate-200">Adoptar upstream</span> — descarta lo local y vuelve al carril común.</li>
                <li><span class="text-slate-200">Rebasar</span> — reaplica tus cambios sobre la versión nueva.</li>
                <li><span class="text-slate-200">Proponer</span> — abre un PR upstream con tu cambio; si se acepta, vuelve a ti como versión oficial.</li>
              </ul>
            </div>

            <div v-if="data.latest?.notes" class="mt-4 text-sm text-slate-300 whitespace-pre-wrap max-h-48 overflow-y-auto bg-slate-900/40 rounded-lg p-3">{{ data.latest.notes }}</div>

            <p class="text-xs text-slate-500 mt-4">
              El upgrade lo ejecuta un Job dedicado, no la consola: así el proceso que conduce la
              actualización sobrevive al reemplazo de la propia API. Todavía no está habilitado
              en esta versión.
            </p>
          </div>
        </div>
      </div>

      <div v-else class="glass-panel p-6 rounded-xl border-emerald-500/25 bg-emerald-500/5">
        <p class="text-emerald-300 font-medium">✅ Esta célula está al día.</p>
      </div>

      <!-- Historial -->
      <div v-if="data.pending_releases?.length" class="glass-panel p-6 rounded-xl">
        <h3 class="font-semibold text-white mb-4">Cambios pendientes de aplicar</h3>
        <div class="space-y-3">
          <div v-for="r in data.pending_releases" :key="r.version" class="flex items-start gap-3 text-sm">
            <span class="font-mono text-xs bg-slate-800 px-2 py-1 rounded text-slate-300 shrink-0">{{ r.version }}</span>
            <div class="min-w-0">
              <p class="text-slate-200">{{ r.name || r.version }}</p>
              <p v-if="r.notes" class="text-xs text-slate-400 line-clamp-2">{{ r.notes }}</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="error" class="glass-panel p-4 rounded-xl border-red-500/30 bg-red-500/5 text-sm text-red-300">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const data = ref(null)
const loading = ref(false)
const error = ref('')

const channelClass = computed(() => ({
  stable: 'bg-emerald-500/20 text-emerald-300',
  dev: 'bg-blue-500/20 text-blue-300',
  custom: 'bg-amber-500/20 text-amber-300',
}[data.value?.channel] || 'bg-slate-500/20 text-slate-300'))

const driftFor = (name) => data.value?.drift?.components?.[name]

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data: payload } = await axios.get('/api/v1/core/updates')
    data.value = payload
  } catch (e) {
    error.value = e.response?.data?.detail || 'No se pudo consultar el estado del engine'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.glass-panel {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.glass-button {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: white;
  font-weight: 500;
  transition: all 0.2s;
}
.glass-button:hover:not(:disabled) { background: rgba(148, 163, 184, 0.22); }
.glass-button:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
