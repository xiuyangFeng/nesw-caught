# 2026-06-13 本地与网络安全加固设计

## 1. 目标与背景
本项目的新闻抓取、大模型聊天以及飞书通知系统在本地运行。用户要求从网络安全等方面，保证所有的 Key、密钥均在本地且不可被窃取。
经排查，目前项目存在以下几个重大的安全漏洞和隐患：
1. **接口完全未授权访问，且绑定了 0.0.0.0：**
   - 后端使用 `uvicorn` 启动时默认监听 `0.0.0.0:8000`，允许外部（如局域网、公网）未经授权直接发起请求。由于项目包含大模型调用、修改配置等重要 API，这有被盗刷或盗取配置的风险。
2. **通过配置篡改 API 基址窃取明文 Key：**
   - 在修改大模型 `base_url` 时，系统允许不输入明文 `api_key`（即保留带星号的掩码）。如果恶意外部用户（或 CSRF）发送请求把大模型基址修改为恶意第三方服务器，后续任何聊天、翻译等 AI 请求，都会将解密后的真实明文 `api_key` 以 `Authorization: Bearer <key>` 发送到这个恶意服务器，导致 Key 被窃取。
3. **飞书密钥明文存储：**
   - 数据库中的 `feishu_notify_config` 表以明文保存了飞书的 `app_secret`，相比 LLM 的 `api_key` 加密，这在本地数据库泄漏时有一定安全隐患。
4. **Git 泄漏防护不足：**
   - `.gitignore` 规则偏向粗放，且没有离线的静态密钥检查，开发者可能会不小心提交包含密钥的文件。

本设计旨在彻底消除这些隐患，构建多层本地与网络安全防线。

---

## 2. 详细设计

### 2.1 引入本地临时应用认证令牌 (App Token) 机制

**机制说明**：
为了只允许本地的前端服务访问后端 API，防止外部未授权请求或恶意网页通过跨站请求篡改本地配置：
1. **Token 的产生与存取**：
   - 后端在启动（`lifespan` 阶段）时，检查并在本地安全数据目录 `data/.app_token` 自动生成一个强随机生成的 32 字节十六进制 Token。
   - 对文件应用 `chmod 600` 权限，确保仅当前系统用户可读写该文件。
2. **前端自动注入 Token**：
   - 因为前端项目也在本地编译/开发：
     - 在开发阶段：Vite 运行在 Node.js 中，Node.js 可以安全地读取物理路径上的 `../data/.app_token`。
     - 在编译阶段（构建静态 HTML 时）：Node 同样可以读取该 Token。
   - 在 `vite.config.ts` 中，使用 `define: { __APP_TOKEN__: JSON.stringify(token) }` 将该 Token 作为全局常量注入前端 JavaScript 中。
3. **前端请求自动携带 Token**：
   - 在前端主入口处，通过 Monkey patch 的方式包装全局的 `window.fetch`。在每次向 `/api/*` 发起请求时，如果 `__APP_TOKEN__` 存在，则自动添加请求头 `X-App-Token: <token>`。该方式能够一劳永逸地覆盖所有的 `fetch` 请求（包含直接请求和封装库）。
4. **后端路由安全校验**：
   - 编写 FastAPI 依赖 `verify_app_token`，校验 Request Headers 中的 `X-App-Token` 是否与本地读取的 `data/.app_token` 一致。如果请求不符，抛出 `401 Unauthorized` 异常。
   - 该依赖项全局应用到 `/api` 路由，仅放行无需鉴权的 `/api/health`（为防外部监控可用，但其余所有业务接口均加锁）。
5. **服务绑定回路**：
   - 在 `Makefile` 和 `scripts/dev.sh` 中，把 `uvicorn` 和 `npm run dev` 的绑定 host 默认改回 `127.0.0.1`，不默认向整个局域网公开。

### 2.2 防御 Base URL 劫持窃取 API Key 的机制

**机制说明**：
1. 在大模型配置保存方法 `LLMProviderConfigRepository.upsert_config` 中，添加强安全约束：
   - 在更新配置时，如果用户提交的配置中大模型的 `base_url` 与数据库中原有的 `base_url` 不一致（表示正在修改 URL），则提交的 `api_key` **绝不能**使用带星号掩码星号的值（如 `sk-***` 等）或为 `None`/空。
   - 如果检测到 `base_url` 被修改，但 `api_key` 却依然是已掩码值或未填，系统应当**抛出异常阻止保存**，或者强制将 API Key 字段置空。
   - **设计选择**：我们选择抛出 `ValueError` 以通知用户：“修改 base_url 时必须重新输入明文 API Key，不能重用已有的掩码 Key。”
   - 这样即使有局域网内的其它来源、或者恶意第三方网页通过伪造请求，想通过更改大模型 API 地址来引流和捕获 Key，也由于它们不知道原 Key 的明文，一旦修改基址，修改请求就会被拦截，原 Key 绝不会发送到新基址。

### 2.3 飞书密钥 (app_secret) 本地加密存储

**机制说明**：
1. 数据库存储的 `FeishuNotifyConfig.app_secret` 目前是明文。
2. 我们要在 `FeishuNotifyConfig` 实体中使用 `app.core.crypto` 的 `encrypt_key` 和 `decrypt_key` 算法。
3. 在 `FeishuNotifyConfigRepository.upsert` 时，对输入的 `app_secret`（如果提供了明文）使用 `encrypt_key` 加密后再保存入库。
4. 在 `FeishuNotifyConfig` 模型中，添加 `decrypted_app_secret` 属性，暴露解密后的密钥。
5. 替换所有用到飞书 `app_secret` 的调用点（例如 `FeishuClient` 的初始化、`notification_service.py` 里的发送等），全部使用解密后的值。

### 2.4 本地 Git 提交防泄漏与静态密钥检查

**机制说明**：
1. 优化根目录下的 `.gitignore` 文件，加入：
   ```gitignore
   **/.secret_key
   **/.app_token
   **/.env*
   **/news_caught.db
   ```
2. 编写一个静态密钥检查脚本 `scripts/check_secrets.py`。该脚本可遍历项目中的敏感文件，并用正则表达式检查是否包含了疑似未被加密的真实大模型 API key（例如 `sk-[a-zA-Z0-9]{48}` 或 Tavily 真实 Key 等），并在检测到泄漏风险时及时拦截和输出警告。

---

## 3. 验证方案

1. **后端单元测试 (TDD)**：
   - 编写 `backend/tests/test_security.py`，测试 `verify_app_token` 依赖。
   - 编写 `backend/tests/test_llm_base_url_safety.py`，验证当修改 `base_url` 却未重新输入明文 `api_key` 时，系统抛出 `ValueError`。
   - 在 `backend/tests/test_feishu_notify.py` 中，验证存储的 `app_secret` 被正确加密且可解密使用。
2. **前后端联调测试**：
   - 启动本地服务，验证前端界面正常通过 `X-App-Token` 与后端通信。
   - 确认在非 127.0.0.1 或无 Token 情况下访问接口直接被返回 401 拦截。
