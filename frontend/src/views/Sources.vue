<template>
  <div>
    <div class="page-header" style="display:flex; justify-content:space-between; align-items:flex-start;">
      <div>
        <h1 class="page-title">Quellen</h1>
        <p class="page-subtitle">{{ total }} Quellen · RSS-Feeds, Websites, APIs</p>
      </div>
      <button class="btn btn-primary" @click="showModal = true">+ Neue Quelle</button>
    </div>

    <!-- Filter -->
    <div class="card" style="margin-bottom:1rem; padding:1rem;">
      <select v-model="filterType" @change="load" class="form-input" style="width:180px;">
        <option value="">Alle Typen</option>
        <option value="website">Website</option>
        <option value="rss">RSS/Atom</option>
        <option value="api">API</option>
      </select>
    </div>

    <div class="card">
      <div v-if="loading" class="loading">Laden...</div>
      <table v-else-if="sources.length">
        <thead>
          <tr><th>Domain</th><th>Typ</th><th>Vertrauen</th><th>Abrufe</th><th>Fehler</th><th>Zuletzt</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="s in sources" :key="s.id">
            <td>
              <div class="source-title">{{ s.title || s.domain }}</div>
              <div class="text-muted">{{ s.domain }}</div>
            </td>
            <td><span class="badge" :class="typeBadge(s.source_type)">{{ s.source_type }}</span></td>
            <td>
              <div class="trust-bar">
                <div class="trust-fill" :style="{ width: (s.trust_score * 100) + '%', background: trustColor(s.trust_score) }"></div>
              </div>
              <span class="text-muted">{{ (s.trust_score * 100).toFixed(0) }}%</span>
            </td>
            <td class="text-muted">{{ s.fetch_count }}</td>
            <td class="text-muted" :class="{ 'text-red': s.error_count > 5 }">{{ s.error_count }}</td>
            <td class="text-muted">{{ s.last_fetched ? formatDate(s.last_fetched) : '–' }}</td>
            <td>
              <button class="btn btn-danger btn-small" @click="deleteSource(s)">🗑</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">Keine Quellen gefunden</div>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">Neue Quelle</h2>
          <button class="modal-close" @click="showModal = false">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label">URL *</label>
          <input v-model="form.url" class="form-input" placeholder="https://example.com/rss.xml" />
        </div>
        <div class="form-group">
          <label class="form-label">Name (optional)</label>
          <input v-model="form.title" class="form-input" placeholder="Heise Online" />
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
          <div class="form-group">
            <label class="form-label">Typ</label>
            <select v-model="form.source_type" class="form-input">
              <option value="website">Website</option>
              <option value="rss">RSS/Atom</option>
              <option value="api">API</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Vertrauen (0.0–1.0)</label>
            <input v-model.number="form.trust_score" type="number" min="0" max="1" step="0.05" class="form-input" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showModal = false">Abbrechen</button>
          <button class="btn btn-primary" @click="saveSource" :disabled="!form.url">Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { format } from 'date-fns'
import { de } from 'date-fns/locale'

const sources    = ref([])
const total      = ref(0)
const loading    = ref(false)
const showModal  = ref(false)
const filterType = ref('')
const form       = ref({ url: '', title: '', source_type: 'website', trust_score: 0.5 })

async function load() {
  loading.value = true
  try {
    const params = { per_page: 50 }
    if (filterType.value) params.source_type = filterType.value
    const { data } = await axios.get('/api/sources/', { params })
    sources.value = data.items
    total.value   = data.total
  } finally { loading.value = false }
}

async function saveSource() {
  await axios.post('/api/sources/', form.value)
  showModal.value = false
  form.value = { url: '', title: '', source_type: 'website', trust_score: 0.5 }
  load()
}

async function deleteSource(s) {
  if (!confirm(`"${s.title || s.domain}" wirklich löschen?`)) return
  await axios.delete(`/api/sources/${s.id}`)
  load()
}

const typeBadge  = t => ({ website: 'badge-blue', rss: 'badge-green', api: 'badge-yellow' }[t] || 'badge-gray')
const trustColor = s => s >= 0.8 ? '#22c55e' : s >= 0.5 ? '#eab308' : '#ef4444'
function formatDate(iso) { try { return format(new Date(iso), 'dd.MM HH:mm', { locale: de }) } catch { return iso } }

onMounted(load)
</script>

<style scoped>
.source-title { font-weight: 500; font-size: 0.9rem; }
.text-muted   { color: var(--text-muted); font-size: 0.85rem; }
.text-red     { color: var(--red); }
.trust-bar    { height: 4px; background: var(--bg-hover); border-radius: 2px; width: 60px; margin-bottom: 2px; }
.trust-fill   { height: 100%; border-radius: 2px; }
</style>
