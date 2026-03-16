import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { apiClient } from '../api/client';
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

  const isConnectionStale = computed(() => isStale(lastEventAt.value ?? streamStatus.value?.last_event_at ?? null, 3));

  async function loadStreamStatus() {
    const response = await apiClient.getStreamStatus();
    streamStatus.value = response.data;
    usingMock.value = response.degraded;
    if (state.value === 'idle') {
      state.value = response.degraded ? 'degraded' : 'connecting';
    }
  }

  function connect(handleEvent: (event: StreamEnvelope) => void) {
    state.value = 'connecting';
    streamHandle?.close();
    streamHandle = createStreamConnection({
      onOpen: () => {
        state.value = usingMock.value ? 'degraded' : 'live';
        streamError.value = null;
      },
      onEvent: (event) => {
        lastEventAt.value = event.occurred_at;
        handleEvent(event);
      },
      onError: () => {
        state.value = usingMock.value ? 'degraded' : 'offline';
        streamError.value = 'SSE disconnected';
      },
    });
  }

  function disconnect() {
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
    loadStreamStatus,
    connect,
    disconnect,
  };
});
