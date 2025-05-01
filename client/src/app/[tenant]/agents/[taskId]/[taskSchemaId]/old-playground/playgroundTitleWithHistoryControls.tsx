import { ChevronLeft12Regular, ChevronRight12Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';

type TitleWithHistoryControlsProps = {
  title: string;
  isPreviousOn: boolean;
  isNextOn: boolean;
  onPrevious?: () => void;
  onNext?: () => void;
  tooltipPreviousText: string;
  tooltipNextText: string;
  showHistoryButtons: boolean;
};

export function TitleWithHistoryControls(props: TitleWithHistoryControlsProps) {
  const {
    title,
    isPreviousOn,
    isNextOn,
    onPrevious,
    onNext,
    tooltipPreviousText,
    tooltipNextText,
    showHistoryButtons,
  } = props;

  return (
    <div className='flex flex-row items-center gap-1.5'>
      {showHistoryButtons && (
        <div className='flex flex-row items-center'>
          <SimpleTooltip asChild content={tooltipPreviousText}>
            <div>
              <Button
                variant='text'
                icon={<ChevronLeft12Regular className='h-3 w-3 text-gray-900' />}
                onClick={onPrevious}
                disabled={!isPreviousOn}
                size='none'
                className={cx('p-1.5', isPreviousOn ? 'opacity-100' : 'opacity-30')}
              />
            </div>
          </SimpleTooltip>
          <SimpleTooltip asChild content={tooltipNextText}>
            <div>
              <Button
                variant='text'
                icon={<ChevronRight12Regular className='h-3 w-3 text-gray-900' />}
                onClick={onNext}
                disabled={!isNextOn}
                size='none'
                className={cx('p-1.5', isNextOn ? 'opacity-100' : 'opacity-30')}
              />
            </div>
          </SimpleTooltip>
        </div>
      )}
      <div className={cx('text-gray-700 text-base font-semibold')}>{title}</div>
    </div>
  );
}
