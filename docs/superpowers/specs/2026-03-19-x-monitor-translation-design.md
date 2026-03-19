# X Monitor Translation Design

## Context

`X Monitor` 当前只展示英文帖子正文和“打开原帖”外链。用户不懂英文，希望在不改变跳转路径的前提下，按需把单条帖子翻译成中文。项目已经有可配置的 `LLM Settings` 和统一的后端 `openai_compatible` provider，因此翻译应复用现有后端配置，而不是把 API key 暴露到浏览器。

本设计按用户确认的边界执行：

- 保留现有 “打开原帖” 链接，不新增站内详情页
- 默认不自动翻译
- 每条帖子提供单独 “翻译” 按钮
- 翻译结果只缓存到当前页面会话，刷新后失效
- 使用后端统一代理调用 LLM provider

## Goals

- 让用户在 `X Monitor` 帖子列表里按需查看中文翻译
- 复用当前 LLM 配置能力，避免前端保存或暴露 API key
- 将改动限制在翻译相关路径，不影响现有刷新、搜索和外链行为

## Non-Goals

- 不做自动翻译批量预取
- 不持久化翻译到数据库
- 不改变 `twitterapi.io` 帖子采集和展示结构
- 不引入语言检测、术语词典或多语言切换

## Chosen Approach

### Backend

新增 `POST /api/llm/translate`：

- 请求体：`text`
- 响应体：`provider_name`、`model_name`、`translated_text`
- 行为：读取当前激活的 `LLMProviderConfig`，调用现有 `OpenAICompatibleProvider`
- prompt 固定为翻译用途：将社交帖文翻译为自然中文，保留 ticker、专有名词、emoji、语气和换行，不添加解释
- 为控制 provider 上下文长度，请求文本先做 `strip()`；若为空或超过 `4000` 字符，后端直接返回 `400`

错误处理：

- 未配置 provider：返回 `400`, `llm provider is not configured`
- `text` 为空或超过长度上限：返回 `400`
- provider 请求失败：返回 `502`，沿用现有 `LLMProviderError` 明确错误
- provider 返回空文本：视为无效翻译并返回 `502`

为避免把“翻译”逻辑硬塞进“分析 JSON”路径，`OpenAICompatibleProvider` 增加一个纯文本生成方法，专门处理普通文本响应。

### Frontend

`X Monitor` 列表和搜索结果中的每条帖子新增：

- `翻译` 按钮
- 翻译中态：按钮文案变为 `翻译中...`
- 成功态：正文下方显示中文翻译块
- 失败态：显示简短错误提示，可再次点击重试

状态存于 `xMonitorStore` 的页面内内存：

- `translationsByKey[translationKey]`
- 每条记录包含 `status`、`translated_text`、`error`
- `translationKey` 优先使用 `canonical_url`；若缺失，则退化为 `${account_handle}:${posted_at ?? captured_at}:${content_text}`
- 同一页面内若已有成功翻译，再次渲染直接复用，不重复请求
- 当帖子列表刷新或搜索结果变化时，不主动清空缓存；只要页面会话还在，同一 `translationKey` 继续复用

如果 LLM 未配置：

- 仍显示 `翻译` 按钮
- 点击后请求后端，由后端返回明确错误
- 前端把错误落到帖子级提示，避免把配置判断复制到多个组件

## Data Flow

1. 用户进入 `X Monitor`
2. 页面照常加载帖子列表，不发生翻译请求
3. 用户点击某条帖子的 `翻译`
4. 前端 store 计算该帖子的 `translationKey` 并标记为 `loading`
5. 前端调用 `POST /api/llm/translate`
6. 后端读取激活 LLM 配置并调用 provider
7. 成功后返回中文文本
8. 前端更新该 `translationKey` 对应的翻译缓存并渲染翻译块

## Testing Strategy

### Backend

- 路由测试：未配置 LLM 时返回 400
- 路由测试：空文本和超长文本返回 400
- 路由测试：provider 返回文本时透传 `provider_name`、`model_name` 和翻译结果
- 路由测试：provider 返回空内容或抛错时返回 502

### Frontend

- 视图测试：帖子项显示 `翻译` 按钮
- store/视图测试：点击按钮后调用翻译动作并展示翻译文本
- 视图测试：翻译失败时显示帖子级错误提示
- 视图测试：搜索结果与监控列表使用相同缓存逻辑，但不会因为 `post.id` 冲突而串译

## Risks

- 列表页可同时存在多条并发翻译请求，当前设计接受这一点，不额外做全局并发限制
- 如果未来 provider 改成只支持 JSON 输出，文本翻译方法需要再适配不同响应格式
- 缓存键依赖 `canonical_url` 或内容级回退串；如果后端将来调整 X 帖子唯一标识，前端需要同步更新该键生成规则
