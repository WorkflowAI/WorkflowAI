import { Code16Regular } from '@fluentui/react-icons';
import { useCallback } from 'react';
import { SiGo, SiPython, SiTypescript } from 'react-icons/si';
import { RadioGroup, RadioGroupItem } from '@/components/ui/RadioGroup';
import { CodeLanguage, displayName } from '@/types/snippets';

function radioIdBuilder(language: CodeLanguage) {
  return `radio-item-${language}`;
}

type LanguageIconProps = {
  language: CodeLanguage;
};

function LanguageIcon(props: LanguageIconProps) {
  const { language } = props;
  switch (language) {
    case CodeLanguage.TYPESCRIPT:
      return <SiTypescript size={16} className='text-gray-400' />;
    case CodeLanguage.PYTHON:
      return <SiPython size={16} className='text-gray-400' />;
    case CodeLanguage.REST:
      return <Code16Regular className='text-gray-400' />;
    case CodeLanguage.GO:
      return <SiGo size={16} className='text-gray-400' />;
  }
}

type APILanguageSelectionProps = {
  languages: CodeLanguage[];
  selectedLanguage: CodeLanguage | undefined;
  setSelectedLanguage: (language: CodeLanguage) => void;
};

export function APILanguageSelection(props: APILanguageSelectionProps) {
  const { languages, selectedLanguage, setSelectedLanguage } = props;

  const onValueChange = useCallback(
    (value: string) => {
      setSelectedLanguage(value as CodeLanguage);
    },
    [setSelectedLanguage]
  );

  return (
    <RadioGroup value={selectedLanguage} onValueChange={onValueChange}>
      {languages.map((language) => (
        <div className='flex items-center gap-2' key={language}>
          <RadioGroupItem value={language} id={radioIdBuilder(language)} isSelected={selectedLanguage === language} />
          <label className='flex flex-row items-center gap-2 cursor-pointer' htmlFor={radioIdBuilder(language)}>
            <LanguageIcon language={language} />
            <div className='text-xs font-medium text-gray-700'>{displayName(language)}</div>
          </label>
        </div>
      ))}
    </RadioGroup>
  );
}
