import axios from 'axios'

const appBasePath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
const defaultApiBaseUrl = `${appBasePath || ''}/api`
const apiBaseUrl = import.meta.env.VITE_API_URL || defaultApiBaseUrl
const loginUrl = `${appBasePath || ''}/login`

const api = axios.create({
  baseURL: apiBaseUrl,
})

// Voeg JWT token toe aan elke request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Bij 401: refresh token of uitloggen
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${apiBaseUrl}/auth/token/refresh/`, { refresh })
          localStorage.setItem('access_token', data.access)
          original.headers.Authorization = `Bearer ${data.access}`
          return api(original)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = loginUrl
        }
      } else {
        window.location.href = loginUrl
      }
    }
    return Promise.reject(error)
  }
)

export default api
