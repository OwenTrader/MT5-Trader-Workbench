import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

import {
  createEmptyPythonQuantOverview,
  getPythonQuantErrorMessage,
  parsePythonQuantBackfillResult,
  parsePythonQuantOverview,
  PYTHON_QUANT_API_BASE,
  type PythonQuantBackfillPayload,
  type PythonQuantJobPayload,
  type PythonQuantJobUpdatePayload,
  type PythonQuantOverview,
} from '@/lib/python-quant'

interface PythonQuantStore {
  overview: PythonQuantOverview
  isLoading: boolean
  error: string | null
  fetchOverview: () => Promise<void>
  createJob: (payload: PythonQuantJobPayload) => Promise<boolean>
  updateJob: (jobId: string, payload: PythonQuantJobUpdatePayload) => Promise<boolean>
  startJob: (jobId: string) => Promise<boolean>
  stopJob: (jobId: string) => Promise<boolean>
  deleteJob: (jobId: string) => Promise<boolean>
  backfillData: (payload: PythonQuantBackfillPayload) => Promise<number | null>
}

async function loadOverview(): Promise<PythonQuantOverview> {
  const response = await apiFetch(`${PYTHON_QUANT_API_BASE}/overview`)
  if (!response.ok) {
    throw new Error(await getPythonQuantErrorMessage(response, 'Failed to fetch Python Quant overview'))
  }

  return parsePythonQuantOverview(await response.json())
}

export const usePythonQuantStore = create<PythonQuantStore>((set) => {
  const fail = (error: unknown) => {
    set({
      error: error instanceof Error ? error.message : String(error),
      isLoading: false,
    })
  }

  const refreshOverview = async () => {
    const overview = await loadOverview()
    set({ overview, isLoading: false, error: null })
  }

  const runMutation = async (request: () => Promise<Response>, fallback: string): Promise<boolean> => {
    set({ isLoading: true, error: null })
    try {
      const response = await request()
      if (!response.ok) {
        throw new Error(await getPythonQuantErrorMessage(response, fallback))
      }
      await refreshOverview()
      return true
    } catch (error) {
      fail(error)
      return false
    }
  }

  return {
    overview: createEmptyPythonQuantOverview(),
    isLoading: false,
    error: null,
    fetchOverview: async () => {
      set({ isLoading: true, error: null })
      try {
        await refreshOverview()
      } catch (error) {
        fail(error)
      }
    },
    createJob: async (payload) => runMutation(
      () => apiFetch(`${PYTHON_QUANT_API_BASE}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
      'Failed to create Python Quant job',
    ),
    updateJob: async (jobId, payload) => runMutation(
      () => apiFetch(`${PYTHON_QUANT_API_BASE}/jobs/${jobId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
      'Failed to update Python Quant job',
    ),
    startJob: async (jobId) => runMutation(
      () => apiFetch(`${PYTHON_QUANT_API_BASE}/jobs/${jobId}/start`, {
        method: 'POST',
      }),
      'Failed to start Python Quant job',
    ),
    stopJob: async (jobId) => runMutation(
      () => apiFetch(`${PYTHON_QUANT_API_BASE}/jobs/${jobId}/stop`, {
        method: 'POST',
      }),
      'Failed to stop Python Quant job',
    ),
    deleteJob: async (jobId) => runMutation(
      () => apiFetch(`${PYTHON_QUANT_API_BASE}/jobs/${jobId}`, {
        method: 'DELETE',
      }),
      'Failed to delete Python Quant job',
    ),
    backfillData: async (payload) => {
      set({ isLoading: true, error: null })
      try {
        const response = await apiFetch(`${PYTHON_QUANT_API_BASE}/data/backfill`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        if (!response.ok) {
          throw new Error(await getPythonQuantErrorMessage(response, 'Failed to backfill Python Quant data'))
        }

        const insertedRows = parsePythonQuantBackfillResult(await response.json())
        await refreshOverview()
        return insertedRows
      } catch (error) {
        fail(error)
        return null
      }
    },
  }
})
