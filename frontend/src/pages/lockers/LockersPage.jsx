import { useCallback, useEffect, useRef, useState } from 'react'
import { lockersApi } from '../../api'
import { buildAccessEventsWebSocketUrl } from '../../api/ws'

const STATUS_COLORS = {
  available: 'bg-green-100 text-green-800',
  occupied: 'bg-red-100 text-red-800',
  occupied_pin: 'bg-red-100 text-red-800',
  occupied_nfc: 'bg-orange-100 text-orange-800',
  maintenance: 'bg-yellow-100 text-yellow-800',
  reserved: 'bg-blue-100 text-blue-800',
}

export default function LockersPage() {
  const [lockers, setLockers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [socketStatus, setSocketStatus] = useState('connecting')
  const refreshTimerRef = useRef(null)

  const loadLockers = useCallback(() => {
    setLoading(true)
    lockersApi.getAll({ search, status: filterStatus || undefined })
      .then(({ data }) => setLockers(data.results ?? data))
      .finally(() => setLoading(false))
  }, [search, filterStatus])

  useEffect(() => { loadLockers() }, [search, filterStatus])

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setSocketStatus('disconnected')
      return undefined
    }

    let socket
    let reconnectTimer
    let isUnmounted = false

    const scheduleRefresh = () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
      refreshTimerRef.current = setTimeout(() => {
        loadLockers()
      }, 250)
    }

    const connect = () => {
      const wsUrl = buildAccessEventsWebSocketUrl(token)

      setSocketStatus('connecting')
      socket = new WebSocket(wsUrl)

      socket.onopen = () => {
        if (!isUnmounted) {
          setSocketStatus('connected')
        }
      }

      socket.onmessage = (message) => {
        try {
          const data = JSON.parse(message.data)
          if (data.type === 'access_events_batch') {
            scheduleRefresh()
          }
        } catch {
          // Ignore malformed messages to keep realtime updates stable.
        }
      }

      socket.onclose = () => {
        if (isUnmounted) return
        setSocketStatus('disconnected')
        reconnectTimer = setTimeout(connect, 3000)
      }

      socket.onerror = () => {
        if (!isUnmounted) {
          setSocketStatus('error')
        }
      }
    }

    connect()

    return () => {
      isUnmounted = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
      if (socket) socket.close()
    }
  }, [loadLockers])

  const socketBadgeClass = {
    connected: 'bg-green-100 text-green-700',
    connecting: 'bg-yellow-100 text-yellow-700',
    disconnected: 'bg-gray-100 text-gray-700',
    error: 'bg-red-100 text-red-700',
  }[socketStatus]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Lockers</h1>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${socketBadgeClass}`}>
          Live: {socketStatus}
        </span>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="Zoek op nummer of locatie..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-72 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Alle statussen</option>
          <option value="available">Beschikbaar</option>
          <option value="occupied">Bezet</option>
          <option value="occupied_pin">Bezet via PIN</option>
          <option value="occupied_nfc">Bezet via NFC</option>
          <option value="maintenance">Onderhoud</option>
          <option value="reserved">Gereserveerd</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-400">Laden...</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Nummer</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Locatie</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Grootte</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Verdieping</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {lockers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-gray-400">Geen lockers gevonden</td>
                </tr>
              ) : lockers.map((locker) => (
                <tr key={locker.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium">{locker.number}</td>
                  <td className="px-4 py-3 text-gray-600">{locker.location_name}</td>
                  <td className="px-4 py-3 text-gray-600">{locker.size_display}</td>
                  <td className="px-4 py-3 text-gray-600">{locker.floor}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[locker.status] ?? 'bg-gray-100 text-gray-700'}`}>
                      {locker.status_display}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
