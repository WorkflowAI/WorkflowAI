import { FaGoogle } from 'react-icons/fa';
import { SiAnthropic } from 'react-icons/si';
import { isNullish } from '@/types';
import { ModelResponse, Provider } from '@/types/workflowAI';
import { AmazonBedrockIcon } from '../icons/models/amazonBedrockIcon';
import { AzureIcon } from '../icons/models/azureIcon';
import { FireworksIcon } from '../icons/models/fireworksIcon';
import { GroqIcon } from '../icons/models/groqIcon';
import { MistralAIIcon } from '../icons/models/mistralAIIcon';
import { OpenAIIcon } from '../icons/models/openAIIcon';

export type AIModelComboboxOption = {
  model: ModelResponse;
  value: string;
  label: string;
  renderLabel: ({
    isSelected,
    showCheck,
    dropdownOpen,
  }: {
    isSelected: boolean;
    showCheck?: boolean;
    dropdownOpen?: boolean;
  }) => React.ReactNode;
  disabled?: boolean;
  isLatest?: boolean;
};

export type AIProviderMetadata = {
  name: string;
  icon: JSX.Element;
  documentationUrl: string;
};

export const AI_PROVIDERS_METADATA: Record<Provider, AIProviderMetadata> = {
  openai: {
    name: 'OpenAI',
    icon: <OpenAIIcon />,
    documentationUrl: 'https://platform.openai.com/account/api-keys',
  },
  amazon_bedrock: {
    name: 'Amazon Bedrock',
    icon: <AmazonBedrockIcon />,
    documentationUrl: 'https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started-api.html',
  },
  azure_openai: {
    name: 'Azure OpenAI',
    icon: <AzureIcon />,
    documentationUrl:
      'https://learn.microsoft.com/en-us/azure/api-management/api-management-authenticate-authorize-azure-openai',
  },
  google: {
    name: 'Google',
    icon: <FaGoogle />,
    documentationUrl: 'https://console.cloud.google.com/apis/credentials',
  },
  groq: {
    name: 'Groq',
    icon: <GroqIcon />,
    documentationUrl: 'https://console.groq.com/keys',
  },
  anthropic: {
    name: 'Anthropic',
    icon: <SiAnthropic />,
    documentationUrl: 'https://console.anthropic.com/account/keys',
  },
  mistral_ai: {
    name: 'Mistral AI',
    icon: <MistralAIIcon />,
    documentationUrl: 'https://console.mistral.ai/api-keys',
  },
  google_gemini: {
    name: 'Gemini',
    icon: <FaGoogle />,
    documentationUrl: 'https://aistudio.google.com/app/apikey',
  },
  fireworks: {
    name: 'Fireworks AI',
    icon: <FireworksIcon />,
    documentationUrl: 'https://fireworks.ai/docs/api-reference/introduction',
  },
};

/*
  This function is used to sort models by price.
  It returns the sum of the price per input and output token.
  If the price per input or output token is undefined, it returns undefined.
  This function should not be used for displaying the price in the UI.
*/
export function getModelPriceForSorting(model: ModelResponse) {
  const metadata = model.metadata;

  if (!metadata) {
    return undefined;
  }

  if (metadata.price_per_input_token_usd === undefined || metadata.price_per_output_token_usd === undefined) {
    return undefined;
  }

  return metadata.price_per_input_token_usd + metadata.price_per_output_token_usd;
}

export function pricingBetweenModelsComparator(reversed: boolean) {
  const factor = reversed ? 1 : -1;
  return (a: { model: ModelResponse }, b: { model: ModelResponse }) => {
    const bHasPricePerRun = !isNullish(b.model.average_cost_per_run_usd);
    // Coalescing to null to treat null and undefined as the same
    if (!isNullish(a.model.average_cost_per_run_usd)) {
      // When both models have pricing, we can compare them
      if (bHasPricePerRun) {
        return (
          //@ts-expect-error we know that average_cost_per_run_usd is a number from the null checks above
          (b.model.average_cost_per_run_usd - a.model.average_cost_per_run_usd) * factor
        );
      }

      // If only a has pricing, it comes up first
      return -1;
    }
    // If only b has pricing, it comes up first
    if (bHasPricePerRun) {
      return 1;
    }

    const aFallbackSortingPrice = getModelPriceForSorting(a.model);
    const bFallbackSortingPrice = getModelPriceForSorting(b.model);

    if (aFallbackSortingPrice === undefined || bFallbackSortingPrice === undefined) {
      return 0;
    }

    return (bFallbackSortingPrice - aFallbackSortingPrice) * factor;
  };
}

export function intelligenceComparator(reversed: boolean) {
  const factor = reversed ? -1 : 1;
  return (a: { model: ModelResponse }, b: { model: ModelResponse }) => {
    if (isNullish(b.model.metadata?.quality_index)) {
      if (isNullish(a.model.metadata?.quality_index)) {
        return 0;
      }
      return -1;
    }

    if (isNullish(a.model.metadata?.quality_index)) {
      return 1;
    }

    return ((b.model.metadata?.quality_index ?? 0) - (a.model.metadata?.quality_index ?? 0)) * factor;
  };
}

export function latestComparator(reversed: boolean) {
  const factor = reversed ? -1 : 1;
  return (a: { model: ModelResponse }, b: { model: ModelResponse }) => {
    // No need to check for empty, release date is always available
    return (
      (new Date(b.model.metadata?.release_date ?? '').getTime() -
        new Date(a.model.metadata?.release_date ?? '').getTime()) *
      factor
    );
  };
}

export function modelComparator(sort: 'intelligence' | 'price' | 'latest', reversed: boolean) {
  switch (sort) {
    case 'intelligence':
      return intelligenceComparator(reversed);
    case 'price':
      return pricingBetweenModelsComparator(reversed);
    case 'latest':
      return latestComparator(reversed);
  }
  throw new Error(`Invalid sort: ${sort}`);
}
