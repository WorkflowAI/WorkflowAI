import { diffWords } from 'diff';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';

type Props = {
  newText: string | undefined;
  oldText: string | undefined;
};

export function ProxyDiffTextarea(props: Props) {
  const { newText, oldText } = props;

  const diff = useMemo(() => {
    return diffWords(oldText ?? '', newText ?? '');
  }, [newText, oldText]);

  return (
    <div className='text-gray-900 font-normal text-[13px] whitespace-pre-wrap'>
      <div className='px-3'>
        {diff.map((part, index) => {
          if (!part.value) return null;
          return (
            <span
              key={index}
              className={cn({
                'bg-green-100 text-green-800 rounded px-0.5': part.added,
                'bg-red-100 text-red-800 rounded px-0.5': part.removed,
              })}
            >
              {part.value}
            </span>
          );
        })}
      </div>
    </div>
  );
}
