import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import { useFeedKeyboard } from './useFeedKeyboard';

function setup(options: { drawerOpen?: boolean; ids?: number[] } = {}) {
  const openDrawer = vi.fn();
  const closeDrawer = vi.fn();
  const onSelect = vi.fn();
  let currentIds = options.ids ?? [11, 22, 33];
  let exposed!: ReturnType<typeof useFeedKeyboard>;
  const wrapper = mount(
    defineComponent({
      setup() {
        exposed = useFeedKeyboard({
          ids: () => currentIds,
          isDrawerOpen: () => options.drawerOpen ?? false,
          openDrawer,
          closeDrawer,
          onSelect,
        });
        return () => h('div');
      },
    }),
  );
  return {
    wrapper,
    openDrawer,
    closeDrawer,
    onSelect,
    keyboard: () => exposed,
    setIds: (next: number[]) => {
      currentIds = next;
    },
  };
}

function press(key: string, target?: EventTarget) {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  if (target) {
    Object.defineProperty(event, 'target', { value: target });
  }
  window.dispatchEvent(event);
  return event;
}

function pressWithModifier(
  key: string,
  modifier: 'metaKey' | 'ctrlKey' | 'altKey',
): KeyboardEvent {
  const event = new KeyboardEvent('keydown', {
    key,
    bubbles: true,
    cancelable: true,
    [modifier]: true,
  });
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

  it('文本域聚焦时忽略快捷键', () => {
    const { keyboard } = setup();
    const textarea = document.createElement('textarea');
    press('j', textarea);
    expect(keyboard().selectedId.value).toBeNull();
  });

  it('contenteditable 聚焦时忽略快捷键', () => {
    const { keyboard } = setup();
    const editable = document.createElement('div');
    // jsdom 不支持 contentEditable 属性联动 isContentEditable getter，
    // 直接覆盖该只读属性以模拟真实浏览器中 contenteditable 元素的行为。
    Object.defineProperty(editable, 'isContentEditable', { value: true });
    press('j', editable);
    expect(keyboard().selectedId.value).toBeNull();
  });

  it('卸载后不再监听', () => {
    const { wrapper, keyboard } = setup();
    wrapper.unmount();
    press('j');
    expect(keyboard().selectedId.value).toBeNull();
  });

  it('meta/ctrl/alt 修饰键按下时 j/k/Enter 全部被忽略', () => {
    const { keyboard, openDrawer } = setup();
    (['metaKey', 'ctrlKey', 'altKey'] as const).forEach((modifier) => {
      pressWithModifier('j', modifier);
      pressWithModifier('k', modifier);
      pressWithModifier('Enter', modifier);
    });
    expect(keyboard().selectedId.value).toBeNull();
    expect(openDrawer).not.toHaveBeenCalled();
  });

  it('抽屉已开时按 Enter 不重复触发 openDrawer', () => {
    const { openDrawer } = setup({ drawerOpen: true });
    press('j');
    expect(openDrawer).toHaveBeenCalledTimes(1);
    openDrawer.mockClear();
    press('Enter');
    expect(openDrawer).not.toHaveBeenCalled();
  });

  it('Enter 时 selectedId 已不在 ids() 中则不调用 openDrawer', () => {
    const { keyboard, openDrawer, setIds } = setup();
    press('j');
    expect(keyboard().selectedId.value).toBe(11);
    setIds([22, 33]);
    openDrawer.mockClear();
    press('Enter');
    expect(openDrawer).not.toHaveBeenCalled();
    expect(keyboard().selectedId.value).toBe(11);
  });
});
