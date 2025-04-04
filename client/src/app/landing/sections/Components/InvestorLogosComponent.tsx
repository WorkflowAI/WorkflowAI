import Image from 'next/image';
import { cn } from '@/lib/utils';

const investorLogos = [
  {
    src: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/InvestorLogo1.png',
    width: 150,
    height: 64,
  },
  {
    src: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/InvestorLogo2.png',
    width: 181,
    height: 64,
  },
  {
    src: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/InvestorLogo3.png',
    width: 286,
    height: 64,
  },
  {
    src: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/InvestorLogo4.png',
    width: 311,
    height: 64,
  },
  {
    src: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/InvestorLogo5.png',
    width: 157,
    height: 64,
  },
  {
    src: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/InvestorLogo6.png',
    width: 241,
    height: 64,
  },
  {
    src: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/InvestorLogo7.png',
    width: 192,
    height: 64,
  },
];

type Props = {
  className?: string;
};

export function InvestorLogosComponent(props: Props) {
  const { className } = props;

  return (
    <div className={cn('flex flex-col gap-6 items-center px-4', className)}>
      <div className='text-[16px] font-normal text-gray-700 text-center'>
        Backed by investors from leading brands and companies from across the globe.
      </div>
      <div className='flex flex-wrap max-w-[1132px] gap-x-11 gap-y-6 items-start justify-center'>
        {investorLogos.map((logo) => (
          <Image
            src={logo.src}
            alt='Investor Logo'
            key={logo.src}
            className='w-fit h-8'
            width={logo.width}
            height={logo.height}
          />
        ))}
      </div>
    </div>
  );
}
