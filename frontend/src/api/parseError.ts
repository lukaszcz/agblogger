/**
 * Parse the `detail` field from a JSON error response body.
 *
 * Handles multiple backend response formats:
 * - `{ detail: "string message" }` → returns the string
 * - `{ detail: [{ field?, message?, msg? }] }` → returns formatted field: message pairs
 * - Anything else → returns the provided fallback
 */
export async function parseErrorDetail(
  response: { text: () => Promise<string> },
  fallback: string,
): Promise<string> {
  try {
    const text = await response.text()
    const parsed: unknown = JSON.parse(text)
    if (typeof parsed !== 'object' || parsed === null || !('detail' in parsed)) {
      return fallback
    }
    const detail = (parsed as { detail: unknown }).detail

    if (typeof detail === 'string') {
      return detail.length > 0 ? detail : fallback
    }

    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((d: unknown) => {
          const item = d as { field?: string; message?: string; msg?: string }
          const msg = item.message ?? item.msg ?? 'Unknown error'
          if (item.field != null && item.field.length > 0) {
            const label = item.field.charAt(0).toUpperCase() + item.field.slice(1)
            return `${label}: ${msg}`
          }
          return msg
        })
        .join(', ')
    }

    return fallback
  } catch {
    return fallback
  }
}
