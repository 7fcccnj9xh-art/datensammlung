import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const useMainStore = defineStore('main', () => {
  const systemStatus  = ref(null)
  const topics        = ref([])
  const jobs          = ref([])
  const notifications = ref([])

  async function fetchStatus() {
    const { data } = await api.get('/status')
    systemStatus.value = data
  }

  async function fetchTopics(params = {}) {
    const { data } = await api.get('/topics/', { params })
    topics.value = data.items
    return data
  }

  async function createTopic(payload) {
    const { data } = await api.post('/topics/', payload)
    return data
  }

  async function updateTopic(id, payload) {
    const { data } = await api.put(`/topics/${id}`, payload)
    return data
  }

  async function deleteTopic(id) {
    await api.delete(`/topics/${id}`)
  }

  async function triggerResearch(topicId) {
    const { data } = await api.post(`/topics/${topicId}/trigger`)
    return data
  }

  async function fetchJobs(params = {}) {
    const { data } = await api.get('/jobs/', { params })
    jobs.value = data.items
    return data
  }

  async function fetchRunningJobs() {
    const { data } = await api.get('/jobs/running')
    return data
  }

  async function fetchWeatherCurrent() {
    const { data } = await api.get('/weather/current')
    return data
  }

  async function fetchWeatherHistory(days = 7) {
    const { data } = await api.get('/weather/history', { params: { days } })
    return data
  }

  async function fetchLLMStatus() {
    const { data } = await api.get('/llm/status')
    return data
  }

  async function testLLM(provider, model) {
    const { data } = await api.post('/llm/test', null, { params: { provider, model } })
    return data
  }

  async function fetchResearchResults(topicId, params = {}) {
    const { data } = await api.get(`/research/results/${topicId}`, { params })
    return data
  }

  async function fetchSources(params = {}) {
    const { data } = await api.get('/sources/', { params })
    return data
  }

  return {
    systemStatus, topics, jobs, notifications,
    fetchStatus, fetchTopics, createTopic, updateTopic, deleteTopic,
    triggerResearch, fetchJobs, fetchRunningJobs,
    fetchWeatherCurrent, fetchWeatherHistory,
    fetchLLMStatus, testLLM,
    fetchResearchResults, fetchSources,
  }
})
