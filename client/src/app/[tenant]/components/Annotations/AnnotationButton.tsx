import { AddSquare16Regular } from '@fluentui/react-icons';

type Props = {
  onClick: () => void;
};

export function AnnotationButton(props: Props) {
  const { onClick } = props;
  return (
    <div
      className='flex flex-row gap-1 text-[12px] font-semibold text-indigo-700 border border-indigo-200 rounded-[2px] px-2 py-1 cursor-pointer hover:bg-indigo-50 items-center'
      onClick={onClick}
    >
      <AddSquare16Regular />
      <div>Add Annotation</div>
    </div>
  );
}
