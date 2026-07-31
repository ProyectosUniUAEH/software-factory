<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">Stacks</h1>
        <p class="mt-2 text-slate-400">Deploy complete application bundles with a single click.</p>
      </div>
      <button @click="loadStacks" :disabled="loading" class="glass-button text-sm flex items-center gap-2">
        <span :class="{'animate-spin': loading}">🔄</span>
        Refresh
      </button>
    </div>

    <!-- Info Banner -->
    <div class="glass-panel p-4 border-purple-500/30 bg-purple-500/5">
      <div class="flex items-start gap-3">
        <span class="text-2xl">📦</span>
        <div>
          <h3 class="font-semibold text-purple-300">What are Stacks?</h3>
          <p class="text-sm text-slate-400 mt-1">
            Stacks are pre-configured bundles of templates that work together. 
            Deploy a complete fullstack app (frontend + backend + database) with proper wiring in one click.
          </p>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading && stacks.length === 0" class="text-center py-12 text-slate-400">
      Loading stacks...
    </div>

    <!-- Stacks Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div 
        v-for="stack in stacks" 
        :key="stack.id" 
        class="glass-panel p-0 rounded-xl overflow-hidden hover:border-purple-500/50 transition-all duration-300"
      >
        <!-- Header -->
        <div class="p-6 border-b border-white/10" :style="`background: linear-gradient(135deg, ${stack.color || '#8b5cf6'}15, transparent)`">
          <div class="flex items-start justify-between">
            <div>
              <div class="flex items-center gap-2 mb-2">
                <span class="text-2xl">{{ stack.icon || '📦' }}</span>
                <h3 class="text-xl font-bold text-white">{{ stack.name }}</h3>
              </div>
              <p class="text-slate-400 text-sm">{{ stack.description }}</p>
            </div>
            <span v-if="stack.popular" class="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded">⭐ Popular</span>
          </div>
        </div>

        <!-- Components -->
        <div class="p-6">
          <h4 class="text-xs uppercase tracking-wider text-slate-500 mb-3">Components</h4>
          <div class="space-y-2">
            <div 
              v-for="component in stack.components" 
              :key="component.name"
              class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50"
            >
              <div class="flex items-center gap-3">
                <span class="w-8 h-8 rounded-lg flex items-center justify-center bg-slate-700">
                  {{ getComponentIcon(component) }}
                </span>
                <div>
                  <p class="text-white text-sm font-medium">{{ component.name }}</p>
                  <p class="text-xs text-slate-500 font-mono">{{ component.template }}</p>
                </div>
              </div>
              <span 
                :class="[
                  'text-xs px-2 py-1 rounded',
                  getExposureClass(component.exposure)
                ]"
              >
                {{ getExposureIcon(component.exposure) }} {{ component.exposure || 'internal' }}
              </span>
            </div>
          </div>

          <!-- Wiring Info -->
          <div v-if="hasWiring(stack)" class="mt-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <h5 class="text-xs font-semibold text-blue-400 mb-2">🔗 Auto-wiring</h5>
            <p class="text-xs text-slate-400">
              Components are automatically connected (env vars, connection strings)
            </p>
          </div>

          <!-- Deploy Button -->
          <button 
            @click="openDeployModal(stack)"
            class="w-full mt-4 glass-button bg-purple-600 hover:bg-purple-500 flex items-center justify-center gap-2"
          >
            <span>🚀</span>
            Deploy Stack
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && stacks.length === 0" class="text-center py-12">
      <div class="text-4xl mb-4">📭</div>
      <p class="text-slate-400">No stacks available yet.</p>
      <p class="text-sm text-slate-500 mt-2">Stacks are defined in the kaanbal-templates catalog.</p>
    </div>

    <!-- Deploy Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showDeployModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="showDeployModal = false"></div>
          
          <div class="relative bg-slate-900 border border-white/10 rounded-2xl w-full max-w-lg shadow-2xl">
            <!-- Header -->
            <div class="p-6 border-b border-white/10">
              <h2 class="text-xl font-bold text-white flex items-center gap-2">
                🚀 Deploy Stack
              </h2>
              <p class="text-sm text-slate-400 mt-1">{{ selectedStack?.name }}</p>
            </div>

            <!-- Form -->
            <form @submit.prevent="deployStack" class="p-6 space-y-4">
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Project Name *</label>
                <input 
                  v-model="deployConfig.name" 
                  type="text" 
                  placeholder="my-project"
                  pattern="[a-z0-9-]+"
                  class="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                  required
                >
                <p class="text-xs text-slate-500 mt-1">This will be the base name for all apps</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Environment</label>
                <select 
                  v-model="deployConfig.environment"
                  class="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-3 text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                >
                  <option value="dev">🧪 Development</option>
                  <option value="staging">🔬 Staging</option>
                  <option value="prod">🚀 Production</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Exposure Mode</label>
                <select 
                  v-model="deployConfig.exposure_mode"
                  class="w-full bg-slate-800 border border-white/10 rounded-lg px-4 py-3 text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                >
                  <option value="tailscale">🔒 Tailscale VPN (Recommended)</option>
                  <option value="public">🌐 Public Internet</option>
                  <option value="internal">🏠 Cluster Only</option>
                </select>
                <p class="text-xs text-slate-500 mt-1">Default for all components (can be overridden per component)</p>
              </div>

              <!-- Preview -->
              <div class="p-4 bg-slate-800/50 rounded-lg border border-white/5">
                <h4 class="text-sm font-semibold text-slate-300 mb-2">Apps to be created:</h4>
                <ul class="space-y-1 text-sm text-slate-400">
                  <li v-for="comp in selectedStack?.components" :key="comp.name" class="flex items-center gap-2">
                    <span class="text-emerald-400">✓</span>
                    <span class="font-mono">{{ deployConfig.name }}-{{ comp.name }}</span>
                    <span class="text-xs text-slate-500">({{ comp.template }})</span>
                  </li>
                </ul>
              </div>
            </form>

            <!-- Actions -->
            <div class="p-6 border-t border-white/10 flex gap-4">
              <button @click="showDeployModal = false" class="flex-1 px-4 py-3 rounded-lg border border-white/10 text-slate-400 hover:bg-white/5">
                Cancel
              </button>
              <button 
                @click="deployStack"
                :disabled="deploying || !deployConfig.name"
                class="flex-1 px-4 py-3 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-semibold disabled:opacity-50"
              >
                {{ deploying ? 'Deploying...' : '🚀 Deploy' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Toast -->
    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toast.show" :class="['fixed bottom-6 right-6 z-[100] px-6 py-4 rounded-xl shadow-2xl backdrop-blur-xl border', toast.type === 'success' ? 'bg-emerald-900/90 border-emerald-500/50 text-emerald-100' : 'bg-red-900/90 border-red-500/50 text-red-100']">
          <div class="flex items-center gap-3">
            <span class="text-2xl">{{ toast.type === 'success' ? '✅' : '❌' }}</span>
            <p class="font-medium">{{ toast.message }}</p>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const loading = ref(false)
const stacks = ref([])

// Deploy modal
const showDeployModal = ref(false)
const selectedStack = ref(null)
const deploying = ref(false)
const deployConfig = reactive({
  name: '',
  environment: 'dev',
  exposure_mode: 'tailscale'
})

// Toast
const toast = reactive({ show: false, message: '', type: 'success' })

const showToast = (message, type = 'success') => {
  toast.message = message
  toast.type = type
  toast.show = true
  setTimeout(() => { toast.show = false }, 4000)
}

const componentIcons = {
  'vue3-spa': '💚',
  'react-spa': '⚛️',
  'fastapi-api': '🐍',
  'express-api': '🟢',
  'mongodb': '🍃',
  'mysql': '🐬',
  'redis': '🔴',
  'n8n': '🔄',
  'grafana': '📊'
}

const getComponentIcon = (component) => {
  return componentIcons[component.template] || '📦'
}

const getExposureClass = (exposure) => {
  const map = {
    'public': 'bg-emerald-500/20 text-emerald-400',
    'tailscale': 'bg-blue-500/20 text-blue-400',
    'internal': 'bg-slate-500/20 text-slate-400',
    'both': 'bg-purple-500/20 text-purple-400'
  }
  return map[exposure] || map['internal']
}

const getExposureIcon = (exposure) => {
  const map = {
    'public': '🌐',
    'tailscale': '🔒',
    'internal': '🏠',
    'both': '🔀'
  }
  return map[exposure] || map['internal']
}

const hasWiring = (stack) => {
  return stack.components?.some(c => c.wiring && Object.keys(c.wiring).length > 0)
}

const loadStacks = async () => {
  loading.value = true
  try {
    const { data } = await axios.get('/api/v1/templates/catalog/stacks')
    stacks.value = data.stacks || []
  } catch (e) {
    console.error('Failed to load stacks:', e)
    showToast('Failed to load stacks', 'error')
  } finally {
    loading.value = false
  }
}

const openDeployModal = (stack) => {
  selectedStack.value = stack
  deployConfig.name = ''
  deployConfig.environment = 'dev'
  deployConfig.exposure_mode = 'tailscale'
  showDeployModal.value = true
}

const deployStack = async () => {
  if (!deployConfig.name || !selectedStack.value) return
  
  deploying.value = true
  try {
    const { data } = await axios.post(`/api/v1/templates/catalog/stacks/${selectedStack.value.id}/deploy`, {
      name: deployConfig.name,
      environment: deployConfig.environment,
      exposure_mode: deployConfig.exposure_mode
    })
    
    showToast(`Stack "${selectedStack.value.name}" deployment started!`)
    showDeployModal.value = false
    
    // Redirect to apps view
    router.push({ name: 'apps' })
  } catch (e) {
    showToast(e.response?.data?.detail || 'Failed to deploy stack', 'error')
  } finally {
    deploying.value = false
  }
}

onMounted(loadStacks)
</script>

<style scoped>
.modal-enter-active, .modal-leave-active {
  transition: all 0.3s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}

.toast-enter-active, .toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.glass-panel {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.glass-button {
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: white;
  font-weight: 500;
  transition: all 0.2s;
}

.glass-button:hover {
  background: rgba(59, 130, 246, 0.3);
}
</style>
