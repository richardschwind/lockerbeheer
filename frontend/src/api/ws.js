function trimTrailingSlash(value) {
  return value.endsWith('/') ? value.slice(0, -1) : value
}

export function buildAccessEventsWebSocketUrl(token) {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const wsBasePath = trimTrailingSlash(import.meta.env.VITE_WS_BASE_PATH || '/ws')
  const wsHost = import.meta.env.DEV ? `${window.location.hostname}:8000` : window.location.host

  return `${wsProtocol}://${wsHost}${wsBasePath}/access-events/?token=${encodeURIComponent(token)}`
}
