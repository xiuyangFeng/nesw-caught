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

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: JSON_HEADERS,
  });

  if (!response.ok) {
    throw new HttpError(`Request failed for ${path}`, response.status);
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
    throw new HttpError(`Request failed for ${path}`, response.status);
  }

  return response.json() as Promise<T>;
}
