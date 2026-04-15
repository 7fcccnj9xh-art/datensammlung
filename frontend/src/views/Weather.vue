<template>
  <div>
    <div class="page-header" style="display:flex; justify-content:space-between; align-items:flex-start;">
      <div>
        <h1 class="page-title">Wetterdaten</h1>
        <p class="page-subtitle">DWD Open Data · {{ location }}</p>
      </div>
      <button class="btn btn-primary btn-small" @click="refreshWeather">🔄 Aktualisieren</button>
    </div>

    <!-- Aktuell -->
    <div class="grid grid-4" style="margin-bottom:1.5rem;" v-if="current">
      <div class="card stat-card">
        <div class="stat-label">Temperatur</div>
        <div class="stat-value">{{ current.temp_c?.toFixed(1) }}°C</div>
        <div class="stat-sub">Gefühlt: {{ current.temp_feels_like_c?.toFixed(1) ?? '–' }}°C</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">Luftfeuchte</div>
        <div class="stat-value">{{ current.humidity_pct }}%</div>
        <div class="stat-sub">Luftdruck: {{ current.pressure_hpa?.toFixed(0) }} hPa</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">Wind</div>
        <div class="stat-value">{{ current.wind_speed_ms?.toFixed(1) }} m/s</div>
        <div class="stat-sub">{{ windDir(current.wind_direction_deg) }} · {{ (current.wind_speed_ms * 3.6).toFixed(0) }} km/h</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">Bewölkung</div>
        <div class="stat-value">{{ current.cloud_cover_pct }}%</div>
        <div class="stat-sub">{{ current.weather_description }}</div>
      </div>
    </div>

    <!-- Temperatur-Chart -->
    <div class="card" style="margin-bottom:1.5rem;">
      <div class="card-header">
        <h3 class="card-title">Temperaturverlauf (7 Tage)</h3>
        <div style="display:flex; gap:0.5rem;">
          <button v-for="d in [3,7,14]" :key="d" class="btn btn-secondary btn-small"
            :class="{ 'btn-primary': historyDays === d }" @click="historyDays = d; loadHistory()">
            {{ d }}d
          </button>
        </div>
      </div>
      <div style="height: 280px;" v-if="chartData">
        <Line :data="chartData" :options="chartOptions" />
      </div>
      <div v-else class="loading">Laden...</div>
    </div>

    <!-- Prognose Tabelle -->
    <div class="card">
      <h3 class="card-title" style="margin-bottom:1rem;">Prognose (48h)</h3>
      <table v-if="forecast.length">
        <thead>
          <tr><th>Zeit</th><th>Temp</th><th>Regen</th><th>Wind</th><th>Bewölkung</th><th>Beschreibung</th></tr>
        </thead>
        <tbody>
          <tr v-for="f in forecast.slice(0, 16)" :key="f.measured_at">
            <td>{{ formatDate(f.measured_at) }}</td>
            <td>{{ f.temp_c?.toFixed(1) }}°C</td>
            <td>{{ f.precipitation_mm ? f.precipitation_mm.toFixed(1) + ' mm' : '–' }}</td>
            <td>{{ f.wind_speed_ms?.toFixed(1) }} m/s</td>
            <td>{{ f.cloud_cover_pct }}%</td>
            <td class="text-muted">{{ f.weather_description }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">Keine Prognose verfügbar</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js'
import { format } from 'date-fns'
import { de } from 'date-fns/locale'
import { useMainStore } from '../stores/main.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const store       = useMainStore()
const current     = ref(null)
const history     = ref([])
const forecast    = ref([])
const historyDays = ref(7)
const location    = ref('Konfiguriert in .env')

const chartData = computed(() => {
  if (!history.value.length) return null
  const sorted = [...history.value].sort((a,b) => new Date(a.measured_at) - new Date(b.measured_at))
  return {
    labels:   sorted.map(d => format(new Date(d.measured_at), 'EEE HH:mm', { locale: de })),
    datasets: [
      {
        label:           'Temperatur °C',
        data:            sorted.map(d => d.temp_c),
        borderColor:     '#6366f1',
        backgroundColor: 'rgba(99,102,241,0.1)',
        fill:            true,
        tension:         0.4,
        pointRadius:     2,
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: '#8892a4' } } },
  scales: {
    x: { ticks: { color: '#8892a4', maxTicksLimit: 14 }, grid: { color: '#2d3148' } },
    y: { ticks: { color: '#8892a4' }, grid: { color: '#2d3148' } },
  },
}

async function loadHistory() {
  history.value = await store.fetchWeatherHistory(historyDays.value)
}

async function refreshWeather() {
  await fetch('/api/weather/fetch', { method: 'POST' })
  setTimeout(async () => {
    current.value = await store.fetchWeatherCurrent()
    await loadHistory()
  }, 2000)
}

function windDir(deg) {
  if (!deg && deg !== 0) return '–'
  const dirs = ['N','NO','O','SO','S','SW','W','NW']
  return dirs[Math.round(deg / 45) % 8]
}

function formatDate(iso) {
  try { return format(new Date(iso), 'EEE HH:mm', { locale: de }) } catch { return iso }
}

onMounted(async () => {
  current.value  = await store.fetchWeatherCurrent()
  forecast.value = await fetch('/api/weather/forecast?hours=48').then(r => r.json())
  await loadHistory()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.card-title  { font-size: 1rem; font-weight: 600; }
.stat-card   { text-align: center; }
.stat-label  { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
.stat-value  { font-size: 2rem; font-weight: 700; color: var(--accent-2); }
.stat-sub    { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; }
.text-muted  { color: var(--text-muted); font-size: 0.85rem; }
.btn-primary { background: var(--accent) !important; }
</style>
