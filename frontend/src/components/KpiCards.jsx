import React from 'react'

function formatNumber(val, decimals = 1, unit = '') {
  if (val === null || val === undefined || isNaN(val)) {
    return 'N/A'
  }
  const formatted = Number(val).toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return unit ? `${formatted} ${unit}` : formatted
}

export function KpiCards({ metrics, matchedCount, expectedCount, coveragePercentage }) {
  const mae = metrics?.mae
  const rmse = metrics?.rmse
  const bias = metrics?.bias
  const mape = metrics?.mape

  // Bias interpretation badge
  let biasBadge = null
  if (bias !== null && bias !== undefined) {
    if (bias > 0) {
      biasBadge = (
        <span
          className="badge"
          style={{
            backgroundColor: 'rgba(45, 212, 191, 0.15)',
            color: 'var(--color-positive)',
            border: '1px solid rgba(45, 212, 191, 0.3)',
          }}
        >
          Over-forecast (Long)
        </span>
      )
    } else if (bias < 0) {
      biasBadge = (
        <span
          className="badge"
          style={{
            backgroundColor: 'rgba(251, 146, 60, 0.15)',
            color: 'var(--color-negative)',
            border: '1px solid rgba(251, 146, 60, 0.3)',
          }}
        >
          Under-forecast (Short)
        </span>
      )
    } else {
      biasBadge = <span className="badge badge-matched">Neutral (0 MW)</span>
    }
  }

  const cards = [
    {
      id: 'kpi-mae',
      label: 'Mean Absolute Error (MAE)',
      value: formatNumber(mae, 1, 'MW'),
      description: 'Average magnitude of forecast error across matched intervals.',
      accent: 'var(--color-forecast)',
    },
    {
      id: 'kpi-rmse',
      label: 'Root Mean Squared Error (RMSE)',
      value: formatNumber(rmse, 1, 'MW'),
      description: 'Heavily penalizes larger errors; measures forecast deviation volatility.',
      accent: '#38bdf8',
    },
    {
      id: 'kpi-bias',
      label: 'Forecast Bias',
      value: formatNumber(bias, 1, 'MW'),
      description: 'Mean signed error: mean(forecast - actual). Positive = over-forecasting.',
      accent: bias !== null && bias !== undefined && bias > 0 ? 'var(--color-positive)' : 'var(--color-negative)',
      badge: biasBadge,
    },
    {
      id: 'kpi-mape',
      label: 'Mean Absolute Percentage Error',
      value: mape !== null && mape !== undefined ? `${formatNumber(mape, 2)}%` : 'N/A',
      description: 'Mean relative percentage deviation (zero actuals excluded).',
      accent: '#a855f7',
    },
    {
      id: 'kpi-coverage',
      label: 'Data Coverage',
      value: coveragePercentage !== null && coveragePercentage !== undefined ? `${coveragePercentage}%` : 'N/A',
      description: `${matchedCount ?? 0} of ${expectedCount ?? 0} expected hourly intervals matched.`,
      accent: coveragePercentage === 100 ? 'var(--color-success)' : 'var(--color-warning)',
      badge: (
        <span className="badge badge-info mono">
          {matchedCount ?? 0}/{expectedCount ?? 0} hrs
        </span>
      ),
    },
  ]

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1rem',
        marginBottom: '1.25rem',
      }}
    >
      {cards.map((c) => (
        <div
          key={c.id}
          className="card"
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            borderTop: `3px solid ${c.accent}`,
          }}
        >
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.4rem',
              }}
            >
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                {c.label}
              </span>
              {c.badge}
            </div>

            <div
              className="mono"
              style={{
                fontSize: '1.625rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                letterSpacing: '-0.02em',
                marginBottom: '0.35rem',
              }}
            >
              {c.value}
            </div>
          </div>

          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.35 }}>
            {c.description}
          </p>
        </div>
      ))}
    </div>
  )
}
