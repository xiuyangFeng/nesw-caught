# LLM Settings Terminal Input Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove bright white input backgrounds from LLM Settings and bring the page into the same dark terminal form system.

**Architecture:** Keep the existing LLM settings data flow unchanged while updating only the view-layer form hooks and styles. Lock the new terminal field hook with a failing test before editing production styles.

**Tech Stack:** Vue 3, TypeScript, Vitest, scoped CSS

---

## Chunk 1: Test Terminal Field Hooks

### Task 1: Add a failing test for terminal form fields

**Files:**
- Modify: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `frontend/src/views/LlmSettingsView.vue`

- [ ] **Step 1: Write the failing test**

```ts
expect(wrapper.find('[data-surface="terminal-field"]').exists()).toBe(true);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts`
Expected: FAIL because the new terminal field hook does not exist yet.

- [ ] **Step 3: Add minimal implementation**

Add `data-surface="terminal-field"` to the form inputs and keep existing submit behavior intact.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts`
Expected: PASS

## Chunk 2: Implement Terminal Input Styling

### Task 2: Replace bright form fields with dark terminal inputs

**Files:**
- Modify: `frontend/src/views/LlmSettingsView.vue`

- [ ] **Step 1: Replace white input backgrounds**

Use `var(--field-bg)` and terminal border colors instead of `#fff`.

- [ ] **Step 2: Improve label and helper readability**

Promote labels and helper text to `var(--text-faint)` / `var(--text-soft)` as appropriate.

- [ ] **Step 3: Align button and status text**

Use the same terminal button gradient and cleaner status text colors already used elsewhere.

## Chunk 3: Verification And Records

### Task 3: Update records and verify

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Record the LLM Settings form input contrast polish.

- [ ] **Step 2: Run targeted tests**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts`
Expected: PASS

- [ ] **Step 3: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS
