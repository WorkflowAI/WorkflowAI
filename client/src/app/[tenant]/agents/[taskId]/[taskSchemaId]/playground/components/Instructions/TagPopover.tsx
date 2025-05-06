import { Add20Regular } from '@fluentui/react-icons';
import { Button } from '@/components/ui/Button';

type TagPopoverProps = {
  text: string;
  onAddTag: (tag: string) => void;
};

export function TagPopover(props: TagPopoverProps) {
  const { text, onAddTag } = props;

  const tags = ['animal', 'color', 'food', 'sport', 'object', 'person'];

  return (
    <div className='flex flex-col pt-2.5 bg-white rounded-[2px] border border-gray-300 shadow-xl min-w-[240px]'>
      <div className='text-indigo-600 font-semibold text-[12px] px-3'>INPUT VARIABLES</div>
      <div className='flex flex-col w-full py-2 px-3'>
        {tags.map((tag) => (
          <div
            key={tag}
            className='flex w-full text-gray-700 font-normal text-[13px] cursor-pointer h-8 items-center'
            onClick={() => onAddTag(tag)}
          >
            {`{x} ${tag}`}
          </div>
        ))}
      </div>
      <div className='flex w-full border-t border-gray-200 p-2'>
        <Button variant='newDesignGray' icon={<Add20Regular />} className='flex w-full'>
          Add New Input Variable
        </Button>
      </div>
    </div>
  );
}
