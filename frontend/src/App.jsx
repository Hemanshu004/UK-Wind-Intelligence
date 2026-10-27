import React, { useState, useEffect } from 'react'
import { fetchAnalysis } from './services/api.js'
import { Header } from './components/Header.jsx'
import { Controls } from './components/Controls.jsx'
import { PolicyBanner } from './components/PolicyBanner.jsx'
import { KpiCards } from './components/KpiCards.jsx'
import { TimeSeriesChart } from './components/TimeSeriesChart.jsx'
import { ErrorChart } from './components/ErrorChart.jsx'
import { DataTable } from './components/DataTable.jsx'
import { DataQualitySummary } from './components/DataQualitySummary.jsx'

export default function App() {
  const [filters, setFilters] = useState({
    startDate: '2026-01-01',
    endDate: '2026-01-31',
    policy: 'day_ahead',
    leadTimeHours: 24,
    dayAheadCutoffTime: '12:00',
  })

  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  // Fetch data whenever filters or reloadKey changes
  useEffect(() => {
    let ignore = false
    const controller = new AbortController()

    fetchAnalysis({
      startDate: filters.startDate,
      endDate: filters.endDate,
      policy: filters.policy,
      leadTimeHours: filters.leadTimeHours,
      dayAheadCutoffTime: filters.dayAheadCutoffTime,
      signal: controller.signal,
    })
      .then((result) => {
        if (!ignore) {
          setData(result)
          setErrorMessage('')
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!ignore && err.name !== 'AbortError') {
          setErrorMessage(err.message || 'An unexpected error occurred while fetching analysis data.')
          setIsLoading(false)
        }
      })

    return () => {
      ignore = true
      controller.abort()
    }
  }, [filters, reloadKey])

  const handleApplyFilters = (newFilters) => {
    setIsLoading(true)
    setFilters(newFilters)
  }

  const handleRetry = () => {
    setIsLoading(true)
    setReloadKey((k) => k + 1)
  }

  return (
    <main style={{ width: '100%' }}>
      {/* 1. Header */}
      <Header
        startDate={filters.startDate}
        endDate={filters.endDate}
        recordCount={data?.records?.length ?? 0}
      />

      {/* 2. Analysis Controls */}
      <Controls
        filters={filters}
        onApply={handleApplyFilters}
        isLoading={isLoading}
      />

      {/* 3. Error Alert with Retry */}
      {errorMessage && (
        <div
          className="card"
          style={{
            backgroundColor: 'var(--color-danger-bg)',
            borderColor: 'rgba(244, 63, 94, 0.4)',
            marginBottom: '1.25rem',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div>
            <div style={{ fontWeight: 600, color: 'var(--color-danger)', marginBottom: '0.25rem' }}>
              Failed to Load Wind Forecast Analysis
            </div>
            <div style={{ color: 'var(--text-primary)', fontSize: '0.875rem' }}>
              {errorMessage}
            </div>
          </div>

          <button
            id="retry-btn"
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handleRetry}
          >
            Retry Request
          </button>
        </div>
      )}

      {/* 4. Loading Overlay Indicator */}
      {isLoading && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.75rem',
            padding: '1rem',
            borderRadius: '6px',
            backgroundColor: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '1.25rem',
            fontSize: '0.875rem',
            color: 'var(--color-info)',
          }}
        >
          <span
            style={{
              display: 'inline-block',
              width: '14px',
              height: '14px',
              border: '2px solid var(--color-info)',
              borderTopColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
            }}
          />
          Querying Elexon BMRS Insights API and executing alignment engine...
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {/* 5. Main Dashboard Results */}
      {data && (
        <>
          {/* Active Policy Notice */}
          <PolicyBanner
            policy={data.policy}
            cutoffRule={data.cutoff_rule}
            leadTimeHours={data.lead_time_hours}
          />

          {/* Key Performance Indicators */}
          <KpiCards
            metrics={data.metrics}
            matchedCount={data.matched_interval_count}
            expectedCount={data.expected_interval_count}
            coveragePercentage={data.coverage_percentage}
          />

          {/* Primary Time-Series Chart (Forecast vs Actual) */}
          <TimeSeriesChart records={data.records} />

          {/* Secondary Error Chart (Signed Bias) */}
          <ErrorChart records={data.records} />

          {/* Detailed Interval Table & CSV Export */}
          <DataTable
            records={data.records}
            startDate={data.start_date}
            endDate={data.end_date}
            policy={data.policy}
          />

          {/* Data Quality & Methodology Audit */}
          <DataQualitySummary
            expectedCount={data.expected_interval_count}
            matchedCount={data.matched_interval_count}
            missingForecastCount={data.missing_forecast_count}
            missingActualCount={data.missing_actual_count}
            coveragePercentage={data.coverage_percentage}
            dataNotes={data.data_notes}
          />
        </>
      )}

      {/* Dashboard Footer */}
      <footer
        style={{
          marginTop: '2rem',
          paddingTop: '1.25rem',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.75rem',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
        }}
      >
        <div>
          UK Wind Intelligence — Built with React + Vite &amp; FastAPI. Data sourced from official Elexon BMRS.
        </div>
        <div>
          National GB Wind Generation Outturn (FUELHH) &amp; Day-Ahead Forecasts (WINDFOR)
        </div>
      </footer>
    </main>
  )
}
