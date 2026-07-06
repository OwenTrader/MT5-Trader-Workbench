/**
 * Frontend API Utility for communicating with the local FastAPI backend.
 * Features built-in timeout, error parsing, and centralizes the base URL.
 */

export const API_BASE_URL = 'http://127.0.0.1:8765';

interface ApiFetchOptions extends RequestInit {
  timeout?: number;
}

/**
 * Enhanced fetch wrapper with timeout support.
 *
 * @param path The path or full URL to fetch. If it's a relative path, it will be prepended with API_BASE_URL.
 * @param options Fetch options, optionally including a timeout in milliseconds.
 * @returns A Promise resolving to the Response object.
 */
export async function apiFetch(path: string, options: ApiFetchOptions = {}): Promise<Response> {
  const { timeout = 10000, ...fetchOptions } = options;
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;

  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return response;
  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.error(`Request to ${url} timed out after ${timeout}ms`);
      throw new Error(`Request timed out (>${timeout}ms)`);
    }
    console.error(`API Fetch Error [${url}]:`, error);
    throw error;
  } finally {
    clearTimeout(id);
  }
}
