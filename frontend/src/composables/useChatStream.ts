import { ref } from 'vue';

import { useToastStore } from '../stores/toastStore';
import type { ChatMessage, ChatSession } from './useChatSessions';

export interface UseChatStreamOptions {
  /** 当前活跃会话（消息会追加到该会话）。 */
  getSession: () => ChatSession | null;
  /** 本次请求使用的模型配置 id。 */
  getConfigId: () => number | null;
  /** 会话内容变更后触发持久化。 */
  persist: () => void;
}

/**
 * 聊天流式消息 composable：负责调用 /api/llm/chat（SSE 流），
 * 打字机式渐进渲染、故障切换提示与中止控制。
 */
export function useChatStream(options: UseChatStreamOptions) {
  const toastStore = useToastStore();

  const isSending = ref(false);
  const currentAbortController = ref<AbortController | null>(null);

  function stopGeneration() {
    if (currentAbortController.value) {
      currentAbortController.value.abort();
      currentAbortController.value = null;
    }
  }

  async function sendMessage(text: string) {
    const session = options.getSession();
    if (!text || isSending.value || !session) return;

    // Set session title automatically on first message
    if (session.title === '新对话') {
      session.title = text.length > 15 ? text.substring(0, 15) + '...' : text;
    }

    // Add user message
    session.messages.push({ role: 'user', content: text });
    isSending.value = true;

    // Create assistant placeholder
    const assistantMsg = ref<ChatMessage>({ role: 'assistant', content: '', isStreaming: true });
    session.messages.push(assistantMsg.value);

    // Build history array
    const history = session.messages
      .slice(0, -2) // Exclude current user message and placeholder
      .filter((m) => m.role !== 'system')
      .map((m) => ({ role: m.role, content: m.content }));

    currentAbortController.value = new AbortController();

    let rawReasoningBuffer = '';
    let displayedReasoning = '';
    let rawTextBuffer = '';
    let displayedText = '';
    let networkComplete = false;
    let typewriterTimer: ReturnType<typeof setInterval> | null = null;

    const advanceBuffer = (raw: string, displayed: string) => {
      const pendingLength = raw.length - displayed.length;
      if (pendingLength <= 0) return displayed;
      const step = Math.ceil(pendingLength / 6);
      return displayed + raw.slice(displayed.length, displayed.length + step);
    };

    const startTypewriter = () => {
      typewriterTimer = setInterval(() => {
        displayedReasoning = advanceBuffer(rawReasoningBuffer, displayedReasoning);
        displayedText = advanceBuffer(rawTextBuffer, displayedText);

        if (displayedReasoning) {
          assistantMsg.value.reasoning = displayedReasoning;
        }
        if (displayedText) {
          assistantMsg.value.content = displayedText;
        }

        const reasoningDrained = displayedReasoning.length === rawReasoningBuffer.length;
        const textDrained = displayedText.length === rawTextBuffer.length;
        if (networkComplete && reasoningDrained && textDrained) {
          if (typewriterTimer !== null) {
            clearInterval(typewriterTimer);
          }
          typewriterTimer = null;
          assistantMsg.value.isStreaming = false;
          options.persist();
        }
      }, 30);
    };

    try {
      startTypewriter();

      const response = await fetch('/api/llm/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          history: history,
          news_id: session.newsId,
          desk_symbol: session.deskSymbol,
          config_id: options.getConfigId(),
          stream: true,
        }),
        signal: currentAbortController.value.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || '请求大模型失败，请检查配置或连接。');
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('当前浏览器不支持读取 Stream。');
      }

      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6);
            try {
              const parsed = JSON.parse(jsonStr);
              if (parsed.reasoning) {
                rawReasoningBuffer += parsed.reasoning;
              } else if (parsed.text) {
                rawTextBuffer += parsed.text;
              } else if (parsed.failover) {
                assistantMsg.value.failover = parsed.failover;
                toastStore.showWarning('由于主大模型异常，已自动为您无缝切换至备选模型！');
              } else if (parsed.error) {
                rawTextBuffer += `\n[错误: ${parsed.error}]`;
              }
            } catch {
              // Buffer chunk incomplete, skip
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        rawTextBuffer += '\n\n*(已中止生成)*';
        toastStore.showInfo('大模型流生成已中止');
      } else {
        if (typewriterTimer) {
          clearInterval(typewriterTimer);
          typewriterTimer = null;
        }
        assistantMsg.value.content = `【发送失败】 ${err.message || '网络连接发生异常'}`;
        assistantMsg.value.isStreaming = false;
        toastStore.showError(err.message || '发送失败，请重试');
      }
    } finally {
      networkComplete = true;
      isSending.value = false;
      currentAbortController.value = null;
      if (!typewriterTimer) {
        assistantMsg.value.isStreaming = false;
        options.persist();
      }
    }
  }

  return {
    isSending,
    stopGeneration,
    sendMessage,
  };
}
