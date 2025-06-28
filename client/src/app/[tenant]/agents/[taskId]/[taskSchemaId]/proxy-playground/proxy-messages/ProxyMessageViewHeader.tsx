import { Attach16Regular, Checkmark16Filled, ChevronUpDown16Regular, Dismiss16Regular } from '@fluentui/react-icons';
import { CopyIcon } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';
import { cn } from '@/lib/utils';
import {
  ContentType,
  ExtendedMessageType,
  getContentTypesToShowToUser,
  getTextAndIconFotContentType,
  getTitleForType,
} from './utils';

type Props = {
  type: ExtendedMessageType;
  avaibleTypes: ExtendedMessageType[];
  isHovering: boolean;
  onRemove?: () => void;
  onChangeType: (type: ExtendedMessageType) => void;
  onAddContentEntry: (type: ContentType) => void;
  onCopy?: () => void;
  readonly?: boolean;
};

export function ProxyMessageViewHeader(props: Props) {
  const { type, avaibleTypes, isHovering, onRemove, onChangeType, onAddContentEntry, onCopy, readonly } = props;

  const [showTypePopover, setShowTypePopover] = useState(false);
  const [showAttachmentPopover, setShowAttachmentPopover] = useState(false);

  useEffect(() => {
    if (!isHovering) {
      setShowTypePopover(false);
      setShowAttachmentPopover(false);
    }
  }, [isHovering]);

  const handleOnTypeChange = useCallback(
    (type: ExtendedMessageType) => {
      onChangeType(type);
      setShowTypePopover(false);
    },
    [onChangeType]
  );

  const handleOnAddContentEntry = useCallback(
    (type: ContentType) => {
      onAddContentEntry(type);
      setShowAttachmentPopover(false);
    },
    [onAddContentEntry]
  );

  const attachemntTypes = useMemo(() => {
    return getContentTypesToShowToUser(type);
  }, [type]);

  return (
    <div className='flex w-full items-center justify-between pl-3 pr-2 h-8'>
      {readonly || avaibleTypes.length === 1 ? (
        <div className='flex flex-row gap-[6px] items-center'>
          <div className='text-gray-700 text-[13px] font-semibold'>{getTitleForType(type)}</div>
        </div>
      ) : (
        <Popover open={showTypePopover} onOpenChange={setShowTypePopover}>
          <PopoverTrigger asChild>
            <div className='flex flex-row gap-[6px] items-center cursor-pointer'>
              <div className='text-gray-700 hover:text-gray-500 text-[13px] font-semibold'>{getTitleForType(type)}</div>
              {isHovering && !readonly && <ChevronUpDown16Regular className='w-[14px] h-[14px] text-gray-600' />}
            </div>
          </PopoverTrigger>
          <PopoverContent className='flex flex-col w-full p-1 rounded-[2px]' side='bottom' align='start'>
            {avaibleTypes.map((avaibleType) => (
              <Button
                key={avaibleType}
                variant='newDesignText'
                className='w-full min-w-[180px] justify-start hover:bg-gray-100 hover:text-gray-900 font-normal pl-1.5'
                onClick={() => handleOnTypeChange(avaibleType)}
              >
                {avaibleType === type ? (
                  <Checkmark16Filled className='w-4 h-4 text-indigo-600 mr-0.5' />
                ) : (
                  <div className='flex w-4 h-4 mr-0.5' />
                )}
                {getTitleForType(avaibleType)}
              </Button>
            ))}
          </PopoverContent>
        </Popover>
      )}
      <div className='flex flex-row items-center'>
        {isHovering && onCopy && (
          <Button
            variant='newDesignText'
            size='none'
            className='w-7 h-7'
            icon={<CopyIcon size={13} />}
            onClick={onCopy}
          />
        )}

        {isHovering && attachemntTypes.length > 0 && !readonly && (
          <Popover open={showAttachmentPopover} onOpenChange={setShowAttachmentPopover}>
            <PopoverTrigger asChild>
              <Button
                variant='newDesignText'
                size='none'
                className={cn('w-7 h-7 rounded-[2px]', showAttachmentPopover && 'bg-gray-300')}
                icon={<Attach16Regular className='w-4 h-4' />}
                onClick={() => {}}
              />
            </PopoverTrigger>
            <PopoverContent className='flex flex-col w-full p-1 rounded-[2px]' side='bottom' align='end'>
              {attachemntTypes.map((avaibleType) => {
                const result = getTextAndIconFotContentType(avaibleType);
                if (!result) {
                  return null;
                }

                const { text, icon: Icon } = result;

                return (
                  <Button
                    key={avaibleType}
                    variant='newDesignText'
                    size='none'
                    className='w-full min-w-[180px] justify-start hover:bg-gray-100 hover:text-gray-900 font-normal pl-1.5 py-1.5'
                    onClick={() => handleOnAddContentEntry(avaibleType)}
                  >
                    <Icon className='w-4 h-4 text-gray-600 mr-0.5' />
                    {text}
                  </Button>
                );
              })}
            </PopoverContent>
          </Popover>
        )}

        {isHovering && !readonly && onRemove && (
          <Button
            variant='newDesignText'
            size='none'
            className='w-7 h-7'
            icon={<Dismiss16Regular className='w-4 h-4' />}
            onClick={onRemove}
          />
        )}
      </div>
    </div>
  );
}
