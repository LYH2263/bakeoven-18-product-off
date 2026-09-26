export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const body = JSON.parse(text);
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // 非 JSON 响应，保留原始文本
    }
    throw new Error(message || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
