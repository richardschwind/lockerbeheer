import { useAuth } from '../context/AuthContext'
import { useEffect, useRef, useState } from 'react'
import { lockersApi, rentalsApi } from '../api'
import { buildAccessEventsWebSocketUrl } from '../api/ws'

const LOCKER_STATE_LABELS = {
  free: 'Vrij',
  occupied_pin: 'Bezet via PIN',
  occupied_nfc: 'Bezet via NFC',
  opened_and_released: 'Geopend + vrij',
  conflict: 'Conflict',
  unknown: 'Onbekend',
}

const LOCKER_STATE_BADGES = {
  free: 'bg-green-100 text-green-700',
  occupied_pin: 'bg-red-100 text-red-700',
  occupied_nfc: 'bg-orange-100 text-orange-700',
  opened_and_released: 'bg-blue-100 text-blue-700',
  conflict: 'bg-rose-100 text-rose-700',
  unknown: 'bg-gray-100 text-gray-700',
}

function StatCard({ label, value, color }) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-100 p-6`}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState({ lockers: 0, available: 0, occupied: 0, occupiedPin: 0, occupiedNfc: 0, rentals: 0 })
  const [loading, setLoading] = useState(true)
  const [socketStatus, setSocketStatus] = useState('connecting')
  const [liveEvents, setLiveEvents] = useState([])
  const clearedAtRef = useRef(null)

  useEffect(() => {
    Promise.all([
      lockersApi.getAll(),
      rentalsApi.getAll({ status: 'active' }),
    ]).then(([lockersRes, rentalsRes]) => {
      const lockers = lockersRes.data.results ?? lockersRes.data
      const rentals = rentalsRes.data.results ?? rentalsRes.data
      const occupiedPin = lockers.filter((l) => l.status === 'occupied_pin').length
      const occupiedNfc = lockers.filter((l) => l.status === 'occupied_nfc').length
      const occupiedLegacy = lockers.filter((l) => l.status === 'occupied').length
      setStats({
        lockers: lockers.length,
        available: lockers.filter((l) => l.status === 'available').length,
        occupied: occupiedLegacy + occupiedPin + occupiedNfc,
        occupiedPin,
        occupiedNfc,
        rentals: Array.isArray(rentals) ? rentals.length : rentals,
      })
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setSocketStatus('disconnected')
      return undefined
    }

    let socket
    let reconnectTimer
    let isUnmounted = false

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
          if (data.type === 'access_events_batch' && Array.isArray(data.events)) {
            const threshold = clearedAtRef.current
            const incoming = data.events.filter((event) => {
              if (!threshold) return true
              const eventTime = Date.parse(event.pi_timestamp || event.created_at || '')
              if (Number.isNaN(eventTime)) return false
              return eventTime > threshold
            })

            if (incoming.length === 0) return

            setLiveEvents((prev) => {
              const seen = new Set(prev.map((event) => event.id))
              const uniqueIncoming = incoming.filter((event) => {
                if (seen.has(event.id)) return false
                seen.add(event.id)
                return true
              })

              return [...uniqueIncoming, ...prev].slice(0, 6)
            })
          }
        } catch {
          // Ignore malformed messages to keep realtime stream stable.
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
      if (socket) socket.close()
    }
  }, [])

  const statusBadgeClass = {
    connected: 'bg-green-100 text-green-700',
    connecting: 'bg-yellow-100 text-yellow-700',
    disconnected: 'bg-gray-100 text-gray-700',
    error: 'bg-red-100 text-red-700',
  }[socketStatus]

  const handleClearEvents = () => {
    const confirmed = window.confirm('Weet je zeker dat je alle access events wilt verwijderen?')
    if (!confirmed) return

    clearedAtRef.current = Date.now()
    setLiveEvents([])
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-2">
        Welkom, {user?.first_name || user?.email}!
      </h1>
      <p className="text-gray-500 mb-8">Overzicht lockerbeheer systeem</p>

      {loading ? (
        <p className="text-gray-400">Laden...</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
          <StatCard label="Totaal lockers" value={stats.lockers} color="text-gray-800" />
          <StatCard label="Beschikbaar" value={stats.available} color="text-green-600" />
          <StatCard label="Bezet" value={stats.occupied} color="text-red-500" />
          <StatCard label="Bezet via PIN" value={stats.occupiedPin} color="text-red-700" />
          <StatCard label="Bezet via NFC" value={stats.occupiedNfc} color="text-orange-600" />
          <StatCard label="Actieve huren" value={stats.rentals} color="text-blue-600" />
        </div>
      )}

      <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">Live Access Events</h2>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${statusBadgeClass}`}>
              Socket: {socketStatus}
            </span>
            <button
              type="button"
              onClick={handleClearEvents}
              className="px-3 py-1 rounded-md text-xs font-semibold bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-60"
            >
              Wis scherm
            </button>
          </div>
        </div>

        {liveEvents.length === 0 ? (
          <p className="text-sm text-gray-500">Nog geen realtime events ontvangen.</p>
        ) : (
          <div className="space-y-2">
            {liveEvents.map((event) => (
              <div
                key={`${event.id}-${event.pi_timestamp}`}
                className="flex items-center justify-between rounded-lg border border-gray-100 p-3"
              >
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    Locker #{event.locker_number} • {event.credential_type?.toUpperCase()}
                  </p>
                  <p className="text-xs text-gray-500">
                    {event.raspberry_pi_name || 'Onbekende Pi'}
                    {event.message ? ` • ${event.message}` : ''}
                  </p>
                  {event.pi_timestamp && (
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(event.pi_timestamp).toLocaleString('nl-NL', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {event.locker_state && (
                    <span
                      className={`text-xs font-semibold px-2 py-1 rounded-full ${
                        LOCKER_STATE_BADGES[event.locker_state] ?? 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {LOCKER_STATE_LABELS[event.locker_state] ?? event.locker_state}
                    </span>
                  )}
                  <span
                    className={`text-xs font-semibold px-2 py-1 rounded-full ${
                      event.status === 'success'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {event.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
