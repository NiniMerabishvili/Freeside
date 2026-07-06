/** Fetch wrapper that aborts hung requests instead of blocking the UI for ~10s. */
export function createFetchWithTimeout(timeoutMs: number): typeof fetch {
  return (input, init) => {
    const controller = new AbortController()
    
    // Link with parent signal if it exists to propagate cancellations
    if (init?.signal) {
      if (init.signal.aborted) {
        controller.abort(init.signal.reason)
      } else {
        const onAbort = () => controller.abort(init.signal?.reason)
        init.signal.addEventListener('abort', onAbort)
      }
    }

    const id = setTimeout(() => {
      controller.abort(new DOMException(`Request timed out after ${timeoutMs}ms`, 'AbortError'))
    }, timeoutMs)

    return fetch(input, { ...init, signal: controller.signal }).finally(() => {
      clearTimeout(id)
    })
  }
}

export function isNetworkError(error: unknown): boolean {
  if (error instanceof TypeError && error.message === 'Failed to fetch') return true
  if (error instanceof DOMException && error.name === 'AbortError') return true
  return false
}

