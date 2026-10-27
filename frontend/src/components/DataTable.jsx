import React, { useState, useMemo } from 'react'

export function DataTable({ records, startDate, endDate, policy }) {
  const [sortField, setSortField] = useState('delivery_start_time')
  const [sortAsc, setSortAsc] = useState(true)
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [pageSize, setPageSize] = useState(24)
  const [currentPage, setCurrentPage] = useState(1)

  // Filtering
  const filteredRecords = useMemo(() => {
    if (!records) return []
    if (statusFilter === 'ALL') return records
    if (statusFilter === 'MATCHED') return records.filter((r) => r.status === 'MATCHED')
    return records.filter((r) => r.status !== 'MATCHED')
  }, [records, statusFilter])

  // Sorting
  const sortedRecords = useMemo(() => {
    const list = [...filteredRecords]
    list.sort((a, b) => {
      let aVal = a[sortField]
      let bVal = b[sortField]

      if (aVal === null || aVal === undefined) return 1
      if (bVal === null || bVal === undefined) return -1

      if (typeof aVal === 'string') {
        return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      return sortAsc ? aVal - bVal : bVal - aVal
    })
    return list
  }, [filteredRecords, sortField, sortAsc])

  // Pagination
  const totalPages = pageSize === 'ALL' ? 1 : Math.max(1, Math.ceil(sortedRecords.length / pageSize))
  const paginatedRecords = useMemo(() => {
    if (pageSize === 'ALL') return sortedRecords
    const start = (currentPage - 1) * pageSize
    return sortedRecords.slice(start, start + pageSize)
  }, [sortedRecords, currentPage, pageSize])

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc)
    } else {
      setSortField(field)
      setSortAsc(true)
    }
  }

  // Export to CSV
  const handleExportCSV = () => {
    if (!records || records.length === 0) return

    const headers = [
      'delivery_start_time_utc',
      'settlement_date',
      'settlement_period_start',
      'settlement_period_end',
      'decision_cutoff_utc',
      'forecast_generation_mw',
      'forecast_publish_time_utc',
      'actual_generation_mw',
      'half_hour_1_mw',
      'half_hour_2_mw',
      'signed_error_mw',
      'absolute_error_mw',
      'status',
    ]

    const csvRows = [headers.join(',')]

    records.forEach((r) => {
      const h1 = r.half_hourly_actuals?.[0] ?? ''
      const h2 = r.half_hourly_actuals?.[1] ?? ''
      const row = [
        `"${r.delivery_start_time || ''}"`,
        `"${r.settlement_date || ''}"`,
        r.settlement_period_start ?? '',
        r.settlement_period_end ?? '',
        `"${r.cutoff_time || ''}"`,
        r.forecast_generation !== null ? r.forecast_generation : '',
        `"${r.forecast_publish_time || ''}"`,
        r.actual_generation !== null ? r.actual_generation : '',
        h1 !== null ? h1 : '',
        h2 !== null ? h2 : '',
        r.error !== null ? r.error : '',
        r.absolute_error !== null ? r.absolute_error : '',
        `"${r.status || ''}"`,
      ]
      csvRows.push(row.join(','))
    })

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `uk_wind_analysis_${policy}_${startDate}_to_${endDate}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const formatTimestamp = (iso) => {
    if (!iso) return '—'
    return iso.replace('T', ' ').replace(':00Z', ' UTC').replace('Z', ' UTC')
  }

  return (
    <div className="card" style={{ marginBottom: '1.25rem' }}>
      {/* Table Header Controls */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '1rem',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Hourly Interval Records
          </h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            Inspecting {sortedRecords.length} intervals across delivery period
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem' }}>
          {/* Status Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8125rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>Status:</span>
            <select
              className="select-control"
              style={{ padding: '0.3rem 0.5rem', fontSize: '0.8125rem' }}
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setCurrentPage(1)
              }}
            >
              <option value="ALL">All Intervals ({records?.length ?? 0})</option>
              <option value="MATCHED">Matched Only</option>
              <option value="UNMATCHED">Incomplete / Missing Only</option>
            </select>
          </div>

          {/* Page Size */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8125rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>Show:</span>
            <select
              className="select-control"
              style={{ padding: '0.3rem 0.5rem', fontSize: '0.8125rem' }}
              value={pageSize}
              onChange={(e) => {
                const val = e.target.value === 'ALL' ? 'ALL' : Number(e.target.value)
                setPageSize(val)
                setCurrentPage(1)
              }}
            >
              <option value={24}>24 (1 Day)</option>
              <option value={48}>48 (2 Days)</option>
              <option value={168}>168 (1 Week)</option>
              <option value="ALL">All Records</option>
            </select>
          </div>

          {/* CSV Export Button */}
          <button
            id="export-csv-btn"
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleExportCSV}
            title="Download full dataset as CSV"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Data Table */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('delivery_start_time')}>
                Delivery Time (UTC) {sortField === 'delivery_start_time' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th>Period</th>
              <th className="sortable" onClick={() => handleSort('forecast_generation')}>
                Forecast (MW) {sortField === 'forecast_generation' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th>Forecast Published (UTC)</th>
              <th className="sortable" onClick={() => handleSort('actual_generation')}>
                Actual (MW) {sortField === 'actual_generation' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSort('error')}>
                Signed Error {sortField === 'error' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th className="sortable" onClick={() => handleSort('absolute_error')}>
                Abs Error {sortField === 'absolute_error' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {paginatedRecords.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No records match the current filter.
                </td>
              </tr>
            ) : (
              paginatedRecords.map((r, idx) => {
                const isOver = r.error !== null && r.error > 0
                const isUnder = r.error !== null && r.error < 0
                const statusBadge =
                  r.status === 'MATCHED' ? (
                    <span className="badge badge-matched">MATCHED</span>
                  ) : (
                    <span className="badge badge-missing">{r.status}</span>
                  )

                return (
                  <tr key={idx}>
                    <td className="mono" style={{ fontWeight: 600 }}>
                      {formatTimestamp(r.delivery_start_time)}
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      SP {r.settlement_period_start}–{r.settlement_period_end}
                    </td>
                    <td className="mono" style={{ color: 'var(--color-forecast)', fontWeight: 600 }}>
                      {r.forecast_generation !== null ? `${r.forecast_generation.toLocaleString()} MW` : '—'}
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {formatTimestamp(r.forecast_publish_time)}
                    </td>
                    <td className="mono" style={{ color: 'var(--color-actual)', fontWeight: 600 }}>
                      {r.actual_generation !== null ? `${r.actual_generation.toLocaleString()} MW` : '—'}
                    </td>
                    <td
                      className="mono"
                      style={{
                        fontWeight: 700,
                        color: isOver
                          ? 'var(--color-positive)'
                          : isUnder
                          ? 'var(--color-negative)'
                          : 'var(--text-primary)',
                      }}
                    >
                      {r.error !== null ? (isOver ? `+${r.error}` : r.error) : '—'}
                    </td>
                    <td className="mono">
                      {r.absolute_error !== null ? `${r.absolute_error}` : '—'}
                    </td>
                    <td>{statusBadge}</td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginTop: '0.85rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid rgba(36, 50, 73, 0.4)',
            fontSize: '0.8125rem',
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>
            Showing page {currentPage} of {totalPages} ({sortedRecords.length} total intervals)
          </span>

          <div style={{ display: 'flex', gap: '0.35rem' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
