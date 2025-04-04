import { ArrowUpFilled, LinkRegular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useCopy } from '@/lib/hooks/useCopy';
import { useRedirectWithParams } from '@/lib/queryString';
import { cleanURL, isValidURL } from './utils';

type Props = {
  companyURL: string | undefined;
  setCompanyURL?: (companyURL: string) => void;
};

export function SuggestedFeaturesSearch(props: Props) {
  const { companyURL, setCompanyURL } = props;
  const inputRef = useRef<HTMLInputElement>(null);

  const redirectWithParams = useRedirectWithParams();

  const [entryField, setEntryField] = useState('');
  const [inProgress, setInProgress] = useState(false);

  const [errorToShow, setErrorToShow] = useState<string | undefined>(undefined);

  const onSetEntryField = useCallback((value: string) => {
    setErrorToShow(undefined);
    setEntryField(value);
  }, []);

  useEffect(() => {
    onSetEntryField(companyURL ?? '');
  }, [companyURL, onSetEntryField]);

  const entryFieldRef = useRef(entryField);
  entryFieldRef.current = entryField;

  useEffect(() => {
    if (!companyURL && inputRef.current && entryFieldRef.current.toLowerCase() !== companyURL?.toLowerCase()) {
      inputRef.current.focus({ preventScroll: true });
    } else {
      inputRef.current?.blur();
    }
  }, [companyURL]);

  const onCompanyURLSelected = useCallback(
    (url: string) => {
      const cleanedURL = cleanURL(url);

      if (!isValidURL(cleanedURL)) {
        setErrorToShow('Invalid URL');
        return;
      }

      inputRef.current?.blur();
      setInProgress(true);
      setEntryField(cleanedURL);
      setErrorToShow(undefined);

      if (setCompanyURL) {
        setCompanyURL(cleanedURL);
      } else {
        redirectWithParams({
          path: `/${cleanedURL}`,
        });
      }

      setTimeout(() => {
        setInProgress(false);
      }, 1000);
    },
    [redirectWithParams, setCompanyURL]
  );

  const copy = useCopy();
  const copyUrl = useCallback(() => {
    const baseUrl = window.location.origin;
    copy(`${baseUrl}/${companyURL}`, {
      successMessage: 'Page link copied to clipboard',
    });
  }, [copy, companyURL]);

  const errorMode = errorToShow !== undefined;

  const isGenerateButtonActive = !inProgress && entryField.length > 0;

  const [isFocused, setIsFocused] = useState(false);
  const showGradientBorder = !inProgress && isFocused && !errorMode;

  const showSendButton = entryField.toLowerCase() !== companyURL?.toLowerCase() || isFocused;

  const shouldShowShareButton =
    companyURL?.toLowerCase() === entryField.toLowerCase() && entryField.length > 0 && !isFocused;

  return (
    <div className='flex flex-col gap-2 w-full'>
      <div
        className={cx(
          'flex w-full rounded-[4px]',
          showGradientBorder ? 'bg-custom-gradient-solid shadow-md' : errorMode ? 'bg-red-500' : 'bg-gray-200'
        )}
      >
        <div
          className={cx(
            'flex flex-row w-full items-center justify-between gap-2 rounded-[2px]',
            inProgress ? 'bg-gray-100' : 'bg-white',
            showGradientBorder || errorMode ? 'm-[2px] px-2 py-1' : 'm-[1px] px-[9px] py-[5px]'
          )}
        >
          <Input
            ref={inputRef}
            placeholder='Enter your product URL'
            className={cx(
              'w-full text-[16px] font-normal py-0 pr-0 pl-1 focus-visible:ring-0 border-none bg-transparent',
              inProgress ? 'text-gray-400' : 'text-gray-900'
            )}
            value={entryField}
            onChange={(event) => onSetEntryField(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && isGenerateButtonActive) {
                onCompanyURLSelected(entryField);
              }
            }}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
          />
          {showSendButton && (
            <Button
              variant='newDesignIndigo'
              icon={<ArrowUpFilled className='w-3.5 h-3.5' />}
              size='none'
              className={cx(
                'w-8 h-8 rounded-full flex-shrink-0 disabled:text-gray-400 disabled:opacity-100',
                isGenerateButtonActive
                  ? 'bg-custom-indigo-gradient'
                  : inProgress
                    ? 'bg-gray-50 disabled:bg-gray-50'
                    : 'bg-gray-100 disabled:bg-gray-100'
              )}
              disabled={!isGenerateButtonActive}
              onClick={() => onCompanyURLSelected(entryField)}
              loading={inProgress}
            />
          )}
          {shouldShowShareButton && (
            <Button variant='newDesign' icon={<LinkRegular className='w-4 h-4' />} size='sm' onClick={copyUrl}>
              Share With Your Team
            </Button>
          )}
        </div>
      </div>
      {errorMode && <div className='text-red-500 text-[13px] font-normal'>{errorToShow}</div>}
    </div>
  );
}
