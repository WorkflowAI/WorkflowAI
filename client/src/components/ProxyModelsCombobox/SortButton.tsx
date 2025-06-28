import { ArrowSortDown16Filled, ArrowSortUp16Filled } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';

type SortButtonProps = {
  icon: React.ReactNode;
  text: string;
  isOn: boolean;
  defaultOrder: 'ascending' | 'descending';
  revert: boolean;
  onSortChange: () => void;
};

export function SortButton(props: SortButtonProps) {
  const { icon, text, isOn, defaultOrder, revert, onSortChange } = props;

  const arrowDown = (defaultOrder === 'ascending' && !revert) || (defaultOrder === 'descending' && revert);

  const orderIcon = arrowDown ? (
    <ArrowSortDown16Filled className='w-4 h-4 text-indigo-700' />
  ) : (
    <ArrowSortUp16Filled className='w-4 h-4 text-indigo-700' />
  );

  return (
    <div
      className={cx(
        'flex flex-row items-center justify-center gap-1 px-2 py-1.5 rounded-[2px] cursor-pointer',
        isOn
          ? 'bg-indigo-50 border border-indigo-700 hover:bg-indigo-100'
          : 'bg-gray-100 border border-white/0 hover:bg-gray-200'
      )}
      onClick={() => onSortChange()}
    >
      <div className={cx('w-4 h-4 flex items-center justify-center', isOn ? 'text-indigo-700' : 'text-gray-900')}>
        {icon}
      </div>
      <div className={cx('text-[12px] font-normal font-lato', isOn ? 'text-indigo-700' : 'text-gray-700')}>{text}</div>
      {isOn && orderIcon}
    </div>
  );
}
