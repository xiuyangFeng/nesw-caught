<script setup lang="ts">
import type { WatchlistQuoteSummary } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../../utils/time';

defineProps<{
  rows: WatchlistQuoteSummary[];
  selectedSymbol: string | null;
  deletingSymbol?: string | null;
}>();

const emit = defineEmits<{
  select: [symbol: string];
  delete: [symbol: string];
}>();
</script>

<template>
  <div class="table-shell terminal-surface" data-surface="terminal-table" data-role="watchlist-table-shell">
    <table>
      <thead>
        <tr>
          <th>股票</th>
          <th>市场</th>
          <th>价格</th>
          <th>涨跌幅</th>
          <th>开盘</th>
          <th>昨收</th>
          <th>最高</th>
          <th>最低</th>
          <th>成交量</th>
          <th>异动</th>
          <th>更新时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.symbol"
          :data-selected="row.symbol === selectedSymbol"
          @click="emit('select', row.symbol)"
        >
          <td>
            <strong>{{ row.display_name }}</strong>
            <span>{{ row.symbol }}</span>
          </td>
          <td>{{ row.market.toUpperCase() }}</td>
          <td>{{ formatNumber(row.price) }}</td>
          <td :class="{ positive: (row.change_percent ?? 0) > 0, negative: (row.change_percent ?? 0) < 0 }">
            {{ formatPercent(row.change_percent) }}
          </td>
          <td>{{ formatNumber(row.open_price) }}</td>
          <td>{{ formatNumber(row.previous_close) }}</td>
          <td>{{ formatNumber(row.day_high) }}</td>
          <td>{{ formatNumber(row.day_low) }}</td>
          <td>{{ formatNumber(row.volume, 0) }}</td>
          <td>
            <!-- 后端 /api/market/watchlist(QuoteSummaryView)不含 is_abnormal 字段，异常态以 status 表达 -->
            <span :class="{ 'pill negative': row.status !== 'ok' }">{{ row.status }}</span>
          </td>
          <td>
            {{
              row.fetched_at
                ? `${formatMarketTime(row.fetched_at, row.market)} ${getMarketTimezoneLabel(row.market)}`
                : '--'
            }}
          </td>
          <td>
            <button
              data-role="delete-watchlist"
              class="delete-button"
              type="button"
              :disabled="row.symbol === deletingSymbol"
              @click.stop="emit('delete', row.symbol)"
            >
              {{ row.symbol === deletingSymbol ? '删除中...' : '删除' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-shell {
  overflow: hidden;
  border-radius: var(--r-lg);
  border: 1px solid var(--border);
  background: var(--panel);
}

table {
  width: 100%;
  border-collapse: collapse;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

thead {
  background: var(--panel-strong);
}

th,
td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

th {
  color: var(--muted);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-family: var(--font-mono);
}

td {
  color: var(--text-soft);
}

tbody tr {
  cursor: pointer;
  transition: background-color 160ms ease;
}

tbody tr:hover {
  background: var(--interactive-hover);
}

tbody tr[data-selected='true'] {
  background: var(--interactive-selected);
  box-shadow: inset 3px 0 0 var(--accent);
}

td strong,
td span {
  display: block;
}

td span {
  color: var(--text-faint);
  font-family: var(--font-mono);
}

/* 数字/时间列等宽对齐（价格·涨跌·开盘·昨收·高·低·成交量·更新时间） */
td:nth-child(3),
td:nth-child(4),
td:nth-child(5),
td:nth-child(6),
td:nth-child(7),
td:nth-child(8),
td:nth-child(9),
td:nth-child(11) {
  font-family: var(--font-mono);
}

.positive {
  color: var(--positive);
}

.negative {
  color: var(--negative);
}

.delete-button {
  border: 1px solid var(--danger);
  border-color: color-mix(in srgb, var(--danger) 32%, transparent);
  border-radius: 999px;
  padding: 7px 12px;
  font: inherit;
  color: var(--danger);
  background: var(--danger-soft);
  cursor: pointer;
  transition: background-color 160ms ease, border-color 160ms ease, opacity 160ms ease;
}

.delete-button:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--danger) 52%, transparent);
  background: color-mix(in srgb, var(--danger) 22%, transparent);
}

.delete-button:disabled {
  opacity: 0.65;
  cursor: progress;
}
</style>
