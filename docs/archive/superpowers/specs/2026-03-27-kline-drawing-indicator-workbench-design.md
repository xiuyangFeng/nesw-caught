# K 线画线与指标工作台设计

## 背景

当前自选股详情页的 K 线模块已经具备蜡烛图、均线、BOLL、副图指标切换和右侧技术面板，但本质上仍是“只读行情渲染”。用户现在需要把它升级为更接近专业看盘软件的工作台，至少覆盖两类能力：

- 主图上的手工画线和编辑，包括趋势线、水平线、矩形区间、斐波那契和价格标注
- 常见指标的一键导入，以及带参数的指标模板导入

用户已经确认以下约束：

- 采用“保留 `lightweight-charts` 渲染层，在上方新增独立绘图覆盖层”的方案
- 指标导入范围只包含内置常见指标和参数模板，不支持外部脚本/公式导入
- 保存策略为“指标模板全局复用，画线按股票单独保存”
- 允许持续开发直到任务完成，不需要在设计和实现阶段再次停下来征求确认

## 目标

把现有 `KlineChart` 升级为一个可持续扩展的 K 线工作台，同时保持现有终端化视觉风格与数据接口不被推翻。

本次设计目标：

- 在主图上提供对象化绘图能力，而不是零散的临时 DOM 交互
- 把指标显示从“固定内置几条线”升级为“可配置的主图指标集 + 副图指标模板”
- 让绘图和模板具备持久化能力，且边界清晰：画线归股票，指标模板归用户全局
- 尽量限制在前端完成，不把这轮需求扩大成后端新表设计或多端同步工程

非目标：

- 不实现 TradingView 级别的脚本语言、策略回测或告警编排
- 不引入后端数据库存储绘图对象
- 不支持多人协作共享画线
- 不在本轮重写现有 K 线数据接口或行情图表库

## 方案比较

### 方案 A：继续在现有 `KlineChart.vue` 里直接堆交互

优点：

- 文件改动最少
- 不需要额外抽象状态模型

缺点：

- 命中检测、拖拽锚点、工具状态、模板状态会全部挤在一个组件里
- 难测试，后续每加一个画线工具都会放大维护成本
- 不利于未来扩展撤销/重做或更多工具

结论：不采用。当前 `KlineChart.vue` 已经承担图表初始化、指标切换、技术面板和布局控制，再继续加专业交互会失控。

### 方案 B：保留图表渲染层，新增绘图覆盖层与独立工作台状态

做法：

- `lightweight-charts` 继续负责蜡烛图和指标线渲染
- 在主图容器上叠加一层独立交互画布，专门处理绘图对象、选中态、拖拽和工具栏
- 把指标模板、当前启用指标、绘图对象序列化数据从组件内逻辑中拆出，交给 store 和纯函数模块

优点：

- 保留现有终端化 UI 和图表数据接入
- 单元边界清晰，适合 TDD
- 后续增加新工具或模板不需要继续膨胀图表组件

缺点：

- 需要明确坐标映射、序列化格式和交互状态机
- 会新增若干前端文件和测试

结论：采用。这是在保留现有投资下最稳妥、可维护的扩展路线。

### 方案 C：整体替换成更重型的图表方案

优点：

- 理论上可能借用更现成的高级交互能力

缺点：

- 会牵连现有终端式 UI、测试、指标线实现和样式层
- 当前收益不足以覆盖替换成本

结论：本轮不采用。

## 设计总览

### 架构分层

K 线工作台拆成四层：

1. 行情渲染层
由现有 `lightweight-charts` 主图和副图负责，继续显示蜡烛、主图指标线、副图指标和新闻事件。

2. 绘图覆盖层
新增一个覆盖在主图上的绝对定位 SVG 或 canvas 交互层。它负责画线对象的显示、命中检测、锚点拖拽、选中高亮和当前绘图预览。

3. 工作台状态层
新增前端状态，负责当前工具、当前选中对象、按股票存储的画线、当前启用的主图指标、副图指标模板、默认模板等。

4. 序列化与模板层
新增纯函数模块，负责绘图对象和指标模板的定义、默认模板、导入校验、localStorage 持久化、旧数据兼容。

### 用户流程

1. 进入某只股票详情页
2. 图表正常渲染默认指标模板
3. 用户从工具栏切换到趋势线/水平线/矩形/斐波那契/价格标注
4. 在主图上点击或拖拽完成对象创建
5. 选中对象后，可拖动端点、整体移动或删除
6. 用户打开指标面板，从内置模板中一键导入，或导入参数模板
7. 画线自动按股票保存在本地；指标模板作为全局模板，下次进入别的股票仍可选

## 画线功能设计

### 工具范围

首轮支持以下对象类型：

- 趋势线 `trend_line`
- 水平线 `horizontal_line`
- 矩形区间 `price_range`
- 斐波那契回撤 `fibonacci_retracement`
- 价格标注线 `price_note`

不在首轮支持：

- 平行通道
- 江恩、波浪、复杂几何图形
- 文本框富编辑

这样可以覆盖多数日常看盘场景，同时避免一次性做过多稀有工具。

### 对象模型

每个绘图对象都采用统一包裹结构：

- `id`
- `symbol`
- `toolType`
- `createdAt`
- `updatedAt`
- `locked`
- `visible`
- `style`
- `anchors`
- `payload`

其中：

- `anchors` 使用图表域坐标，不直接保存像素坐标
- 时间锚点优先保存 candle 的 `time` 字符串
- 价格锚点保存 number
- `style` 允许基础颜色、线宽、虚线、填充透明度
- `payload` 用于保存特定工具的附加字段；除 `price_note` 外，首轮其他工具默认空对象

不同类型的最小锚点数：

- 趋势线：2 个点
- 水平线：1 个价格点，横向延伸到当前可视区
- 矩形区间：2 个对角点
- 斐波那契：2 个端点
- 价格标注线：1 个价格点和可选标签文本

首轮对象契约补充如下：

- `trend_line`
  - `anchors`: `[{ time, price }, { time, price }]`
  - 渲染为双点线段，不自动延长成射线
- `horizontal_line`
  - `anchors`: `[{ time, price }]`
  - 渲染为贯穿当前主图可视区的水平线
- `price_range`
  - `anchors`: `[{ time, price }, { time, price }]`
  - 渲染为矩形选区，支持边框和半透明填充
- `fibonacci_retracement`
  - `anchors`: `[{ time, price }, { time, price }]`
  - 默认 level 固定为 `0 / 0.236 / 0.382 / 0.5 / 0.618 / 0.786 / 1`
  - 每条 level 右侧显示百分比标签和对应价格
  - 首轮不支持自定义 fib level 集合
- `price_note`
  - `anchors`: `[{ time, price }]`
  - `payload`: `{ text: string }`
  - 渲染为一条短水平价格标记线加右侧文本标签
  - 文本标签允许编辑短文本，最长 24 个字符
  - `payload.text` 参与序列化、持久化和恢复
  - 首轮不支持多行文本、富文本或箭头注释

### 交互规则

基础交互采用统一规则：

- 工具栏切到某个绘图工具后，主图进入绘制模式
- 绘制完成后自动退回选择模式，避免连续误画
- 选择模式下点击对象可选中
- 选中对象显示锚点和高亮描边
- 拖动锚点修改形状
- 拖动对象本体整体平移
- `Delete/Backspace` 删除当前选中对象
- `Esc` 退出绘制或取消选中

首轮不做撤销/重做栈，但状态建模上保留将来补这个能力的空间，不把对象修改写死在 DOM 回调里。

### 交互状态机

首轮统一采用“选择模式 + 单工具绘制模式”的状态机：

- `idle`
  - 默认态，无对象选中
- `selected`
  - 某个对象被选中，可编辑样式、删除、拖拽
- `drawing`
  - 某个工具处于创建中
- `dragging-anchor`
  - 正在拖拽锚点
- `dragging-object`
  - 正在整体平移对象
- `editing-label`
  - 仅 `price_note` 文本编辑中

各工具的创建时序固定如下：

- 趋势线
  - 第一次点击落起点
  - 第二次点击落终点并完成创建
- 水平线
  - 单次点击按该价格创建，横向自动铺满可视区
- 矩形区间
  - 鼠标按下开始，拖拽预览，松开完成
- 斐波那契
  - 第一次点击落起点
  - 第二次点击落终点并立即生成默认 fib levels
- 价格标注
  - 单次点击创建价格标记线
  - 创建后立刻进入 `editing-label`
  - `Enter` 提交文本，`Esc` 取消编辑；若文本为空则保留默认标签为价格值

编辑规则：

- 锚点拖拽支持吸附到最近 candle 的时间槽位
- 价格不做离散吸附，保持连续值
- 对象本体拖拽时，所有锚点同步平移
- 锁定对象不可进入 `dragging-anchor` 或 `dragging-object`

切换股票、切换周期和数据重载时的进行中状态收尾规则：

- 若当前处于 `drawing` 且草稿对象尚未完成，直接取消草稿，不保存
- 若当前处于 `editing-label`：
  - 已输入文本非空则把文本写入 `payload.text` 后提交
  - 空文本则回退为默认价格标签后写入 `payload.text` 再提交
- 若当前处于 `dragging-anchor` 或 `dragging-object`，先按当前位置完成一次提交保存，再切换上下文
- 切换 `symbol` 前先 flush 当前 symbol 画线，再加载新 symbol 画线
- 切换周期不会清空当前 symbol 的画线集合，只触发覆盖层重映射和重新渲染

### 坐标映射

覆盖层不保存像素结果，只在渲染时把对象域坐标映射到当前图表像素坐标。

需要使用图表 API 完成：

- 时间值到 x 坐标的换算
- 价格值到 y 坐标的换算
- 监听图表尺寸变化和可视范围变化后重绘

这样画线可以跟随：

- 周期切换
- 图表缩放
- 横向滚动
- 容器宽度变化

跨周期和聚合后的锚点回退规则：

- 锚点时间始终保存为原始 ISO 日期字符串
- 渲染时先尝试精确匹配当前 candles 中同一 `time`
- 若不存在精确匹配，则回退到“时间上最近且不晚于原锚点”的 candle
- 若整个可见序列都晚于原锚点，则使用第一根 candle
- 若整个可见序列都早于原锚点，则使用最后一根 candle

这样可以让跨 `1D / 1W / 1M / 1Y` 周期时对象位置稳定，而不要求每个周期都存在完全相同的时间戳。

### 持久化边界

画线按股票单独保存到本地存储，key 结构采用：

- `news-caught:kline-drawings:<symbol>`

全局模板采用独立 key：

- `news-caught:kline-indicator-templates`
- `news-caught:kline-active-indicator-template`

localStorage 数据增加顶层版本包装：

- `version`
- `savedAt`
- `payload`

这是本轮最合适的边界，因为用户明确要求“画线按股票保存”，且当前项目没有用户账户体系，不值得上后端。

当切换股票时：

- 加载对应 symbol 的画线集合
- 当前 symbol 变化时自动保存旧 symbol 的最新对象状态
- 没有数据时回退为空列表

正常编辑过程中的保存策略：

- 创建对象后立即保存
- 拖拽结束后保存，不在每一帧拖动时落盘
- 样式修改、删除、锁定、可见性切换后立即保存
- 使用 150ms 级别的轻量 debounce 合并连续同步修改
- 页面 `beforeunload` 时执行一次 flush，降低刷新或关闭标签页时的丢失概率

异常处理：

- localStorage 配额不足时停止后续写入，保留当前内存态，并给出轻量错误提示
- 数据结构版本不匹配时优先尝试迁移；迁移失败则清理坏数据并回退为空状态
- 模板或画线 JSON 解析失败时只丢弃损坏 key，不影响 K 线主体渲染
- 多标签页并发修改简化为 `last write wins`
- 首轮不做 `storage` 事件同步、不做冲突提示、不做跨标签合并
- 当前标签页只保证本页刷新恢复；其他标签页同时修改的结果不保证即时可见

本轮验收要求默认包含“硬刷新后仍能恢复当前股票画线”和“硬刷新后仍能恢复模板库及最近使用模板”。

`news-caught:kline-active-indicator-template` 的作用域定义为：

- 单个浏览器全局共享
- 不按 symbol 保存
- 不按 tab 保存
- 表示“最近一次被应用到任意股票详情页的模板 id”

因此用户切换股票时默认沿用最近应用模板；多标签页下若被其他标签改写，也按 `last write wins` 处理。

## 指标导入与模板设计

### 指标范围

这轮把指标分成两类：

主图指标：

- `MA`
- `EMA`
- `BOLL`

副图指标：

- `VOL`
- `MACD`
- `KDJ`
- `RSI`

其中 `VOL/MACD/KDJ` 已经有现成渲染能力；`EMA/RSI` 需要补计算和渲染接入。

### 模板定义

指标模板不直接保存“当前所有 UI 状态”，而是保存一组可应用的配置：

- 模板 `id`
- 模板 `name`
- 模板 `scope` 固定为 `global`
- 主图指标数组
- 默认副图指标
- 创建来源 `preset` 或 `custom`

模板数据契约固定为：

- `overlayIndicators`
  - 数组
  - 每项包含 `kind`、`params`、`visible`
  - `kind` 只允许 `MA | EMA | BOLL`
- `subIndicator`
  - 单值
  - 只允许 `VOL | MACD | KDJ | RSI`
- `version`
  - number
  - 便于未来模板结构迁移

`params` 的首轮精确结构如下：

- `MA`
  - `{ periods: number[] }`
  - 默认值 `5 / 10 / 20 / 60`
  - 允许范围 `2..250`
  - 最多 6 条
  - 导入时去重、升序排序、过滤非法值
  - 结果为空则拒绝该模板
- `EMA`
  - `{ periods: number[] }`
  - 默认值 `12 / 26`
  - 允许范围 `2..250`
  - 最多 4 条
  - 导入时去重、升序排序、过滤非法值
  - 结果为空则拒绝该模板
- `BOLL`
  - `{ period: number, stdDev: number }`
  - 默认值 `20, 2`
  - `period` 允许范围 `5..250`
  - `stdDev` 允许范围 `1..4`，步长 `0.1`
  - 非法值直接拒绝，不做自动修正
- `RSI`
  - `{ period: number }`
  - 默认值 `14`
  - 允许范围 `2..100`
  - 非法值直接拒绝，不做自动修正

模板版本迁移策略：

- 首轮写入版本为 `1`
- 读取到缺失 `version` 的旧模板时按 `version=0` 处理，并尝试补齐默认字段迁移到 `1`
- 迁移失败的模板不应用，直接从模板库中过滤

模板导入与编辑校验规则：

- 内置模板始终保证合法，不经过用户校验流程
- 自定义模板保存前先做结构校验
- 周期数组类参数会“过滤非法值 -> 去重 -> 升序 -> 检查非空”
- 单值类参数若非法则直接阻止保存并提示用户
- 校验失败的模板不写入 localStorage

这里明确规定“副图一次只激活一个指标”，延续当前 K 线模块的交互，不在本轮扩展成多副图并列。

模板示例：

- `经典均线`：MA5 / MA10 / MA20 / MA60 + VOL
- `趋势跟随`：EMA12 / EMA26 / BOLL20,2 + MACD
- `震荡观察`：MA20 / BOLL20,2 + KDJ
- `强弱判断`：EMA12 / EMA26 + RSI14

### 导入方式

用户需要的两种导入方式对应为：

1. 一键导入内置模板
从预置模板列表中直接应用

2. 导入参数模板
从“常见模板库”中导入带参数配置，或基于现有模板复制一份后改参数保存

“导入参数模板”在 UI 上定义为两个具体动作：

- 从内置参数模板库点击“导入”，把该模板加入全局模板库并立即可应用
- 从当前已应用模板点击“另存为模板”，生成一份自定义模板并允许编辑名称

本轮不做自由公式编辑器；用户只能在受控表单中调整常见参数，例如：

- `MA`：周期数组，例如 `5 / 10 / 20 / 60`
- `EMA`：周期数组，例如 `12 / 26`
- `BOLL`：`period` 与 `stdDev`
- `RSI`：`period`

本轮不做文件上传导入，不做脚本文本解析。这里的“导入”定义为“把模板加入当前全局模板库并可一键应用”，而不是读外部文件。

### 模板管理规则

- 内置模板不可删除，但可以复制为自定义模板
- 自定义模板可重命名、覆盖保存、删除
- 当前股票应用哪个模板，不强制单独存档；默认使用最近一次应用的全局模板
- 副图一次只显示一个主副图指标，延续当前交互；模板决定默认副图类型
- 若当前 active template 被删除、迁移失败或读取不到，则自动回退到内置模板 `经典均线`
- 回退发生时同步重写 `news-caught:kline-active-indicator-template`，避免悬空 id 持续存在

### 指标数据来源

为了把这轮工作留在前端：

- 对已有 K 线 candles 使用前端纯函数计算 `EMA` 和 `RSI`
- 现有后端返回的 `MA/BOLL/MACD/KDJ` 继续沿用
- 前端把“需要显示哪些指标”与“实际可渲染的数据”解耦

这意味着首轮无需修改后端 API，也不需要迁移数据库。

## UI 设计

### 主图工具栏

在当前 K 线周期条同一层增加一个“画线工具簇”，位置放在主图上方工具条的右侧或第二行，避免塞进右侧指标栏导致主图交互割裂。

包含：

- 选择/移动
- 趋势线
- 水平线
- 矩形区间
- 斐波那契
- 价格标注
- 清空当前股票画线

交互要求：

- 当前工具有明显激活态
- 绘制模式时给主图容器加准星或工具提示
- 移动端仍能点击，但本轮优先保证桌面体验

### 覆盖层与图表手势协同

覆盖层和 `lightweight-charts` 的事件边界固定如下：

- 选择模式下：
  - 点击空白区域让事件透传给图表，保持原有 hover、crosshair 和拖拽平移
  - 点击命中对象时由覆盖层接管，进入选中或拖拽
- 绘制模式下：
  - 主图指针事件优先交给覆盖层，用于落点和预览
  - 鼠标滚轮缩放仍保留给图表
- 拖拽锚点或对象时：
  - 暂停图表横向平移，避免对象编辑和图表拖动同时触发
- `Esc` 退出绘制后恢复普通图表交互

重叠对象和视图变化规则：

- 命中检测按“可见对象逆序”执行，最后创建或最近操作的对象优先被选中
- 若多个对象重叠命中，本轮直接选中最上层对象，不做层级菜单
- 锁定对象仍可被命中查看样式，但不可拖拽修改
- 图表可视区变化时，覆盖层只重算像素位置，不修改对象域坐标
- 周期切换时保留同一股票的画线集合；若某些时间锚点在新周期下不可见，仅表现为暂时不在视区中
- 行情刷新或新 candle 到来时，不清空已绘对象；覆盖层根据最新比例尺重绘
- 副图区域不支持画线，本轮所有绘图仅限主图

### 指标工作台

把现有右侧“指标面板”升级成“指标工作台”，但不替换掉全部原有读数内容。

建议结构：

- 顶部：当前模板名称、快速应用按钮
- 中部：主图指标开关与参数摘要
- 下部：副图指标默认项与模板库列表
- 底部：导入模板、复制模板、重置为默认

这样用户不需要跳出当前终端视图，就能完成模板切换。

### 选中对象浮层

当对象被选中时，在图表右上或对象附近出现轻量浮层：

- 颜色
- 线宽
- 虚线/实线
- 锁定
- 删除

首轮不做复杂颜色面板，只提供一组固定终端风格色板。

## 首轮验收范围

首轮必须交付以下能力：

- 支持趋势线、水平线、矩形区间、斐波那契、价格标注五种工具
- 支持选择、拖拽锚点、整体移动、删除、锁定
- 画线按股票保存，并能在刷新页面后恢复
- 支持至少四个内置指标模板
- 支持从模板库导入参数模板，以及把当前模板另存为自定义模板
- 支持 `EMA` 与 `RSI` 的前端计算和渲染接入
- 模板库与最近使用模板可在刷新后恢复
- 不修改现有后端 K 线接口

不属于首轮验收：

- 撤销/重做
- 导入外部脚本或文件
- 多副图同时显示
- 多端同步

## 文件边界

建议新增或拆分的前端单元如下：

- `frontend/src/components/watchlist/KlineChart.vue`
  继续做总装配，但把绘图和模板逻辑下沉；仍负责接收 `klineData`、`currentPeriod`、`highlightedEventTime`，并继续向外发出 `focusNews`、`switchPeriod`

- `frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  负责覆盖层渲染、命中检测、鼠标事件和当前草稿对象预览

- `frontend/src/components/watchlist/KlineToolbar.vue`
  负责周期切换和绘图工具切换；周期切换仍透传为现有 `switchPeriod` 事件

- `frontend/src/components/watchlist/KlineIndicatorWorkbench.vue`
  负责模板应用、模板库、主图指标摘要和副图默认项；原本 `activeSubIndicator` 状态从 `KlineChart.vue` 挪到这里与模板状态统一管理

- `frontend/src/stores/watchlistChartStore.ts`
  负责当前工具、当前模板、全局模板库、按股票画线缓存、选中对象、当前副图指标和 localStorage 同步

- `frontend/src/utils/klineDrawings.ts`
  绘图对象类型、默认样式、序列化/反序列化、对象变更纯函数

- `frontend/src/utils/klineOverlayGeometry.ts`
  域坐标到像素坐标映射、命中检测、拖拽辅助计算

- `frontend/src/utils/klineIndicatorTemplates.ts`
  内置模板、模板校验、模板迁移和 localStorage 读写

- `frontend/src/utils/klineIndicators.ts`
  前端计算 EMA 和 RSI，并把模板映射成主图/副图渲染配置

这个拆分可以让图表渲染、绘图交互、模板管理分别测试，而不需要所有逻辑都塞在 `KlineChart.vue`。

与现有页面的边界保持如下：

- `StockDetailPanel.vue` 不感知新增画线细节，只继续把行情数据、周期、新闻高亮传给 `KlineChart`
- 新闻事件 chips 和相关新闻联动保持现状，不进入新的工作台 store
- 周期切换仍由 `watchlistStore.switchPeriod()` 驱动，不因画线系统改接口
- 现有副图切换入口改为模板工作台驱动，但仍保持“单副图指标”展示语义

状态归属表：

- `watchlistStore`
  - 唯一负责：`selectedSymbol`、`currentPeriod`、`klineData`、`klineLoading`、`klineError`
  - 不负责：画线对象、模板库、选中对象、工具模式
- `watchlistChartStore`
  - 唯一负责：当前工具、当前草稿对象、选中对象、按 symbol 画线集合、模板库、active template、副图指标
  - 只读取 `selectedSymbol` 与 `klineData` 作为上下文，不反向写入 `watchlistStore`
- `KlineChart.vue`
  - 作为组合层，把 `watchlistStore` 的行情数据和 `watchlistChartStore` 的工作台状态拼装到 UI
  - 不自行持有重复的长期状态；仅允许局部瞬态 DOM 状态

这意味着：

- `symbol` 与 `period` 的单一数据源始终是 `watchlistStore`
- 模板、画线和工具状态的单一数据源始终是 `watchlistChartStore`
- 两个 store 之间采用单向依赖：`watchlistChartStore` 读取 `watchlistStore` 当前上下文，但不直接修改它

公开动作与事件契约：

- `watchlistChartStore`
  - `hydrateForSymbol(symbol, candles)`
  - `selectTool(toolType | 'select')`
  - `startDraft(anchor)`
  - `updateDraft(anchor)`
  - `commitDraft()`
  - `cancelDraft()`
  - `selectDrawing(id | null)`
  - `updateDrawingAnchors(id, anchors)`
  - `moveDrawing(id, delta)`
  - `updateDrawingStyle(id, stylePatch)`
  - `commitLabelEdit(id, text)`
  - `deleteDrawing(id)`
  - `clearSymbolDrawings(symbol)`
  - `applyTemplate(templateId)`
  - `saveCustomTemplate(templateInput)`
  - `deleteCustomTemplate(templateId)`
  - `setSubIndicator(indicator)`

- `KlineDrawingOverlay.vue`
  - props: `candles`, `drawings`, `selectedDrawingId`, `activeTool`, `disabled`
  - emits: `draft-start`, `draft-update`, `draft-commit`, `draft-cancel`, `drawing-select`, `drawing-move`, `anchor-drag`, `label-edit`

- `KlineIndicatorWorkbench.vue`
  - props: `templates`, `activeTemplateId`, `subIndicator`, `disabled`
  - emits: `template-apply`, `template-save`, `template-delete`, `subindicator-change`

- `KlineToolbar.vue`
  - props: `currentPeriod`, `activeTool`, `drawingDisabled`
  - emits: `period-change`, `tool-change`, `clear-drawings`

## 错误处理与降级

### 绘图层

- localStorage 读写失败时，不阻塞图表渲染，只禁用持久化并给出轻量提示
- 反序列化失败时丢弃坏数据，回退为空画线集合
- 周期切换后如果部分锚点时间不在当前视图内，对象仍保留，只在可见范围内部分显示
- `klineData` 为空或加载中时不渲染覆盖层对象，不接受新建或编辑输入
- 没有 candles 数据时覆盖层进入只读空态，工具按钮显示禁用态

### 指标模板

- 模板结构校验失败时不应用该模板
- 当前模板引用到未支持指标时跳过该指标并记录控制台警告
- EMA/RSI 计算因数据量不足时，允许显示空段，不视为错误
- `klineData` 为空或 candles 为空时，指标工作台仍可展示模板列表，但“应用到图表”的按钮禁用
- loading 态下保留最近一次模板名称显示，但不渲染新的 overlay indicators，避免在空图上制造假状态

## 测试策略

### 单元测试

重点覆盖纯函数模块：

- 绘图对象序列化、反序列化、默认样式
- 趋势线/水平线/矩形/斐波那契/价格标注的命中检测
- 对象锚点更新与整体平移
- 模板导入、复制、删除、覆盖保存
- EMA/RSI 计算和模板映射

### 组件测试

重点覆盖：

- 工具栏切换后进入对应绘制模式
- 点击/拖拽创建对象
- 选中对象后删除
- 切换股票后恢复该股票画线
- 应用模板后主图图例和副图默认指标更新

### 构建验证

最小验证仍然是：

- `npm --prefix frontend run test -- --run ...`
- `npm --prefix frontend run build`

## 风险与取舍

### 风险 1：`lightweight-charts` 交互 API 对覆盖层支持有限

处理方式：

- 覆盖层只依赖现有图表公开坐标换算与容器尺寸，不直接侵入图表内部实现
- 如果个别坐标无法精确映射，优先保证趋势线和水平线体验，再细化矩形和斐波那契

### 风险 2：单文件复杂度再次膨胀

处理方式：

- 在本轮实现中强制拆出 overlay、toolbar、indicator workbench 与纯函数模块

### 风险 3：模板和现有指标渲染耦合过深

处理方式：

- 先做“模板 -> 渲染配置”的中间层，不让模板对象直接驱动 series 实例

## 实施结论

本轮按方案 B 实施：

- 保留现有 `lightweight-charts` 行情层
- 新增主图绘图覆盖层
- 引入全局指标模板库和按股票画线存储
- 在前端补足 `EMA/RSI` 计算
- 通过组件拆分和纯函数测试控制复杂度

这样可以在不改后端接口的前提下，把当前 K 线模块从“读图组件”升级为“可操作的看盘工作台”。
