import { Checkmark12Filled } from '@fluentui/react-icons';
import Image from 'next/image';
import GitHubSrc from '@/components/Images/GitHubIcon.png';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

type HeaderEntryProps = {
  text: string;
  href?: string;
  onClick?: () => void;
};

function HeaderEntry(props: HeaderEntryProps) {
  const { text, href, onClick } = props;

  if (!href && !onClick) {
    return (
      <div className='flex flex-row gap-[6px] items-center'>
        <Checkmark12Filled className='text-gray-700' />
        <div className='text-[16px] text-gray-500 font-normal'>{text}</div>
      </div>
    );
  }

  return (
    <div className='flex flex-row gap-[6px] items-center'>
      <Checkmark12Filled className='text-gray-700' />
      <a
        href={href}
        className='text-[16px] text-gray-700 font-normal underline cursor-pointer'
        target='_blank'
        onClick={onClick}
      >
        {text}
      </a>
    </div>
  );
}

type Props = {
  scrollToPricing: () => void;
  showSuggestedFeaturesModal: () => void;
  className?: string;
};

export function HeaderComponent(props: Props) {
  const { className, scrollToPricing, showSuggestedFeaturesModal } = props;

  return (
    <div className={cn('flex flex-col items-center sm:px-16 px-4 w-full max-w-[1260px]', className)}>
      <div className='sm:text-[60px] text-[48px] text-gray-900 font-semibold text-center leading-[1.1]'>
        Build AI features your users will love.
      </div>
      <div className='sm:text-[20px] text-[18px] text-gray-500 font-normal text-center leading-[1.5] max-w-[860px] mt-4'>
        WorkflowAI is an open-source platform where product and engineering teams collaborate to build and iterate on AI
        features.
      </div>
      <div className='flex sm:flex-row flex-col sm:w-fit w-full gap-4 my-10 items-center justify-center'>
        <Button variant='newDesignIndigo' className='sm:w-fit w-full' onClick={showSuggestedFeaturesModal}>
          Try Demo
        </Button>
        <Button
          variant='newDesign'
          icon={<Image src={GitHubSrc} alt='GitHub' className='w-4 h-4' />}
          toRoute='https://github.com/WorkflowAI/workflowai'
          target='_blank'
          rel='noopener noreferrer'
          className='sm:w-fit w-full'
        >
          Star on Github
        </Button>
      </div>
      <div className='flex sm:flex-wrap sm:flex-row flex-col sm:gap-4 gap-1 items-center justify-center'>
        <HeaderEntry text='Open-Source (deploy anywhere)' href='https://github.com/workflowai/workflowai' />
        <HeaderEntry text='Compatible with any backend' />
        <HeaderEntry text='No markup from AI providers' onClick={scrollToPricing} />
      </div>
    </div>
  );
}

type URLHeaderComponentProps = {
  className?: string;
};

export function URLHeaderComponent(props: URLHeaderComponentProps) {
  const { className } = props;

  return (
    <div className={cn('flex flex-col items-center sm:px-16 px-4 w-full max-w-[1260px]', className)}>
      <div className='sm:text-[60px] text-[48px] text-gray-900 font-semibold text-center leading-[1.1]'>
        Build AI features your users will love.
      </div>
      <div className='sm:text-[20px] text-[18px] text-gray-500 font-normal text-center leading-[1.5] max-w-[750px] mt-4'>
        WorkflowAI is an open-source platform where product and engineering teams collaborate to build and iterate on AI
        features.
      </div>
      <div className='flex sm:flex-row flex-col sm:w-fit w-full gap-4 my-10 items-center justify-center'>
        <Button variant='newDesignIndigo' className='sm:w-fit w-full' toRoute='/'>
          Learn more about WorkflowAI
        </Button>
      </div>
    </div>
  );
}
