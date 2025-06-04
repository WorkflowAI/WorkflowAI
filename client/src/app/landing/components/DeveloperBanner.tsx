import Link from 'next/link';

type DeveloperBannerProps = {
  customLink?: string;
  linkText?: string;
};

export function DeveloperBanner(props: DeveloperBannerProps) {
  const { customLink, linkText = 'Learn more' } = props;

  return (
    <div className='flex w-full h-9 bg-indigo-500 text-white justify-between items-center px-4 flex-shrink-0'>
      <div />
      <div className='flex flex-row gap-2 items-center'>
        <span className='text-white text-[13px] font-normal'>
          <span className='font-semibold'>Introducing WorkflowAI for Developers:</span> Bring the benefits of WorkflowAI
          to your existing agents with just 2 lines of code.
        </span>
        {customLink && (
          <Link href={customLink} className='text-white text-[13px] font-medium underline'>
            {linkText}
          </Link>
        )}
      </div>
      <div />
    </div>
  );
}
