import React from 'react'

export function DataQualitySummary({
  expectedCount,
  matchedCount,
  missingForecastCount,
  missingActualCount,
  coveragePercentage,
  dataNotes,
}) {
  return (
    <div
      className="card"
      style={{
        marginBottom: '1.25rem',
        fontSize: '0.8125rem',
        backgroundColor: 'rgba(21, 31, 50, 0.9)',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Data Quality &amp; Alignment Audit</span>
          <span className="badge badge-info mono">{coveragePercentage ?? 0}% Coverage</span>
        </div>

        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
          Methodology: Temporal alignment computes the arithmetic mean of two 30-min FUELHH actuals per hourly WINDFOR delivery interval.
        </div>
      </div>

      {/* Grid of Counts */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '0.75rem',
          padding: '0.75rem',
          backgroundColor: '#0f172a',
          borderRadius: '6px',
          border: '1px solid var(--border-subtle)',
          marginBottom: '0.75rem',
        }}
      >
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Expected Intervals</div>
          <div className="mono" style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {expectedCount ?? 0} hrs
          </div>
        </div>

        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Matched Intervals</div>
          <div className="mono" style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--color-success)' }}>
            {matchedCount ?? 0} hrs
          </div>
        </div>

        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Missing Forecasts</div>
          <div
            className="mono"
            style={{
              fontSize: '1.125rem',
              fontWeight: 700,
              color: missingForecastCount > 0 ? 'var(--color-danger)' : 'var(--text-secondary)',
            }}
          >
            {missingForecastCount ?? 0}
          </div>
        </div>

        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Incomplete Actuals</div>
          <div
            className="mono"
            style={{
              fontSize: '1.125rem',
              fontWeight: 700,
              color: missingActualCount > 0 ? 'var(--color-danger)' : 'var(--text-secondary)',
            }}
          >
            {missingActualCount ?? 0}
          </div>
        </div>

        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Coverage Ratio</div>
          <div className="mono" style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {coveragePercentage !== null && coveragePercentage !== undefined ? `${coveragePercentage}%` : '—'}
          </div>
        </div>
      </div>

      {/* Explanatory Note & Backend Notes */}
      <div style={{ color: 'var(--text-secondary)', lineHeight: 1.5, fontSize: '0.8125rem' }}>
        <p>
          Accuracy metrics (MAE, RMSE, Bias, and MAPE) are calculated <strong>strictly over valid matched forecast/actual pairs</strong>.
          Intervals with missing forecasts or incomplete half-hourly actuals are cataloged for operational transparency but excluded from mathematical aggregates to avoid biasing error statistics.
        </p>

        {dataNotes && (
          <div
            style={{
              marginTop: '0.5rem',
              padding: '0.4rem 0.65rem',
              borderRadius: '4px',
              backgroundColor: 'rgba(251, 191, 36, 0.1)',
              border: '1px solid rgba(251, 191, 36, 0.25)',
              color: '#fbbf24',
              fontSize: '0.75rem',
            }}
          >
            <strong>Note from API:</strong> {dataNotes}
          </div>
        )}
      </div>
    </div>
  )
}
