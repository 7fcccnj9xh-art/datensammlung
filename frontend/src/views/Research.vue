<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Recherchen</h1>
      <p class="page-subtitle">Ergebnisse durchsuchen und ad-hoc Recherchen starten</p>
    </div>

    <!-- Topic-Auswahl -->
    <div class="card" style="margin-bottom:1rem; padding:1rem;">
      <div style="display:flex; gap:1rem; align-items:center; flex-wrap:wrap;">
        <select v-model="selectedTopicId" @change="loadResults" class="form-input" style="width:280px;">
          <option value="">Topic auswählen...</option>
          <option v-for="t in topics" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <button v-if="selectedTopicId" class="btn btn-primary btn-small" @click="triggerResearch">
          ▶ Jetzt recherchieren
        </button>
        <button class="btn btn-secondary btn-small" @click="showAdhoc = true">
          🔎 Ad-hoc Suche
        </button>
      </div>
    </div>

    <!-- Ergebnisse -->
    <div v-if="selectedTopicId">
      <div v-if="loading" class="loading">Laden...</div>

      <div v-else-if="results.length" class="results-grid">
        <div v-for="r in results" :key="r.id" class="card result-card">
          <div class="result-header">
            <h3 class="result-title">{{ r.title }}</h3>
            <div style="display:flex; gap:0.4rem; align-items:center;">
              <span v-if="r.relevance_score" class="badge" :class="relevanceBadge(r.relevance_score)">
                {{ (r.relevance_score * 100).toFixed(0) }}%
              </span>
              <span class="text-muted">{{ formatDate(r.created_at) }}</span>
            </div>
          </div>

          <p v-if="r.summary" class="result-summary">{{ r.summary }}</p>
          <p v-else class="text-muted">Keine Zusammenfassung verfügbar</p>

          <div v-if="r.delta_summary" class="delta-box">
            <strong>Neu seit letztem Mal:</strong><br>{{ r.delta_summary }}
          </div>

          <div class="result-footer">
            <a v-if="r.source_url" :href="r.source_url" target="_blank" class="source-link">
              🔗 Quelle öffnen
            </a>
            <span class="text-muted">Version {{ r.version }}</span>
          </div>
        </div>
      </div>

      <div v-else class="card empty-state">
        Noch keine Ergebnisse für dieses Topic. Starte die erste Recherche!
      </div>
    </div>

    <!-- Platzhalter -->
    <div v-else class="card empty-state">
      Wähle ein Topic aus um Ergebnisse zu sehen
    </div>

    <!-- Ad-hoc Modal -->
    <div v-if="showAdhoc" class="modal-overlay" @click.self="showAdhoc = false">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">Ad-hoc Recherche</h2>
          <button class="modal-close" @click="showAdhoc = false">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label">Suchanfrage / Thema *</label>
          <input v-model="adhocQuery" class="form-input" placeholder="z.B. Raspberry Pi 5 neue Features" />
        </div>
        <div class="form-group">
          <label class="form-label">URLs (eine pro Zeile, optional)</label>
          <textarea v-model="adhocUrls" class="form-input" rows="3" placeholder="https://example.com/article"></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">LLM-Provider</label>
          <select v-model="adhocProvider" class="form-input">
            <option value="">Auto</option>
            <option value="ollama">Ollama (lokal)</option>
            <option value="claude">Claude</option>
          </select>
        </div>

        <div v-if="adhocResults.length" class="adhoc-results">
          <div v-for="(r, i) in adhocResults" :key="i" class="adhoc-result">
            <h4>{{ r.title || r.url }}</h4>
            <p>{{ r.summary }}</p>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showAdhoc = false">Schließen</button>
          <button class="btn btn-primary" @click="runAdhoc" :disabled="!adhocQuery || adhocLoading">
            {{ adhocLoading ? 'Läuft...' : '🔎 Suchen' }}
          </button>
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
import { useMainStore } from '../stores/main.js'

const store           = useMainStore()
const topics          = ref([])
const results         = ref([])
const selectedTopicId = ref('')
const loading         = ref(false)
const showAdhoc       = ref(false)
const adhocQuery      = ref('')
const adhocUrls       = ref('')
const adhocProvider   = ref('')
const adhocResults    = ref([])
const adhocLoading    = ref(false)

async function loadResults() {
  if (!selectedTopicId.value) return
  loading.value = true
  try {
    const data    = await store.fetchResearchResults(selectedTopicId.value, { per_page: 20 })
    results.value = data.items
  } finally { loading.value = false }
}

async function triggerResearch() {
  await store.triggerResearch(selectedTopicId.value)
  alert('Recherche gestartet!')
  setTimeout(loadResults, 3000)
}

async function runAdhoc() {
  adhocLoading.value = true
  adhocResults.value = []
  try {
    const urls = adhocUrls.value.split('\n').map(s => s.trim()).filter(Boolean)
    const { data } = await axios.post('/api/research/adhoc', {
      query:       adhocQuery.value,
      urls,
      llm_provider: adhocProvider.value || null,
    })
    adhocResults.value = data.results
  } finally { adhocLoading.value = false }
}

function relevanceBadge(score) {
  if (score >= 0.7) return 'badge-green'
  if (score >= 0.4) return 'badge-yellow'
  return 'badge-red'
}

function formatDate(iso) {
  try { return format(new Date(iso), 'dd.MM.yy HH:mm', { locale: de }) } catch { return iso }
}

onMounted(async () => {
  const data    = await store.fetchTopics({ status: 'active', per_page: 100 })
  topics.value  = data.items
})
</script>

<style scoped>
.results-grid { display: flex; flex-direction: column; gap: 1rem; }
.result-card  {}
.result-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem; gap: 1rem; }
.result-title  { font-size: 1rem; font-weight: 600; flex: 1; }
.result-summary { line-height: 1.6; color: var(--text-muted); font-size: 0.9rem; }
.result-footer  { display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border); }
.source-link    { color: var(--accent-2); text-decoration: none; font-size: 0.85rem; }
.source-link:hover { text-decoration: underline; }
.delta-box { background: var(--bg); border-left: 3px solid var(--accent); padding: 0.75rem 1rem; border-radius: 0 0.4rem 0.4rem 0; margin: 0.75rem 0; font-size: 0.85rem; }
.adhoc-results { margin: 1rem 0; border-top: 1px solid var(--border); padding-top: 1rem; }
.adhoc-result  { margin-bottom: 1rem; }
.adhoc-result h4 { font-size: 0.9rem; margin-bottom: 0.3rem; }
.adhoc-result p  { font-size: 0.85rem; color: var(--text-muted); }
.text-muted { color: var(--text-muted); font-size: 0.85rem; }
</style>
