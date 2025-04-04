'use client';

import { Dispatch, SetStateAction, useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { displayErrorToaster, displaySuccessToaster } from '@/components/ui/Sonner';
import { RequestError } from '@/lib/api/client';
import { ProviderConfig } from '@/store/organization_settings';
import { Provider, ProviderSettings } from '@/types/workflowAI';
import { TenantData } from '@/types/workflowAI';
import { AI_PROVIDERS_METADATA } from '../AIModelsCombobox/utils';
import { Textarea } from '../ui/Textarea';
import { GoogleConfigForm } from './GoogleConfigForm';

type SetProviderConfigProps = {
  providerSettings: ProviderSettings[] | undefined;
  currentProvider: string | undefined | null;
  onSetProviderConfig(provider: Provider, value: Record<string, unknown>): Promise<void>;
  onClose: (keyWasCreated: boolean) => void;
};

type ProviderConfigFormProps = {
  current_provider: Provider;
  setConfig: Dispatch<SetStateAction<Record<string, unknown> | undefined>>;
};

function APIKeyConfigForm(props: ProviderConfigFormProps) {
  const { current_provider, setConfig } = props;

  const [apiKey, setApiKey] = useState<string>();

  useEffect(() => {
    if (!apiKey) {
      setConfig(undefined);
      return;
    }

    setConfig({ api_key: apiKey });
  }, [apiKey, setConfig]);

  const onChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setApiKey(e.target.value);
  }, []);

  const placeholder: string = useMemo(() => {
    switch (current_provider) {
      case 'anthropic':
        return 'Your Anthropic API Key';
      case 'azure_openai':
        return 'Your Azure OpenAI API Key';
      case 'google':
        return 'Your Google Vertex Credentials';
      case 'amazon_bedrock':
        return 'Your Amazon Bedrock Credentials';
      case 'groq':
        return 'Your Groq API Key';
      case 'openai':
        return 'Your OpenAI API Key';
      case 'mistral_ai':
        return 'Your Mistral AI API Key';
      case 'google_gemini':
        return 'Your Gemini API Key';
      case 'fireworks':
        return 'Your Fireworks API Key';
    }
  }, [current_provider]);

  return (
    <div className='flex flex-col items-start gap-3 w-full max-w-[600px]'>
      <label htmlFor='api-key' className='text-[14px] text-slate-600 font-medium'>
        API Key
      </label>
      <Input
        id='api-key'
        placeholder={placeholder}
        onChange={onChange}
        value={apiKey}
        className='w-full rounded-[10px] mb-32'
      />
    </div>
  );
}

function JSONProviderConfigForm(props: ProviderConfigFormProps) {
  const { current_provider, setConfig } = props;

  const name = AI_PROVIDERS_METADATA[current_provider as Provider].name;
  const [code, setCode] = useState<string>('');
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!code) {
      setConfig(undefined);
      setError(undefined);
      return;
    }

    try {
      const json = JSON.parse(code);
      setConfig(json);
      setError(undefined);
    } catch (e) {
      setConfig(undefined);
      setError(`${e}`);
    }
  }, [code, setConfig]);

  return (
    <div className='w-full h-full flex flex-col gap-2'>
      <div className='text-[14px] text-slate-600 font-medium'>{name} Credentials</div>
      {error && <div className='text-red-500 text-[14px]'>{error}</div>}
      <Textarea value={code} onChange={(e) => setCode(e.target.value)} className='min-h-48' />
    </div>
  );
}

function ProviderConfigForm(props: ProviderConfigFormProps) {
  const { current_provider, setConfig } = props;

  if (current_provider === 'google') {
    return <GoogleConfigForm setConfig={setConfig} />;
  }

  if (current_provider === 'amazon_bedrock' || current_provider === 'azure_openai') {
    return <JSONProviderConfigForm current_provider={current_provider} setConfig={setConfig} />;
  }

  return <APIKeyConfigForm current_provider={current_provider} setConfig={setConfig} />;
}

export function AddProviderKeyModalContent(props: SetProviderConfigProps) {
  const { currentProvider, onSetProviderConfig, onClose } = props;

  const providerMetadata = AI_PROVIDERS_METADATA[currentProvider as Provider];

  const [config, setConfig] = useState<Record<string, unknown>>();

  const onAddConfigClick = useCallback(() => {
    if (!config) {
      return;
    }

    return onSetProviderConfig(currentProvider as Provider, config);
  }, [currentProvider, onSetProviderConfig, config]);

  const handleCancel = useCallback(() => {
    onClose(false);
  }, [onClose]);

  if (!providerMetadata) {
    return null;
  }

  return (
    <>
      <div className='flex flex-col items-start px-6 py-5 gap-6'>
        <div className='flex flex-row justify-between items-center w-full'>
          <div className='font-medium text-[20px] text-slate-900'>Add Model Provider Keys</div>
        </div>
        <div className='flex flex-row items-center gap-4 pt-3'>
          <div className='w-10 h-10 flex items-center justify-center bg-slate-50 rounded-[8px]'>
            {providerMetadata.icon}
          </div>
          <div className='text-slate-700 text-[14px] font-medium'>{providerMetadata.name ?? currentProvider}</div>
        </div>
        {providerMetadata.documentationUrl && (
          <div className='text-[14px] text-normal text-slate-600'>
            Get your{' '}
            <a
              href={providerMetadata.documentationUrl}
              className='text-blue-600 underline font-semibold'
              target='_blank'
            >
              Provider API Key
            </a>{' '}
            and enter it here.
          </div>
        )}
        {currentProvider === 'google' ? (
          <GoogleConfigForm setConfig={setConfig} />
        ) : (
          <ProviderConfigForm current_provider={currentProvider as Provider} setConfig={setConfig} />
        )}
      </div>
      <div className='flex gap-[8px] w-full justify-between px-[24px] py-[12px] bg-slate-50 border-t'>
        <Button variant='link' onClick={handleCancel}>
          <div>Cancel</div>
        </Button>
        <Button variant='default' disabled={!config} onClick={onAddConfigClick}>
          Add Key
        </Button>
      </div>
    </>
  );
}

type AddProviderKeyModalProps = {
  currentProvider: string | null | undefined;
  organizationSettings: TenantData | undefined;
  open: boolean;
  onClose: (keyWasCreated: boolean) => void;
  addProviderConfig: (provider: ProviderConfig) => Promise<void>;
};

export function AddProviderKeyModal(props: AddProviderKeyModalProps) {
  const { currentProvider, organizationSettings, open, onClose, addProviderConfig } = props;

  const onSetProviderConfig = useCallback(
    async (provider: Provider, value: Record<string, unknown>) => {
      try {
        await addProviderConfig({
          provider,
          ...value,
        });
        displaySuccessToaster('Provider Key Added');
        onClose(true);
      } catch (e: unknown) {
        if (e instanceof RequestError) {
          displayErrorToaster('Invalid Provider Key');
          return;
        }
        throw e;
      }
    },
    [addProviderConfig, onClose]
  );

  const onOpenChange = useCallback(
    (open: boolean) => {
      if (!open) {
        onClose(false);
      }
    },
    [onClose]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='w-[440px] max-w-[90vw] p-0 overflow-hidden'>
        <AddProviderKeyModalContent
          providerSettings={organizationSettings?.providers}
          currentProvider={currentProvider}
          onSetProviderConfig={onSetProviderConfig}
          onClose={onClose}
        />
      </DialogContent>
    </Dialog>
  );
}
