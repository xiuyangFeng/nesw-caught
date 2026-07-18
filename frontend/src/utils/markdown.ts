/**
 * Simple, high-performance Markdown parser for financial and investment analysis chat.
 * Renders lists, bold, italics, tables, and code blocks with "Copy" functionality.
 */

function escapeHtml(unsafe: string): string {
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function replaceInline(str: string): string {
  return str
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-white/10 rounded font-mono text-[11px] text-warning">$1</code>');
}

function renderTable(rows: string[][]): string {
  if (rows.length === 0) return '';
  
  let hasHeader = false;
  let startIdx = 0;
  
  if (rows.length >= 2 && rows[1].every(cell => /^:?-+:?$/.test(cell))) {
    hasHeader = true;
    startIdx = 2;
  }

  let html = '<div class="overflow-x-auto my-4 rounded-xl border border-border/50 bg-white/[0.02] shadow-sm"><table class="w-full text-left text-xs border-collapse">';
  
  if (hasHeader) {
    html += '<thead class="bg-white/[0.04] border-b border-border/40 text-text-faint font-semibold uppercase tracking-wider">';
    html += '<tr>';
    for (const cell of rows[0]) {
      html += `<th class="px-4 py-3">${cell}</th>`;
    }
    html += '</tr></thead>';
  }

  html += '<tbody class="divide-y divide-border/20 text-text">';
  for (let i = startIdx; i < rows.length; i++) {
    html += '<tr class="hover:bg-white/[0.01] transition-colors">';
    for (const cell of rows[i]) {
      html += `<td class="px-4 py-2.5">${cell}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table></div>';
  return html;
}

function renderList(items: string[]): string {
  let html = '<ul class="list-disc list-inside my-2 pl-2 space-y-1 text-text-muted">';
  for (const item of items) {
    html += `<li>${item}</li>`;
  }
  html += '</ul>';
  return html;
}

// Bind clipboard copy helper globally
if (typeof window !== 'undefined' && !(window as any).__copyCodeToClipboard) {
  (window as any).__copyCodeToClipboard = (btn: HTMLButtonElement) => {
    const encodedCode = btn.getAttribute('data-code');
    if (!encodedCode) return;
    const code = decodeURIComponent(encodedCode);
    navigator.clipboard.writeText(code).then(() => {
      const originalText = btn.innerText;
      btn.innerText = '已复制!';
      btn.classList.add('text-success');
      setTimeout(() => {
        btn.innerText = originalText;
        btn.classList.remove('text-success');
      }, 2000);
    }).catch((err) => {
      console.error('Failed to copy', err);
    });
  };
}

export function parseMarkdown(text: string): string {
  if (!text) return '';

  // 1. Escape HTML for security
  const safeText = escapeHtml(text);

  // 2. Extract code blocks & replace with placeholders
  const codeBlocks: string[] = [];
  let processed = safeText.replace(/```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)\r?\n?```/g, (match, lang, code) => {
    const codeId = codeBlocks.length;
    const escapedCodeForAttr = encodeURIComponent(code.trim());
    const htmlCodeBlock = `
<div class="code-block-wrapper relative my-3 rounded-lg overflow-hidden border border-border/60 bg-black/35 font-mono text-xs">
  <div class="flex items-center justify-between px-4 py-1.5 bg-white/[0.03] border-b border-border/30 text-text-faint">
    <span class="uppercase font-bold tracking-wider text-[10px]">${lang || 'text'}</span>
    <button class="copy-code-btn px-2 py-0.5 rounded bg-white/[0.05] hover:bg-white/[0.12] transition text-[10px] font-semibold text-text active:scale-95" data-code="${escapedCodeForAttr}" onclick="window.__copyCodeToClipboard(this)">
      复制
    </button>
  </div>
  <pre class="p-3.5 overflow-x-auto leading-relaxed text-text-muted"><code>${code}</code></pre>
</div>`.trim();
    codeBlocks.push(htmlCodeBlock);
    return `__CODE_BLOCK_PLACEHOLDER_${codeId}__`;
  });

  // 3. Process line-by-line for blocks (tables, lists, paragraphs)
  const lines = processed.split(/\r?\n/);
  const newLines: string[] = [];
  
  let inTable = false;
  let tableRows: string[][] = [];
  
  let inList = false;
  let listItems: string[] = [];
  
  let paraLines: string[] = [];

  const flushPara = () => {
    if (paraLines.length === 0) return '';
    const content = paraLines.join('<br>');
    paraLines = [];
    if (content.trim()) {
      return `<p class="mb-3 last:mb-0 leading-relaxed text-text-muted">${content}</p>`;
    }
    return '';
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Check code placeholder - must be rendered as block-level item without <p> wrapper
    if (trimmed.startsWith('__CODE_BLOCK_PLACEHOLDER_') && trimmed.endsWith('__')) {
      const p = flushPara();
      if (p) newLines.push(p);
      
      if (inTable) {
        newLines.push(renderTable(tableRows));
        inTable = false;
        tableRows = [];
      }
      if (inList) {
        newLines.push(renderList(listItems));
        inList = false;
        listItems = [];
      }
      
      newLines.push(trimmed);
      continue;
    }

    // Check table
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const p = flushPara();
      if (p) newLines.push(p);

      if (inList) {
        newLines.push(renderList(listItems));
        inList = false;
        listItems = [];
      }

      const cells = trimmed
        .split('|')
        .map(c => replaceInline(c.trim()))
        .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        
      if (!inTable) {
        inTable = true;
        tableRows = [cells];
      } else {
        tableRows.push(cells);
      }
      continue;
    }

    if (inTable) {
      newLines.push(renderTable(tableRows));
      inTable = false;
      tableRows = [];
    }

    // Check list
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const p = flushPara();
      if (p) newLines.push(p);

      const content = replaceInline(trimmed.substring(2).trim());
      if (!inList) {
        inList = true;
        listItems = [content];
      } else {
        listItems.push(content);
      }
      continue;
    }

    if (inList) {
      newLines.push(renderList(listItems));
      inList = false;
      listItems = [];
    }

    // Empty line separates paragraphs
    if (!trimmed) {
      const p = flushPara();
      if (p) newLines.push(p);
      continue;
    }

    // Regular text line
    paraLines.push(replaceInline(line));
  }

  // Final flush
  const p = flushPara();
  if (p) newLines.push(p);
  if (inTable) newLines.push(renderTable(tableRows));
  if (inList) newLines.push(renderList(listItems));

  // 4. Restore code block placeholders
  let finalHtml = newLines.filter(line => line !== '').join('\n');
  for (let i = 0; i < codeBlocks.length; i++) {
    finalHtml = finalHtml.replace(`__CODE_BLOCK_PLACEHOLDER_${i}__`, codeBlocks[i]);
  }

  return finalHtml;
}
