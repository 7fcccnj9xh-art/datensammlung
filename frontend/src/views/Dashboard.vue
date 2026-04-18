<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Dashboard</h1>
      <p class="page-subtitle">Systemübersicht · Aktualisiert {{ lastUpdated }}</p>
    </div>

    <!-- System-Status -->
    <div class="grid grid-4" style="margin-bottom: 1.5rem;">
      <div class="card stat-card">
        <div class="stat-label">Aktive Topics</div>
        <div class="stat-value">{{ stats.activeTopics }}</div>
        <div class="stat-sub">{{ stats.totalTopics }} gesamt</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">Jobs heute</div>
        <div class="stat-value">{{ stats.jobsToday }}</div>
        <div class="stat-sub">{{ stats.failedToday }} fehlgeschlagen</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">Neue Inhalte</div>
        <div class="stat-value">{{ stats.newResults }}</div>
        <div class="stat-sub">letzte 24h</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">LLM Kosten</div>
        <div class="stat-value">{{ stats.costsThisMonth }}€</div>
        <div class="stat-sub">diesen Monat</div>
      </div>
    </div>

    <div class="grid grid-2" style="margin-bottom: 1.5rem;">
      <!-- Provider Status -->
      <div class="card">
        <h3 class="card-title">System-Status</h3>
        <div class="status-list">
          <div v-for="(item, key) in providerStatus" :key="key" class="status-item">
            <div class="status-info">
              <span class="status-name">{{ item.label }}</span>
              <span class="status-detail">{{ item.detail }}</span>
            </div>
            <span class="badge" :class="item.ok ? 'badge-green' : 'badge-red'">
              {{ item.ok ? 'OK' : 'Fehler' }}
            </span>
          </div>
        </div>
      </div>

    </div>

    <!-- Letzte Jobs -->
    <div class="card" style="margin-bottom: 1.5rem;">
      <div class="card-header">
        <h3 class="card-title">Letzte Jobs</h3>
        <button class="btn btn-secondary btn-small" @click="loadJobs">Aktualisieren</button>
      </div>
      <table v-if="recentJobs.length">
        <thead>
          <tr>
            <th>Typ</th><th>Topic</th><th>Status</th><th>Dauer</th><th>Zeit</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in recentJobs" :key="job.id">
            <td><span class="badge badge-blue">{{ job.job_type }}</span></td>
            <td>{{ job.topic_id ? `#${job.topic_id}` : '–' }}</td>
            <td>
              <span class="badge" :class="statusBadge(job.status)">{{ job.status }}</span>
            </td>
            <td>{{ job.duration_seconds ? job.duration_seconds + 's' : '–' }}</td>
            <td class="text-muted">{{ formatDate(job.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">Noch keine Jobs</div>
    </div>

    <!-- Nächste geplante Jobs -->
    <div class="card">
      <h3 class="card-title">Geplante Jobs</h3>
      <div v-if="scheduledJobs.length" class="scheduled-list">
        <div v-for="job in scheduledJobs" :key="job.id" class="scheduled-item">
          <span class="scheduled-name">{{ job.name }}</span>
          <span class="scheduled-next" :class="{ paused: job.paused }">
            {{ job.paused ? 'Pausiert' : formatDate(job.next_run) }}
          </span>
        </div>
      </div>
      <div v-else class="empty-state">Keine geplanten Jobs</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useMainStore } from '../stores/main.js'
import { format } from 'date-fns'
import { de } from 'date-fns/locale'

const store         = useMainStore()
const recentJobs    = ref([])
const scheduledJobs = ref([])
const lastUpdated   = ref('–')
const llmStatus     = ref(null)
const stats         = ref({ activeTopics: 0, totalTopics: 0, jobsToday: 0, failedToday: 0, newResults: 0, costsThisMonth: '0.00' })

const providerStatus = computed(() => {
  if (!llmStatus.value) return {}
  const s = llmStatus.value
  return {
    database: { label: 'Datenbank',      detail: 'MySQL auf NAS',        ok: true },
    ollama:   { label: 'Ollama (lokal)', detail: s.ollama?.default_model, ok: s.ollama?.available  },
    claude:   { label: 'Claude API',     detail: s.claude?.default_model, ok: s.claude?.available  },
    scheduler:{ label: 'Scheduler',      detail: `${scheduledJobs.value.length} Jobs`, ok: true },
  }
})

async function loadAll() {
  await Promise.all([loadJobs(), loadLLMStatus(), loadTopicStats()])
  lastUpdated.value = format(new Date(), 'HH:mm', { locale: de })
}

async function loadJobs() {
  try {
    const data = await store.fetchJobs({ per_page: 10 })
    recentJobs.value = data.items

    const schedData = await fetch('/api/jobs/scheduled').then(r => r.json())
    scheduledJobs.value = schedData
  } catch(e) { console.error(e) }
}

async function loadLLMStatus() {
  try { llmStatus.value = await store.fetchLLMStatus() } catch {}
}

async function loadTopicStats() {
  try {
    const data = await store.fetchTopics()
    stats.value.totalTopics  = data.total
    stats.value.activeTopics = data.items.filter(t => t.status === 'active').length
  } catch {}
}

function statusBadge(status) {
  const map = { completed: 'badge-green', failed: 'badge-red', running: 'badge-yellow', queued: 'badge-blue' }
  return map[status] || 'badge-gray'
}

function formatDate(iso) {
  if (!iso) return '–'
  try { return format(new Date(iso), 'dd.MM HH:mm', { locale: de }) } catch { return iso }
}

let timer = null
onMounted(async () => {
  await loadAll()
  timer = setInterval(loadAll, 30_000)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.card-title  { font-size: 1rem; font-weight: 600; }

.stat-card   { text-align: center; }
.stat-label  { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; }
.stat-value  { font-size: 2rem; font-weight: 700; color: var(--accent-2); }
.stat-sub    { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; }

.status-list { display: flex; flex-direction: column; gap: 0.75rem; }
.status-item { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid var(--border); }
.status-item:last-child { border-bottom: none; }
.status-name  { font-size: 0.9rem; font-weight: 500; }
.status-detail { font-size: 0.8rem; color: var(--text-muted); display: block; }

.scheduled-list { display: flex; flex-direction: column; gap: 0.5rem; }
.scheduled-item { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; background: var(--bg); border-radius: 0.4rem; }
.scheduled-name { font-size: 0.875rem; }
.scheduled-next { font-size: 0.8rem; color: var(--text-muted); }
.scheduled-next.paused { color: var(--yellow); }
.text-muted { color: var(--text-muted); }
</style>
