import { Link16Regular } from '@fluentui/react-icons';
import { Button } from '@/components/ui/Button';

type PageHeaderRightComponentsProps = {
  name?: string | React.ReactNode;
  rightBarText?: string;
  documentationLink?: string;
  extraButton?: React.ReactNode;
  showCopyLink?: boolean;
  rightBarChildren?: React.ReactNode;
  copyUrl?: () => void;
  documentationText?: string;
};

export function PageHeaderRightComponents(props: PageHeaderRightComponentsProps) {
  const {
    name,
    rightBarText,
    documentationLink,
    extraButton,
    showCopyLink,
    rightBarChildren,
    copyUrl,
    documentationText,
  } = props;
  return (
    <div className='flex flex-row gap-2 items-center sm:w-fit px-4 w-full justify-between sm:border-t-0 border-t border-gray-100'>
      <div className='flex flex-col gap-[2px] py-2'>
        <div className='font-semibold text-[18px] text-gray-900 sm:hidden block'>{name}</div>
        {!!rightBarText && <div className='text-gray-500 text-xs pr-1 line-clamp-1'>{rightBarText}</div>}
      </div>
      <div className='flex flex-row gap-2 items-center'>
        {!!documentationLink && (
          <Button
            variant='newDesign'
            toRoute={documentationLink}
            target='_blank'
            rel='noopener noreferrer'
            className='sm:block hidden'
          >
            {documentationText ?? 'Documentation'}
          </Button>
        )}
        {extraButton}
        {showCopyLink && (
          <Button variant='newDesign' icon={<Link16Regular />} onClick={copyUrl} className='w-9 h-9 px-0 py-0' />
        )}
        {rightBarChildren}
      </div>
    </div>
  );
}
