import Image from 'next/image';
import { useCallback } from 'react';
import { useCopyToClipboard } from 'usehooks-ts';
import { Button } from '@/components/ui/Button';
import { displaySuccessToaster } from '@/components/ui/Sonner';

type Props = {
  title: string;
  description: string;
  imageURL: string;
  prompt: string;
};

export function ProxyNewAgentPromptComponent(props: Props) {
  const { title, description, imageURL, prompt } = props;
  const [, copy] = useCopyToClipboard();

  const onCopy = useCallback(() => {
    copy(prompt);
    displaySuccessToaster('Copied to clipboard');
  }, [copy, prompt]);

  return (
    <div className='flex flex-col gap-4 w-full p-4 bg-white rounded-[2px] border border-gray-200'>
      <div className='flex flex-row gap-2 justify-between w-full'>
        <div className='flex flex-col gap-1'>
          <div className='text-gray-900 text-[16px] font-semibold'>{title}</div>
          <div className='text-gray-500 text-[13px] font-normal'>{description}</div>
        </div>
        <Button variant='newDesignGray' size='sm' onClick={onCopy}>
          Copy Prompt
        </Button>
      </div>
      <Image src={imageURL} alt='Image' width={560} height={200} className='w-full h-full object-cover' />
    </div>
  );
}
