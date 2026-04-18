<template>
  <div class="app">
    <!-- Sidebar Navigation -->
    <nav class="sidebar">
      <div class="logo">
        <span class="logo-icon">🔍</span>
        <span class="logo-text">Knowledge<br>Collector</span>
      </div>
      <ul class="nav-links">
        <li v-for="item in navItems" :key="item.to">
          <router-link :to="item.to" :class="['nav-link', { active: $route.path === item.to }]">
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
      <div class="sidebar-footer">
        <div class="status-dot" :class="connected ? 'online' : 'offline'"></div>
        <span>{{ connected ? 'Verbunden' : 'Getrennt' }}</span>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useMainStore } from './stores/main.js'

const store     = useMainStore()
const connected = ref(false)

const navItems = [
  { to: '/',        icon: '📊', label: 'Dashboard'  },
  { to: '/topics',  icon: '📚', label: 'Topics'     },
  { to: '/research',icon: '🔎', label: 'Recherchen' },
  { to: '/sources', icon: '🌐', label: 'Quellen'    },
  { to: '/settings',icon: '⚙️', label: 'Einstellungen' },
]

let refreshTimer = null

async function checkConnection() {
  try {
    await store.fetchStatus()
    connected.value = true
  } catch {
    connected.value = false
  }
}

onMounted(async () => {
  await checkConnection()
  refreshTimer = setInterval(checkConnection, 30_000)  // alle 30s
})

onUnmounted(() => clearInterval(refreshTimer))
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:        #0f1117;
  --bg-card:   #1a1d2e;
  --bg-hover:  #252840;
  --border:    #2d3148;
  --text:      #e2e8f0;
  --text-muted:#8892a4;
  --accent:    #6366f1;
  --accent-2:  #818cf8;
  --green:     #22c55e;
  --yellow:    #eab308;
  --red:       #ef4444;
  --orange:    #f97316;
}

body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; }

.app { display: flex; min-height: 100vh; }

/* ---- Sidebar ---- */
.sidebar {
  width: 220px;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 1.5rem 0;
  position: fixed;
  height: 100vh;
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border);
}
.logo-icon { font-size: 1.5rem; }
.logo-text { font-size: 0.85rem; font-weight: 700; line-height: 1.3; color: var(--accent-2); }

.nav-links { list-style: none; flex: 1; padding: 1rem 0; }
.nav-links li { padding: 0.15rem 0.75rem; }

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-radius: 0.5rem;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 0.9rem;
  transition: all 0.15s;
}
.nav-link:hover { background: var(--bg-hover); color: var(--text); }
.nav-link.active { background: var(--accent); color: #fff; }
.nav-icon { font-size: 1.1rem; width: 1.5rem; text-align: center; }

.sidebar-footer {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 1.5rem 0;
  border-top: 1px solid var(--border);
  font-size: 0.8rem;
  color: var(--text-muted);
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.online  { background: var(--green); }
.status-dot.offline { background: var(--red); }

/* ---- Main Content ---- */
.main-content {
  margin-left: 220px;
  flex: 1;
  padding: 2rem;
  min-height: 100vh;
}

/* ---- Shared Styles ---- */
.page-header { margin-bottom: 2rem; }
.page-title  { font-size: 1.5rem; font-weight: 700; }
.page-subtitle { color: var(--text-muted); font-size: 0.9rem; margin-top: 0.25rem; }

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1.5rem;
}

.grid { display: grid; gap: 1rem; }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.15s;
}
.btn-primary  { background: var(--accent); color: #fff; }
.btn-primary:hover  { background: var(--accent-2); }
.btn-secondary { background: var(--bg-hover); color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { border-color: var(--accent); }
.btn-danger   { background: #7f1d1d; color: #fca5a5; }
.btn-small    { padding: 0.3rem 0.6rem; font-size: 0.8rem; }

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge-green  { background: #14532d; color: var(--green); }
.badge-yellow { background: #713f12; color: var(--yellow); }
.badge-red    { background: #7f1d1d; color: var(--red); }
.badge-blue   { background: #1e3a5f; color: #60a5fa; }
.badge-gray   { background: #374151; color: #9ca3af; }

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--text-muted);
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}

table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 0.75rem 1rem; font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); }
td { padding: 0.875rem 1rem; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }

input, select, textarea {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  outline: none;
  transition: border-color 0.15s;
}
input:focus, select:focus, textarea:focus { border-color: var(--accent); }

.form-group { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem; }
.form-label { font-size: 0.85rem; font-weight: 500; color: var(--text-muted); }
.form-input { width: 100%; }

.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 1rem;
  padding: 2rem;
  width: 90%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-title  { font-size: 1.1rem; font-weight: 700; }
.modal-close  { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 1.2rem; }
.modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem; }
</style>
