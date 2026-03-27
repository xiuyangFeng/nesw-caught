# Watchlist Terminal Redesign Design

## Goal

把 watchlist 列表和详情页从当前偏大卡片、留白偏多的 dashboard 风格，改成更接近同花顺的高密度交易终端：列表卡片更紧凑，详情页以放大版 K 线为主，右侧补高端技术指标仪表盘。

## Constraints

- 先不扩后端 API 契约，优先使用现有 `quote` 和 `klineData` 字段。
- 详情页应继续兼容当前 `WatchlistDetailView -> StockDetailPanel -> KlineChart` 数据流。
- 技术指标优先，基本面字段如总市值/PE/换手率在当前数据不足时不做伪造展示。
- 保持移动端和窄屏下可用，桌面端优先体现交易终端视觉。

## Chosen Approach

采用“紧凑报价头 + 放大主图 + 右侧精密仪表栏 + 底部副图切换”的结构，而不是把页面拆成多个平铺卡片。

### 列表页

- `StockCard` 改成更低高度的横向终端卡。
- 左侧只保留名称、代码和主价格。
- 右侧压缩市场标签、涨跌幅、成交量和删除操作。
- Sparkline 保留但缩短高度，状态标签不再单独占大块空间。

### 详情页

- `StockDetailPanel` 顶部行情头压缩成双栏：
  - 左侧：名称、代码、最新价、涨跌额、涨跌幅。
  - 右侧：`Open / Prev Close / High / Low / Volume / Session Range / 6M Range / Avg Vol` 等紧凑指标矩阵。
- 主体区域改成 `主图 72% + 右栏 28%` 的交易终端布局。
- `KlineChart` 升级为大图容器，主图显示蜡烛 + MA + BOLL，并在下方提供副图切换：
  - `VOL`
  - `MACD`
  - `KDJ`
- 右栏展示由现有行情和 K 线推导出的仪表化指标：
  - 当日涨跌强度
  - 当日波动区间位置
  - 6 月区间位置
  - MA/BOLL 最新值读数
  - MACD / KDJ 最新值读数

## Derived Metrics

在不新增后端字段的前提下，前端根据已有数据推导：

- `Session Range`: `(price - day_low) / (day_high - day_low)`
- `6M Range`: `(latest_close - range_low) / (range_high - range_low)`
- `Amplitude`: `(day_high - day_low) / previous_close`
- `Avg Vol`: 最近 20 根 candle 的平均成交量
- `Trend Bias`: `close` 相对 `ma20` / `ma60` 的位置

这些指标都只依赖 `quote` 与 `klineData`，不引入伪基本面。

## Visual Direction

- 深蓝黑终端底色，去掉现有大面积空白。
- 强调色使用铜橙金，涨跌继续保留红绿。
- 仪表采用半环、刻度条、细线网格和数显读数混排，而不是大面积圆表堆砌。
- 字体层级更紧：数字更大但占位更短，说明性标签更细更小。
- K 线区域高度明显提升，成为页面主视觉。

## Testing

- 更新 `StockDetailPanel.test.ts`，验证紧凑行情头、右侧指标区和设置入口仍可用。
- 更新 `KlineChart.test.ts`，验证副图切换、右栏仪表面板和事件联动仍成立。
- 必要时补 `WatchlistView` 或 `StockCard` 相关测试，确保更紧凑的卡片仍保持选择和删除交互。
