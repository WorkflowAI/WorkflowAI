import { DismissFilled, ErrorCircle24Filled, List16Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { PlusCircle, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';
import { Badge } from '@/components/ui/Badge';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/HoverCard';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { AUDIO_REF_NAME, IMAGE_REF_NAME, PDF_REF_NAME } from '@/lib/constants';
import { FieldType } from '@/lib/schemaUtils';
import { cn } from '@/lib/utils';
import { JsonValueSchema } from '@/types';
import { Button } from '../ui/Button';
import { FieldViewerLabelExampleHints } from './FieldViewerLabelExampleHints';
import { TypeSelector } from './TypeSelector';

const TOOLTIP_DELAY = 100;

type FieldViewerLabelProps = {
  editable: boolean | undefined;
  fieldKey: string;
  fieldKeyPath: string;
  subSchemaFieldType: FieldType | undefined;
  subSchema: JsonValueSchema | undefined;
  showExamplesHints?: boolean;
  showTypes: boolean;
  showDescriptionExamples: 'all' | 'description' | undefined;
  isNull: boolean;
  isRequired: boolean;
  isValueVisible: boolean;
  onNullClick: (() => void) | undefined;
  textColor: string;
  toggleValueVisible: () => void;
  isParentArray: boolean;
  isArrayObject: boolean;
  onRemove: (() => void) | undefined;
  isError: boolean;
  handleFieldKeyPositionChange?: (key: string, position: number) => void;
  onShowEditSchemaModal?: () => void;
  onShowEditDescriptionModal?: () => void;
  showDescriptionPopover: boolean;
  onTypeChange?: (keyPath: string, newType: string) => void;
  schemaRefName: string | undefined;
};

export function FieldViewerLabel(props: FieldViewerLabelProps) {
  const {
    editable,
    fieldKey,
    fieldKeyPath,
    isNull,
    subSchemaFieldType,
    subSchema,
    isRequired,
    showExamplesHints = false,
    showTypes,
    showDescriptionExamples,
    onNullClick,
    textColor,
    toggleValueVisible,
    isParentArray,
    isArrayObject,
    onRemove,
    isError,
    handleFieldKeyPositionChange,
    onShowEditSchemaModal,
    onShowEditDescriptionModal,
    showDescriptionPopover,
    onTypeChange,
    schemaRefName,
  } = props;

  // This is a side effect that updates the position of the field key in the parent component
  // It is necessary in order to properly position the corresponding FieldEvaluationSelector
  const fieldRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!!handleFieldKeyPositionChange && fieldRef.current) {
      const key = fieldKeyPath;
      const position = fieldRef.current.getBoundingClientRect().top;
      handleFieldKeyPositionChange(key, position);
    }
  }, [handleFieldKeyPositionChange, fieldKeyPath]);

  const onlyShowDescriptionsAndExamplesAndHideTypes = !showTypes && !!showDescriptionExamples;

  const labelKey = useMemo(() => {
    if (isArrayObject) {
      return showTypes || onlyShowDescriptionsAndExamplesAndHideTypes || editable ? 'Object' : '';
    }
    return fieldKey;
  }, [isArrayObject, showTypes, editable, fieldKey, onlyShowDescriptionsAndExamplesAndHideTypes]);
  const NullToggleIcon = isNull ? PlusCircle : Trash2;

  const showTypeChangeButtons = useMemo(() => {
    return (
      !!onTypeChange &&
      (subSchemaFieldType === 'undefined' ||
        subSchemaFieldType === 'audio' ||
        subSchemaFieldType === 'document' ||
        subSchemaFieldType === 'image' ||
        subSchemaFieldType === 'string')
    );
  }, [onTypeChange, subSchemaFieldType]);

  const realFieldType: FieldType | undefined = useMemo(() => {
    if (schemaRefName) {
      switch (schemaRefName) {
        case IMAGE_REF_NAME:
          return 'image';
        case AUDIO_REF_NAME:
          return 'audio';
        case PDF_REF_NAME:
          return 'document';
      }
    }
    return subSchemaFieldType;
  }, [schemaRefName, subSchemaFieldType]);

  const content = (
    <div
      className={cx('flex items-center justify-between self-start', {
        'w-full': isArrayObject || !!onTypeChange,
      })}
      ref={fieldRef}
    >
      <div
        className={cx(
          'relative flex items-center gap-1 text-[13px] font-medium min-h-[32px] justify-center group',
          textColor,
          {
            'pr-2': !isParentArray,
          }
        )}
      >
        {subSchemaFieldType === 'array' && (
          <Button
            variant='newDesign'
            onClick={toggleValueVisible}
            icon={<List16Regular className='w-[15px] h-[15px] text-gray-900' />}
            className='rounded-[2px] h-[22px] w-[22px] mr-[2px] items-center justify-center p-0 text-gray-500'
          />
        )}
        {isError && <ErrorCircle24Filled className='text-red-600 h-4 w-4' />}
        {(!isParentArray || isArrayObject) && (
          <HoverCard
            open={!onShowEditSchemaModal ? false : undefined}
            closeDelay={TOOLTIP_DELAY}
            openDelay={TOOLTIP_DELAY}
          >
            <HoverCardTrigger>
              <SimpleTooltip
                asChild
                align='start'
                content={
                  !!showDescriptionPopover ? (
                    <FieldViewerLabelExampleHints
                      onClick={onShowEditDescriptionModal}
                      description={subSchema?.description}
                      examples={showExamplesHints ? subSchema?.examples : undefined}
                    />
                  ) : undefined
                }
                side='bottom'
                tooltipClassName='bg-white p-0 overflow-visible'
                tooltipDelay={TOOLTIP_DELAY}
              >
                <label
                  onClick={onShowEditSchemaModal}
                  className={cn(
                    {
                      'h-8 pr-3 text-[13px] flex items-center font-medium': subSchemaFieldType === 'object',
                      'text-gray-600': !isError && isArrayObject,
                      'text-gray-900': !isError && !isArrayObject,
                      'text-red-600': isError,
                    },
                    'min-w-[16px]',
                    (!!onShowEditSchemaModal || !!showDescriptionPopover) &&
                      'hover:underline hover:underline-offset-4 hover:decoration-dashed',
                    !!onShowEditSchemaModal && 'cursor-pointer'
                  )}
                >
                  {`${labelKey}${isRequired ? '*' : ''}`}
                  {!isNull && subSchemaFieldType !== 'object' && ':'}
                </label>
              </SimpleTooltip>
            </HoverCardTrigger>
            <HoverCardContent
              className='px-3 py-1.5 bg-gray-700 text-white text-[13px] items-center font-normal justify-center w-fit rounded-[3px]'
              side='top'
            >
              Add or Update Field
            </HoverCardContent>
          </HoverCard>
        )}
        {subSchemaFieldType === 'array' && showTypes && (
          <Badge
            variant='tertiaryWithHover'
            className='font-medium text-gray-700 text-[13px] h-6 rounded-[2px] border-gray-200'
          >
            list
          </Badge>
        )}
        {!isParentArray && editable && !!onNullClick && (
          <NullToggleIcon
            size={24}
            onClick={onNullClick}
            className='text-gray-600 cursor-pointer invisible group-hover:visible'
          />
        )}
      </div>
      {showTypeChangeButtons && !!realFieldType && !!onTypeChange && (
        <div className='flex w-full items-center justify-end'>
          <TypeSelector keyPath={fieldKeyPath} type={realFieldType} onTypeChange={onTypeChange} />
        </div>
      )}
      {!!onRemove && <DismissFilled onClick={onRemove} className='cursor-pointer text-gray-600 h-[18px] w-[18px]' />}
    </div>
  );

  if (isArrayObject && !showTypes && !onlyShowDescriptionsAndExamplesAndHideTypes && !editable) {
    return null;
  }

  if (subSchemaFieldType === 'object') {
    return (
      <div className='w-full rounded-t-[2px] overflow-hidden bg-gray-50 text-gray-400 flex items-center font-medium border border-b-0 border-gray-200'>
        <div className='w-full h-full flex border-b border-gray-200 border-dashed px-3'>{content}</div>
      </div>
    );
  }

  return content;
}
