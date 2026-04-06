import api from './client'

export const authApi = {
  login: (username, password) =>
    api.post('/auth/token/', { username, password }),

  refresh: (refresh) =>
    api.post('/auth/token/refresh/', { refresh }),

  register: (data) =>
    api.post('/users/register/', data),

  getProfile: () =>
    api.get('/users/me/'),

  updateProfile: (data) =>
    api.patch('/users/me/', data),
}

export const lockersApi = {
  getAll: (params) => api.get('/lockers/', { params }),
  getOne: (id) => api.get(`/lockers/${id}/`),
  create: (data) => api.post('/lockers/', data),
  update: (id, data) => api.patch(`/lockers/${id}/`, data),
  delete: (id) => api.delete(`/lockers/${id}/`),

  getLocations: () => api.get('/lockers/locations/'),
  createLocation: (data) => api.post('/lockers/locations/', data),
}

export const rentalsApi = {
  getAll: (params) => api.get('/rentals/', { params }),
  getOne: (id) => api.get(`/rentals/${id}/`),
  create: (data) => api.post('/rentals/', data),
  update: (id, data) => api.patch(`/rentals/${id}/`, data),
  end: (id) => api.patch(`/rentals/${id}/`, { status: 'ended' }),
  activate: (id) => api.patch(`/rentals/${id}/`, { status: 'active' }),
}

export const usersApi = {
  getLockerUsers: (params) => api.get('/users/locker-users/', { params }),
}

export const devicesApi = {
  getEvents: (params) => api.get('/devices/access-events/', { params }),
}
