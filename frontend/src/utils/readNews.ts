import { reactive } from 'vue';

const STORAGE_KEY = 'news-caught:read-news-ids';
const MAX_TRACKED = 2000;

// Node22+ 实验性全局 storage 可能抛错,统一防御式获取(与 watchlistChartStore 同模式)
const safeStorage = (() => {
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
})();

function loadInitial(): number[] {
  try {
    const raw = safeStorage?.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value): value is number => typeof value === 'number') : [];
  } catch {
    return [];
  }
}

// Set 迭代按插入顺序,天然可当 FIFO 用:超限时淘汰最早标记的 id
const readIds = reactive(new Set<number>(loadInitial()));

function persist(): void {
  try {
    safeStorage?.setItem(STORAGE_KEY, JSON.stringify([...readIds]));
  } catch {
    // storage 不可用时已读功能静默失效
  }
}

export function isNewsRead(id: number): boolean {
  return readIds.has(id);
}

export function markNewsRead(id: number): void {
  if (readIds.has(id)) {
    return;
  }
  readIds.add(id);
  while (readIds.size > MAX_TRACKED) {
    const oldest = readIds.values().next().value;
    if (oldest === undefined) {
      break;
    }
    readIds.delete(oldest);
  }
  persist();
}

export function useReadNewsIds(): ReadonlySet<number> {
  return readIds;
}

export function resetReadNewsForTest(): void {
  readIds.clear();
  persist();
}
