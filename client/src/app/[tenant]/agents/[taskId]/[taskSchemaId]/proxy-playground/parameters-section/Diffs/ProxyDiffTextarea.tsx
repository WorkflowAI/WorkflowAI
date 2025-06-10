import { diffWords } from 'diff';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';

type Props = {
  newText: string | undefined;
  oldText: string | undefined;
};

// Helper to flatten diff parts into a single string with metadata
function flattenDiffParts(diff: { value: string; added?: boolean; removed?: boolean }[]) {
  const flat: { char: string; added?: boolean; removed?: boolean }[] = [];
  diff.forEach((part) => {
    for (let i = 0; i < part.value.length; i++) {
      flat.push({ char: part.value[i], added: part.added, removed: part.removed });
    }
  });
  return flat;
}

// Helper to find all {{...}} ranges in a string
function findDoubleCurlyRanges(text: string) {
  const ranges: { start: number; end: number }[] = [];
  let idx = 0;
  while (idx < text.length) {
    const start = text.indexOf('{{', idx);
    if (start === -1) break;
    const end = text.indexOf('}}', start + 2);
    if (end === -1) break;
    ranges.push({ start, end: end + 2 });
    idx = end + 2;
  }
  return ranges;
}

// Helper to check if a char index is inside any of the ranges
function isInRanges(idx: number, ranges: { start: number; end: number }[]) {
  return ranges.some((r) => idx >= r.start && idx < r.end);
}

export function ProxyDiffTextarea(props: Props) {
  const { newText, oldText } = props;

  const diff = useMemo(() => {
    return diffWords(oldText ?? '', newText ?? '');
  }, [newText, oldText]);

  // Flatten diff parts to char array with metadata
  const flat = useMemo(() => flattenDiffParts(diff), [diff]);
  // Reconstruct the full string
  const fullText = flat.map((f) => f.char).join('');
  // Find all {{...}} ranges
  const curlyRanges = useMemo(() => findDoubleCurlyRanges(fullText), [fullText]);

  // Group chars by contiguous style (added/removed/bold)
  const grouped: { text: string; added?: boolean; removed?: boolean; bold?: boolean }[] = [];
  let current: { added?: boolean; removed?: boolean; bold?: boolean } | null = null;
  let buffer = '';
  for (let i = 0; i < flat.length; i++) {
    const meta = flat[i];
    const bold = isInRanges(i, curlyRanges);
    if (!current || current.added !== meta.added || current.removed !== meta.removed || current.bold !== bold) {
      if (buffer) grouped.push({ ...current, text: buffer });
      buffer = '';
      current = { added: meta.added, removed: meta.removed, bold };
    }
    buffer += meta.char;
  }
  if (buffer) grouped.push({ ...current, text: buffer });

  return (
    <div className='text-gray-900 font-normal text-[13px] whitespace-pre-wrap'>
      <div className='px-3'>
        {grouped.map((part, idx) => (
          <span
            key={idx}
            className={cn({
              'bg-green-100 text-green-800 rounded px-0.5': part.added,
              'bg-red-100 text-red-800 rounded px-0.5': part.removed,
              'font-bold': part.bold,
            })}
          >
            {part.text}
          </span>
        ))}
      </div>
    </div>
  );
}
