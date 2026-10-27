import React from 'react'

export function Header({ startDate, endDate, recordCount }) {
  return (
    <header
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        paddingBottom: '1.25rem',
        borderBottom: '1px solid var(--border-subtle)',
        marginBottom: '1.25rem',
      }}
    >
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
          <h1
            style={{
              fontSize: '1.75rem',
              fontWeight: 700,
              letterSpacing: '-0.025em',
              color: '#ffffff',
            }}
          >
            UK Wind Intelligence
          </h1>
          <span className="badge badge-info" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Historical Analysis
          </span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
          UK national wind generation forecast evaluation and procurement analytics
        </p>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.75rem',
        }}
      >
        {/* Date Range Badge */}
        <div
          style={{
            padding: '0.4rem 0.75rem',
            borderRadius: '6px',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.8125rem',
          }}
        >
          <span style={{ color: 'var(--text-muted)', marginRight: '0.35rem' }}>Delivery:</span>
          <span className="mono" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
            {startDate} <span style={{ color: 'var(--text-muted)' }}>→</span> {endDate}
          </span>
          {recordCount > 0 && (
            <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
              ({recordCount} hrs)
            </span>
          )}
        </div>

        {/* Data Source Badge */}
        <div
          style={{
            padding: '0.4rem 0.75rem',
            borderRadius: '6px',
            backgroundColor: 'rgba(56, 189, 248, 0.08)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            fontSize: '0.8125rem',
            color: '#38bdf8',
          }}
          title="Data source: Official Elexon BMRS Insights Solution API (Datasets: FUELHH & WINDFOR)"
        >
          <span style={{ fontWeight: 600 }}>Data Source:</span> Official Elexon BMRS
        </div>

        {/* Historical Notice Badge */}
        <div
          style={{
            padding: '0.4rem 0.75rem',
            borderRadius: '6px',
            backgroundColor: 'rgba(251, 191, 36, 0.1)',
            border: '1px solid rgba(251, 191, 36, 0.3)',
            fontSize: '0.8125rem',
            color: '#fbbf24',
          }}
          title="This platform analyzes historical settlement periods for January 2026, not live real-time feeds."
        >
          <span>January 2026 Outturn &amp; Forecasts</span>
        </div>
      </div>
    </header>
  )
}
