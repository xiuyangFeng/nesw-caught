import { describe, expect, it, vi } from 'vitest';

import {
  DynamicImportTimeoutError,
  isDynamicImportError,
  lazyView,
  recoverFromChunkError,
} from './lazyImport';

describe('isDynamicImportError', () => {
  it('matches the known chunk-load failure messages', () => {
    for (const message of [
      'Failed to fetch dynamically imported module: http://x/assets/View.js',
      'error loading dynamically imported module',
      'Importing a module script failed.',
      'Unable to preload CSS for /assets/View.css',
    ]) {
      expect(isDynamicImportError(new Error(message))).toBe(true);
      expect(isDynamicImportError(message)).toBe(true);
    }
  });

  it('treats an import timeout as a dynamic import error', () => {
    expect(isDynamicImportError(new DynamicImportTimeoutError())).toBe(true);
  });

  it('does not match unrelated errors', () => {
    expect(isDynamicImportError(new Error('Cannot read properties of undefined'))).toBe(false);
    expect(isDynamicImportError(null)).toBe(false);
    expect(isDynamicImportError(undefined)).toBe(false);
  });
});

describe('recoverFromChunkError', () => {
  function makeStorage(initial: Record<string, string> = {}) {
    const map = new Map(Object.entries(initial));
    return {
      getItem: (k: string) => map.get(k) ?? null,
      setItem: (k: string, v: string) => void map.set(k, v),
    };
  }

  it('reloads the first time and records the timestamp', () => {
    const reload = vi.fn();
    const storage = makeStorage();
    const did = recoverFromChunkError(reload, () => 1_000_000, storage);
    expect(did).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(storage.getItem('nc:chunk-reload-at')).toBe('1000000');
  });

  it('refuses to reload again within the guard window (no infinite loop)', () => {
    const reload = vi.fn();
    const storage = makeStorage({ 'nc:chunk-reload-at': '1000000' });
    const did = recoverFromChunkError(reload, () => 1_000_500, storage);
    expect(did).toBe(false);
    expect(reload).not.toHaveBeenCalled();
  });

  it('reloads again once the guard window has passed', () => {
    const reload = vi.fn();
    const storage = makeStorage({ 'nc:chunk-reload-at': '1000000' });
    const did = recoverFromChunkError(reload, () => 1_000_000 + 11_000, storage);
    expect(did).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
  });
});

describe('lazyView', () => {
  it('passes the loaded module through on success', async () => {
    const mod = { default: 'component' };
    const load = lazyView(async () => mod);
    await expect(load()).resolves.toBe(mod);
  });

  it('retries once on a chunk-load error and then resolves', async () => {
    const mod = { default: 'component' };
    let calls = 0;
    const onGiveUp = vi.fn();
    const load = lazyView(
      async () => {
        calls += 1;
        if (calls === 1) {
          throw new Error('Failed to fetch dynamically imported module');
        }
        return mod;
      },
      { onGiveUp },
    );
    await expect(load()).resolves.toBe(mod);
    expect(calls).toBe(2);
    expect(onGiveUp).not.toHaveBeenCalled();
  });

  it('gives up with recovery when both attempts fail with a chunk error', async () => {
    const onGiveUp = vi.fn();
    const load = lazyView(
      async () => {
        throw new Error('Failed to fetch dynamically imported module');
      },
      { onGiveUp },
    );
    await expect(load()).rejects.toThrow(/dynamically imported/);
    expect(onGiveUp).toHaveBeenCalledTimes(1);
  });

  it('surfaces genuine module errors without retry or recovery', async () => {
    let calls = 0;
    const onGiveUp = vi.fn();
    const load = lazyView(
      async () => {
        calls += 1;
        throw new Error('ReferenceError: foo is not defined');
      },
      { onGiveUp },
    );
    await expect(load()).rejects.toThrow(/ReferenceError/);
    expect(calls).toBe(1);
    expect(onGiveUp).not.toHaveBeenCalled();
  });
});
