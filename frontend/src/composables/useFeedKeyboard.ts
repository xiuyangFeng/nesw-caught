import { onBeforeUnmount, onMounted, ref } from 'vue';
import type { Ref } from 'vue';

export interface FeedKeyboardOptions {
  ids: () => number[];
  isDrawerOpen: () => boolean;
  openDrawer: (id: number) => void;
  closeDrawer: () => void;
  onSelect?: (id: number, index: number) => void;
}

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return EDITABLE_TAGS.has(target.tagName) || target.isContentEditable;
}

export function useFeedKeyboard(options: FeedKeyboardOptions): {
  selectedId: Ref<number | null>;
  handleKeydown: (event: KeyboardEvent) => void;
} {
  const selectedId = ref<number | null>(null);

  function move(step: 1 | -1): void {
    const ids = options.ids();
    if (!ids.length) {
      return;
    }
    const currentIndex = selectedId.value === null ? -1 : ids.indexOf(selectedId.value);
    const nextIndex =
      currentIndex === -1
        ? step === 1
          ? 0
          : ids.length - 1
        : Math.min(ids.length - 1, Math.max(0, currentIndex + step));
    const nextId = ids[nextIndex];
    if (nextId === undefined) {
      return;
    }
    selectedId.value = nextId;
    if (options.isDrawerOpen()) {
      options.openDrawer(nextId);
    }
    options.onSelect?.(nextId, nextIndex);
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (isEditableTarget(event.target)) {
      return;
    }
    if (event.key === 'j') {
      event.preventDefault();
      move(1);
      return;
    }
    if (event.key === 'k') {
      event.preventDefault();
      move(-1);
      return;
    }
    if (event.key === 'Enter') {
      // 防护：列表可能因筛选/刷新变化，selectedId 可能已不在当前 ids() 中；
      // 此时忽略 Enter，避免对已消失的 id 调用 openDrawer。不清空 selectedId，
      // 交由 j/k 的 indexOf 回退逻辑处理后续移动。
      if (
        selectedId.value !== null &&
        !options.isDrawerOpen() &&
        options.ids().includes(selectedId.value)
      ) {
        event.preventDefault();
        options.openDrawer(selectedId.value);
      }
      return;
    }
    if (event.key === 'Escape' && options.isDrawerOpen()) {
      event.preventDefault();
      options.closeDrawer();
    }
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown));
  onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown));

  return { selectedId, handleKeydown };
}
