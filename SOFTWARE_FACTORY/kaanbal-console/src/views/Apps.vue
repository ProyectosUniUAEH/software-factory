<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">Applications</h1>
        <p class="mt-2 text-slate-400">Manage your deployed Kaanbal Engine ecosystem.</p>
      </div>
      <div class="flex gap-4">
        <button
          @click="cleanupOrphanSecrets"
          :disabled="cleanupOrphansRunning"
          class="text-xs px-3 py-2 rounded-lg border transition-colors"
          :class="cleanupOrphansRunning ? 'text-slate-500 border-slate-700 cursor-not-allowed' : 'text-amber-300 border-amber-500/30 hover:bg-amber-500/10'"
        >
          {{ cleanupOrphansRunning ? 'Cleaning...' : 'Cleanup Orphan Secrets' }}
        </button>
        <button @click="showSystemApps = !showSystemApps" class="text-xs text-slate-500 hover:text-white transition-colors">
          {{ showSystemApps ? 'Hide' : 'Show' }} Core Apps
        </button>
        <router-link to="/wizard" class="glass-button flex items-center gap-2">
          <span>+ New App</span>
        </router-link>
      </div>
    </div>

    <!-- Toast Notifications -->
    <Teleport to="body">
      <Transition name="toast">
        <div v-if="toast.show" :class="['fixed top-6 right-6 z-[100] px-6 py-4 rounded-xl shadow-2xl backdrop-blur-xl border', toastStyles[toast.type]]">
          <div class="flex items-center gap-3">
            <span class="text-2xl">{{ toastIcons[toast.type] }}</span>
            <div>
              <p class="font-semibold">{{ toast.title }}</p>
              <p class="text-sm opacity-80">{{ toast.message }}</p>
            </div>
            <button @click="toast.show = false" class="ml-4 opacity-60 hover:opacity-100 transition-opacity">✕</button>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Loading State -->
    <div v-if="loading" class="text-center py-12">
      <div class="relative inline-block">
        <div class="w-16 h-16 border-4 border-blue-500/30 rounded-full animate-spin border-t-blue-500"></div>
        <div class="absolute inset-0 flex items-center justify-center">⚙️</div>
      </div>
      <p class="text-slate-400 mt-4">Syncing with cluster state...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="apps.length === 0 && !rootApp" class="text-center py-16 bg-gradient-to-b from-white/5 to-transparent rounded-2xl border border-white/10">
      <div class="text-7xl mb-6 animate-bounce">🚀</div>
      <h3 class="text-2xl font-bold text-white mb-2">No apps deployed yet</h3>
      <p class="text-slate-400 mb-8 max-w-md mx-auto">Start your Kaanbal Engine by creating your first application.</p>
      <router-link to="/wizard" class="glass-button inline-flex items-center gap-2 px-8 py-3">
        <span class="text-lg">+ Create Your First App</span>
      </router-link>
    </div>

    <!-- Apps Grid -->
    <div v-else class="space-y-8">

      <!-- ━━━ Root Domain Hero Card ━━━ -->
      <div v-if="rootApp" class="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-900/20 via-slate-900/80 to-purple-900/20 shadow-xl shadow-amber-500/10">
        <!-- Decorative top bar -->
        <div class="h-1.5 w-full bg-gradient-to-r from-amber-400 via-amber-500 to-orange-500"></div>
        
        <div class="p-6 flex flex-col lg:flex-row gap-6 items-start lg:items-center">
          <!-- Left: Identity -->
          <div class="flex items-center gap-4 flex-1 min-w-0">
            <div class="relative shrink-0">
              <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500/30 to-orange-500/30 flex items-center justify-center text-3xl border border-amber-500/30 shadow-lg shadow-amber-500/20">
                🏠
              </div>
              <div :class="['absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-slate-900 flex items-center justify-center text-xs', getStatusBadge(rootApp)]">
                {{ getStatusIcon(rootApp) }}
              </div>
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2 mb-0.5">
                <span class="text-amber-400 text-sm">👑</span>
                <span class="text-[10px] font-bold uppercase tracking-widest text-amber-400/80">Main Website</span>
              </div>
              <h2 class="text-2xl font-bold text-white truncate">{{ getPublicDomain() }}</h2>
              <p class="text-xs text-slate-500 mt-0.5">Internal: <span class="text-slate-400 font-mono">{{ rootApp.name }}</span> · {{ rootApp.type }}</p>
            </div>
          </div>

          <!-- Center: Status Chips -->
          <div class="flex flex-wrap gap-2">
            <div class="px-3 py-1.5 rounded-lg bg-black/30 border border-white/5 text-center">
              <p class="text-sm font-bold" :class="getHealthColor(rootApp.argocd)">{{ rootApp.argocd?.health?.status || '...' }}</p>
              <p class="text-[9px] text-slate-600 uppercase">Health</p>
            </div>
            <div class="px-3 py-1.5 rounded-lg bg-black/30 border border-white/5 text-center">
              <p class="text-sm font-bold" :class="rootApp.argocd?.isSynced ? 'text-emerald-400' : 'text-amber-400'">{{ rootApp.argocd?.isSynced ? 'Synced' : 'Pending' }}</p>
              <p class="text-[9px] text-slate-600 uppercase">Sync</p>
            </div>
            <button
              v-for="env in rootApp.environments"
              :key="'root-' + env"
              @click="openEnvironmentDetail(rootApp, env)"
              :class="['px-3 py-1.5 rounded-lg text-xs font-medium transition-all border cursor-pointer', getEnvStyle(rootApp, env)]"
            >
              {{ getEnvIcon(env) }} {{ env }}
              <span :class="['ml-1.5 w-2 h-2 rounded-full inline-block', getEnvDot(rootApp, env)]"></span>
            </button>
          </div>

          <!-- Right: Actions -->
          <div class="flex items-center gap-2 shrink-0">
            <a
              :href="getAppUrl(rootApp)"
              target="_blank"
              class="px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-white text-sm font-bold rounded-xl transition-all flex items-center gap-2 shadow-lg shadow-amber-500/30"
            >
              🌐 Open Site <span class="text-xs opacity-75">↗</span>
            </a>
            <button
              @click="openEnvironments(rootApp)"
              class="px-4 py-3 bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 rounded-xl transition-colors"
              title="Environments"
            >
              🌍
            </button>
            <div class="relative">
              <button @click="rootApp.showMenu = !rootApp.showMenu" class="p-3 hover:bg-white/5 rounded-xl transition-colors">
                <span class="text-slate-400">⋮</span>
              </button>
              <Transition name="dropdown">
                <div v-if="rootApp.showMenu" class="absolute right-0 top-12 w-48 bg-slate-800 border border-white/10 rounded-xl shadow-2xl z-20 overflow-hidden">
                  <button @click="viewAppDetails(rootApp); rootApp.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3">
                    <span>📊</span> View Details
                  </button>
                  <button @click="openEnvironments(rootApp); rootApp.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3">
                    <span>🌍</span> Environments
                  </button>
                  <button @click="showConfirmDelete(rootApp); rootApp.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-red-500/10 text-red-400 flex items-center gap-3 border-t border-white/5">
                    <span>🗑️</span> Delete App
                  </button>
                </div>
              </Transition>
            </div>
          </div>
        </div>
      </div>

      <!-- User Apps -->
      <div v-if="groupedRegularApps.length > 0" class="space-y-6">
        <div v-for="group in groupedRegularApps" :key="group.key" class="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
          <div class="flex items-center justify-between gap-3 mb-4">
            <button @click="toggleGroupCollapse(group.key)" class="flex items-center gap-3 text-left">
              <span class="text-slate-300 text-xs">{{ isGroupCollapsed(group.key) ? '▶' : '▼' }}</span>
              <span class="text-sm font-semibold text-white">{{ group.label }}</span>
              <span class="text-[10px] px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">{{ group.apps.length }} apps</span>
            </button>
            <span class="text-[10px] uppercase tracking-wider text-slate-500">Group</span>
          </div>

          <div v-if="!isGroupCollapsed(group.key)" class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            <div
              v-for="app in group.apps"
              :key="app.id"
              class="glass-panel rounded-2xl overflow-hidden hover:border-blue-500/30 transition-all duration-500 group relative"
              :class="{ 'ring-2 ring-red-500/50': app.argocd?.isDegraded }"
            >
          <!-- Gradient Accent Bar -->
          <div :class="['h-1 w-full', getGradientBar(app)]"></div>
          
          <!-- Card Header -->
          <div class="p-6 pb-4">
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-4">
                <div class="relative">
                  <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center text-3xl border border-white/10">
                    {{ app.icon }}
                  </div>
                  <!-- Status Badge -->
                  <div :class="['absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-slate-900 flex items-center justify-center text-xs', getStatusBadge(app)]">
                    {{ getStatusIcon(app) }}
                  </div>
                </div>
                <div>
                  <h3 class="font-bold text-white text-xl group-hover:text-blue-400 transition-colors">{{ app.name }}</h3>
                  <p class="text-xs text-slate-500 font-medium uppercase tracking-wider">{{ app.type }}</p>
                  <p v-if="app.app_group" class="text-[10px] text-cyan-300 mt-1">Group: {{ app.app_group }}</p>
                </div>
              </div>
              
              <!-- Quick Actions Dropdown -->
              <div class="relative">
                <button @click="app.showMenu = !app.showMenu" class="p-2 hover:bg-white/5 rounded-lg transition-colors">
                  <span class="text-slate-400">⋮</span>
                </button>
                <Transition name="dropdown">
                  <div v-if="app.showMenu" class="absolute right-0 top-10 w-48 bg-slate-800 border border-white/10 rounded-xl shadow-2xl z-20 overflow-hidden">
                    <button @click="viewAppDetails(app); app.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3">
                      <span>📊</span> View Details
                    </button>
                    <button @click="openEnvironments(app); app.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3">
                      <span>🌍</span> Environments
                    </button>
                    <button @click="openExposureManager(app); app.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3">
                      <span>⚙</span> Manage exposure
                    </button>
                    <button @click="promptSetGroup(app); app.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3">
                      <span>🗂️</span> Set Group
                    </button>
                    <button v-if="app.app_group" @click="clearGroup(app); app.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3 text-amber-300">
                      <span>🧹</span> Clear Group
                    </button>
                    <button v-if="app.argocd?.isDegraded" @click="analyzeApp(app); app.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-white/5 flex items-center gap-3 text-purple-400">
                      <span>🔍</span> AI Analysis
                    </button>
                    <button @click="showConfirmDelete(app); app.showMenu = false" class="w-full px-4 py-3 text-left text-sm hover:bg-red-500/10 text-red-400 flex items-center gap-3 border-t border-white/5">
                      <span>🗑️</span> Delete App
                    </button>
                  </div>
                </Transition>
              </div>
            </div>
          </div>

          <!-- Stats Row -->
          <div class="px-6 grid grid-cols-3 gap-3 mb-4">
            <div class="bg-black/30 rounded-lg p-3 text-center border border-white/5">
              <p class="text-lg font-bold" :class="getHealthColor(app.argocd)">
                {{ app.argocd?.health?.status?.charAt(0) || '?' }}
              </p>
              <p class="text-[10px] text-slate-500 uppercase">Health</p>
            </div>
            <div class="bg-black/30 rounded-lg p-3 text-center border border-white/5">
              <p class="text-lg font-bold" :class="app.argocd?.isSynced ? 'text-emerald-400' : 'text-amber-400'">
                {{ app.argocd?.isSynced ? '✓' : '⟳' }}
              </p>
              <p class="text-[10px] text-slate-500 uppercase">Sync</p>
            </div>
            <div class="bg-black/30 rounded-lg p-3 text-center border border-white/5">
              <p class="text-lg font-bold text-blue-400">{{ app.environments?.length || 0 }}</p>
              <p class="text-[10px] text-slate-500 uppercase">Envs</p>
            </div>
          </div>

          <!-- Environment Pills -->
          <div class="px-6 mb-4">
            <div class="flex flex-wrap gap-2">
              <button 
                v-for="env in app.environments" 
                :key="env" 
                @click="openEnvironmentDetail(app, env)"
                :class="['px-3 py-1.5 rounded-lg text-xs font-medium transition-all border', getEnvStyle(app, env)]"
              >
                <span class="mr-1.5">{{ getEnvIcon(env) }}</span>
                {{ env }}
                <span :class="['ml-2 w-2 h-2 rounded-full inline-block', getEnvDot(app, env)]"></span>
              </button>
            </div>
          </div>

          <!-- Diagnosis Alert -->
          <div v-if="app.diagnosis?.status === 'degraded'" class="mx-6 mb-4 p-3 bg-gradient-to-r from-red-500/10 to-red-500/5 border border-red-500/20 rounded-xl">
            <div class="flex items-start gap-3">
              <span class="text-red-400 animate-pulse">⚠️</span>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-red-300 font-medium truncate">{{ app.diagnosis.message }}</p>
                <button @click="viewAppDetails(app)" class="text-xs text-red-400/80 hover:text-red-300 mt-1">
                  View full diagnosis →
                </button>
              </div>
            </div>
          </div>

          <!-- AI Summary -->
          <div v-if="app.aiSummary && !app.aiSummary.includes('Analyzing')" class="mx-6 mb-4 p-3 bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-xl">
            <p class="text-xs text-purple-300 flex items-center gap-2">
              <span>🤖</span> {{ app.aiSummary }}
            </p>
          </div>

          <!-- Action Buttons -->
          <div class="p-6 pt-2 border-t border-white/5 bg-black/20">
            <div class="flex items-center gap-2">
              <a 
                :href="getAppUrl(app)" 
                target="_blank" 
                class="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white text-sm font-bold py-3 rounded-xl text-center transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25"
              >
                <span>Open App</span>
                <span class="text-xs opacity-75">↗</span>
              </a>
              <button 
                v-if="app.argocd?.exists && !app.argocd?.isSynced" 
                @click="syncApp(app)" 
                class="px-4 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-colors shadow-lg shadow-emerald-500/25"
                title="Force Sync"
              >
                🔄
              </button>
              <button 
                @click="openEnvironments(app)" 
                class="px-4 py-3 bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 rounded-xl transition-colors"
                title="View Environments"
              >
                🌍
              </button>
            </div>
          </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Core Apps Section -->
      <div v-if="showSystemApps" class="mt-8">
        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-2">
          <span class="w-8 h-px bg-slate-700"></span>
          Core Infrastructure
          <span class="flex-1 h-px bg-slate-700"></span>
        </h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div v-for="app in systemApps" :key="app.id" class="glass-panel p-4 rounded-xl border border-white/5 opacity-75 hover:opacity-100 transition-all hover:scale-[1.02]">
            <div class="flex items-center gap-3 mb-3">
              <div class="text-2xl">{{ app.icon }}</div>
              <div>
                <h4 class="font-bold text-white text-sm">{{ app.name }}</h4>
                <p class="text-[10px] text-slate-500 uppercase">{{ app.type }}</p>
              </div>
              <div class="ml-auto h-2 w-2 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/50"></div>
            </div>
            <a v-if="app.url" :href="app.url" target="_blank" class="block w-full text-center py-2 bg-black/30 hover:bg-black/50 text-xs text-slate-400 rounded-lg transition-colors">
              Open Service ↗
            </a>
            <div v-else class="block w-full text-center py-2 text-[10px] text-slate-600 italic">
              Internal service
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============================================ -->
    <!-- MODALS -->
    <!-- ============================================ -->

    <!-- Confirm Delete Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="modals.confirmDelete.show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <!-- Backdrop -->
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="modals.confirmDelete.show = false"></div>
          
          <!-- Modal Content -->
          <div class="relative bg-gradient-to-b from-slate-800 to-slate-900 border border-red-500/30 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden transform transition-all">
            <!-- Red Accent -->
            <div class="h-1 bg-gradient-to-r from-red-500 to-orange-500"></div>
            
            <div class="p-8">
              <div class="flex justify-center mb-6">
                <div class="w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center text-5xl border-2 border-red-500/30">
                  🗑️
                </div>
              </div>
              
              <h3 class="text-2xl font-bold text-center text-white mb-2">Delete Application?</h3>
              <p class="text-center text-slate-400 mb-6">
                You're about to delete <span class="text-red-400 font-semibold">{{ modals.confirmDelete.app?.name }}</span>
              </p>
              
              <div class="bg-red-500/10 border border-red-500/20 rounded-xl p-4 mb-6">
                <p class="text-sm text-red-300 text-center">
                  ⚠️ This will permanently destroy:
                </p>
                <ul class="mt-3 space-y-2 text-sm text-red-400/80">
                  <li class="flex items-center gap-2"><span>•</span> Bitbucket repository</li>
                  <li class="flex items-center gap-2"><span>•</span> All Kubernetes resources</li>
                  <li class="flex items-center gap-2"><span>•</span> ArgoCD application</li>
                  <li class="flex items-center gap-2"><span>•</span> Vault secrets (dev/staging/prod)</li>
                  <li class="flex items-center gap-2"><span>•</span> Mongo app records and test references</li>
                </ul>
              </div>
              
              <div class="flex gap-3">
                <button 
                  @click="modals.confirmDelete.show = false" 
                  class="flex-1 py-3 px-4 bg-white/5 hover:bg-white/10 text-slate-300 rounded-xl transition-colors border border-white/10"
                >
                  Cancel
                </button>
                <button 
                  @click="confirmDeleteApp" 
                  class="flex-1 py-3 px-4 bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white font-bold rounded-xl transition-all shadow-lg shadow-red-500/25"
                >
                  Yes, Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- App Details Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="modals.details.show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="modals.details.show = false"></div>
          
          <div class="relative bg-gradient-to-b from-slate-800 to-slate-900 border border-white/10 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden">
            <!-- Header -->
            <div class="bg-gradient-to-r from-blue-600/20 to-purple-600/20 border-b border-white/10 p-6">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-4">
                  <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500/30 to-purple-500/30 flex items-center justify-center text-3xl">
                    {{ modals.details.app?.icon }}
                  </div>
                  <div>
                    <h3 class="text-2xl font-bold text-white">{{ modals.details.app?.name }}</h3>
                    <p class="text-sm text-slate-400">{{ modals.details.app?.type }}</p>
                  </div>
                </div>
                <button @click="modals.details.show = false" class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                  <span class="text-2xl text-slate-400">×</span>
                </button>
              </div>
              
              <!-- Tabs -->
              <div class="flex gap-2 mt-6">
                <button 
                  v-for="tab in ['overview', 'resources', 'timeline', 'logs']" 
                  :key="tab"
                  @click="modals.details.activeTab = tab"
                  :class="['px-4 py-2 rounded-lg text-sm font-medium transition-all', modals.details.activeTab === tab ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5']"
                >
                  {{ tab.charAt(0).toUpperCase() + tab.slice(1) }}
                </button>
              </div>
            </div>
            
            <!-- Content -->
            <div class="p-6 overflow-y-auto max-h-[calc(85vh-180px)]">
              <!-- Overview Tab -->
              <div v-if="modals.details.activeTab === 'overview'" class="space-y-6">
                <!-- Status Cards -->
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div class="bg-black/30 rounded-xl p-4 border border-white/5">
                    <p class="text-xs text-slate-500 uppercase mb-1">Health</p>
                    <p :class="['text-xl font-bold', getHealthColor(modals.details.data?.argocd)]">
                      {{ modals.details.data?.argocd?.health?.status || 'N/A' }}
                    </p>
                  </div>
                  <div class="bg-black/30 rounded-xl p-4 border border-white/5">
                    <p class="text-xs text-slate-500 uppercase mb-1">Sync Status</p>
                    <p :class="['text-xl font-bold', modals.details.data?.argocd?.isSynced ? 'text-emerald-400' : 'text-amber-400']">
                      {{ modals.details.data?.argocd?.sync?.status || 'N/A' }}
                    </p>
                  </div>
                  <div class="bg-black/30 rounded-xl p-4 border border-white/5">
                    <p class="text-xs text-slate-500 uppercase mb-1">Pipeline</p>
                    <p :class="['text-xl font-bold', modals.details.data?.pipeline?.result === 'SUCCESSFUL' ? 'text-emerald-400' : 'text-red-400']">
                      {{ modals.details.data?.pipeline?.result || 'N/A' }}
                    </p>
                  </div>
                  <div class="bg-black/30 rounded-xl p-4 border border-white/5">
                    <p class="text-xs text-slate-500 uppercase mb-1">Pods</p>
                    <p class="text-xl font-bold text-blue-400">
                      {{ modals.details.data?.resources?.pods?.length || 0 }}
                    </p>
                  </div>
                </div>

                <!-- Pipeline Monitor -->
                <div class="bg-black/30 rounded-xl p-4 border border-white/5">
                  <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
                    <div>
                      <p class="text-xs text-slate-500 uppercase">Pipeline Monitor</p>
                      <p class="text-sm text-slate-300">Live Bitbucket pipeline summary and steps</p>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-[11px] px-2 py-1 rounded border"
                            :class="isPipelineRunning(modals.details.data?.pipeline) ? 'text-blue-300 border-blue-500/30 bg-blue-500/10' : 'text-slate-400 border-slate-500/20 bg-slate-500/10'">
                        {{ isPipelineRunning(modals.details.data?.pipeline) ? 'Auto refresh: 3s' : 'Auto refresh paused' }}
                      </span>
                      <button
                        @click="refreshDetailsData(modals.details.app)"
                        class="px-3 py-1.5 text-xs rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300"
                      >
                        Refresh
                      </button>
                    </div>
                  </div>

                  <div v-if="modals.details.pipeline.loading" class="text-sm text-slate-400">Loading pipeline details...</div>
                  <div v-else-if="modals.details.pipeline.error" class="text-sm text-red-300">{{ modals.details.pipeline.error }}</div>

                  <div v-else-if="modals.details.pipeline.data" class="space-y-3">
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                      <div class="bg-black/30 rounded-lg p-2 border border-white/5">
                        <p class="text-slate-500">Build</p>
                        <p class="text-white font-semibold">#{{ modals.details.pipeline.data?.pipeline_info?.build_number || '-' }}</p>
                      </div>
                      <div class="bg-black/30 rounded-lg p-2 border border-white/5">
                        <p class="text-slate-500">Branch</p>
                        <p class="text-white font-semibold">{{ modals.details.pipeline.data?.pipeline_info?.branch || '-' }}</p>
                      </div>
                      <div class="bg-black/30 rounded-lg p-2 border border-white/5">
                        <p class="text-slate-500">State</p>
                        <p :class="['font-semibold', getPipelineStateColor(modals.details.pipeline.data?.pipeline_info?.state)]">
                          {{ modals.details.pipeline.data?.pipeline_info?.state || '-' }}
                        </p>
                      </div>
                      <div class="bg-black/30 rounded-lg p-2 border border-white/5">
                        <p class="text-slate-500">Result</p>
                        <p :class="['font-semibold', getPipelineResultColor(modals.details.pipeline.data?.pipeline_info?.result)]">
                          {{ modals.details.pipeline.data?.pipeline_info?.result || 'N/A' }}
                        </p>
                      </div>
                    </div>

                    <div v-if="modals.details.pipeline.data?.steps?.length" class="space-y-2">
                      <div
                        v-for="step in modals.details.pipeline.data.steps"
                        :key="step.uuid || step.name"
                        class="flex items-center justify-between text-xs bg-black/20 border border-white/5 rounded-lg px-3 py-2"
                      >
                        <span class="text-slate-300">{{ step.name || 'Step' }}</span>
                        <span class="flex items-center gap-2">
                          <span :class="getPipelineStateColor(step.state)">{{ step.state || '-' }}</span>
                          <span :class="getPipelineResultColor(step.result)">{{ step.result || 'N/A' }}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div v-else class="text-sm text-slate-500">No pipeline information available yet.</div>
                </div>

                <!-- Image Info -->
                <div v-if="modals.details.data?.argocd?.images?.length" class="bg-black/30 rounded-xl p-4 border border-white/5">
                  <p class="text-xs text-slate-500 uppercase mb-2">Current Image</p>
                  <code class="text-sm text-blue-300 break-all">{{ modals.details.data.argocd.images[0] }}</code>
                </div>

                <!-- Diagnosis -->
                <div v-if="modals.details.data?.diagnosis" class="bg-gradient-to-r from-red-500/10 to-orange-500/10 border border-red-500/20 rounded-xl p-5">
                  <h4 class="text-lg font-bold text-red-400 mb-3 flex items-center gap-2">
                    <span>🔍</span> Diagnosis
                  </h4>
                  <p class="text-red-300 mb-4">{{ modals.details.data.diagnosis.message }}</p>
                  
                  <div v-if="modals.details.data.diagnosis.issues?.length" class="mb-4">
                    <p class="text-xs text-slate-500 uppercase mb-2">Issues Found</p>
                    <ul class="space-y-2">
                      <li v-for="(issue, i) in modals.details.data.diagnosis.issues" :key="i" class="text-sm text-red-400/80 flex items-start gap-2">
                        <span class="text-red-500 mt-0.5">•</span>
                        <span>{{ issue }}</span>
                      </li>
                    </ul>
                  </div>
                  
                  <div v-if="modals.details.data.diagnosis.recommendations?.length">
                    <p class="text-xs text-slate-500 uppercase mb-2">Recommendations</p>
                    <ul class="space-y-2">
                      <li v-for="(rec, i) in [...new Set(modals.details.data.diagnosis.recommendations)]" :key="i" class="text-sm text-emerald-400/80 flex items-start gap-2">
                        <span class="text-emerald-500 mt-0.5">💡</span>
                        <span>{{ rec }}</span>
                      </li>
                    </ul>
                  </div>
                </div>

                <!-- URLs -->
                <div v-if="modals.details.data?.argocd?.externalURLs?.length" class="bg-black/30 rounded-xl p-4 border border-white/5">
                  <p class="text-xs text-slate-500 uppercase mb-2">External URLs</p>
                  <div class="flex flex-wrap gap-2">
                    <a 
                      v-for="url in modals.details.data.argocd.externalURLs" 
                      :key="url" 
                      :href="url" 
                      target="_blank"
                      class="px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 rounded-lg text-sm transition-colors"
                    >
                      {{ url }} ↗
                    </a>
                  </div>
                </div>
              </div>

              <!-- Resources Tab -->
              <div v-if="modals.details.activeTab === 'resources'" class="space-y-6">
                <!-- Resource Summary -->
                <div class="grid grid-cols-4 gap-4">
                  <div class="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 text-center">
                    <p class="text-3xl font-bold text-emerald-400">{{ modals.details.data?.resources?.summary?.healthy || 0 }}</p>
                    <p class="text-xs text-emerald-300/60 uppercase mt-1">Healthy</p>
                  </div>
                  <div class="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-center">
                    <p class="text-3xl font-bold text-red-400">{{ modals.details.data?.resources?.summary?.degraded || 0 }}</p>
                    <p class="text-xs text-red-300/60 uppercase mt-1">Degraded</p>
                  </div>
                  <div class="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 text-center">
                    <p class="text-3xl font-bold text-blue-400">{{ modals.details.data?.resources?.summary?.progressing || 0 }}</p>
                    <p class="text-xs text-blue-300/60 uppercase mt-1">Progressing</p>
                  </div>
                  <div class="bg-slate-500/10 border border-slate-500/20 rounded-xl p-4 text-center">
                    <p class="text-3xl font-bold text-slate-400">{{ modals.details.data?.resources?.summary?.total || 0 }}</p>
                    <p class="text-xs text-slate-400/60 uppercase mt-1">Total</p>
                  </div>
                </div>

                <!-- Pods List -->
                <div v-if="modals.details.data?.resources?.pods?.length">
                  <h4 class="text-sm font-bold text-slate-400 uppercase mb-3">Pods</h4>
                  <div class="space-y-2">
                    <div 
                      v-for="pod in modals.details.data.resources.pods" 
                      :key="pod.name"
                      :class="['p-4 rounded-xl border transition-all', pod.health === 'Healthy' ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20']"
                    >
                      <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                          <div :class="['w-3 h-3 rounded-full', pod.health === 'Healthy' ? 'bg-emerald-500' : 'bg-red-500 animate-pulse']"></div>
                          <code class="text-sm text-slate-300">{{ pod.name }}</code>
                        </div>
                        <span :class="['text-xs px-2 py-1 rounded', pod.health === 'Healthy' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300']">
                          {{ pod.health }}
                        </span>
                      </div>
                      <p v-if="pod.healthMessage" class="mt-2 text-xs text-slate-500 pl-6">{{ pod.healthMessage }}</p>
                    </div>
                  </div>
                </div>

                <!-- Other Resources -->
                <div v-if="modals.details.data?.resources?.services?.length">
                  <h4 class="text-sm font-bold text-slate-400 uppercase mb-3">Services</h4>
                  <div class="flex flex-wrap gap-2">
                    <span v-for="svc in modals.details.data.resources.services" :key="svc.name" class="px-3 py-1.5 bg-blue-500/10 text-blue-300 rounded-lg text-sm border border-blue-500/20">
                      {{ svc.name }}
                    </span>
                  </div>
                </div>

                <div v-if="modals.details.data?.resources?.ingresses?.length">
                  <h4 class="text-sm font-bold text-slate-400 uppercase mb-3">Ingresses</h4>
                  <div class="flex flex-wrap gap-2">
                    <span v-for="ing in modals.details.data.resources.ingresses" :key="ing.name" class="px-3 py-1.5 bg-purple-500/10 text-purple-300 rounded-lg text-sm border border-purple-500/20">
                      {{ ing.name }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Timeline Tab -->
              <div v-if="modals.details.activeTab === 'timeline'" class="space-y-4">
                <div v-if="modals.details.data?.argocd?.history?.length" class="relative">
                  <!-- Timeline Line -->
                  <div class="absolute left-4 top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-500 to-purple-500"></div>
                  
                  <!-- Timeline Items -->
                  <div v-for="(item, i) in modals.details.data.argocd.history.slice().reverse()" :key="i" class="relative pl-12 pb-8 last:pb-0">
                    <div class="absolute left-2 w-5 h-5 rounded-full bg-blue-500 border-4 border-slate-900 shadow-lg shadow-blue-500/50"></div>
                    <div class="bg-black/30 rounded-xl p-4 border border-white/5">
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-bold text-white">Deploy #{{ modals.details.data.argocd.history.length - i }}</span>
                        <span class="text-xs text-slate-500">{{ formatDate(item.deployedAt) }}</span>
                      </div>
                      <code class="text-xs text-slate-400 block mb-2">{{ item.revision }}</code>
                      <span :class="['text-xs px-2 py-0.5 rounded', item.initiatedBy === 'automated' ? 'bg-blue-500/20 text-blue-300' : 'bg-purple-500/20 text-purple-300']">
                        {{ item.initiatedBy === 'automated' ? '🤖 Auto' : '👤 Manual' }}
                      </span>
                    </div>
                  </div>
                </div>
                <div v-else class="text-center py-12 text-slate-500">
                  <p class="text-4xl mb-4">📜</p>
                  <p>No deployment history available</p>
                </div>
              </div>

              <!-- Logs Tab -->
              <div v-if="modals.details.activeTab === 'logs'" class="space-y-4">
                <div class="bg-black rounded-xl p-4 border border-white/10 font-mono text-sm text-slate-400 h-64 overflow-y-auto">
                  <p class="text-slate-600"># Pod logs coming soon...</p>
                  <p class="text-slate-600"># This feature will stream real-time logs from ArgoCD</p>
                  <p class="mt-4 text-blue-400">$ kubectl logs deployment/{{ modals.details.app?.name }} -n prod</p>
                  <p class="text-emerald-400 mt-2">→ Feature in development 🚧</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Environments Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="modals.environments.show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="modals.environments.show = false"></div>
          
          <div class="relative bg-gradient-to-b from-slate-800 to-slate-900 border border-white/10 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] overflow-hidden">
            <!-- Header -->
            <div class="bg-gradient-to-r from-emerald-600/20 to-blue-600/20 border-b border-white/10 p-6">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-4">
                  <div class="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center text-2xl">🌍</div>
                  <div>
                    <h3 class="text-xl font-bold text-white">{{ modals.environments.app?.name }} - Environments</h3>
                    <p class="text-sm text-slate-400">Multi-environment deployment status</p>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    @click="openExposureManager(modals.environments.app)"
                    class="px-3 py-2 rounded-lg text-xs font-medium bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 transition-colors"
                  >
                    ⚙ Manage exposure
                  </button>
                  <button @click="modals.environments.show = false" class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                    <span class="text-2xl text-slate-400">×</span>
                  </button>
                </div>
              </div>
            </div>
            
            <!-- Environments Grid -->
            <div class="p-6 overflow-y-auto max-h-[calc(85vh-100px)]">
              <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div 
                  v-for="env in ['dev', 'staging', 'prod']" 
                  :key="env"
                  :class="['rounded-2xl border overflow-hidden transition-all', getEnvCardStyle(modals.environments.app, env)]"
                >
                  <!-- Env Header -->
                  <div :class="['p-4 border-b', getEnvHeaderStyle(env)]">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-3">
                        <span class="text-2xl">{{ getEnvIcon(env) }}</span>
                        <div>
                          <h4 class="font-bold text-white capitalize">{{ env }}</h4>
                          <p class="text-xs text-slate-400">{{ env === 'prod' ? 'Production' : env === 'staging' ? 'Pre-production' : 'Development' }}</p>
                        </div>
                      </div>
                      <div :class="['px-2 py-1 rounded text-xs font-medium', isEnvActive(modals.environments.app, env) ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-500/20 text-slate-400']">
                        {{ isEnvActive(modals.environments.app, env) ? 'Active' : 'Inactive' }}
                      </div>
                    </div>
                  </div>
                  
                  <!-- Env Content -->
                  <div class="p-4 space-y-4">
                    <template v-if="isEnvActive(modals.environments.app, env)">
                      <!-- Status -->
                      <div class="flex justify-between items-center">
                        <span class="text-sm text-slate-500">Health</span>
                        <span :class="['font-medium', getEnvHealthColor(modals.environments.app, env)]">
                          {{ getEnvHealth(modals.environments.app, env) }}
                        </span>
                      </div>
                      
                      <!-- Sync -->
                      <div class="flex justify-between items-center">
                        <span class="text-sm text-slate-500">Sync</span>
                        <span :class="['font-medium', (modals.environments.app?.argocd_per_env?.[env]?.isSynced ?? modals.environments.app?.argocd?.isSynced) ? 'text-emerald-400' : 'text-amber-400']">
                          {{ (modals.environments.app?.argocd_per_env?.[env]?.sync?.status) || (modals.environments.app?.argocd?.sync?.status) || 'Unknown' }}
                        </span>
                      </div>
                      
                      <!-- Image -->
                      <div class="bg-black/30 rounded-lg p-3">
                        <p class="text-xs text-slate-500 mb-1">Image Tag</p>
                        <code class="text-xs text-blue-300">{{ env }}-{{ getImageTag(modals.environments.app) }}</code>
                      </div>
                      
                      <!-- URLs -->
                      <div class="space-y-2 mb-3">
                        <template v-for="(link, i) in getEnvLinks(modals.environments.app, env)" :key="i">
                            <a v-if="!link.copyable"
                                :href="link.url"
                                target="_blank"
                                :class="['block w-full text-center py-2 rounded-lg text-xs font-medium transition-all border flex items-center justify-center gap-2', link.class]"
                            >
                                <span>{{ link.icon }}</span>
                                {{ link.label }} <span class="opacity-50">↗</span>
                            </a>
                            <div v-else :class="['block w-full text-center py-2 rounded-lg text-xs font-mono transition-all border flex items-center justify-center gap-2 cursor-pointer', link.class]" @click="copyToClipboard(link.url)" title="Click to copy">
                                <span>{{ link.icon }}</span>
                                <span class="truncate max-w-[200px]">{{ link.url }}</span>
                                <span class="text-slate-600 ml-1">📋</span>
                            </div>
                        </template>
                      </div>

                      <!-- Connection Info -->
                      <div class="bg-black/30 rounded-lg p-3 space-y-2">
                        <p class="text-xs text-slate-500 uppercase font-bold mb-2">Connection Info</p>
                        <!-- Exposure Type Badge -->
                        <div class="flex items-center justify-between gap-2">
                          <span class="text-[10px] text-slate-500 shrink-0">Type</span>
                          <span :class="['text-[10px] px-2 py-0.5 rounded-full font-bold uppercase', getExposureBadgeStyle(modals.environments.app, env)]">
                            {{ getExposureType(modals.environments.app, env) }}
                          </span>
                        </div>
                        <!-- DNS / URL -->
                        <div class="flex items-center justify-between gap-2">
                          <span class="text-[10px] text-slate-500 shrink-0">DNS</span>
                          <code class="text-[11px] truncate cursor-pointer hover:opacity-80 transition-opacity" :class="getExposureType(modals.environments.app, env) === 'tailscale' ? 'text-purple-300' : getExposureType(modals.environments.app, env) === 'public' ? 'text-blue-300' : 'text-cyan-300'" @click="copyToClipboard(getSmartDns(modals.environments.app, env))" title="Click to copy">
                            {{ getSmartDns(modals.environments.app, env) }}
                          </code>
                        </div>
                        <!-- Port -->
                        <div class="flex items-center justify-between gap-2">
                          <span class="text-[10px] text-slate-500 shrink-0">Port</span>
                          <code class="text-[11px] text-slate-300">{{ getAppPort(modals.environments.app) }}</code>
                        </div>
                        <!-- Connection URI -->
                        <div v-if="getConnectionUri(modals.environments.app, env)" class="flex items-center justify-between gap-2">
                          <span class="text-[10px] text-slate-500 shrink-0">URI</span>
                          <code class="text-[11px] text-emerald-300 truncate cursor-pointer hover:text-emerald-200 transition-colors max-w-[200px]" @click="copyToClipboard(getConnectionUri(modals.environments.app, env))" title="Click to copy full URI">
                            {{ getConnectionUri(modals.environments.app, env) }}
                          </code>
                        </div>
                        <!-- Secrets -->
                        <div class="flex items-center justify-between gap-2">
                          <span class="text-[10px] text-slate-500 shrink-0">Secret</span>
                          <code class="text-[11px] text-amber-300 cursor-pointer hover:text-amber-200 transition-colors" @click="copyToClipboard(`${modals.environments.app?.name}-secrets`)" title="Click to copy">
                            {{ modals.environments.app?.name }}-secrets
                          </code>
                        </div>
                        <!-- Vault Path + UI Link -->
                        <div class="flex items-center justify-between gap-2">
                          <span class="text-[10px] text-slate-500 shrink-0">Vault</span>
                          <div class="flex items-center gap-2">
                            <code class="text-[11px] text-purple-300 cursor-pointer hover:text-purple-200 transition-colors" @click="copyToClipboard(`secret/${env}/${modals.environments.app?.name}`)" title="Click to copy">
                              secret/{{ env }}/{{ modals.environments.app?.name }}
                            </code>
                            <a v-if="getVaultUiUrl(modals.environments.app)" :href="getVaultUiUrl(modals.environments.app)" target="_blank" class="text-[10px] text-purple-400 hover:text-purple-300 transition-colors shrink-0" title="Open Vault UI">
                              UI
                            </a>
                          </div>
                        </div>

                        <!-- Database Direct Access Panel (Tailscale L4 TCP) -->
                        <div
                          v-if="isTcpService(modals.environments.app) && hasTailscaleTcp(modals.environments.app, env)"
                          class="mt-2 p-3 rounded-lg bg-gradient-to-br from-purple-500/10 to-indigo-500/10 border border-purple-500/20 space-y-3"
                        >
                          <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                              <p class="text-[11px] text-purple-200 font-bold uppercase tracking-wide">Direct Access</p>
                            </div>
                            <span class="text-[9px] text-purple-400/60 px-2 py-0.5 rounded-full border border-purple-500/20 bg-purple-500/10 font-mono">L4 TCP</span>
                          </div>

                          <!-- Connection URI (main action) -->
                          <div
                            class="group p-2.5 rounded-lg bg-black/40 border border-white/5 hover:border-emerald-500/30 cursor-pointer transition-all"
                            @click="copyToClipboard(getTailscaleTcpUri(modals.environments.app, env))"
                            title="Click to copy connection URI"
                          >
                            <div class="flex items-center justify-between mb-1">
                              <span class="text-[9px] text-slate-500 uppercase font-bold">Connection URI</span>
                              <span class="text-[9px] text-slate-600 group-hover:text-emerald-400 transition-colors">📋 click to copy</span>
                            </div>
                            <code class="text-[11px] text-emerald-300 break-all leading-relaxed">
                              {{ getTailscaleTcpUri(modals.environments.app, env) }}
                            </code>
                          </div>

                          <!-- Host + Port row -->
                          <div class="grid grid-cols-2 gap-2">
                            <div class="p-2 rounded-lg bg-black/30 border border-white/5">
                              <span class="text-[9px] text-slate-500 uppercase block mb-0.5">Host</span>
                              <code class="text-[11px] text-purple-300 cursor-pointer hover:text-purple-200 transition-colors truncate block"
                                @click="copyToClipboard(getEnvTcpHost(modals.environments.app, env))">
                                {{ getEnvTcpHost(modals.environments.app, env) }}
                              </code>
                            </div>
                            <div class="p-2 rounded-lg bg-black/30 border border-white/5">
                              <span class="text-[9px] text-slate-500 uppercase block mb-0.5">Port</span>
                              <code class="text-[11px] text-slate-300">{{ getEnvTcpPort(modals.environments.app, env) }}</code>
                            </div>
                          </div>

                          <!-- Tailscale Tags (ACL) -->
                          <div class="p-2 rounded-lg bg-black/30 border border-white/5">
                            <div class="flex items-center justify-between mb-1.5">
                              <span class="text-[9px] text-slate-500 uppercase font-bold">ACL Tags</span>
                              <button
                                class="text-[9px] text-purple-400 hover:text-purple-300 transition-colors"
                                @click="openTagsEditor(modals.environments.app)"
                              >✏️ Edit</button>
                            </div>
                            <div class="flex flex-wrap gap-1">
                              <span
                                v-for="tag in getAppTags(modals.environments.app)"
                                :key="tag"
                                class="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/20 font-mono"
                              >{{ tag }}</span>
                            </div>
                          </div>

                          <p class="text-[10px] text-slate-500 flex items-center gap-1">
                            <span class="text-purple-400">ℹ</span> Requires <span class="text-purple-300 font-medium">Tailscale</span> installed and connected to the org Tailnet.
                          </p>
                        </div>

                        <!-- Internal-only notice for TCP services without Tailscale -->
                        <div
                          v-else-if="isTcpService(modals.environments.app) && !hasTailscaleTcp(modals.environments.app, env)"
                          class="mt-2 p-2.5 rounded-lg bg-slate-500/10 border border-slate-500/20"
                        >
                          <p class="text-[10px] text-slate-400">
                            <span class="text-amber-400">⚠</span> Internal access only.<br/>
                            Use <code class="text-cyan-300">{{ getInternalDns(modals.environments.app, env) }}:{{ getAppPort(modals.environments.app) }}</code> from within the cluster.
                          </p>
                        </div>
                      </div>

                      <!-- Quick Tools -->
                      <div class="grid grid-cols-2 gap-2">
                        <a :href="getRepoUrl(modals.environments.app)" target="_blank" class="py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 rounded-lg text-xs transition-colors text-center border border-blue-500/10 flex items-center justify-center gap-1">
                          <span>📦</span> Repo
                        </a>
                        <a :href="getArgoUrl(modals.environments.app, env)" target="_blank" class="py-1.5 bg-orange-500/10 hover:bg-orange-500/20 text-orange-300 rounded-lg text-xs transition-colors text-center border border-orange-500/10 flex items-center justify-center gap-1">
                          <span>🐙</span> Argo
                        </a>
                        <button @click="syncApp(modals.environments.app)" class="py-1.5 bg-white/5 hover:bg-white/10 text-slate-400 rounded-lg text-xs transition-colors flex items-center justify-center gap-1">
                          <span>🔄</span> Sync
                        </button>
                        <button class="py-1.5 bg-white/5 hover:bg-white/10 text-slate-400 rounded-lg text-xs transition-colors flex items-center justify-center gap-1">
                          <span>📋</span> Logs
                        </button>
                      </div>
                    </template>
                    
                    <template v-else>
                      <div class="text-center py-8">
                        <p class="text-3xl mb-3 opacity-50">🔒</p>
                        <p class="text-sm text-slate-500">Environment not deployed</p>
                        <button
                          @click="openExposureManager(modals.environments.app)"
                          class="mt-4 px-4 py-2 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 rounded-lg text-xs transition-colors border border-emerald-500/30"
                        >
                          + Enable {{ env }}
                        </button>
                      </div>
                    </template>
                  </div>
                </div>
              </div>

              <!-- Comparison Table -->
              <div class="mt-8">
                <h4 class="text-sm font-bold text-slate-400 uppercase mb-4">Environment Comparison</h4>
                <div class="bg-black/30 rounded-xl border border-white/5 overflow-hidden">
                  <table class="w-full text-sm">
                    <thead class="bg-black/30">
                      <tr>
                        <th class="text-left p-4 text-slate-500 font-medium">Property</th>
                        <th v-for="env in ['dev', 'staging', 'prod']" :key="env" class="text-center p-4 text-slate-500 font-medium capitalize">{{ env }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr class="border-t border-white/5">
                        <td class="p-4 text-slate-400">Replicas</td>
                        <td class="p-4 text-center text-white">1</td>
                        <td class="p-4 text-center text-white">2</td>
                        <td class="p-4 text-center text-white">3</td>
                      </tr>
                      <tr class="border-t border-white/5">
                        <td class="p-4 text-slate-400">CPU Limit</td>
                        <td class="p-4 text-center text-white">250m</td>
                        <td class="p-4 text-center text-white">500m</td>
                        <td class="p-4 text-center text-white">1000m</td>
                      </tr>
                      <tr class="border-t border-white/5">
                        <td class="p-4 text-slate-400">Memory</td>
                        <td class="p-4 text-center text-white">256Mi</td>
                        <td class="p-4 text-center text-white">512Mi</td>
                        <td class="p-4 text-center text-white">1Gi</td>
                      </tr>
                      <tr class="border-t border-white/5">
                        <td class="p-4 text-slate-400">Auto-scaling</td>
                        <td class="p-4 text-center text-red-400">✕</td>
                        <td class="p-4 text-center text-emerald-400">✓</td>
                        <td class="p-4 text-center text-emerald-400">✓</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- AI Analysis Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="modals.analysis.show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="modals.analysis.show = false"></div>
          
          <div class="relative bg-gradient-to-b from-slate-800 to-slate-900 border border-purple-500/30 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
            <div class="h-1 bg-gradient-to-r from-purple-500 to-pink-500"></div>
            
            <div class="p-8">
              <div class="flex items-center gap-4 mb-6">
                <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-purple-500/30 to-pink-500/30 flex items-center justify-center text-3xl animate-pulse">
                  🤖
                </div>
                <div>
                  <h3 class="text-xl font-bold text-white">AI Analysis</h3>
                  <p class="text-sm text-slate-400">{{ modals.analysis.app?.name }}</p>
                </div>
                <button @click="modals.analysis.show = false" class="ml-auto p-2 hover:bg-white/10 rounded-lg transition-colors">
                  <span class="text-xl text-slate-400">×</span>
                </button>
              </div>
              
              <div v-if="modals.analysis.loading" class="text-center py-12">
                <div class="inline-block animate-spin text-4xl mb-4">⚙️</div>
                <p class="text-slate-400">Analyzing with AI...</p>
              </div>
              
              <div v-else-if="modals.analysis.data" class="space-y-6">
                <!-- Summary -->
                <div class="bg-black/30 rounded-xl p-5 border border-white/5">
                  <h4 class="text-sm font-bold text-slate-400 uppercase mb-3">Summary</h4>
                  <p class="text-white">{{ modals.analysis.data.summary }}</p>
                </div>
                
                <!-- Severity -->
                <div class="flex items-center gap-4">
                  <span class="text-sm text-slate-500">Severity:</span>
                  <span :class="['px-3 py-1 rounded-lg font-bold', getSeverityStyle(modals.analysis.data.severity)]">
                    {{ modals.analysis.data.severity?.toUpperCase() }}
                  </span>
                </div>
                
                <!-- Cause -->
                <div class="bg-red-500/10 border border-red-500/20 rounded-xl p-5">
                  <h4 class="text-sm font-bold text-red-400 uppercase mb-3">Root Cause</h4>
                  <p class="text-red-300">{{ modals.analysis.data.cause }}</p>
                </div>
                
                <!-- Recommendations -->
                <div class="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-5">
                  <h4 class="text-sm font-bold text-emerald-400 uppercase mb-3">Recommendations</h4>
                  <ul class="space-y-2">
                    <li v-for="(rec, i) in modals.analysis.data.recommendations" :key="i" class="text-emerald-300 flex items-start gap-2">
                      <span class="text-emerald-500">{{ i + 1 }}.</span>
                      <span>{{ rec }}</span>
                    </li>
                  </ul>
                </div>
              </div>
              
              <div v-else class="text-center py-12 text-slate-500">
                <p>Analysis not available</p>
              </div>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Tags Editor Modal -->
      <Transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100" leave-to-class="opacity-0">
        <div v-if="modals.tagsEditor.show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="modals.tagsEditor.show = false"></div>
          <div class="relative bg-[#0d1117] rounded-2xl border border-white/10 w-full max-w-md overflow-hidden shadow-2xl">
            <div class="p-6">
              <!-- Header -->
              <div class="flex items-center justify-between mb-6">
                <div>
                  <h3 class="text-lg font-bold text-white">Tailscale ACL Tags</h3>
                  <p class="text-sm text-slate-400">{{ modals.tagsEditor.app?.name }}</p>
                </div>
                <button @click="modals.tagsEditor.show = false" class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                  <span class="text-slate-400 text-lg">✕</span>
                </button>
              </div>

              <!-- Explanation -->
              <div class="mb-5 p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                <p class="text-[11px] text-slate-400 leading-relaxed">
                  Tags control <span class="text-purple-300 font-medium">who can access</span> this service on the Tailnet.
                  Configure matching ACL rules in the
                  <a href="https://login.tailscale.com/admin/acls" target="_blank" class="text-purple-400 hover:text-purple-300 underline">Tailscale Admin Console</a> to enforce access policies.
                </p>
                <div class="mt-2 p-2 rounded bg-black/30 border border-white/5">
                  <p class="text-[10px] text-slate-500 mb-1 uppercase font-bold">Example ACL Rule</p>
                  <code class="text-[10px] text-cyan-300 leading-relaxed block whitespace-pre">{ "action": "accept",
  "src": ["group:developers"],
  "dst": ["tag:database:*"] }</code>
                </div>
              </div>

              <!-- Current Tags -->
              <div class="mb-4">
                <label class="text-[10px] text-slate-500 uppercase font-bold block mb-2">Current Tags</label>
                <div class="flex flex-wrap gap-2 min-h-[32px] p-2 rounded-lg bg-black/30 border border-white/10">
                  <span
                    v-for="tag in modals.tagsEditor.tags"
                    :key="tag"
                    class="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg bg-purple-500/20 text-purple-300 border border-purple-500/20 font-mono"
                  >
                    {{ tag }}
                    <button
                      @click="removeTag(tag)"
                      class="ml-0.5 text-purple-400/50 hover:text-red-400 transition-colors text-[10px]"
                      :disabled="tag === 'tag:k8s'"
                      :class="tag === 'tag:k8s' ? 'opacity-30 cursor-not-allowed' : ''"
                    >✕</button>
                  </span>
                  <span v-if="!modals.tagsEditor.tags.length" class="text-[11px] text-slate-600 italic">No tags</span>
                </div>
              </div>

              <!-- Add Tag -->
              <div class="mb-5">
                <label class="text-[10px] text-slate-500 uppercase font-bold block mb-2">Add Tag</label>
                <div class="flex gap-2">
                  <div class="flex-1 relative">
                    <span class="absolute left-3 top-1/2 -translate-y-1/2 text-[11px] text-slate-500 font-mono">tag:</span>
                    <input
                      v-model="modals.tagsEditor.newTag"
                      @keydown.enter="addTag"
                      type="text"
                      class="w-full pl-11 pr-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm text-white placeholder-slate-600 focus:outline-none focus:border-purple-500/50 font-mono"
                      placeholder="database, team-alpha, read-only..."
                    />
                  </div>
                  <button
                    @click="addTag"
                    class="px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded-lg text-sm transition-colors border border-purple-500/20"
                  >+ Add</button>
                </div>
                <p class="text-[10px] text-slate-600 mt-1">
                  Common: <span class="text-slate-500 cursor-pointer hover:text-purple-400" @click="modals.tagsEditor.newTag = 'database'">database</span> ·
                  <span class="text-slate-500 cursor-pointer hover:text-purple-400" @click="modals.tagsEditor.newTag = 'read-only'">read-only</span> ·
                  <span class="text-slate-500 cursor-pointer hover:text-purple-400" @click="modals.tagsEditor.newTag = 'dev-only'">dev-only</span> ·
                  <span class="text-slate-500 cursor-pointer hover:text-purple-400" @click="modals.tagsEditor.newTag = 'prod'">prod</span>
                </p>
              </div>

              <!-- Actions -->
              <div class="flex gap-3">
                <button
                  @click="modals.tagsEditor.show = false"
                  class="flex-1 py-2.5 bg-white/5 hover:bg-white/10 text-slate-400 rounded-lg text-sm transition-colors"
                >Cancel</button>
                <button
                  @click="saveTags"
                  :disabled="modals.tagsEditor.saving"
                  class="flex-1 py-2.5 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded-lg text-sm transition-colors border border-purple-500/20 disabled:opacity-50"
                >
                  <span v-if="modals.tagsEditor.saving">Saving...</span>
                  <span v-else>Save & Apply</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Exposure / Environments runtime manager -->
    <ExposureManagerModal
      :show="modals.exposureManager.show"
      :app="modals.exposureManager.app"
      @close="modals.exposureManager.show = false"
      @updated="onExposureManagerUpdated"
      @toast="onExposureManagerToast"
    />
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { getConfig } from '../config'
import ExposureManagerModal from '../components/ExposureManagerModal.vue'

// State
const apps = ref([])
const loading = ref(true)
const showSystemApps = ref(true)
const cleanupOrphansRunning = ref(false)

// Toast System
const toast = reactive({
  show: false,
  type: 'info',
  title: '',
  message: ''
})

const toastStyles = {
  success: 'bg-emerald-900/90 border-emerald-500/50 text-emerald-100',
  error: 'bg-red-900/90 border-red-500/50 text-red-100',
  warning: 'bg-amber-900/90 border-amber-500/50 text-amber-100',
  info: 'bg-blue-900/90 border-blue-500/50 text-blue-100'
}

const toastIcons = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️'
}

const showToast = (type, title, message) => {
  toast.type = type
  toast.title = title
  toast.message = message
  toast.show = true
  setTimeout(() => toast.show = false, 5000)
}

// Modals System
const modals = reactive({
  confirmDelete: { show: false, app: null },
  details: {
    show: false,
    app: null,
    data: null,
    activeTab: 'overview',
    pipeline: {
      loading: false,
      error: '',
      data: null,
      lastUpdated: null
    }
  },
  environments: { show: false, app: null },
  exposureManager: { show: false, app: null },
  analysis: { show: false, app: null, data: null, loading: false },
  tagsEditor: { show: false, app: null, tags: [], newTag: '', saving: false }
})

const DETAILS_POLL_MS = 3000
let detailsPollTimer = null

// System Apps
const getPublicDomain = () => {
  const configured = getConfig('domain', '')
  if (configured) return configured
  return window.location.hostname.replace(/^kaanbal-console\./, '')
}
const getTailscaleSuffix = () => getConfig('tailscaleSuffix', '')
const normalizeTailscaleUrl = (value) => {
  if (!value) return null
  return /^https?:\/\//.test(value) ? value : `http://${value}`
}
const getArgoBaseUrl = () => (getConfig('argocdUrl', '') || '').replace(/\/$/, '')
const getVaultBaseUrl = () => {
  const vaultHostname = getConfig('vaultHostname', '')
  const domain = getPublicDomain()
  if (vaultHostname && vaultHostname.includes('.')) return `https://${vaultHostname}`
  if (vaultHostname && domain) return `https://${vaultHostname}.${domain}`
  if (domain) return `https://vault.${domain}`
  return ''
}
const getGitProvider = () => getConfig('gitProvider', 'bitbucket')
const getGitNamespace = () => getConfig('gitNamespace', '')

// Core app names that should never appear in user apps grid
const CORE_APP_NAMES = new Set(['datastore'])
const groupCollapseState = ref({})

// Separate root-domain app from regular apps for special rendering
const rootApp = computed(() => apps.value.find(a => a.is_root_domain))
const regularApps = computed(() => {
  return apps.value
    .filter(a => !a.is_root_domain)
    .sort((a, b) => {
      return a.name.localeCompare(b.name)
    })
})

const groupedRegularApps = computed(() => {
  const map = new Map()
  regularApps.value.forEach(app => {
    const groupName = (app.app_group || '').trim()
    const key = groupName ? `group:${groupName.toLowerCase()}` : 'group:ungrouped'
    const label = groupName || 'Ungrouped'
    if (!map.has(key)) map.set(key, { key, label, apps: [] })
    map.get(key).apps.push(app)
  })
  return Array.from(map.values()).sort((a, b) => {
    if (a.key === 'group:ungrouped') return 1
    if (b.key === 'group:ungrouped') return -1
    return a.label.localeCompare(b.label)
  })
})

const isGroupCollapsed = (groupKey) => !!groupCollapseState.value[groupKey]

const toggleGroupCollapse = (groupKey) => {
  groupCollapseState.value[groupKey] = !groupCollapseState.value[groupKey]
}

const systemApps = [
  { id: 'sys-datastore', name: 'Datastore', type: 'MongoDB', url: null, icon: '🗄️' },
  { id: 'sys-kaanbal-api', name: 'Kaanbal API', type: 'Core Service', url: `https://kaanbal-api.${getPublicDomain()}/docs`, icon: '⚡' },
  { id: 'sys-kaanbal-console', name: 'Kaanbal Console', type: 'Frontend', url: `https://kaanbal-console.${getPublicDomain()}`, icon: '🖥️' },
  { id: 'sys-argocd', name: 'ArgoCD', type: 'GitOps', url: getArgoBaseUrl(), icon: '🐙' },
  { id: 'sys-vault', name: 'Vault', type: 'Secrets', url: getVaultBaseUrl(), icon: '🔒' }
]

// Helper Functions
const getGradientBar = (app) => {
  if (app.argocd?.isHealthy) return 'bg-gradient-to-r from-emerald-500 to-emerald-400'
  if (app.argocd?.isDegraded) return 'bg-gradient-to-r from-red-500 to-orange-500'
  if (app.argocd?.isProgressing) return 'bg-gradient-to-r from-blue-500 to-cyan-500'
  return 'bg-gradient-to-r from-amber-500 to-yellow-500'
}

const getStatusBadge = (app) => {
  if (app.argocd?.isHealthy) return 'bg-emerald-500'
  if (app.argocd?.isDegraded) return 'bg-red-500 animate-pulse'
  if (app.argocd?.isProgressing) return 'bg-blue-500 animate-pulse'
  return 'bg-amber-500'
}

const getStatusIcon = (app) => {
  if (app.argocd?.isHealthy) return '✓'
  if (app.argocd?.isDegraded) return '!'
  if (app.argocd?.isProgressing) return '↻'
  return '?'
}

const getHealthColor = (argocd) => {
  if (!argocd) return 'text-slate-400'
  const health = argocd.health?.status
  if (health === 'Healthy') return 'text-emerald-400'
  if (health === 'Degraded') return 'text-red-400'
  if (health === 'Progressing') return 'text-blue-400'
  return 'text-amber-400'
}

const getPipelineResultColor = (result) => {
  if (result === 'SUCCESSFUL') return 'text-emerald-400'
  if (result === 'FAILED') return 'text-red-400'
  return 'text-slate-400'
}

const getPipelineStateColor = (state) => {
  if (state === 'IN_PROGRESS' || state === 'PENDING') return 'text-blue-400'
  if (state === 'COMPLETED') return 'text-emerald-400'
  if (state === 'ERROR') return 'text-red-400'
  return 'text-slate-400'
}

const isPipelineRunning = (pipeline) => {
  const state = (pipeline?.state || '').toUpperCase()
  return state === 'IN_PROGRESS' || state === 'PENDING'
}

const getEnvStyle = (app, env) => {
  const isActive = app.environments?.includes(env)
  if (!isActive) return 'bg-slate-800/50 border-slate-700 text-slate-500 opacity-50'
  if (env === 'prod') return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20'
  if (env === 'staging') return 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
  return 'bg-blue-500/10 border-blue-500/30 text-blue-300 hover:bg-blue-500/20'
}

const getEnvIcon = (env) => {
  if (env === 'prod') return '🚀'
  if (env === 'staging') return '🧪'
  return '🔧'
}

const getEnvDot = (app, env) => {
  const isActive = app.environments?.includes(env)
  if (!isActive) return 'bg-slate-600'
  // Use per-environment status if available
  const envArgo = app.argocd_per_env?.[env]
  if (envArgo?.exists) {
    if (envArgo.isHealthy) return 'bg-emerald-500'
    if (envArgo.isDegraded) return 'bg-red-500'
    if (envArgo.isProgressing) return 'bg-blue-500 animate-pulse'
    return 'bg-amber-500'
  }
  if (app.argocd?.isHealthy) return 'bg-emerald-500'
  if (app.argocd?.isDegraded) return 'bg-red-500'
  return 'bg-amber-500'
}

const getEnvCardStyle = (app, env) => {
  const isActive = isEnvActive(app, env)
  if (!isActive) return 'bg-slate-800/30 border-slate-700/50 opacity-60'
  if (env === 'prod') return 'bg-emerald-900/10 border-emerald-500/30'
  if (env === 'staging') return 'bg-amber-900/10 border-amber-500/30'
  return 'bg-blue-900/10 border-blue-500/30'
}

const getEnvHeaderStyle = (env) => {
  if (env === 'prod') return 'bg-emerald-500/10 border-emerald-500/20'
  if (env === 'staging') return 'bg-amber-500/10 border-amber-500/20'
  return 'bg-blue-500/10 border-blue-500/20'
}

const isEnvActive = (app, env) => app?.environments?.includes(env)

const getEnvHealth = (app, env) => {
  if (!isEnvActive(app, env)) return 'N/A'
  // Use per-environment ArgoCD status if available
  const envArgo = app.argocd_per_env?.[env]
  if (envArgo?.exists) return envArgo.health?.status || 'Unknown'
  return app.argocd?.health?.status || 'Unknown'
}

const getEnvHealthColor = (app, env) => {
  const health = getEnvHealth(app, env)
  if (health === 'Healthy') return 'text-emerald-400'
  if (health === 'Degraded') return 'text-red-400'
  if (health === 'Progressing') return 'text-blue-400'
  return 'text-amber-400'
}

const getEnvUrl = (app, env) => {
  // Fallback to simple logic if no detailed exposure
  const domain = getPublicDomain()
  const base = app.url?.replace('https://', '').replace(`.${domain}`, '')
  if (env === 'prod') return app.url
  return `https://${env}-${base}.${domain}`
}

/**
 * Get the best available URL for the main "Open App" button.
 * Priority: prod public URL > first env with public > first env with tailscale > repo
 * Scans all envs to find the best working link.
 */
const getAppUrl = (app) => {
  const envs = app.environments || ['prod']
  const perEnvExposure = app?.connection_info?.per_env_exposure || {}

  // 1. Look for a public URL (prefer prod)
  const orderedEnvs = ['prod', ...envs.filter(e => e !== 'prod')]
  for (const env of orderedEnvs) {
    const mode = getExposureType(app, env)
    if (mode === 'public' || mode === 'both') {
      if (env === 'prod' && app.is_root_domain) {
        return `https://${getPublicDomain()}`
      }
      const prefix = env === 'prod' ? '' : `${env}-`
      return `https://${prefix}${app.name}.${getPublicDomain()}`
    }
  }

  // 2. Look for tailscale URL (prefer first env)
  for (const env of envs) {
    const mode = getExposureType(app, env)
    if (mode === 'tailscale' || mode === 'both') {
      const perEnv = perEnvExposure[env]
      if (perEnv?.tailscale_url) {
        return normalizeTailscaleUrl(perEnv.tailscale_url)
      }
      // Fallback: Service-based Tailscale hostnames (dev-app, staging-app, app)
      const tsSuffix = getTailscaleSuffix()
      if (tsSuffix) {
        const prefix = env === 'prod' ? '' : `${env}-`
        return `http://${prefix}${app.name}.${tsSuffix}`
      }
    }
  }

  // 3. Fallback to stored app.url or repo
  if (app.url) return app.url
  return app.repo || '#'
}

const getRepoUrl = (app) => {
  if (app.repo) return app.repo
  if (app.repo_url) return app.repo_url

  const namespace = getGitNamespace()
  if (!namespace) return '#'

  if (getGitProvider() === 'github') {
    return `https://github.com/${namespace}/${app.name}`
  }
  return `https://bitbucket.org/${namespace}/${app.name}`
}

const getArgoUrl = (app, env = 'prod') => {
  const base = getArgoBaseUrl()
  if (!base) return '#'
  return `${base}/applications/${app.name}-${env}`
}

const getEnvLinks = (app, env) => {
    const links = []
    
    // Base subdomain logic (standardized)
    // Prod: appname (or bare domain for root-domain apps)
    // Dev: dev-appname
    // Staging: staging-appname
    const isRootProd = env === 'prod' && app.is_root_domain
    let hostname = isRootProd ? '' : app.name
    if (env === 'dev') hostname = `dev-${app.name}`
    if (env === 'staging') hostname = `staging-${app.name}`

    // Helper: resolve the Tailscale URL for a given env.
    // Priority: connection_info (accurate, set during deploy) > constructed fallback
    const resolveTailscaleUrl = (overrideHostname) => {
      const perEnv = app?.connection_info?.per_env_exposure?.[env]
      // Use the URL stored at deploy time or imported from cluster (includes actual operator-generated hostname)
      if (perEnv?.tailscale_url) {
        return normalizeTailscaleUrl(perEnv.tailscale_url)
      }
      // Fallback: build from suffix config using Service-based hostname pattern
      const tsSuffix = getTailscaleSuffix()
      if (tsSuffix) return `http://${overrideHostname || hostname}.${tsSuffix}`
      return null
    }

    // Check for multi-port
    if (app.exposure?.ports && app.exposure?.ports.length > 0) {
        // Multi-port mode
        app.exposure.ports.forEach(port => {
            const portName = port.name
            // Get exposure mode for this port/env
            // Port-level override wins; fall back to per-env type from connection_info
            const portExp = app.exposure.port_exposure?.[env] || {}
            const mode = portExp[portName] || getExposureType(app, env)
            
            if (mode === 'public' || mode === 'both') {
                let portHostname = hostname
                // Convention: primary ports use main hostname, auxiliary use suffix
                if (!['http', 'web', 'ui', 'default'].includes(portName)) {
                     portHostname = `${hostname}-${portName}`
                }
                
                links.push({
                    label: `Open ${portName} (Public)`,
                    url: `https://${portHostname}.${getPublicDomain()}`,
                    type: 'public',
                    class: 'bg-gradient-to-r from-blue-600/20 to-purple-600/20 hover:from-blue-600/30 hover:to-purple-600/30 text-blue-300 border-blue-500/20',
                    icon: '🌐'
                })
            } 
            
            if (mode === 'tailscale' || mode === 'both') {
                 let portHostname = hostname
                 if (!['http', 'web', 'ui', 'default'].includes(portName)) {
                     portHostname = `${hostname}-${portName}`
                 }
                 const tsUrl = resolveTailscaleUrl(portHostname)
                 if (tsUrl) {
                  links.push({
                    label: `Open ${portName} (Private)`,
                    url: tsUrl,
                    type: 'tailscale',
                    class: 'bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border-purple-500/20',
                    icon: '🔒'
                  })
                 }
            } 
            
            if (mode === 'internal') {
                links.push({
                    label: `${portName} (Internal)`,
                    url: `${app.name}.${env}.svc.cluster.local:${port.port}`,
                    type: 'internal',
                    class: 'bg-slate-600/20 text-slate-400 border-slate-500/20 cursor-text select-all',
                    icon: '🏠',
                    copyable: true
                })
            }
        })
    } else {
        // Single port mode — use getExposureType for authoritative per-env mode
        // (reads connection_info.per_env_exposure[env].type first, which is set at deploy
        // time and preserved by import-from-cluster including "internal" envs)
        const mode = getExposureType(app, env)
        
        if (mode === 'public' || mode === 'both') {
            const publicUrl = isRootProd ? `https://${getPublicDomain()}` : `https://${hostname}.${getPublicDomain()}`
            links.push({
                label: `Open ${env.toUpperCase()}`,
                url: publicUrl,
                type: 'public',
                class: 'bg-gradient-to-r from-blue-600/20 to-purple-600/20 hover:from-blue-600/30 hover:to-purple-600/30 text-blue-300 border-blue-500/20',
                icon: '🌐'
            })
        }
        
        if (mode === 'tailscale' || mode === 'both') {
          const tsUrl = resolveTailscaleUrl()
          if (tsUrl) {
            links.push({
              label: `Open ${env.toUpperCase()} (VPN)`,
              url: tsUrl,
              type: 'tailscale',
              class: 'bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border-purple-500/20',
              icon: '🔒'
            })
          }
        }
        
        if (mode === 'internal') {
             links.push({
                label: `Cluster Internal`,
                url: `http://${app.name}.${env}.svc.cluster.local`,
                type: 'internal',
                class: 'bg-slate-600/20 text-slate-400 border-slate-500/20 cursor-text select-all',
                icon: '🏠',
                copyable: true
            })
        }
    }
    return links
}

const getImageTag = (app) => {
  const image = app.argocd?.images?.[0] || ''
  return image.split(':')[1]?.substring(0, 7) || 'latest'
}

const getInternalDns = (app, env) => {
  if (app?.connection_info?.internal_dns_pattern) {
    return app.connection_info.internal_dns_pattern.replace('{env}', env)
  }
  return `${app?.name}.${env}.svc.cluster.local`
}

const getAppPort = (app) => {
  if (app?.connection_info?.port) return app.connection_info.port
  // Infer port from template type
  if (app?.template_id?.includes('mongo')) return 27017
  if (app?.template_id?.includes('mysql')) return 3306
  if (app?.template_id?.includes('postgres')) return 5432
  if (app?.template_id?.includes('api') || app?.template_id?.includes('fastapi')) return 8000
  if (app?.template_id?.includes('n8n')) return 5678
  if (app?.template_id?.includes('emqx')) return 1883
  return 80
}

const getExposureType = (app, env) => {
  // Check per_env_exposure from connection_info (set during deploy / switch)
  const perEnv = app?.connection_info?.per_env_exposure?.[env]
  if (perEnv?.mode) return perEnv.mode
  if (perEnv?.type) return perEnv.type
  // Fallback to exposure config from app data
  if (app?.exposure?.per_env?.[env]) return app.exposure.per_env[env]
  return app?.exposure?.type || 'internal'
}

const getExposureBadgeStyle = (app, env) => {
  const type = getExposureType(app, env)
  if (type === 'tailscale') return 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
  if (type === 'public') return 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
  if (type === 'both') return 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
  if (type === 'lan') return 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
  if (type === 'off') return 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
  return 'bg-slate-500/20 text-slate-400 border border-slate-500/30'
}

const getSmartDns = (app, env) => {
  const type = getExposureType(app, env)
  const perEnv = app?.connection_info?.per_env_exposure?.[env]
  // For TCP services (databases), use the TCP-specific hostname
  if ((type === 'tailscale' || type === 'both') && perEnv?.tailscale_tcp_host) {
    return perEnv.tailscale_tcp_host
  }
  // Tailscale DNS (L7/HTTPS) — strip protocol for clean DNS display
  if ((type === 'tailscale' || type === 'both') && perEnv?.tailscale_url) {
    return perEnv.tailscale_url.replace(/^https?:\/\//, '')
  }
  // Tailscale hostname fallback (append suffix)
  if ((type === 'tailscale' || type === 'both') && perEnv?.tailscale_hostname) {
    const suffix = getTailscaleSuffix()
    return suffix ? `${perEnv.tailscale_hostname}.${suffix}` : perEnv.tailscale_hostname
  }
  // Public URL
  if (type === 'public' || type === 'both') {
    if (env === 'prod' && app?.is_root_domain) return getPublicDomain()
    const prefix = env === 'prod' ? '' : `${env}-`
    return `${prefix}${app?.name}.${getPublicDomain()}`
  }
  // Internal DNS
  return getInternalDns(app, env)
}

const isTcpService = (app) => {
  // Check both new field and template_id as fallback
  if (app?.connection_info?.is_tcp_service) return true
  const templateId = (app?.template_id || '').toLowerCase()
  return templateId.includes('mongo') || templateId.includes('postgres') || templateId.includes('redis') || templateId.includes('mysql') || templateId.includes('mariadb')
}

const hasTailscaleTcp = (app, env) => {
  const perEnv = app?.connection_info?.per_env_exposure?.[env]
  return !!perEnv?.tailscale_tcp_host
}

const getTailscaleTcpUri = (app, env) => {
  const perEnv = app?.connection_info?.per_env_exposure?.[env]
  const host = perEnv?.tailscale_tcp_host
  const port = perEnv?.tailscale_tcp_port || app?.connection_info?.tcp_port || getAppPort(app)
  if (!host) return null
  
  const templateId = (app?.template_id || '').toLowerCase()
  if (templateId.includes('mongo')) {
    return `mongodb://<MONGO_USER>:<MONGO_PASSWORD>@${host}:${port}/?authSource=admin`
  }
  if (templateId.includes('postgres')) {
    return `postgresql://<POSTGRES_USER>:<POSTGRES_PASSWORD>@${host}:${port}/<DB_NAME>`
  }
  if (templateId.includes('mysql')) {
    return `mysql://<MYSQL_USER>:<MYSQL_PASSWORD>@${host}:${port}/<DB_NAME>`
  }
  if (templateId.includes('redis')) {
    return `redis://:<REDIS_PASSWORD>@${host}:${port}`
  }
  return `${host}:${port}`
}

const getConnectionUri = (app, env) => {
  // Build connection URI for databases (MongoDB, etc.)
  const templateId = app?.template_id || ''
  const port = getAppPort(app)
  const dns = getSmartDns(app, env)

  if (templateId.includes('mongo')) {
    return `mongodb://***:***@${dns}:${port}`
  }
  if (templateId.includes('postgres')) {
    return `postgresql://***:***@${dns}:${port}`
  }
  if (templateId.includes('mysql')) {
    return `mysql://***:***@${dns}:${port}`
  }
  if (templateId.includes('redis')) {
    return `redis://***@${dns}:${port}`
  }
  // For HTTP services, no URI needed (they have links)
  return null
}

const isMongoApp = (app) => {
  const templateId = (app?.template_id || '').toLowerCase()
  return templateId.includes('mongo') || templateId.includes('mongodb')
}

const getEnvTcpHost = (app, env) => {
  return app?.connection_info?.per_env_exposure?.[env]?.tailscale_tcp_host || ''
}

const getEnvTcpPort = (app, env) => {
  return app?.connection_info?.per_env_exposure?.[env]?.tailscale_tcp_port || app?.connection_info?.tcp_port || getAppPort(app)
}

const getAppTags = (app) => {
  return app?.tailscale_tags || ['tag:k8s']
}

const openTagsEditor = (app) => {
  modals.tagsEditor.app = app
  modals.tagsEditor.tags = [...(app?.tailscale_tags || ['tag:k8s'])]
  modals.tagsEditor.newTag = ''
  modals.tagsEditor.saving = false
  modals.tagsEditor.show = true
}

const addTag = () => {
  let tag = modals.tagsEditor.newTag.trim().toLowerCase()
  if (!tag) return
  if (!tag.startsWith('tag:')) tag = `tag:${tag}`
  if (!modals.tagsEditor.tags.includes(tag)) {
    modals.tagsEditor.tags.push(tag)
  }
  modals.tagsEditor.newTag = ''
}

const removeTag = (tag) => {
  modals.tagsEditor.tags = modals.tagsEditor.tags.filter(t => t !== tag)
}

const saveTags = async () => {
  const app = modals.tagsEditor.app
  if (!app) return
  modals.tagsEditor.saving = true
  try {
    const { data } = await axios.patch(`/api/v1/apps/${app.name}/tailscale-tags`, {
      tags: modals.tagsEditor.tags
    })
    // Update local app state
    app.tailscale_tags = data.tags
    showToast('success', 'Tags Updated', `Applied to: ${data.applied_to_cluster?.join(', ') || 'saved'}`)
    modals.tagsEditor.show = false
  } catch (e) {
    showToast('error', 'Error', e.response?.data?.detail || 'Failed to update tags')
  } finally {
    modals.tagsEditor.saving = false
  }
}

const getVaultUiUrl = (app) => {
  if (app?.connection_info?.vault_ui) return app.connection_info.vault_ui
  return null
}

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    showToast('success', 'Copied!', text.length > 50 ? text.substring(0, 50) + '...' : text)
  } catch (e) {
    // Fallback for non-HTTPS contexts
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    showToast('success', 'Copied!', text.length > 50 ? text.substring(0, 50) + '...' : text)
  }
}

const getSeverityStyle = (severity) => {
  if (severity === 'critical') return 'bg-red-500/20 text-red-300'
  if (severity === 'high') return 'bg-orange-500/20 text-orange-300'
  if (severity === 'medium') return 'bg-amber-500/20 text-amber-300'
  return 'bg-blue-500/20 text-blue-300'
}

const formatDate = (dateString) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return date.toLocaleString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

// Actions
const showConfirmDelete = (app) => {
  modals.confirmDelete.app = app
  modals.confirmDelete.show = true
}

const confirmDeleteApp = async () => {
  const app = modals.confirmDelete.app
  modals.confirmDelete.show = false
  
  try {
    showToast('info', 'Deleting...', `Removing ${app.name} and all resources`)
    const { data } = await axios.delete(`/api/v1/apps/${app.id}`)
    apps.value = apps.value.filter(a => a.id !== app.id)

    const deletedVault = data?.cleanup?.vault?.deleted_paths?.length || 0
    const failedVault = data?.cleanup?.vault?.failed_paths?.length || 0
    const suffix = deletedVault > 0 || failedVault > 0
      ? ` | Vault deleted: ${deletedVault}${failedVault ? `, failed: ${failedVault}` : ''}`
      : ''

    showToast('success', 'Deleted!', `${app.name} has been removed${suffix}`)
  } catch (e) {
    console.error(e)
    showToast('error', 'Delete Failed', e.response?.data?.detail || e.message)
  }
}

const cleanupOrphanSecrets = async () => {
  if (cleanupOrphansRunning.value) return

  const confirmed = window.confirm(
    'This will delete Vault secrets for apps that are not present in Mongo apps list. Continue?'
  )
  if (!confirmed) return

  try {
    cleanupOrphansRunning.value = true
    showToast('info', 'Cleanup Running', 'Removing orphan Vault secrets...')

    const { data } = await axios.post('/api/v1/apps/maintenance/cleanup-orphans')
    const deleted = data?.report?.deleted?.length || 0
    const failed = data?.report?.failed?.length || 0

    if (failed > 0) {
      showToast('warning', 'Cleanup Completed', `Deleted ${deleted} orphan paths, ${failed} failed`)
    } else {
      showToast('success', 'Cleanup Completed', `Deleted ${deleted} orphan Vault paths`)
    }
  } catch (e) {
    console.error(e)
    showToast('error', 'Cleanup Failed', e.response?.data?.detail || e.message)
  } finally {
    cleanupOrphansRunning.value = false
  }
}

const viewAppDetails = async (app) => {
  modals.details.app = app
  modals.details.activeTab = 'overview'
  modals.details.show = true

  await refreshDetailsData(app)
  if (isPipelineRunning(modals.details.data?.pipeline)) {
    startDetailsPolling()
  }
}

const openEnvironments = (app) => {
  modals.environments.app = app
  modals.environments.show = true
}

const openExposureManager = (app) => {
  if (!app) return
  modals.exposureManager.app = app
  modals.exposureManager.show = true
}

const onExposureManagerToast = ({ type, title, message }) => {
  showToast(type || 'info', title || '', message || '')
}

const onExposureManagerUpdated = (partial) => {
  if (!partial?.name) return
  const idx = apps.value.findIndex(a => a.name === partial.name)
  if (idx >= 0) {
    apps.value[idx] = { ...apps.value[idx], ...partial }
  }
  // Keep open modals pointing at fresh object
  if (modals.environments.app?.name === partial.name) {
    modals.environments.app = { ...modals.environments.app, ...partial }
  }
  if (modals.exposureManager.app?.name === partial.name) {
    modals.exposureManager.app = { ...modals.exposureManager.app, ...partial }
  }
}

const openEnvironmentDetail = (app, env) => {
  openEnvironments(app)
}

const analyzeApp = async (app) => {
  modals.analysis.app = app
  modals.analysis.loading = true
  modals.analysis.data = null
  modals.analysis.show = true
  
  try {
    const { data } = await axios.post(`/api/v1/apps/${app.name}/analyze`)
    modals.analysis.data = data.analysis
  } catch (e) {
    console.error(e)
    showToast('error', 'Analysis Failed', e.response?.data?.detail || e.message)
  } finally {
    modals.analysis.loading = false
  }
}

const syncApp = async (app) => {
  try {
    showToast('info', 'Syncing...', `Initiating sync for ${app.name}`)
    const { data } = await axios.post(`/api/v1/apps/${app.name}/argocd/sync`)
    
    if (data.success) {
      showToast('success', 'Sync Started!', 'ArgoCD is syncing the application')
      setTimeout(() => fetchPipelineStatus(app), 3000)
    } else {
      showToast('error', 'Sync Failed', data.error)
    }
  } catch (e) {
    console.error(e)
    showToast('error', 'Sync Error', e.response?.data?.detail || e.message)
  }
}

const applyRuntimeStatus = (app, data) => {
  app.pipeline = data.pipeline
  app.argocd = data.argocd
  app.argocd_per_env = data.argocd_per_env || {}
  app.diagnosis = data.diagnosis
  app.realStatus = data.realStatus
  app.aiSummary = data.summary
  app.connection_info = data.app?.connection_info || null
  app.template_id = data.app?.template || ''
  app.exposure = data.app?.exposure || null

  if (data.argocd?.isHealthy) app.status = 'Running'
  else if (data.argocd?.isDegraded) app.status = 'Degraded'
  else if (data.argocd?.isProgressing) app.status = 'Deploying'
  else if (data.pipeline?.result === 'FAILED') app.status = 'Build Failed'
  else app.status = 'Unknown'
}

const refreshDetailsData = async (app, silent = false) => {
  if (!app?.name) return

  if (!silent) {
    modals.details.pipeline.loading = true
    modals.details.pipeline.error = ''
  }

  try {
    const { data } = await axios.get(`/api/v1/apps/${app.name}/status/full`)
    modals.details.data = data
    applyRuntimeStatus(app, data)

    try {
      const pipelineRes = await axios.get(`/api/v1/apps/${app.name}/pipeline/logs`)
      modals.details.pipeline.data = pipelineRes.data
      modals.details.pipeline.error = ''
      modals.details.pipeline.lastUpdated = new Date().toISOString()
    } catch (pipelineError) {
      modals.details.pipeline.error = pipelineError.response?.data?.detail || 'Failed to load pipeline details'
    }
  } catch (e) {
    if (!silent) {
      showToast('error', 'Error', 'Failed to load app details')
    }
    console.error(e)
  } finally {
    modals.details.pipeline.loading = false
  }
}

const stopDetailsPolling = () => {
  if (detailsPollTimer) {
    clearInterval(detailsPollTimer)
    detailsPollTimer = null
  }
}

const startDetailsPolling = () => {
  stopDetailsPolling()
  detailsPollTimer = setInterval(async () => {
    if (!modals.details.show || !modals.details.app) {
      stopDetailsPolling()
      return
    }

    await refreshDetailsData(modals.details.app, true)

    if (!isPipelineRunning(modals.details.data?.pipeline)) {
      stopDetailsPolling()
    }
  }, DETAILS_POLL_MS)
}

const fetchPipelineStatus = async (app) => {
  try {
    const { data } = await axios.get(`/api/v1/apps/${app.name}/status/full`)
    applyRuntimeStatus(app, data)
  } catch (e) {
    console.error(`Failed to fetch status for ${app.name}:`, e)
  }
}

const updateAppGroup = async (app, groupValue) => {
  const payload = { app_group: groupValue || null }
  await axios.patch(`/api/v1/apps/${app.name}/group`, payload)
  app.app_group = groupValue || null
}

const promptSetGroup = async (app) => {
  const current = app.app_group || ''
  const next = window.prompt('Group name for this app (empty to cancel):', current)
  if (next === null) return
  const normalized = next.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-_]/g, '').replace(/-+/g, '-').replace(/^-+|-+$/g, '')
  if (!normalized) {
    showToast('warning', 'Group not changed', 'Use Clear Group if you want to remove it.')
    return
  }
  try {
    await updateAppGroup(app, normalized)
    showToast('success', 'Group updated', `${app.name} is now in group '${normalized}'.`)
  } catch (e) {
    console.error(e)
    showToast('error', 'Failed', 'Could not update app group')
  }
}

const clearGroup = async (app) => {
  try {
    await updateAppGroup(app, null)
    showToast('success', 'Group cleared', `${app.name} is now ungrouped.`)
  } catch (e) {
    console.error(e)
    showToast('error', 'Failed', 'Could not clear app group')
  }
}

const fetchApps = async () => {
  try {
    loading.value = true
    const { data } = await axios.get('/api/v1/apps')
    
    apps.value = data
      .filter(app => !CORE_APP_NAMES.has(app.name))  // Core apps go to system section
      .map(app => {
      let icon = '📦', type = 'Application'
      const templateId = (app.template || '').toLowerCase()
      if (templateId.includes('api') || templateId.includes('fastapi')) { icon = '⚡'; type = 'Backend Service' }
      else if (templateId.includes('vue') || templateId.includes('spa')) { icon = '🖥️'; type = 'Frontend App' }
      else if (templateId.includes('emqx')) { icon = '📡'; type = 'MQTT Broker' }
      else if (templateId.includes('mysql')) { icon = '🗄️'; type = 'MySQL Database' }
      else if (templateId.includes('postgres')) { icon = '🗄️'; type = 'PostgreSQL Database' }
      else if (templateId.includes('db') || templateId.includes('mongo')) { icon = '🗄️'; type = 'MongoDB Database' }
      else if (templateId.includes('n8n')) { icon = '🤖'; type = 'Workflow Engine' }

      return {
        id: app._id,
        name: app.name,
        app_group: app.app_group || null,
        type,
        status: 'Checking...',
        url: app.subdomain ? `https://${app.subdomain}` : app.repo_url,
        icon,
        repo: app.repo_url,
        environments: app.environments || ['prod'],
        exposure: app.exposure,
        connection_info: app.connection_info || null,
        tailscale_tags: app.tailscale_tags || ['tag:k8s'],
        template_id: app.template || '',
        is_root_domain: !!app.is_root_domain,
        dns_claims: app.dns_claims || [],
        category: app.category || null,
        pipeline: null,
        argocd: null,
        argocd_per_env: {},
        diagnosis: null,
        realStatus: null,
        aiSummary: null,
        showMenu: false
      }
    })

    apps.value.forEach(app => fetchPipelineStatus(app))
  } catch (e) {
    console.error('Failed to fetch apps:', e)
    showToast('error', 'Error', 'Failed to load applications')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchApps()
  
  // Listen for global sync complete event
  window.addEventListener('kaanbal:sync-complete', onGlobalSyncComplete)
})

const onGlobalSyncComplete = () => {
  fetchApps()
}

watch(() => modals.details.show, (isOpen) => {
  if (!isOpen) {
    stopDetailsPolling()
  }
})

onUnmounted(() => {
  stopDetailsPolling()
  window.removeEventListener('kaanbal:sync-complete', onGlobalSyncComplete)
})
</script>

<style scoped>
/* Toast Animation */
.toast-enter-active, .toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

/* Modal Animation */
.modal-enter-active, .modal-leave-active {
  transition: all 0.3s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-from .relative, .modal-leave-to .relative {
  transform: scale(0.95);
}

/* Dropdown Animation */
.dropdown-enter-active, .dropdown-leave-active {
  transition: all 0.2s ease;
}
.dropdown-enter-from, .dropdown-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
