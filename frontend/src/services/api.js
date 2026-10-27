/**
 * API client service for UK Wind Intelligence backend.
 *
 * Configurable via VITE_API_BASE_URL (defaults to http://localhost:8000).
 * Handles timeouts, network cancellations, and descriptive HTTP error extraction.
 */

const RAW_BASE_URL =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : 'http://localhost:8000'

const BASE_URL = RAW_BASE_URL.replace(/\/+$/, '')

/**
 * Fetch forecast accuracy analysis from GET /api/v1/wind/analysis.
 *
 * @param {Object} params
 * @param {string} params.startDate - YYYY-MM-DD
 * @param {string} params.endDate - YYYY-MM-DD
 * @param {string} [params.policy='day_ahead'] - 'day_ahead' | 'rolling' | 'latest_before_delivery'
 * @param {number} [params.leadTimeHours] - Positive float (required for rolling policy)
 * @param {string} [params.dayAheadCutoffTime='12:00'] - HH:MM UTC
 * @param {AbortSignal} [params.signal] - Optional AbortSignal for request cancellation
 * @returns {Promise<Object>} AnalysisResponse
 */
export async function fetchAnalysis({
  startDate,
  endDate,
  policy = 'day_ahead',
  leadTimeHours,
  dayAheadCutoffTime = '12:00',
  signal,
}) {
  const queryParams = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
    policy,
  })

  if (policy === 'rolling' && leadTimeHours !== undefined && leadTimeHours !== null) {
    queryParams.set('lead_time_hours', String(leadTimeHours))
  }

  if (policy === 'day_ahead' && dayAheadCutoffTime) {
    queryParams.set('day_ahead_cutoff_time', dayAheadCutoffTime)
  }

  const url = `${BASE_URL}/api/v1/wind/analysis?${queryParams.toString()}`

  let response
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') {
      throw err // Request intentionally cancelled
    }
    throw new Error(
      `Network error: Unable to connect to backend service at ${BASE_URL}. Ensure the FastAPI server is running.`
    )
  }

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`
    try {
      const errorJson = await response.json()
      if (errorJson && errorJson.detail) {
        errorDetail = errorJson.detail
      }
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

/**
 * Check backend health.
 */
export async function fetchHealth(signal) {
  const url = `${BASE_URL}/health`
  const response = await fetch(url, {
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }
  return response.json()
}
