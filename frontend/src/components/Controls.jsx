import React, { useState } from 'react'

export function Controls({
  filters,
  onApply,
  isLoading,
}) {
  const [startDate, setStartDate] = useState(filters.startDate)
  const [endDate, setEndDate] = useState(filters.endDate)
  const [policy, setPolicy] = useState(filters.policy)
  const [leadTimeHours, setLeadTimeHours] = useState(filters.leadTimeHours ?? 24)
  const [cutoffTime, setCutoffTime] = useState(filters.dayAheadCutoffTime ?? '12:00')
  const [validationError, setValidationError] = useState('')

  const handlePreset = (start, end) => {
    setStartDate(start)
    setEndDate(end)
    setValidationError('')
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    if (!startDate || !endDate) {
      setValidationError('Please specify both a start date and an end date.')
      return
    }

    if (startDate > endDate) {
      setValidationError(`Start date (${startDate}) cannot be after end date (${endDate}).`)
      return
    }

    if (policy === 'rolling') {
      const numLead = parseFloat(leadTimeHours)
      if (isNaN(numLead) || numLead <= 0) {
        setValidationError('Rolling lead time must be a positive number of hours (e.g. 24, 12, 4, 1).')
        return
      }
    }

    if (policy === 'day_ahead') {
      if (!/^\d{1,2}:\d{2}$/.test(cutoffTime.trim())) {
        setValidationError('Day-ahead cutoff time must be in HH:MM format (e.g. 12:00).')
        return
      }
    }

    setValidationError('')
    onApply({
      startDate,
      endDate,
      policy,
      leadTimeHours: policy === 'rolling' ? parseFloat(leadTimeHours) : undefined,
      dayAheadCutoffTime: policy === 'day_ahead' ? cutoffTime.trim() : undefined,
    })
  }

  return (
    <div className="card" style={{ marginBottom: '1.25rem' }}>
      <form onSubmit={handleSubmit}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '1rem',
            alignItems: 'flex-end',
          }}
        >
          {/* Start Date */}
          <div>
            <label
              htmlFor="start-date-input"
              style={{
                display: 'block',
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '0.35rem',
              }}
            >
              Start Date
            </label>
            <input
              id="start-date-input"
              type="date"
              className="input-control"
              style={{ width: '100%' }}
              value={startDate}
              min="2026-01-01"
              max="2026-01-31"
              onChange={(e) => {
                setStartDate(e.target.value)
                setValidationError('')
              }}
            />
          </div>

          {/* End Date */}
          <div>
            <label
              htmlFor="end-date-input"
              style={{
                display: 'block',
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '0.35rem',
              }}
            >
              End Date
            </label>
            <input
              id="end-date-input"
              type="date"
              className="input-control"
              style={{ width: '100%' }}
              value={endDate}
              min="2026-01-01"
              max="2026-01-31"
              onChange={(e) => {
                setEndDate(e.target.value)
                setValidationError('')
              }}
            />
          </div>

          {/* Forecast Policy */}
          <div style={{ minWidth: '220px' }}>
            <label
              htmlFor="policy-select"
              style={{
                display: 'block',
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                marginBottom: '0.35rem',
              }}
            >
              Forecast Selection Policy
            </label>
            <select
              id="policy-select"
              className="select-control"
              style={{ width: '100%' }}
              value={policy}
              onChange={(e) => {
                setPolicy(e.target.value)
                setValidationError('')
              }}
            >
              <option value="day_ahead">Day-Ahead Fixed Cutoff (D-1)</option>
              <option value="rolling">Rolling Lead Time</option>
              <option value="latest_before_delivery">Latest Available Before Delivery</option>
            </select>
          </div>

          {/* Conditional: Rolling Lead Time */}
          {policy === 'rolling' && (
            <div>
              <label
                htmlFor="lead-time-input"
                style={{
                  display: 'block',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  color: 'var(--text-secondary)',
                  marginBottom: '0.35rem',
                }}
              >
                Lead Time (Hours)
              </label>
              <div style={{ display: 'flex', gap: '0.35rem' }}>
                <input
                  id="lead-time-input"
                  type="number"
                  step="0.5"
                  min="0.5"
                  max="168"
                  className="input-control"
                  style={{ width: '100%' }}
                  value={leadTimeHours}
                  onChange={(e) => {
                    setLeadTimeHours(e.target.value)
                    setValidationError('')
                  }}
                />
                {[24, 12, 4, 1].map((h) => (
                  <button
                    key={h}
                    type="button"
                    className="btn btn-secondary btn-sm mono"
                    style={{
                      padding: '0 0.5rem',
                      backgroundColor: Number(leadTimeHours) === h ? '#334155' : undefined,
                    }}
                    onClick={() => setLeadTimeHours(h)}
                    title={`Set lead time to ${h} hours`}
                  >
                    {h}h
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Conditional: Day-Ahead Cutoff Time */}
          {policy === 'day_ahead' && (
            <div>
              <label
                htmlFor="cutoff-time-input"
                style={{
                  display: 'block',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  color: 'var(--text-secondary)',
                  marginBottom: '0.35rem',
                }}
              >
                D-1 Gate Closure (UTC)
              </label>
              <div style={{ display: 'flex', gap: '0.35rem' }}>
                <input
                  id="cutoff-time-input"
                  type="text"
                  className="input-control mono"
                  style={{ width: '100%' }}
                  value={cutoffTime}
                  placeholder="12:00"
                  onChange={(e) => {
                    setCutoffTime(e.target.value)
                    setValidationError('')
                  }}
                />
                {['11:00', '12:00', '14:00'].map((t) => (
                  <button
                    key={t}
                    type="button"
                    className="btn btn-secondary btn-sm mono"
                    style={{
                      padding: '0 0.45rem',
                      backgroundColor: cutoffTime === t ? '#334155' : undefined,
                    }}
                    onClick={() => setCutoffTime(t)}
                    title={`Set cutoff to ${t} UTC`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Submit Button */}
          <div>
            <button
              id="analyze-submit-btn"
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', height: '38px' }}
              disabled={isLoading}
            >
              {isLoading ? 'Fetching Data...' : 'Analyze Forecasts'}
            </button>
          </div>
        </div>

        {/* Quick Date Presets */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            marginTop: '0.85rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid rgba(36, 50, 73, 0.4)',
            fontSize: '0.8125rem',
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>Quick Presets:</span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => handlePreset('2026-01-01', '2026-01-31')}
          >
            Full Month (Jan 1–31)
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => handlePreset('2026-01-01', '2026-01-07')}
          >
            Week 1 (Jan 1–7)
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => handlePreset('2026-01-01', '2026-01-01')}
          >
            Single Day (Jan 1)
          </button>
        </div>

        {/* Validation Error Banner */}
        {validationError && (
          <div
            style={{
              marginTop: '0.75rem',
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              backgroundColor: 'var(--color-danger-bg)',
              color: 'var(--color-danger)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              fontSize: '0.8125rem',
            }}
          >
            {validationError}
          </div>
        )}
      </form>
    </div>
  )
}
