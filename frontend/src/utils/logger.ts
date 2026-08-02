// 前端分级日志封装。
//
// - dev（`import.meta.env.DEV`）：所有级别都原样打到 console，保留调用方对
//   console.debug/info/warn/error 的既有期望（堆栈、格式化参数等）。
// - prod：只有 warn/error 落 console；error 额外限流批量上报到后端，方便
//   在没有浏览器访问权限的情况下排查线上问题；页面卸载时使用带鉴权头的
//   keepalive fetch 尽力发送剩余队列。
//
// 上报传输层刻意使用独立的原生 fetch，不 import `../api/http` 或
// `../api/client`：那两个模块将来可能反过来调用 logger 记录请求失败，
// 若 logger 又依赖它们就会形成循环依赖。App Token 的取值方式与
// `api/http.ts` 保持一致（同一个 `__APP_TOKEN__` 全局常量、同一个请求头
// 名），但在这里独立复刻一份，而不是复用其 fetch monkey-patch。

declare const __APP_TOKEN__: string | undefined;

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogContext {
  [key: string]: unknown;
}

interface LogEntry {
  level: 'error';
  message: string;
  stack?: string;
  url?: string;
  ts: string;
  context?: LogContext;
}

const REPORT_ENDPOINT = '/api/logs/frontend';
const FLUSH_INTERVAL_MS = 5_000;
const MAX_BATCH_SIZE = 10;
const MAX_ENTRIES_PER_MINUTE = 30;
const RATE_LIMIT_WINDOW_MS = 60_000;

const isDev = Boolean(import.meta.env.DEV);

let queue: LogEntry[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let sentThisWindow = 0;
let windowResetAt = 0;

function getAppToken(): string | undefined {
  try {
    return typeof __APP_TOKEN__ !== 'undefined' && __APP_TOKEN__ ? __APP_TOKEN__ : undefined;
  } catch {
    return undefined;
  }
}

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getAppToken();
  if (token) {
    headers['X-App-Token'] = token;
  }
  return headers;
}

function currentUrl(): string | undefined {
  try {
    return typeof window !== 'undefined' ? window.location.href : undefined;
  } catch {
    return undefined;
  }
}

// 每分钟最多允许上报 30 条，超出的直接静默丢弃（不入队、不重试）。
function canSendMore(): boolean {
  const now = Date.now();
  if (now >= windowResetAt) {
    windowResetAt = now + RATE_LIMIT_WINDOW_MS;
    sentThisWindow = 0;
  }
  return sentThisWindow < MAX_ENTRIES_PER_MINUTE;
}

function clearFlushTimer() {
  if (flushTimer !== null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
}

function scheduleFlush() {
  if (flushTimer !== null) {
    return;
  }
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flush();
  }, FLUSH_INTERVAL_MS);
}

// 上报失败（网络错误、非 2xx、超时……）一律静默吞掉：这是日志管线自身，
// 绝不能抛异常打断调用方，也绝不能反过来调用 logger.error 记录自己的失败
// 造成递归上报。
async function flush(): Promise<void> {
  if (queue.length === 0) {
    return;
  }
  const batch = queue.splice(0, MAX_BATCH_SIZE);
  try {
    const response = await fetch(REPORT_ENDPOINT, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({ entries: batch }),
    });
    if (!response.ok) {
      // 静默丢弃，不重新入队（避免失败条目无限堆积/重试风暴）。
      return;
    }
  } catch {
    return;
  } finally {
    if (queue.length > 0) {
      scheduleFlush();
    }
  }
}

// pagehide 时使用 keepalive fetch 尽力发送剩余队列。sendBeacon 不能携带
// X-App-Token，会被生产鉴权拒绝，因此这里继续复用与常规 flush 相同的请求头。
function flushOnPageHide() {
  if (queue.length === 0) {
    return;
  }
  clearFlushTimer();
  const batch = queue.splice(0, queue.length);
  try {
    void fetch(REPORT_ENDPOINT, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({ entries: batch }),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // 静默放弃。
  }
}

function enqueueReport(entry: LogEntry) {
  if (!canSendMore()) {
    return;
  }
  sentThisWindow += 1;
  queue.push(entry);
  if (queue.length >= MAX_BATCH_SIZE) {
    clearFlushTimer();
    void flush();
  } else {
    scheduleFlush();
  }
}

function extractError(err: unknown): { stack?: string; extra?: string } {
  if (err instanceof Error) {
    return { stack: err.stack, extra: err.message };
  }
  if (err === undefined) {
    return {};
  }
  return { extra: typeof err === 'string' ? err : safeStringify(err) };
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function reportError(message: string, err?: unknown, context?: LogContext) {
  if (isDev) {
    // dev 环境默认不上报，只打 console（见 error()）。
    return;
  }
  const { stack, extra } = extractError(err);
  const fullMessage = extra && extra.trim() && extra !== message ? `${message}: ${extra}` : message;
  enqueueReport({
    level: 'error',
    message: fullMessage.slice(0, 2000),
    stack,
    url: currentUrl(),
    ts: new Date().toISOString(),
    context,
  });
}

function debug(message: unknown, ...args: unknown[]) {
  if (isDev) {
    // eslint-disable-next-line no-console
    console.debug(message, ...args);
  }
}

function info(message: unknown, ...args: unknown[]) {
  if (isDev) {
    // eslint-disable-next-line no-console
    console.info(message, ...args);
  }
}

function warn(message: unknown, ...args: unknown[]) {
  // eslint-disable-next-line no-console
  console.warn(message, ...args);
}

function error(message: unknown, err?: unknown, context?: LogContext) {
  const consoleArgs: unknown[] = [message];
  if (err !== undefined) {
    consoleArgs.push(err);
  }
  if (context !== undefined) {
    consoleArgs.push(context);
  }
  // eslint-disable-next-line no-console
  console.error(...consoleArgs);
  reportError(typeof message === 'string' ? message : safeStringify(message), err, context);
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', flushOnPageHide);
}

export const logger = {
  debug,
  info,
  warn,
  error,
};

export default logger;
