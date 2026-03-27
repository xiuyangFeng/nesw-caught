const JSON_HEADERS = {
  Accept: 'application/json',
  'Content-Type': 'application/json',
};

export class HttpError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
  }
}

async function toHttpError(response: Response, path: string): Promise<HttpError> {
  let message = `Request failed for ${path}`;

  try {
    const payload = await response.json() as { detail?: string };
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      message = payload.detail;
    }
  } catch {
    // Fall back to the generic message when the backend does not return JSON.
  }

  return new HttpError(message, response.status);
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: JSON_HEADERS,
  });

  if (!response.ok) {
    throw await toHttpError(response, path);
  }

  return response.json() as Promise<T>;
}

export async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await toHttpError(response, path);
  }

  return response.json() as Promise<T>;
}

export async function patchJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await toHttpError(response, path);
  }

  return response.json() as Promise<T>;
}

export async function deleteJson(path: string): Promise<void> {
  const response = await fetch(path, {
    method: 'DELETE',
    headers: JSON_HEADERS,
  });

  if (!response.ok) {
    throw await toHttpError(response, path);
  }
}
