<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { apiClient } from '../../api/client';
import type { ImpactDirection, ImpactInput, ImpactStrength, ImpactTargetType, NewsAi } from '../../types/api';
import {
  DIRECTION_LABELS,
  DIRECTION_OPTIONS,
  STRENGTH_LABELS,
  STRENGTH_OPTIONS,
  TARGET_TYPE_LABELS,
  TARGET_TYPE_OPTIONS,
  impactChipText,
  impactChipTone,
  importanceLabel,
  importanceTone,
} from '../../utils/aiImpact';

const props = defineProps<{
  newsId: number;
}>();

const payload = ref<NewsAi | null>(null);
const loading = ref(false);
const loadError = ref<string | null>(null);
let loadSeq = 0;

const screen = computed(() => payload.value?.screen ?? null);
const analysis = computed(() => payload.value?.analysis ?? null);
const impacts = computed(() => payload.value?.impacts ?? []);

// --- 修正（编辑）态：草稿只在本地，保存时整表 PUT，取消即丢弃 ---
type DraftRow = ImpactInput & { key: number; source: 'ai' | 'user' };

const editing = ref(false);
const drafts = ref<DraftRow[]>([]);
const note = ref('');
const saving = ref(false);
const saveError = ref<string | null>(null);
let draftKey = 0;

const addForm = reactive({
  target_type: 'stock' as ImpactTargetType,
  name: '',
  code: '',
  direction: 'bullish' as ImpactDirection,
  strength: 'medium' as ImpactStrength,
  rationale: '',
});

function resetAddForm() {
  addForm.target_type = 'stock';
  addForm.name = '';
  addForm.code = '';
  addForm.direction = 'bullish';
  addForm.strength = 'medium';
  addForm.rationale = '';
}

function startEdit() {
  drafts.value = impacts.value.map((impact) => ({
    key: ++draftKey,
    source: impact.source,
    target_type: impact.target_type,
    code: impact.code ?? null,
    name: impact.name,
    direction: impact.direction,
    strength: impact.strength,
    rationale: impact.rationale ?? null,
  }));
  note.value = '';
  saveError.value = null;
  resetAddForm();
  editing.value = true;
}

function cancelEdit() {
  editing.value = false;
  drafts.value = [];
  note.value = '';
  saveError.value = null;
  resetAddForm();
}

function removeDraft(key: number) {
  drafts.value = drafts.value.filter((row) => row.key !== key);
}

function addDraft() {
  const name = addForm.name.trim();
  if (!name) {
    saveError.value = '请填写名称后再添加';
    return;
  }
  saveError.value = null;
  drafts.value.push({
    key: ++draftKey,
    source: 'user',
    target_type: addForm.target_type,
    code: addForm.code.trim() || null,
    name,
    direction: addForm.direction,
    strength: addForm.strength,
    rationale: addForm.rationale.trim() || null,
  });
  resetAddForm();
}

async function save() {
  saving.value = true;
  saveError.value = null;
  const impactsPayload: ImpactInput[] = drafts.value.map((row) => ({
    target_type: row.target_type,
    code: row.code,
    name: row.name,
    direction: row.direction,
    strength: row.strength,
    rationale: row.rationale,
  }));
  const trimmedNote = note.value.trim();
  const targetNewsId = props.newsId;
  try {
    const response = await apiClient.updateNewsImpacts(targetNewsId, {
      impacts: impactsPayload,
      ...(trimmedNote ? { note: trimmedNote } : {}),
    });
    // 保存途中切换了新闻：旧新闻的结果不能显示到新新闻上（否则再次"修正"会把它写进新新闻）。
    if (targetNewsId !== props.newsId) {
      return;
    }
    payload.value = response.data;
    cancelEdit();
  } catch (error) {
    if (targetNewsId === props.newsId) {
      saveError.value = `保存失败：${error instanceof Error ? error.message : '请稍后再试'}`;
    }
  } finally {
    saving.value = false;
  }
}

async function load(newsId: number) {
  const seq = ++loadSeq;
  loading.value = true;
  loadError.value = null;
  try {
    const response = await apiClient.getNewsAi(newsId);
    if (seq === loadSeq) {
      if (response.degraded) {
        // 后端不可用时 client 会退回演示数据：既不能当真展示，更不能在其上"修正"后整表覆盖真实结果。
        payload.value = null;
        loadError.value = '后端暂不可用，AI 结论未加载';
      } else {
        payload.value = response.data ?? null;
      }
    }
  } catch (error) {
    if (seq === loadSeq) {
      payload.value = null;
      loadError.value = error instanceof Error ? error.message : '加载 AI 结论失败';
    }
  } finally {
    if (seq === loadSeq) {
      loading.value = false;
    }
  }
}

onMounted(() => {
  void load(props.newsId);
});

watch(
  () => props.newsId,
  (next) => {
    cancelEdit();
    void load(next);
  },
);

const selectClass =
  'rounded-[10px] border border-border bg-black/20 px-2 py-1 text-xs text-text outline-none focus:border-system/40';
const inputClass =
  'rounded-[10px] border border-border bg-black/20 px-2.5 py-1.5 text-sm text-text outline-none focus:border-system/40';
</script>

<template>
  <SectionCard title="AI 影响" subtitle="AI 粗筛与精读结论、利多/利空标的；判断不准可以直接修正" data-role="news-ai-card">
    <template #actions>
      <button
        v-if="!editing && !loading && !loadError"
        type="button"
        class="shrink-0 rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent transition hover:bg-accent/20"
        data-role="news-ai-edit"
        @click="startEdit"
      >
        修正
      </button>
    </template>

    <p v-if="loading" class="text-sm text-text-faint">加载 AI 结论…</p>
    <div v-else class="grid gap-3.5">
      <p v-if="loadError" class="text-sm text-danger" data-role="news-ai-load-error">{{ loadError }}</p>
      <p v-else-if="!screen" class="text-sm text-text-faint" data-role="news-ai-not-screened">AI 尚未处理这条新闻</p>
      <template v-else>
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <span class="rounded-full border px-2 py-0.5 font-semibold" :class="importanceTone(screen.importance)" data-role="news-ai-importance">
            {{ importanceLabel(screen.importance) }}
          </span>
          <span
            v-if="screen.overseas"
            class="rounded-full border border-system/40 bg-system/10 px-2 py-0.5 text-system"
            data-role="news-ai-overseas"
          >
            海外
          </span>
          <span v-if="screen.status === 'error'" class="text-danger">AI 粗筛失败</span>
        </div>
        <p v-if="screen.title_zh" class="m-0 text-base font-semibold text-text" data-role="news-ai-title-zh">{{ screen.title_zh }}</p>

        <template v-if="analysis">
          <p v-if="analysis.status === 'error'" class="m-0 text-sm text-danger" data-role="news-ai-analysis-error">
            AI 精读失败：{{ analysis.error || '未知错误' }}
          </p>
          <template v-else>
            <p v-if="analysis.summary_zh" class="m-0 text-sm leading-6 text-text-soft" data-role="news-ai-summary">{{ analysis.summary_zh }}</p>
            <div
              v-if="analysis.view"
              class="rounded-lg border border-ai/40 bg-ai/10 px-3.5 py-2.5"
              data-role="news-ai-view"
            >
              <p class="m-0 text-[11px] font-semibold tracking-[0.12em] text-ai">明确看法</p>
              <p class="m-0 mt-1 text-sm font-semibold text-text">{{ analysis.view }}</p>
            </div>
          </template>
        </template>
        <div v-else-if="!screen.deep_read" class="grid gap-1 text-sm" data-role="news-ai-not-deep-read">
          <p v-if="screen.reason" class="m-0 text-text-soft">{{ screen.reason }}</p>
          <p class="m-0 text-text-faint">未达精读标准</p>
        </div>
        <p v-else class="m-0 text-sm text-text-faint" data-role="news-ai-pending">已列入精读，等待 AI 分析…</p>
      </template>

      <!-- 只读影响列表 -->
      <template v-if="!editing">
        <ul v-if="impacts.length > 0" class="grid gap-2" data-role="news-ai-impacts">
          <li
            v-for="impact in impacts"
            :key="impact.id"
            class="grid gap-1 rounded-lg border border-border bg-panel-strong px-3.5 py-2.5"
            data-role="news-ai-impact-row"
          >
            <div class="flex flex-wrap items-center gap-2 text-sm">
              <strong class="text-text">{{ impact.name }}</strong>
              <span v-if="impact.code" class="font-mono text-xs text-text-faint">{{ impact.code }}</span>
              <span class="text-[11px] text-text-faint">{{ TARGET_TYPE_LABELS[impact.target_type] }}</span>
              <span
                class="rounded-full border px-2 py-0.5 text-xs font-semibold"
                :class="impactChipTone(impact.direction)"
                data-role="news-ai-impact-chip"
              >
                {{ impactChipText(impact.direction, impact.strength) }}
              </span>
              <span
                v-if="impact.source === 'user'"
                class="rounded-full border border-accent/40 px-2 py-0.5 text-[11px] text-accent"
                data-role="news-ai-impact-corrected"
              >
                已修正
              </span>
            </div>
            <p v-if="impact.rationale" class="m-0 text-sm text-text-soft">{{ impact.rationale }}</p>
          </li>
        </ul>
        <p v-else-if="analysis && analysis.status !== 'error'" class="m-0 text-sm text-text-faint" data-role="news-ai-no-impacts">
          AI 未发现受明确影响的个股或板块
        </p>
      </template>

      <!-- 修正态 -->
      <div v-else class="grid gap-3" data-role="news-ai-editor">
        <ul v-if="drafts.length > 0" class="grid gap-2">
          <li
            v-for="row in drafts"
            :key="row.key"
            class="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-panel-strong px-3 py-2 text-sm"
            data-role="news-ai-draft-row"
          >
            <strong class="text-text">{{ row.name }}</strong>
            <span v-if="row.code" class="font-mono text-xs text-text-faint">{{ row.code }}</span>
            <span class="text-[11px] text-text-faint">{{ TARGET_TYPE_LABELS[row.target_type] }}</span>
            <select v-model="row.direction" :class="selectClass" aria-label="方向" data-role="news-ai-row-direction">
              <option v-for="option in DIRECTION_OPTIONS" :key="option" :value="option">{{ DIRECTION_LABELS[option] }}</option>
            </select>
            <select v-model="row.strength" :class="selectClass" aria-label="强度" data-role="news-ai-row-strength">
              <option v-for="option in STRENGTH_OPTIONS" :key="option" :value="option">{{ STRENGTH_LABELS[option] }}</option>
            </select>
            <button
              type="button"
              class="ml-auto rounded-full px-2 py-0.5 text-xs text-text-faint transition hover:bg-danger/15 hover:text-danger"
              data-role="news-ai-row-delete"
              @click="removeDraft(row.key)"
            >
              删除
            </button>
            <p v-if="row.rationale" class="m-0 basis-full text-xs text-text-faint">{{ row.rationale }}</p>
          </li>
        </ul>
        <p v-else class="m-0 text-sm text-text-faint">当前没有影响标的；保存空列表表示这条新闻不影响任何标的。</p>

        <div class="grid gap-2 rounded-lg border border-dashed border-border px-3 py-2.5" data-role="news-ai-add-form">
          <p class="m-0 text-xs font-semibold text-muted">添加标的</p>
          <div class="flex flex-wrap items-center gap-2">
            <select v-model="addForm.target_type" :class="selectClass" aria-label="类型" data-role="news-ai-add-type">
              <option v-for="option in TARGET_TYPE_OPTIONS" :key="option" :value="option">{{ TARGET_TYPE_LABELS[option] }}</option>
            </select>
            <input
              v-model="addForm.name"
              type="text"
              :placeholder="addForm.target_type === 'stock' ? '股票名称' : '板块名称'"
              :class="[inputClass, 'w-32']"
              data-role="news-ai-add-name"
            />
            <input
              v-model="addForm.code"
              type="text"
              placeholder="代码（可选）"
              :class="[inputClass, 'w-32']"
              data-role="news-ai-add-code"
            />
            <select v-model="addForm.direction" :class="selectClass" aria-label="方向" data-role="news-ai-add-direction">
              <option v-for="option in DIRECTION_OPTIONS" :key="option" :value="option">{{ DIRECTION_LABELS[option] }}</option>
            </select>
            <select v-model="addForm.strength" :class="selectClass" aria-label="强度" data-role="news-ai-add-strength">
              <option v-for="option in STRENGTH_OPTIONS" :key="option" :value="option">{{ STRENGTH_LABELS[option] }}</option>
            </select>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <input
              v-model="addForm.rationale"
              type="text"
              placeholder="理由（可选）"
              :class="[inputClass, 'min-w-0 flex-1']"
              data-role="news-ai-add-rationale"
            />
            <button
              type="button"
              class="rounded-full border border-border px-3 py-1 text-xs text-text-soft transition hover:text-text"
              data-role="news-ai-add-submit"
              @click="addDraft"
            >
              添加
            </button>
          </div>
        </div>

        <textarea
          v-model="note"
          rows="2"
          placeholder="说明，会作为 AI 以后判断的参考"
          :class="[inputClass, 'w-full resize-y']"
          data-role="news-ai-note"
        />

        <p v-if="saveError" class="m-0 text-sm text-danger" data-role="news-ai-save-error">{{ saveError }}</p>

        <div class="flex items-center justify-end gap-2">
          <button
            type="button"
            class="rounded-full border border-border px-4 py-1.5 text-sm text-text-soft transition hover:text-text"
            data-role="news-ai-cancel"
            :disabled="saving"
            @click="cancelEdit"
          >
            取消
          </button>
          <button
            type="button"
            class="rounded-full bg-accent px-4 py-1.5 text-sm font-semibold text-bg transition hover:brightness-110 disabled:cursor-progress disabled:opacity-60"
            data-role="news-ai-save"
            :disabled="saving"
            @click="save"
          >
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </SectionCard>
</template>
