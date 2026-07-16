import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import { useFeedKeyboard } from './useFeedKeyboard';

function setup(options: { drawerOpen?: boolean } = {}) {
  const openDrawer = vi.fn();
  const closeDrawer = vi.fn();
  const onSelect = vi.fn();
  let exposed!: ReturnType<typeof useFeedKeyboard>;
  const wrapper = mount(
    defineComponent({
      setup() {
        exposed = useFeedKeyboard({
          ids: () => [11, 22, 33],
          isDrawerOpen: () => options.drawerOpen ?? false,
          openDrawer,
          closeDrawer,
          onSelect,
        });
        return () => h('div');
      },
    }),
  );
  return { wrapper, openDrawer, closeDrawer, onSelect, keyboard: () => exposed };
}

function press(key: string, target?: EventTarget) {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  if (target) {
    Object.defineProperty(event, 'target', { value: target });
  }
  window.dispatchEvent(event);
  return event;
}

describe('useFeedKeyboard', () => {
  it('j/k 顺序移动选中并回调 onSelect', () => {
    const { keyboard, onSelect } = setup();
    press('j');
    expect(keyboard().selectedId.value).toBe(11);
    press('j');
    expect(keyboard().selectedId.value).toBe(22);
    press('k');
    expect(keyboard().selectedId.value).toBe(11);
    expect(onSelect).toHaveBeenCalledWith(11, 0);
  });

  it('Enter 打开当前选中', () => {
    const { keyboard, openDrawer } = setup();
    press('j');
    press('Enter');
    expect(openDrawer).toHaveBeenCalledWith(11);
    expect(keyboard().selectedId.value).toBe(11);
  });

  it('抽屉打开时 j 直接切换抽屉内容, Esc 关闭', () => {
    const { openDrawer, closeDrawer } = setup({ drawerOpen: true });
    press('j');
    expect(openDrawer).toHaveBeenCalledWith(11);
    press('Escape');
    expect(closeDrawer).toHaveBeenCalled();
  });

  it('输入框聚焦时忽略快捷键', () => {
    const { keyboard } = setup();
    const input = document.createElement('input');
    press('j', input);
    expect(keyboard().selectedId.value).toBeNull();
  });

  it('卸载后不再监听', () => {
    const { wrapper, keyboard } = setup();
    wrapper.unmount();
    press('j');
    expect(keyboard().selectedId.value).toBeNull();
  });
});
