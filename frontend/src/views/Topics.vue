<template>
  <div>
    <div class="page-header" style="display:flex; justify-content:space-between; align-items:flex-start;">
      <div>
        <h1 class="page-title">Topics</h1>
        <p class="page-subtitle">{{ total }} Themen verwalten</p>
      </div>
      <button class="btn btn-primary" @click="showModal = true">+ Neues Topic</button>
    </div>

    <!-- Filter -->
    <div class="card" style="margin-bottom:1rem; padding:1rem;">
      <div style="display:flex; gap:1rem; align-items:center; flex-wrap:wrap;">
        <select v-model="filterStatus" @change="load" class="form-input" style="width:160px;">
          <option value="">Alle Status</option>
          <option value="active">Aktiv</option>
          <option value="paused">Pausiert</option>
          <option value="archived">Archiviert</option>
        </select>
        <select v-model="filterSchedule" @change="load" class="form-input" style="width:180px;">
          <option value="">Alle Typen</option>
          <option value="continuous">Kontinuierlich</option>
          <option value="sporadic">Sporadisch</option>
          <option value="once">Einmalig</option>
        </select>
      </div>
    </div>

    <!-- Topics Tabelle -->
    <div class="card">
      <div v-if="loading" class="loading">Laden...</div>
      <table v-else-if="topics.length">
        <thead>
          <tr>
            <th>Name</th><th>Kategorie</th><th>Typ</th><th>Status</th>
            <th>LLM</th><th>Zuletzt</th><th>Aktionen</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in topics" :key="t.id">
            <td>
              <div class="topic-name">{{ t.name }}</div>
              <div class="topic-slug text-muted">{{ t.slug }}</div>
            </td>
            <td><span v-if="t.category" class="badge badge-blue">{{ t.category }}</span></td>
            <td>
              <span class="badge" :class="scheduleClass(t.schedule_type)">{{ t.schedule_type }}</span>
            </td>
            <td>
              <span class="badge" :class="statusClass(t.status)">{{ t.status }}</span>
            </td>
            <td class="text-muted">{{ t.llm_provider || 'auto' }}</td>
            <td class="text-muted">{{ t.last_researched ? formatDate(t.last_researched) : '–' }}</td>
            <td>
              <div style="display:flex; gap:0.4rem;">
                <button class="btn btn-secondary btn-small" @click="triggerResearch(t)" title="Jetzt recherchieren">▶</button>
                <button class="btn btn-secondary btn-small" @click="togglePause(t)" :title="t.status === 'paused' ? 'Fortsetzen' : 'Pausieren'">
                  {{ t.status === 'paused' ? '▶▶' : '⏸' }}
                </button>
                <button class="btn btn-secondary btn-small" @click="editTopic(t)" title="Bearbeiten">✏️</button>
                <button class="btn btn-danger btn-small" @click="deleteTopic(t)" title="Löschen">🗑</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">Keine Topics vorhanden. Erstelle dein erstes Topic!</div>
    </div>

    <!-- Paginierung -->
    <div v-if="total > perPage" style="display:flex; justify-content:center; gap:0.5rem; margin-top:1rem;">
      <button class="btn btn-secondary btn-small" :disabled="page <= 1" @click="page--; load()">‹</button>
      <span style="padding:0.4rem 0.6rem; font-size:0.85rem;">{{ page }} / {{ Math.ceil(total/perPage) }}</span>
      <button class="btn btn-secondary btn-small" :disabled="page >= Math.ceil(total/perPage)" @click="page++; load()">›</button>
    </div>

    <!-- Modal: Topic erstellen/bearbeiten -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">{{ editingTopic ? 'Topic bearbeiten' : 'Neues Topic' }}</h2>
          <button class="modal-close" @click="closeModal">✕</button>
        </div>

        <div class="form-group">
          <label class="form-label">Name *</label>
          <input v-model="form.name" class="form-input" placeholder="z.B. KI-Modelle neue Releases" />
        </div>
        <div class="form-group">
          <label class="form-label">Beschreibung</label>
          <textarea v-model="form.description" class="form-input" rows="2" placeholder="Worum geht es in diesem Topic?"></textarea>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
          <div class="form-group">
            <label class="form-label">Kategorie</label>
            <input v-model="form.category" class="form-input" placeholder="z.B. Technologie" />
          </div>
          <div class="form-group">
            <label class="form-label">Scheduling-Typ</label>
            <select v-model="form.schedule_type" class="form-input">
              <option value="continuous">Kontinuierlich</option>
              <option value="sporadic">Sporadisch</option>
              <option value="once">Einmalig</option>
            </select>
          </div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
          <div class="form-group">
            <label class="form-label">LLM-Provider</label>
            <select v-model="form.llm_provider" class="form-input">
              <option value="">Auto (Standard)</option>
              <option value="ollama">Ollama (lokal)</option>
              <option value="claude">Claude</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Priorität (1-10)</label>
            <input v-model.number="form.priority" type="number" min="1" max="10" class="form-input" />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Suchbegriffe (kommagetrennt)</label>
          <input v-model="keywordsInput" class="form-input" placeholder="raspberry pi, raspberry pi 5, RPi release" />
        </div>
        <div class="form-group">
          <label class="form-label">Tags (kommagetrennt)</label>
          <input v-model="tagsInput" class="form-input" placeholder="Hardware, DIY, IoT" />
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeModal">Abbrechen</button>
          <button class="btn btn-primary" @click="saveTopic" :disabled="!form.name">
            {{ editingTopic ? 'Speichern' : 'Erstellen' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { format } from 'date-fns'
import { de } from 'date-fns/locale'
import { useMainStore } from '../stores/main.js'

const store         = useMainStore()
const topics        = ref([])
const total         = ref(0)
const loading       = ref(false)
const page          = ref(1)
const perPage       = 20
const filterStatus  = ref('')
const filterSchedule = ref('')
const showModal     = ref(false)
const editingTopic  = ref(null)
const keywordsInput = ref('')
const tagsInput     = ref('')

const form = ref({ name: '', description: '', category: '', schedule_type: 'sporadic', llm_provider: '', priority: 5 })

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, per_page: perPage }
    if (filterStatus.value) params.status = filterStatus.value
    const data = await store.fetchTopics(params)
    topics.value = data.items
    total.value  = data.total
  } finally { loading.value = false }
}

async function saveTopic() {
  const keywords = keywordsInput.value.split(',').map(s => s.trim()).filter(Boolean)
  const tags     = tagsInput.value.split(',').map(s => s.trim()).filter(Boolean)
  const payload  = {
    ...form.value,
    llm_provider:  form.value.llm_provider || null,
    tags:          tags.length ? tags : null,
    search_config: keywords.length ? { keywords } : null,
  }
  if (editingTopic.value) {
    await store.updateTopic(editingTopic.value.id, payload)
  } else {
    await store.createTopic(payload)
  }
  closeModal()
  load()
}

function editTopic(t) {
  editingTopic.value  = t
  form.value          = { name: t.name, description: t.description || '', category: t.category || '',
                          schedule_type: t.schedule_type, llm_provider: t.llm_provider || '', priority: t.priority }
  keywordsInput.value = (t.search_config?.keywords || []).join(', ')
  tagsInput.value     = (t.tags || []).join(', ')
  showModal.value     = true
}

function closeModal() {
  showModal.value     = false
  editingTopic.value  = null
  form.value          = { name: '', description: '', category: '', schedule_type: 'sporadic', llm_provider: '', priority: 5 }
  keywordsInput.value = ''
  tagsInput.value     = ''
}

async function triggerResearch(t) {
  await store.triggerResearch(t.id)
  alert(`Recherche für "${t.name}" gestartet`)
}

async function togglePause(t) {
  const newStatus = t.status === 'paused' ? 'active' : 'paused'
  await store.updateTopic(t.id, { status: newStatus })
  load()
}

async function deleteTopic(t) {
  if (!confirm(`"${t.name}" wirklich löschen? Alle Ergebnisse werden gelöscht!`)) return
  await store.deleteTopic(t.id)
  load()
}

function statusClass(s) { return { active: 'badge-green', paused: 'badge-yellow', archived: 'badge-gray' }[s] || 'badge-gray' }
function scheduleClass(s) { return { continuous: 'badge-green', sporadic: 'badge-blue', once: 'badge-gray' }[s] || 'badge-gray' }
function formatDate(iso) {
  try { return format(new Date(iso), 'dd.MM HH:mm', { locale: de }) } catch { return iso }
}

onMounted(load)
</script>

<style scoped>
.topic-name { font-weight: 500; }
.topic-slug { font-size: 0.8rem; margin-top: 0.1rem; }
.text-muted { color: var(--text-muted); font-size: 0.85rem; }
</style>
