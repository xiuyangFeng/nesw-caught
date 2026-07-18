import { describe, expect, it } from 'vitest';
import { parseMarkdown } from './markdown';

describe('parseMarkdown', () => {
  it('escapes raw HTML to prevent XSS', () => {
    const raw = '<script>alert("xss")</script>';
    const parsed = parseMarkdown(raw);
    expect(parsed).not.toContain('<script>');
    expect(parsed).toContain('&lt;script&gt;');
  });

  it('parses bold and italic inline styles', () => {
    const raw = 'This is **bold** and this is *italic*.';
    const parsed = parseMarkdown(raw);
    expect(parsed).toContain('<strong>bold</strong>');
    expect(parsed).toContain('<em>italic</em>');
  });

  it('parses inline code', () => {
    const raw = 'Run `npm run dev` to start.';
    const parsed = parseMarkdown(raw);
    expect(parsed).toContain('<code class="px-1.5 py-0.5 bg-white/10 rounded font-mono text-[11px] text-warning">npm run dev</code>');
  });

  it('parses lists', () => {
    const raw = '- Item 1\n- Item 2';
    const parsed = parseMarkdown(raw);
    expect(parsed).toContain('<ul class="list-disc list-inside my-2 pl-2 space-y-1 text-text-muted">');
    expect(parsed).toContain('<li>Item 1</li>');
    expect(parsed).toContain('<li>Item 2</li>');
  });

  it('parses multi-line code blocks with language', () => {
    const raw = '```python\ndef foo():\n    return 42\n```';
    const parsed = parseMarkdown(raw);
    expect(parsed).toContain('<span class="uppercase font-bold tracking-wider text-[10px]">python</span>');
    expect(parsed).toContain('def foo():');
  });

  it('parses Markdown tables', () => {
    const raw = '| Symbol | Price | Change |\n|---|---|---|\n| AAPL | 215.3 | -1.3% |\n| 0700.HK | 332.4 | +3.3% |';
    const parsed = parseMarkdown(raw);
    expect(parsed).toContain('<table class="w-full text-left text-xs border-collapse">');
    expect(parsed).toContain('<th class="px-4 py-3">Symbol</th>');
    expect(parsed).toContain('<td class="px-4 py-2.5">AAPL</td>');
  });

  it('does not wrap code blocks inside paragraph tags', () => {
    const raw = 'Intro paragraph.\n\n```js\nconst x = 1;\n```\n\nOutro paragraph.';
    const parsed = parseMarkdown(raw);
    expect(parsed).toContain('<p class="mb-3 last:mb-0 leading-relaxed text-text-muted">Intro paragraph.</p>');
    expect(parsed).toContain('<p class="mb-3 last:mb-0 leading-relaxed text-text-muted">Outro paragraph.</p>');
    expect(parsed).not.toContain('<p class="mb-3 last:mb-0 leading-relaxed text-text-muted"><div class="code-block-wrapper');
  });
});
