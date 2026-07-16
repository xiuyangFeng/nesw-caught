import type { EditorialStoryEntry } from './newsEditorial';

export interface FoldedStream {
  visible: EditorialStoryEntry[];
  folded: EditorialStoryEntry[];
}

const MIN_VISIBLE = 10;
const FOLD_PERCENTILE = 0.7;
const MIN_FOLD_SIZE = 3;

/**
 * 把已按编辑分降序的流切成「可见段 + 折叠段」。
 * 折叠段 = 排名 P70 之后的尾部;不足 MIN_FOLD_SIZE 条就不折叠(避免「已折叠 1 条」)。
 */
export function partitionFoldableStream(entries: EditorialStoryEntry[]): FoldedStream {
  const cutoff = Math.max(MIN_VISIBLE, Math.ceil(entries.length * FOLD_PERCENTILE));
  if (entries.length - cutoff < MIN_FOLD_SIZE) {
    return { visible: entries, folded: [] };
  }
  return { visible: entries.slice(0, cutoff), folded: entries.slice(cutoff) };
}
