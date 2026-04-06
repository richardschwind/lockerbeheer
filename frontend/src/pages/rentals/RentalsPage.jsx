import { useEffect, useState } from 'react'
import { rentalsApi } from '../../api'
import { useAuth } from '../../context/AuthContext'

const STATUS_COLORS = {
  active: 'bg-green-100 text-green-800',
  ended: 'bg-gray-100 text-gray-600',
  cancelled: 'bg-red-100 text-red-700',
}

export default function RentalsPage() {
  const { user } = useAuth()
  const [rentals, setRentals] = useState([])
  const [loading, setLoading] = useState(true)
  const [submittingId, setSubmittingId] = useState(null)

  const canManageRentals = ['superadmin', 'company_admin'].includes(user?.role) || user?.is_superuser

  const loadPageData = () => {
    setLoading(true)
    rentalsApi
      .getAll()
      .then((response) => {
        const data = response.data?.results ?? response.data ?? []
        setRentals(data)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPageData()
  }, [])

  const handleStatusChange = async (id, nextStatus) => {
    const isEnding = nextStatus === 'ended'
    const confirmed = confirm(
      isEnding
        ? 'Wil je deze huurovereenkomst beëindigen?'
        : 'Wil je deze huurovereenkomst opnieuw actief maken?'
    )
    if (!confirmed) return

    setSubmittingId(id)

    try {
      if (isEnding) {
        await rentalsApi.end(id)
      } else {
        await rentalsApi.activate(id)
      }
      loadPageData()
    } finally {
      setSubmittingId(null)
    }
  }

  return (
    <div>
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Huurovereenkomsten</h1>
          <p className="text-sm text-gray-500 mt-1">Overzicht van alle huurovereenkomsten</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-600 shadow-sm">
          Actief: <span className="font-semibold text-gray-800">{rentals.filter((r) => r.status === 'active').length}</span>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-400">Laden...</p>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Gebruiker</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Locker</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Startdatum</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Einddatum</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Acties</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rentals.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-gray-400">
                    Geen huurovereenkomsten gevonden
                  </td>
                </tr>
              ) : (
                rentals.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-800">{r.locker_user_detail?.full_name ?? r.locker_user}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{r.locker_user_detail?.company_name ?? ''}</div>
                    </td>
                    <td className="px-4 py-3">
                      {r.locker_detail ? (
                        <div>
                          <span className="font-medium text-gray-800">Locker {r.locker_detail.number}</span>
                          <div className="text-xs text-gray-500 mt-0.5">{r.locker_detail.location_name}</div>
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{r.start_date}</td>
                    <td className="px-4 py-3 text-gray-600">{r.end_date ?? '–'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[r.status]}`}>
                        {r.status_display}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {canManageRentals && r.status === 'active' && (
                        <button
                          onClick={() => handleStatusChange(r.id, 'ended')}
                          disabled={submittingId === r.id}
                          className="text-xs text-red-600 hover:underline disabled:text-gray-400 disabled:no-underline"
                        >
                          Beëindigen
                        </button>
                      )}
                      {canManageRentals && r.status !== 'active' && (
                        <button
                          onClick={() => handleStatusChange(r.id, 'active')}
                          disabled={submittingId === r.id}
                          className="text-xs text-blue-600 hover:underline disabled:text-gray-400 disabled:no-underline"
                        >
                          Actief maken
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

