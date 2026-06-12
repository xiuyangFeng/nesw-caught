import { ref } from 'vue';
import { defineStore } from 'pinia';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

export const useToastStore = defineStore('toastStore', () => {
  const toasts = ref<ToastMessage[]>([]);

  function show(message: string, type: ToastMessage['type'] = 'info', duration = 3000) {
    const id = Math.random().toString(36).substring(2, 9);
    const toast: ToastMessage = { id, type, message, duration };
    toasts.value.push(toast);

    if (duration > 0) {
      setTimeout(() => {
        remove(id);
      }, duration);
    }
  }

  function showSuccess(message: string, duration = 3000) {
    show(message, 'success', duration);
  }

  // Errors stay slightly longer by default
  function showError(message: string, duration = 4500) {
    show(message, 'error', duration);
  }

  function showWarning(message: string, duration = 3500) {
    show(message, 'warning', duration);
  }

  function showInfo(message: string, duration = 3000) {
    show(message, 'info', duration);
  }

  function remove(id: string) {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }

  return {
    toasts,
    show,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    remove,
  };
});
