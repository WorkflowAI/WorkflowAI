import { Dismiss12Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { Button } from '@/components/ui/Button';
import { SuggestedFeatures } from './SuggestedFeatures';

type Props = {
  className?: string;
  companyURL?: string;
  setCompanyURL?: (companyURL: string) => void;
  hideSidebar?: boolean;
  onClose?: () => void;
};

export function SuggestedFeaturesComponent(props: Props) {
  const { className, companyURL, setCompanyURL, hideSidebar = false } = props;
  return (
    <div className={cx('flex items-center justify-center w-full h-max px-4 sm:px-16', className)}>
      <div className='flex w-full max-w-[1132px] sm:h-[820px] h-max sm:max-h-[820px] max-h-max bg-white rounded-[4px] border border-gray-200 shadow-md overflow-hidden'>
        <SuggestedFeatures companyURL={companyURL} setCompanyURL={setCompanyURL} hideSidebar={hideSidebar} />
      </div>
    </div>
  );
}

export function SuggestedFeaturesComponentModal(props: Props) {
  const { companyURL, setCompanyURL, hideSidebar = false, onClose } = props;
  return (
    <div className='flex flex-col w-full h-full rounded-[4px] border border-gray-200 overflow-hidden relative'>
      <div className='absolute top-0 left-0 sm:p-4 py-6 px-2'>
        <Button
          variant='newDesign'
          icon={<Dismiss12Regular className='w-3 h-3' />}
          className='w-7 h-7'
          size='none'
          onClick={onClose}
        />
      </div>
      <SuggestedFeatures companyURL={companyURL} setCompanyURL={setCompanyURL} hideSidebar={hideSidebar} />
    </div>
  );
}
