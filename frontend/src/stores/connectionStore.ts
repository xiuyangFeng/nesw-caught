import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { createStreamConnection } from '../api/sse';
import type { StreamEnvelope, StreamStatus } from '../types/api';
import { isStale } from '../utils/time';

type ConnectionState = 'idle' | 'connecting' | 'live' | 'degraded' | 'offline';

export const useConnectionStore = defineStore('connectionStore', () => {
  const state = ref<ConnectionState>('idle');
  const streamStatus = ref<StreamStatus | null>(null);
  const lastEventAt = ref<string | null>(null);
  const usingMock = ref(false);
  const streamError = ref<string | null>(null);
  let streamHandle: { close: () => void } | null = null;
  let reconnectTimer: any = null;
  let reconnectDelay = 2000;
  let lastHandleEvent: ((event: StreamEnvelope) => void) | null = null;

  // 后端 /api/stream/status 返回 last_published_at（最近一次事件发布时间），
  // 在本地还没收到任何 SSE 事件时作为陈旧度判断的兜底。
  const isConnectionStale = computed(() => isStale(lastEventAt.value ?? streamStatus.value?.last_published_at ?? null, 3));

  function applyStreamStatus(status: StreamStatus | null, degraded: boolean) {
    streamStatus.value = status;
    usingMock.value = degraded;
    if (state.value === 'idle') {
      state.value = degraded ? 'degraded' : 'connecting';
    }
  }

  function connect(handleEvent: (event: StreamEnvelope) => void) {
    lastHandleEvent = handleEvent;
    state.value = 'connecting';
    streamHandle?.close();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    streamHandle = createStreamConnection({
      onOpen: () => {
        state.value = usingMock.value ? 'degraded' : 'live';
        streamError.value = null;
        reconnectDelay = 2000; // 重置延迟
      },
      onEvent: (event) => {
        lastEventAt.value = event.occurred_at;
        handleEvent(event);
      },
      onError: () => {
        state.value = usingMock.value ? 'degraded' : 'offline';
        streamError.value = 'SSE disconnected';
        
        // 自动重连逻辑，使用指数退避机制。
        // 此处 state 刚被置为 degraded/offline，不可能是 idle；
        // disconnect() 会清掉定时器，所以无需再判断 idle。
        if (!reconnectTimer) {
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            if (state.value === 'offline' && lastHandleEvent) {
              const currentDelay = reconnectDelay;
              reconnectDelay = Math.min(reconnectDelay * 2, 30000);
              connect(lastHandleEvent);
            }
          }, reconnectDelay);
        }
      },
    });
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    lastHandleEvent = null;
    reconnectDelay = 2000;
    streamHandle?.close();
    streamHandle = null;
    state.value = 'idle';
  }

  return {
    state,
    streamStatus,
    lastEventAt,
    usingMock,
    streamError,
    isConnectionStale,
    applyStreamStatus,
    connect,
    disconnect,
  };
});
