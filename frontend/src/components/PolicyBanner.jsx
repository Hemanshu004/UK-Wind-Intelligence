import React from 'react'

export function PolicyBanner({ policy, cutoffRule, leadTimeHours }) {
  let policyBadge = 'Day-Ahead Fixed Cutoff'
  let policyDetail = 'Selects the latest forecast published at or before D-1 at 12:00 UTC.'

  if (policy === 'rolling') {
    policyBadge = `Rolling Lead Time (${leadTimeHours}h)`
    policyDetail = `Evaluates the forecast available exactly ${leadTimeHours} hours before each delivery interval start time.`
  } else if (policy === 'latest_before_delivery') {
    policyBadge = 'Latest Before Delivery'
    policyDetail = 'Selects the most recent forecast published up to interval delivery. Note: Operational benchmark only, not a day-ahead purchasing forecast.'
  }

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '0.75rem',
        padding: '0.75rem 1rem',
        borderRadius: '8px',
        backgroundColor: 'rgba(30, 41, 59, 0.7)',
        border: '1px solid var(--border-subtle)',
        marginBottom: '1.25rem',
        fontSize: '0.8125rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--text-muted)' }}>Active Decision Policy:</span>
        <span className="badge badge-forecast">{policyBadge}</span>
        <span style={{ color: 'var(--text-secondary)' }}>{cutoffRule || policyDetail}</span>
      </div>

      {policy === 'day_ahead' && (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontStyle: 'italic' }}>
          * Cutoff reflects standard GB Day-Ahead auction timing assumptions (provisional analytical setting, not an official Elexon rule).
        </div>
      )}
    </div>
  )
}
