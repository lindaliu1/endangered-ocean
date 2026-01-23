export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Build a full API URL for the FastAPI service.
 *
 * Usage:
 *   apiUrl("/api/species")
 *   apiUrl("/api/species", { status: "Endangered" })
 */
export function apiUrl(
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>
): string {
  const base = API_BASE_URL.replace(/\/+$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;

  const url = new URL(`${base}${p}`);

  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === null || v === undefined || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }

  return url.toString();
}

/**
 * Small wrapper around fetch() that:
 * - prefixes the FastAPI base URL
 * - sets JSON headers by default
 */
export async function apiFetch(
  path: string,
  options: RequestInit = {},
  query?: Record<string, string | number | boolean | null | undefined>
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");

  // Only set Content-Type automatically when a body is present and caller hasn't set it.
  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(apiUrl(path, query), {
    ...options,
    headers,
  });
}
