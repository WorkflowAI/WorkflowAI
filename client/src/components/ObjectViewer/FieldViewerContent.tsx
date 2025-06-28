import { DismissFilled } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useMemo } from 'react';
import { FieldType } from '@/lib/schemaUtils';
import { ValueViewer } from './ValueViewer';
import { ValueViewerProps } from './utils';

type FieldViewerContentProps = ValueViewerProps<unknown> & {
  subSchemaFieldType: FieldType | undefined;
  isRoot: boolean;
  isParentArray?: boolean;
  isArrayObject?: boolean;
  onRemove: (() => void) | undefined;
  fieldKey: string;
};

export function FieldViewerContent(props: FieldViewerContentProps) {
  const { subSchemaFieldType, isRoot, isParentArray, isArrayObject, fieldKey, onRemove, ...rest } = props;

  const content = useMemo(() => {
    if (onRemove) {
      return (
        <div className='w-full flex items-center gap-2 p-1.5 border border-gray-200 rounded-[2px] bg-white'>
          <ValueViewer {...rest} />
          <DismissFilled className='cursor-pointer text-gray-500' onClick={onRemove} />
        </div>
      );
    }
    if (!!isParentArray) {
      return (
        <div className='bg-white rounded-[2px] p-1.5 border border-gray-200 flex items-center'>
          <ValueViewer {...rest} />
        </div>
      );
    }
    return <ValueViewer {...rest} />;
  }, [onRemove, isParentArray, rest]);

  if (subSchemaFieldType === 'object' && !isRoot) {
    return (
      <div
        className={cx(
          'w-full rounded-b-[2px] overflow-hidden bg-white border border-gray-200',
          isArrayObject && !rest.showTypes && !rest.editable ? 'rounded-t-[2px]' : 'border-t-0'
        )}
      >
        {content}
      </div>
    );
  }

  return content;
}
