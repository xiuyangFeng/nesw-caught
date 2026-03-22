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
            <span v-if="row.is_abnormal" class="pill negative">{{ row.abnormal_reason ?? 'abnormal' }}</span>
            <span v-else>{{ row.status }}</span>
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
  border-radius: 16px;
  border: 1px solid rgba(133, 161, 191, 0.18);
  background: linear-gradient(180deg, rgba(11, 18, 28, 0.98), rgba(8, 14, 23, 0.98));
}

table {
  width: 100%;
  border-collapse: collapse;
  color: var(--text);
}

thead {
  background: rgba(255, 159, 47, 0.08);
}

th,
td {
  padding: 14px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

th {
  color: #ffd5b0;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
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
  box-shadow: inset 3px 0 0 rgba(125, 211, 252, 0.7);
}

td strong,
td span {
  display: block;
}

td span {
  color: var(--text-faint);
}

.positive {
  color: var(--positive);
}

.negative {
  color: var(--negative);
}

.delete-button {
  border: 1px solid rgba(248, 113, 113, 0.28);
  border-radius: 999px;
  padding: 8px 12px;
  font: inherit;
  color: #fecaca;
  background: rgba(127, 29, 29, 0.22);
  cursor: pointer;
  transition: background-color 160ms ease, border-color 160ms ease, opacity 160ms ease;
}

.delete-button:hover:not(:disabled) {
  border-color: rgba(248, 113, 113, 0.48);
  background: rgba(153, 27, 27, 0.34);
}

.delete-button:disabled {
  opacity: 0.65;
  cursor: progress;
}
</style>
