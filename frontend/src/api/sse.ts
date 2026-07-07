import type { StreamEnvelope } from '../types/api';

// 与 http.ts 相同来源：由 vite.config.ts 的 define 注入的 App Token
declare const __APP_TOKEN__: string;

function buildStreamUrl(): string {
  const base = '/api/stream/events';
  // 原生 EventSource 无法携带自定义请求头，App Token 只能通过 query 参数传递
  if (typeof __APP_TOKEN__ !== 'undefined' && __APP_TOKEN__) {
    return `${base}?token=${encodeURIComponent(__APP_TOKEN__)}`;
  }
  return base;
}

interface StreamHandlers {
  onOpen?: () => void;
  onEvent?: (event: StreamEnvelope) => void;
  onError?: () => void;
}

// Mock events are only bundled in dev builds: the dynamic import inside the
// DEV guard lets production builds tree-shake mock.ts entirely.
function createMockConnection(handlers: StreamHandlers) {
  let closed = false;
  handlers.onOpen?.();
  if (import.meta.env.DEV) {
    void import('./mock').then(({ mockStreamEvents }) => {
      if (closed) {
        return;
      }
      mockStreamEvents.forEach((event) => handlers.onEvent?.(event));
    });
  }
  return {
    close() {
      closed = true;
    },
  };
}

export function createStreamConnection(handlers: StreamHandlers) {
  if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
    return createMockConnection(handlers);
  }

  try {
    const source = new EventSource(buildStreamUrl());

    source.onopen = () => {
      handlers.onOpen?.();
    };

    source.onmessage = (message) => {
      try {
        const parsed = JSON.parse(message.data) as StreamEnvelope;
        handlers.onEvent?.(parsed);
      } catch {
        handlers.onError?.();
      }
    };

    source.onerror = () => {
      handlers.onError?.();
      source.close();
    };

    return {
      close() {
        source.close();
      },
    };
  } catch {
    return createMockConnection(handlers);
  }
}
