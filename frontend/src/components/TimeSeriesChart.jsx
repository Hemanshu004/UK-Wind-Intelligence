import React, { useState, useRef } from 'react'

export function TimeSeriesChart({ records }) {
  const containerRef = useRef(null)
  const [hoverIndex, setHoverIndex] = useState(null)

  if (!records || records.length === 0) {
    return (
      <div className="card" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        No interval data available to plot.
      </div>
    )
  }

  // Dimensions
  const svgWidth = 1000
  const svgHeight = 360
  const margin = { top: 25, right: 30, bottom: 45, left: 75 }
  const plotWidth = svgWidth - margin.left - margin.right
  const plotHeight = svgHeight - margin.top - margin.bottom

  // Compute min / max generation
  let maxGen = 1000 // baseline min max
  records.forEach((r) => {
    if (r.forecast_generation !== null && r.forecast_generation > maxGen) {
      maxGen = r.forecast_generation
    }
    if (r.actual_generation !== null && r.actual_generation > maxGen) {
      maxGen = r.actual_generation
    }
  })

  // Round maxGen up to a clean multiple
  const yUpper = Math.ceil((maxGen * 1.08) / 2000) * 2000
  const yLower = 0

  const getX = (index) => {
    if (records.length <= 1) return margin.left + plotWidth / 2
    return margin.left + (index / (records.length - 1)) * plotWidth
  }

  const getY = (val) => {
    if (val === null || val === undefined) return null
    const clamped = Math.max(yLower, Math.min(yUpper, val))
    return margin.top + plotHeight - ((clamped - yLower) / (yUpper - yLower)) * plotHeight
  }

  // Build SVG path segments handling missing gaps (null values break lines)
  const buildSegments = (valKey) => {
    const segments = []
    let currentSegment = []

    records.forEach((r, i) => {
      const val = r[valKey]
      if (val !== null && val !== undefined) {
        currentSegment.push({ x: getX(i), y: getY(val) })
      } else {
        if (currentSegment.length > 0) {
          segments.push(currentSegment)
          currentSegment = []
        }
      }
    })
    if (currentSegment.length > 0) {
      segments.push(currentSegment)
    }

    return segments.map((seg) => {
      return seg.reduce((acc, pt, idx) => {
        return idx === 0 ? `M ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}` : `${acc} L ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`
      }, '')
    })
  }

  const forecastSegments = buildSegments('forecast_generation')
  const actualSegments = buildSegments('actual_generation')

  // Y-axis gridlines
  const yTicksCount = 5
  const yTicks = []
  for (let i = 0; i <= yTicksCount; i++) {
    const val = yLower + (i / yTicksCount) * (yUpper - yLower)
    yTicks.push({ val, y: getY(val) })
  }

  // X-axis ticks (stride calculated so at most 8-10 ticks appear)
  const targetTicks = 8
  const stride = Math.max(1, Math.floor(records.length / targetTicks))
  const xTicks = []
  for (let i = 0; i < records.length; i += stride) {
    xTicks.push({ index: i, record: records[i] })
  }
  // Ensure the last record is also labeled if gap is large
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

  const formatFullTimestamp = (isoString) => {
    if (!isoString) return 'N/A'
    return isoString.replace('T', ' ').replace('Z', ' UTC')
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

  return (
    <div className="card" style={{ marginBottom: '1.25rem' }}>
      {/* Chart Title and Legend */}
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
            Wind Generation: Forecast vs Actual
          </h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            Hourly delivery profile in Megawatts (MW) comparing selected forecast against aligned actual outturn
          </p>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', fontSize: '0.8125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span
              style={{
                width: '16px',
                height: '3px',
                backgroundColor: 'var(--color-forecast)',
                borderRadius: '2px',
                display: 'inline-block',
              }}
            />
            <span style={{ color: 'var(--color-forecast)', fontWeight: 600 }}>Forecast (MW)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span
              style={{
                width: '16px',
                height: '3px',
                backgroundColor: 'var(--color-actual)',
                borderRadius: '2px',
                display: 'inline-block',
              }}
            />
            <span style={{ color: 'var(--color-actual)', fontWeight: 600 }}>Actual Outturn (MW)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: 'var(--color-danger)',
                display: 'inline-block',
              }}
            />
            <span style={{ color: 'var(--text-muted)' }}>Incomplete / Missing</span>
          </div>
        </div>
      </div>

      {/* SVG Time-Series Plot */}
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
          {/* Background Grid & Y-Ticks */}
          {yTicks.map(({ val, y }, idx) => (
            <g key={idx}>
              <line
                x1={margin.left}
                y1={y}
                x2={margin.left + plotWidth}
                y2={y}
                stroke="var(--border-subtle)"
                strokeDasharray={idx === 0 ? undefined : '3 3'}
                strokeWidth={idx === 0 ? '1.5' : '1'}
                opacity={idx === 0 ? 0.8 : 0.4}
              />
              <text
                x={margin.left - 10}
                y={y + 4}
                textAnchor="end"
                fill="var(--text-muted)"
                fontSize="11"
                className="mono"
              >
                {val.toLocaleString()} MW
              </text>
            </g>
          ))}

          {/* Missing / Incomplete Indicators (vertical warning stripes) */}
          {records.map((r, i) => {
            if (r.status !== 'MATCHED') {
              const x = getX(i)
              const bandWidth = Math.max(2, plotWidth / records.length)
              return (
                <rect
                  key={`missing-${i}`}
                  x={x - bandWidth / 2}
                  y={margin.top}
                  width={bandWidth}
                  height={plotHeight}
                  fill="rgba(244, 63, 94, 0.15)"
                />
              )
            }
            return null
          })}

          {/* Forecast Path (Teal) */}
          {forecastSegments.map((d, sIdx) => (
            <path
              key={`fc-${sIdx}`}
              d={d}
              fill="none"
              stroke="var(--color-forecast)"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}

          {/* Actual Path (Amber) */}
          {actualSegments.map((d, sIdx) => (
            <path
              key={`act-${sIdx}`}
              d={d}
              fill="none"
              stroke="var(--color-actual)"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}

          {/* X-Axis Ticks & Labels */}
          {xTicks.map(({ index, record }) => {
            const x = getX(index)
            return (
              <g key={`xtick-${index}`}>
                <line
                  x1={x}
                  y1={margin.top + plotHeight}
                  x2={x}
                  y2={margin.top + plotHeight + 6}
                  stroke="var(--text-muted)"
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={margin.top + plotHeight + 20}
                  textAnchor="middle"
                  fill="var(--text-muted)"
                  fontSize="11"
                >
                  {formatXTime(record.delivery_start_time)}
                </text>
              </g>
            )
          })}

          {/* Interactive Hover Crosshair & Dots */}
          {hoveredRecord && (
            <g>
              {/* Vertical Guide Line */}
              <line
                x1={getX(hoverIndex)}
                y1={margin.top}
                x2={getX(hoverIndex)}
                y2={margin.top + plotHeight}
                stroke="#64748b"
                strokeDasharray="4 4"
                strokeWidth="1.2"
              />

              {/* Forecast Point Dot */}
              {hoveredRecord.forecast_generation !== null && (
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(hoveredRecord.forecast_generation)}
                  r="5"
                  fill="var(--color-forecast)"
                  stroke="#ffffff"
                  strokeWidth="2"
                />
              )}

              {/* Actual Point Dot */}
              {hoveredRecord.actual_generation !== null && (
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(hoveredRecord.actual_generation)}
                  r="5"
                  fill="var(--color-actual)"
                  stroke="#ffffff"
                  strokeWidth="2"
                />
              )}
            </g>
          )}
        </svg>

        {/* Hover Tooltip Box */}
        {hoveredRecord && (
          <div
            style={{
              position: 'absolute',
              top: '12px',
              left: `${Math.min(78, Math.max(12, (getX(hoverIndex) / svgWidth) * 100))}%`,
              transform: 'translateX(-50%)',
              backgroundColor: '#0f172a',
              border: '1px solid #334155',
              boxShadow: '0 8px 20px rgba(0,0,0,0.4)',
              borderRadius: '6px',
              padding: '0.65rem 0.85rem',
              pointerEvents: 'none',
              fontSize: '0.75rem',
              minWidth: '220px',
              zIndex: 10,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '1px solid #243249',
                paddingBottom: '0.35rem',
                marginBottom: '0.4rem',
              }}
            >
              <span className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {formatFullTimestamp(hoveredRecord.delivery_start_time)}
              </span>
              <span
                className={`badge ${
                  hoveredRecord.status === 'MATCHED'
                    ? 'badge-matched'
                    : 'badge-missing'
                }`}
              >
                {hoveredRecord.status}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.3rem 0.75rem', alignItems: 'center' }}>
              <span style={{ color: 'var(--color-forecast)', fontWeight: 600 }}>Forecast:</span>
              <span className="mono" style={{ textAlign: 'right', fontWeight: 600 }}>
                {hoveredRecord.forecast_generation !== null
                  ? `${hoveredRecord.forecast_generation.toLocaleString()} MW`
                  : 'N/A (Missing)'}
              </span>

              <span style={{ color: 'var(--color-actual)', fontWeight: 600 }}>Actual:</span>
              <span className="mono" style={{ textAlign: 'right', fontWeight: 600 }}>
                {hoveredRecord.actual_generation !== null
                  ? `${hoveredRecord.actual_generation.toLocaleString()} MW`
                  : 'N/A (Incomplete)'}
              </span>

              {hoveredRecord.error !== null && (
                <>
                  <span style={{ color: 'var(--text-muted)' }}>Signed Error:</span>
                  <span
                    className="mono"
                    style={{
                      textAlign: 'right',
                      fontWeight: 700,
                      color:
                        hoveredRecord.error > 0
                          ? 'var(--color-positive)'
                          : hoveredRecord.error < 0
                          ? 'var(--color-negative)'
                          : 'var(--text-primary)',
                    }}
                  >
                    {hoveredRecord.error > 0 ? `+${hoveredRecord.error}` : hoveredRecord.error} MW
                  </span>
                </>
              )}

              {hoveredRecord.forecast_publish_time && (
                <span
                  style={{
                    gridColumn: '1 / -1',
                    fontSize: '0.7rem',
                    color: 'var(--text-muted)',
                    borderTop: '1px solid #1e293b',
                    paddingTop: '0.25rem',
                    marginTop: '0.2rem',
                  }}
                >
                  Published: {formatFullTimestamp(hoveredRecord.forecast_publish_time)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
