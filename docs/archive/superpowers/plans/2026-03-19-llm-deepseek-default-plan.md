# LLM DeepSeek Default Persistence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让本地 LLM 默认配置稳定保持为 DeepSeek，刷新设置页时显示数据库中的真实值，并修复错误 DeepSeek 域名导致的 SSL 请求失败。

**Architecture:** 后端仍以 `llm_provider_config` 作为唯一真实来源，前端停止对 LLM 配置静默回退 mock。后端在保存 DeepSeek OpenAI-compatible 配置时规范化已知错误域名，前端通过真实错误态显示配置加载/保存失败。

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, Pinia, Vitest, pytest, SQLite

---

## File Map

- Modify: `backend/app/repositories/llm_provider_config_repository.py`
- Modify: `backend/tests/test_llm_config.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/stores/llmStore.ts`
- Modify: `frontend/src/views/LlmSettingsView.vue`
- Modify: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `docs/code-change-log.md`

## Chunk 1: Backend DeepSeek URL Normalization

### Task 1: Add failing repository/API test for mistaken DeepSeek host

**Files:**
- Modify: `backend/tests/test_llm_config.py`
- Test: `backend/tests/test_llm_config.py`

- [ ] **Step 1: Write the failing test**

```python
def test_post_llm_config_normalizes_known_deepseek_typo_host() -> None:
    response = client.post("/api/llm/config", json={... "base_url": "https://api.deepssek.com/v1"})
    assert response.json()["base_url"] == "https://api.deepseek.com/v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q -k typo_host`
Expected: FAIL because the response still returns the unnormalized typo host.

- [ ] **Step 3: Write minimal implementation**

在仓库层加入仅针对已知 DeepSeek 错拼 host 的规范化逻辑，再继续复用现有 upsert 流程。

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q -k typo_host`
Expected: PASS

## Chunk 2: Frontend Stop Mocking LLM Config

### Task 2: Add failing client tests for config fetch/save errors

**Files:**
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

- [ ] **Step 1: Write the failing tests**

```ts
it('does not fall back to mock llm config when loading config fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));
  await expect(apiClient.getLlmConfig()).rejects.toThrow('backend offline');
});
```

```ts
it('does not fall back to mock llm config when saving config fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));
  await expect(apiClient.saveLlmConfig({...})).rejects.toThrow('backend offline');
});
```

- [ ] **Step 2: Run test to verify they fail**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: FAIL because current implementation returns degraded mock data.

- [ ] **Step 3: Write minimal implementation**

让 `getLlmConfig()` 和 `saveLlmConfig()` 直接调用真实接口，不使用 `withMockFallback`。

- [ ] **Step 4: Run test to verify they pass**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: PASS

### Task 3: Add failing settings view test for load error state

**Files:**
- Modify: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `frontend/src/stores/llmStore.ts`
- Modify: `frontend/src/views/LlmSettingsView.vue`
- Test: `frontend/src/views/LlmSettingsView.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it('shows load error when llm config cannot be fetched', () => {
  llmStore.loadError = 'backend offline';
  const wrapper = mount(LlmSettingsView);
  expect(wrapper.text()).toContain('backend offline');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts`
Expected: FAIL because the store/view do not expose load errors yet.

- [ ] **Step 3: Write minimal implementation**

给 `llmStore` 增加 `loadError`，在 `loadConfig()` 捕获错误并保留；在视图中展示真实加载失败提示。

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts`
Expected: PASS

## Chunk 3: Local Data Repair And Verification

### Task 4: Repair the existing local config and verify end-to-end

**Files:**
- Modify: `backend/data/app.db`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the active local LLM config**

Run a targeted SQLite update so the currently active config uses `https://api.deepseek.com/v1`.

- [ ] **Step 2: Run focused verification**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q`
Expected: PASS

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts`
Expected: PASS

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Update change log**

记录本次真实修改、验证结果和剩余风险。
