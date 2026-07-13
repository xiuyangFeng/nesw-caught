// Vitest 全局初始化：为「原生 Web Storage 会抛错」的运行环境提供内存兜底。
//
// 背景：Node 22+ 引入了实验性的全局 localStorage/sessionStorage，未配
// `--localstorage-file` 时**任何访问都会抛 SecurityError**（连 `typeof localStorage`
// 都会触发抛错的 getter）。当测试真实挂载带 Pinia 的应用时，Pinia 的 devtools
// 会在模块求值阶段读取该全局，从而在这类环境（如本机 Node 25）下直接崩溃。
//
// 该 setup 在 worker 全局作用域内、任何测试模块/依赖被 import 之前运行，因此能在
// devtools 读取前把 storage 换成可用的内存实现。它是**条件式**的：仅当原生访问
// 抛错/不可用时才替换；在 jsdom 原生 storage 正常的环境（如 CI 的 Node 20）里是
// 无副作用的 no-op，不改变任何既有测试行为。

function createMemoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    key: (index: number) => Array.from(map.keys())[index] ?? null,
    getItem: (key: string) => (map.has(key) ? (map.get(key) as string) : null),
    setItem: (key: string, value: string) => {
      map.set(key, String(value));
    },
    removeItem: (key: string) => {
      map.delete(key);
    },
    clear: () => map.clear(),
  } as Storage;
}

function ensureUsableStorage(key: 'localStorage' | 'sessionStorage'): void {
  let usable = false;
  try {
    const existing = (globalThis as Record<string, unknown>)[key] as Storage | undefined;
    if (existing) {
      existing.getItem('__vitest_storage_probe__');
      usable = true;
    }
  } catch {
    usable = false;
  }
  if (usable) {
    return;
  }
  Object.defineProperty(globalThis, key, {
    value: createMemoryStorage(),
    configurable: true,
    writable: true,
  });
}

ensureUsableStorage('localStorage');
ensureUsableStorage('sessionStorage');
