import type { StreamEnvelope } from '../types/api';
import { mockStreamEvents } from './mock';

interface StreamHandlers {
  onOpen?: () => void;
  onEvent?: (event: StreamEnvelope) => void;
  onError?: () => void;
}

export function createStreamConnection(handlers: StreamHandlers) {
  if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
    handlers.onOpen?.();
    mockStreamEvents.forEach((event) => handlers.onEvent?.(event));
    return {
      close() {
        return undefined;
      },
    };
  }

  try {
    const source = new EventSource('/api/stream/events');

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
    handlers.onOpen?.();
    mockStreamEvents.forEach((event) => handlers.onEvent?.(event));
    return {
      close() {
        return undefined;
      },
    };
  }
}
