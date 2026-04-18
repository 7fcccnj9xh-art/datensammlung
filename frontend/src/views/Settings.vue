<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Einstellungen</h1>
      <p class="page-subtitle">System- und LLM-Konfiguration</p>
    </div>

    <!-- LLM Status & Test -->
    <div class="card" style="margin-bottom:1.5rem;">
      <h3 class="section-title">LLM-Provider Status</h3>
      <div class="grid grid-3" style="margin-bottom:1rem;">
        <div v-for="(p, key) in providers" :key="key" class="provider-card" :class="{ active: p.available }">
          <div class="provider-header">
            <span class="provider-name">{{ p.label }}</span>
            <span class="badge" :class="p.available ? 'badge-green' : 'badge-red'">
              {{ p.available ? 'Verfügbar' : 'N/A' }}
            </span>
          </div>
          <div class="provider-model">{{ p.model }}</div>
          <button v-if="p.available" class="btn btn-secondary btn-small" style="margin-top:0.5rem;"
            @click="testProvider(key)" :disabled="testing === key">
            {{ testing === key ? 'Teste...' : '▶ Test' }}
          </button>
          <div v-if="testResults[key]" class="test-result" :class="testResults[key].success ? 'success' : 'error'">
            {{ testResults[key].content || testResults[key].error }}
            <span v-if="testResults[key].cost_eur" class="cost-hint">
              ({{ testResults[key].duration_ms }}ms · {{ (testResults[key].cost_eur * 100).toFixed(4) }}¢)
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- System-Konfiguration (read-only) -->
    <div class="card" style="margin-bottom:1.5rem;">
      <h3 class="section-title">Aktive Konfiguration</h3>
      <p class="section-hint">Änderungen in der <code>.env</code> Datei vornehmen und Container neustarten.</p>
      <table v-if="config">
        <tbody>
          <tr v-for="(value, key) in configDisplay" :key="key">
            <td style="font-weight:500; width:280px;">{{ key }}</td>
            <td class="text-muted">{{ value }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Scheduler-Kontrolle -->
    <div class="card">
      <h3 class="section-title">Geplante Jobs</h3>
      <table v-if="scheduledJobs.length">
        <thead>
          <tr><th>Name</th><th>Nächster Lauf</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr v-for="job in scheduledJobs" :key="job.id">
            <td>{{ job.name }}</td>
            <td class="text-muted">{{ job.next_run ? formatDate(job.next_run) : '–' }}</td>
            <td><span class="badge" :class="job.paused ? 'badge-yellow' : 'badge-green'">
              {{ job.paused ? 'Pausiert' : 'Aktiv' }}
            </span></td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">Keine geplanten Jobs</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { format } from 'date-fns'
import { de } from 'date-fns/locale'
import { useMainStore } from '../stores/main.js'

const store         = useMainStore()
const llmStatus     = ref(null)
const config        = ref(null)
const scheduledJobs = ref([])
const testing       = ref(null)
const testResults   = ref({})

const providers = computed(() => {
  if (!llmStatus.value) return {}
  const s = llmStatus.value
  return {
    ollama: { label: 'Ollama (lokal)', available: s.ollama?.available, model: s.ollama?.default_model, key: 'ollama' },
    claude: { label: 'Claude API',    available: s.claude?.available, model: s.claude?.default_model, key: 'claude' },
    openai: { label: 'OpenAI GPT',    available: s.openai?.available, model: s.openai?.default_model, key: 'openai' },
  }
})

const configDisplay = computed(() => {
  if (!config.value) return {}
  return {
    'Standard LLM-Provider':  config.value.default_llm_provider,
    'Scraping-Delay':         `${config.value.scraping_delay_min}–${config.value.scraping_delay_max}s`,
    'robots.txt respektieren':config.value.respect_robots_txt ? 'Ja' : 'Nein',
    'Max. parallele Scraper': config.value.max_concurrent_scrapers,
    'LLM-Budget/Monat':       `${config.value.llm_monthly_budget_eur}€`,
    'Log-Level':              config.value.log_level,
    'Zeitzone':               config.value.tz,
  }
})

async function testProvider(provider) {
  testing.value = provider
  try {
    const result = await store.testLLM(provider)
    testResults.value[provider] = result
  } finally { testing.value = null }
}

function formatDate(iso) {
  try { return format(new Date(iso), 'dd.MM HH:mm', { locale: de }) } catch { return iso }
}

onMounted(async () => {
  llmStatus.value     = await store.fetchLLMStatus()
  const { data }      = await axios.get('/api/config')
  config.value        = data
  const jobsData      = await axios.get('/api/jobs/scheduled')
  scheduledJobs.value = jobsData.data
})
</script>

<style scoped>
.section-title { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
.section-hint  { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem; }
.section-hint code { background: var(--bg); padding: 0.1rem 0.3rem; border-radius: 0.25rem; }

.provider-card { background: var(--bg); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; }
.provider-card.active { border-color: var(--accent); }
.provider-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; }
.provider-name   { font-weight: 600; }
.provider-model  { font-size: 0.8rem; color: var(--text-muted); }
.test-result { margin-top: 0.5rem; font-size: 0.8rem; padding: 0.4rem; border-radius: 0.3rem; }
.test-result.success { background: #14532d; color: #86efac; }
.test-result.error   { background: #7f1d1d; color: #fca5a5; }
.cost-hint { opacity: 0.7; margin-left: 0.3rem; }
.text-muted { color: var(--text-muted); font-size: 0.875rem; }
</style>
