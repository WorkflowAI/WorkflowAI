import { useEffect, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

type TagPopoverProps = {
  text: string;
  onAddTag: (tag: string) => void;
  tags?: string[];
};

export function TagPopover(props: TagPopoverProps) {
  const { text, onAddTag, tags } = props;
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filteredTags = useMemo(() => {
    if (!tags || tags.length === 0) {
      return undefined;
    }

    const lowerCaseText = text.toLowerCase().trim();
    return tags.filter((tag) => tag.toLowerCase().trim().startsWith(lowerCaseText));
  }, [tags, text]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [filteredTags]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!filteredTags) return;

      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((prev) => (prev > 0 ? prev - 1 : filteredTags.length - 1));
          break;
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((prev) => (prev < filteredTags.length - 1 ? prev + 1 : 0));
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [filteredTags, selectedIndex, onAddTag]);

  if (!filteredTags || filteredTags.length === 0) {
    return null;
  }

  return (
    <div className='flex flex-col pt-2.5 bg-white rounded-[2px] border border-gray-300 shadow-xl min-w-[240px] tag-popover'>
      <div className='text-indigo-600 font-semibold text-[12px] px-3'>INPUT VARIABLES</div>
      <div className='flex flex-col w-full py-2 px-1'>
        {filteredTags.map((tag, index) => (
          <div
            key={tag}
            className={cn(
              'flex w-full text-gray-700 font-normal text-[13px] cursor-pointer h-8 items-center rounded-[2px] px-2',
              index === selectedIndex && 'bg-gray-100 tag-item'
            )}
            onClick={() => onAddTag(tag)}
          >
            {`{x} ${tag}`}
          </div>
        ))}
      </div>
    </div>
  );
}
