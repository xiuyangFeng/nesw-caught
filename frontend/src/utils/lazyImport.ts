// Recovery helpers for lazily-loaded route views.
//
// The app code-splits every route via `() => import('../views/X.vue')`. When a
// chunk cannot be fetched — a stale content hash after a redeploy, a transient
// Vite dev-server 504 while it re-optimizes deps, an offline blip, or an import
// that simply hangs — vue-router cannot render the target view. With no
// handling, the user is left on a frozen half-navigated page and has to refresh
// manually. These helpers detect that failure mode and recover automatically.

const DYNAMIC_IMPORT_ERROR_PATTERNS = [
  'failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'importing a module script failed',
  'failed to load module script',
  'unable to preload css',
  'dynamic import timed out',
];

export class DynamicImportTimeoutError extends Error {
  constructor(message = 'dynamic import timed out') {
    super(message);
    this.name = 'DynamicImportTimeoutError';
  }
}

export function isDynamicImportError(error: unknown): boolean {
  if (error instanceof DynamicImportTimeoutError) {
    return true;
  }
  const message = (
    error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  ).toLowerCase();
  if (!message) {
    return false;
  }
  return DYNAMIC_IMPORT_ERROR_PATTERNS.some((pattern) => message.includes(pattern));
}

const RELOAD_GUARD_KEY = 'nc:chunk-reload-at';
const RELOAD_MIN_INTERVAL_MS = 10_000;

// Reload once to recover from a chunk-load failure, guarded through
// sessionStorage so a genuinely broken build cannot trap the user in an
// infinite reload loop: we refuse to auto-reload again within a short window.
// Returns true if a reload was actually triggered.
export function recoverFromChunkError(
  reload: () => void = () => window.location.reload(),
  now: () => number = () => Date.now(),
  storage: Pick<Storage, 'getItem' | 'setItem'> | null = safeSessionStorage(),
): boolean {
  const current = now();
  if (storage) {
    const last = Number(storage.getItem(RELOAD_GUARD_KEY) ?? '0');
    if (Number.isFinite(last) && last > 0 && current - last < RELOAD_MIN_INTERVAL_MS) {
      return false;
    }
    try {
      storage.setItem(RELOAD_GUARD_KEY, String(current));
    } catch {
      // storage unavailable (private mode / quota) — still attempt one reload
    }
  }
  reload();
  return true;
}

function safeSessionStorage(): Pick<Storage, 'getItem' | 'setItem'> | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

const DEFAULT_IMPORT_TIMEOUT_MS = 12_000;

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  if (timeoutMs <= 0) {
    return promise;
  }
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new DynamicImportTimeoutError()), timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

interface LazyViewOptions {
  timeoutMs?: number;
  onGiveUp?: () => void;
}

// Wrap a route component loader with a bounded timeout and one silent retry.
// A transient dev-server 504 or flaky network usually succeeds on retry; only
// if both attempts fail with a chunk-load/timeout error do we give up and
// trigger a controlled reload. Genuine module errors (syntax/runtime in the
// chunk) are surfaced unchanged so they are not masked as network flakes.
export function lazyView<T>(
  loader: () => Promise<T>,
  options: LazyViewOptions = {},
): () => Promise<T> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_IMPORT_TIMEOUT_MS;
  const onGiveUp = options.onGiveUp ?? (() => recoverFromChunkError());

  return async () => {
    try {
      return await withTimeout(loader(), timeoutMs);
    } catch (firstError) {
      if (!isDynamicImportError(firstError)) {
        throw firstError;
      }
      try {
        return await withTimeout(loader(), timeoutMs);
      } catch (secondError) {
        if (isDynamicImportError(secondError)) {
          onGiveUp();
        }
        throw secondError;
      }
    }
  };
}
