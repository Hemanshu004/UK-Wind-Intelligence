import React, { useState, useRef } from 'react'

export function ErrorChart({ records }) {
  const containerRef = useRef(null)
  const [hoverIndex, setHoverIndex] = useState(null)

  if (!records || records.length === 0) {
    return null
  }

  const svgWidth = 1000
  const svgHeight = 220
  const margin = { top: 20, right: 30, bottom: 35, left: 75 }
  const plotWidth = svgWidth - margin.left - margin.right
  const plotHeight = svgHeight - margin.top - margin.bottom

  // Find max absolute error for symmetrical Y-axis around zero
  let maxAbsError = 1000
  records.forEach((r) => {
    if (r.error !== null && r.error !== undefined) {
      const abs = Math.abs(r.error)
      if (abs > maxAbsError) maxAbsError = abs
    }
  })

  // Round up to clean step
  const yLimit = Math.ceil((maxAbsError * 1.1) / 1000) * 1000

  const getX = (index) => {
    if (records.length <= 1) return margin.left + plotWidth / 2
    return margin.left + (index / (records.length - 1)) * plotWidth
  }

  const getY = (errVal) => {
    if (errVal === null || errVal === undefined) return null
    const clamped = Math.max(-yLimit, Math.min(yLimit, errVal))
    // -yLimit -> margin.top + plotHeight
    // 0 -> margin.top + plotHeight / 2
    // +yLimit -> margin.top
    const ratio = (clamped + yLimit) / (2 * yLimit)
    return margin.top + plotHeight - ratio * plotHeight
  }

  const yZero = getY(0)

  // X-axis ticks (stride calculated so at most 8-10 ticks appear)
  const targetTicks = 8
  const stride = Math.max(1, Math.floor(records.length / targetTicks))
  const xTicks = []
  for (let i = 0; i < records.length; i += stride) {
    xTicks.push({ index: i, record: records[i] })
  }
  if (records.length > 1 && records.length - 1 - (xTicks[xTicks.length - 1]?.index ?? 0) > stride / 2) {
    xTicks.push({ index: records.length - 1, record: records[records.length - 1] })
  }

  const formatXTime = (isoString) => {
    try {
      const d = new Date(isoString)
      const day = d.getUTCDate().toString().padStart(2, '0')
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      const month = monthNames[d.getUTCMonth()]
      const hours = d.getUTCHours().toString().padStart(2, '0')
      const mins = d.getUTCMinutes().toString().padStart(2, '0')
      if (records.length <= 48) {
        return `${day} ${month} ${hours}:${mins}`
      }
      return `${day} ${month}`
    } catch {
      return isoString
    }
  }

  const handleMouseMove = (e) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const svgRelX = (mouseX / rect.width) * svgWidth

    if (svgRelX < margin.left || svgRelX > margin.left + plotWidth) {
      setHoverIndex(null)
      return
    }

    const fraction = (svgRelX - margin.left) / plotWidth
    const idx = Math.round(fraction * (records.length - 1))
    if (idx >= 0 && idx < records.length) {
      setHoverIndex(idx)
    }
  }

  const hoveredRecord = hoverIndex !== null ? records[hoverIndex] : null
  const barWidth = Math.max(1.8, Math.min(10, plotWidth / records.length - 1))

  return (
    <div className="card" style={{ marginBottom: '1.25rem' }}>
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
        <div>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Hourly Forecast Error Profile (Signed Bias)
          </h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            Signed Error = Forecast − Actual (MW). Positive = Over-forecasting (Long), Negative = Under-forecasting (Short).
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: '12px', height: '12px', backgroundColor: 'var(--color-positive)', borderRadius: '2px' }} />
            <span style={{ color: 'var(--color-positive)', fontWeight: 600 }}>Over-forecast (+MW)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: '12px', height: '12px', backgroundColor: 'var(--color-negative)', borderRadius: '2px' }} />
            <span style={{ color: 'var(--color-negative)', fontWeight: 600 }}>Under-forecast (−MW)</span>
          </div>
        </div>
      </div>

      <div
        ref={containerRef}
        style={{ position: 'relative', width: '100%', cursor: 'crosshair', userSelect: 'none' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          {/* Y-Axis Gridlines & Reference Lines */}
          {[-yLimit, -yLimit / 2, 0, yLimit / 2, yLimit].map((val, idx) => {
            const y = getY(val)
            const isZero = val === 0
            return (
              <g key={idx}>
                <line
                  x1={margin.left}
                  y1={y}
                  x2={margin.left + plotWidth}
                  y2={y}
                  stroke={isZero ? '#94a3b8' : 'var(--border-subtle)'}
                  strokeWidth={isZero ? '1.5' : '1'}
                  strokeDasharray={isZero ? undefined : '3 3'}
                  opacity={isZero ? 0.9 : 0.35}
                />
                <text
                  x={margin.left - 10}
                  y={y + 4}
                  textAnchor="end"
                  fill={isZero ? 'var(--text-primary)' : 'var(--text-muted)'}
                  fontSize="11"
                  fontWeight={isZero ? '600' : '400'}
                  className="mono"
                >
                  {val > 0 ? `+${val.toLocaleString()}` : val.toLocaleString()} MW
                </text>
              </g>
            )
          })}

          {/* Error Bars for each interval */}
          {records.map((r, i) => {
            if (r.error === null || r.error === undefined) {
              return null
            }
            const x = getX(i)
            const yVal = getY(r.error)
            const yTop = Math.min(yZero, yVal)
            const height = Math.max(1.5, Math.abs(yVal - yZero))
            const isPositive = r.error >= 0

            return (
              <rect
                key={`err-bar-${i}`}
                x={x - barWidth / 2}
                y={yTop}
                width={barWidth}
                height={height}
                fill={isPositive ? 'var(--color-positive)' : 'var(--color-negative)'}
                opacity={hoverIndex === i ? 1 : 0.8}
                rx="1"
              />
            )
          })}

          {/* X-Axis Ticks */}
          {xTicks.map(({ index, record }) => {
            const x = getX(index)
            return (
              <g key={`xtick-err-${index}`}>
                <line
                  x1={x}
                  y1={margin.top + plotHeight}
                  x2={x}
                  y2={margin.top + plotHeight + 5}
                  stroke="var(--text-muted)"
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={margin.top + plotHeight + 18}
                  textAnchor="middle"
                  fill="var(--text-muted)"
                  fontSize="10"
                >
                  {formatXTime(record.delivery_start_time)}
                </text>
              </g>
            )
          })}

          {/* Hover Crosshair Guide */}
          {hoveredRecord && (
            <line
              x1={getX(hoverIndex)}
              y1={margin.top}
              x2={getX(hoverIndex)}
              y2={margin.top + plotHeight}
              stroke="#cbd5e1"
              strokeDasharray="3 3"
              strokeWidth="1.2"
            />
          )}
        </svg>

        {/* Floating Tooltip */}
        {hoveredRecord && (
          <div
            style={{
              position: 'absolute',
              top: '8px',
              left: `${Math.min(80, Math.max(12, (getX(hoverIndex) / svgWidth) * 100))}%`,
              transform: 'translateX(-50%)',
              backgroundColor: '#0f172a',
              border: '1px solid #334155',
              boxShadow: '0 8px 16px rgba(0,0,0,0.4)',
              borderRadius: '6px',
              padding: '0.5rem 0.75rem',
              pointerEvents: 'none',
              fontSize: '0.75rem',
              zIndex: 10,
              whiteSpace: 'nowrap',
            }}
          >
            <div style={{ color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
              {hoveredRecord.delivery_start_time?.replace('T', ' ').replace('Z', ' UTC')}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontWeight: 600 }}>Error:</span>
              <span
                className="mono"
                style={{
                  fontWeight: 700,
                  color:
                    hoveredRecord.error > 0
                      ? 'var(--color-positive)'
                      : hoveredRecord.error < 0
                      ? 'var(--color-negative)'
                      : 'var(--text-primary)',
                }}
              >
                {hoveredRecord.error !== null
                  ? `${hoveredRecord.error > 0 ? `+${hoveredRecord.error}` : hoveredRecord.error} MW`
                  : 'N/A (Missing)'}
              </span>
              <span
                className={`badge ${
                  hoveredRecord.status === 'MATCHED' ? 'badge-matched' : 'badge-missing'
                }`}
                style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}
              >
                {hoveredRecord.status}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
