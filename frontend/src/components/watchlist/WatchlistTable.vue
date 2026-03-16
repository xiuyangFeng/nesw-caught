<script setup lang="ts">
import type { WatchlistQuoteSummary } from '../../types/api';
import { formatNumber, formatPercent } from '../../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../../utils/time';

defineProps<{
  rows: WatchlistQuoteSummary[];
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
          <th>开盘</th>
          <th>昨收</th>
          <th>最高</th>
          <th>最低</th>
          <th>成交量</th>
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
