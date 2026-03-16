<script setup lang="ts">
import type { MarketSnapshot, WatchlistItem } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../../utils/time';

defineProps<{
  rows: Array<WatchlistItem & { snapshot?: MarketSnapshot }>;
  selectedSymbol: string | null;
}>();

const emit = defineEmits<{
  select: [symbol: string];
}>();
</script>

<template>
  <div class="table-shell">
    <table>
      <thead>
        <tr>
          <th>股票</th>
          <th>市场</th>
          <th>价格</th>
          <th>涨跌幅</th>
          <th>异动</th>
          <th>更新时间</th>
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
          <td>{{ formatNumber(row.snapshot?.price) }}</td>
          <td :class="{ positive: (row.snapshot?.change_percent ?? 0) > 0, negative: (row.snapshot?.change_percent ?? 0) < 0 }">
            {{ formatPercent(row.snapshot?.change_percent) }}
          </td>
          <td>
            <span v-if="row.snapshot?.is_abnormal" class="pill negative">{{ row.snapshot?.abnormal_reason ?? 'abnormal' }}</span>
            <span v-else>正常</span>
          </td>
          <td>
            {{
              row.snapshot?.fetched_at
                ? `${formatMarketTime(row.snapshot?.fetched_at, row.market)} ${getMarketTimezoneLabel(row.market)}`
                : '--'
            }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-shell {
  overflow: hidden;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.56);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 14px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

tbody tr {
  cursor: pointer;
}

tbody tr[data-selected='true'] {
  background: rgba(31, 94, 168, 0.08);
}

td strong,
td span {
  display: block;
}

.positive {
  color: var(--positive);
}

.negative {
  color: var(--negative);
}
</style>
