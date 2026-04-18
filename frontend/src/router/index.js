import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/',          name: 'Dashboard',      component: () => import('../views/Dashboard.vue') },
  { path: '/topics',    name: 'Topics',         component: () => import('../views/Topics.vue') },
  { path: '/research',  name: 'Research',       component: () => import('../views/Research.vue') },
  { path: '/sources',   name: 'Sources',        component: () => import('../views/Sources.vue') },
  { path: '/settings',  name: 'Settings',       component: () => import('../views/Settings.vue') },
]

export default createRouter({ history: createWebHistory(), routes })
