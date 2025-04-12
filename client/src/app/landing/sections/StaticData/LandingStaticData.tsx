import { ClipboardTaskList16Regular } from '@fluentui/react-icons';
import { ArrowTrendingRegular } from '@fluentui/react-icons';
import { ChatRegular, CloudRegular, DataUsageRegular, ListBarTreeRegular } from '@fluentui/react-icons';
import { StaticImageData } from 'next/image';
import { ReactNode } from 'react';
import GitHubSrc from '@/components/Images/GitHubIcon.png';

// Types

export type QuoteEntry = {
  quote: string | ReactNode;
  quoteMaxWidth?: string;
  authorImageSrc: string;
  quoteAuthor: string;
  authorsPosition: string;
  authorsCompany: string;
  companyURL: string;
};

export type HeaderEntry = {
  logoURL?: string;
  logoLink?: string;
  logoWidth?: number;
  logoHeight?: number;
  title: string;
  titleSizeClassName?: string;
  description?: string | ReactNode;
  descriptionMaxWidth?: string;
  buttonText?: string;
  buttonIcon?: StaticImageData;
  url?: string | 'SignUp';
  buttonVariant?: 'newDesign' | 'newDesignIndigo' | 'newDesignGray';
};

export type FeatureEntry = {
  title?: string;
  description?: string;
  imageSrc: string | StaticImageData;
  imageWidth?: number;
  imageHeight?: number;
  showImageWithoutPadding?: boolean;
  buttonText?: string;
  url?: string | 'ScrollToSuggestedFeatures';
  qoute?: QuoteEntry;
  buttonOnlyForDesktop?: boolean;
};

export type ImageEntry = {
  imageSrc: string | StaticImageData;
  width: number;
  height: number;
  mobileImageSrc?: string | StaticImageData;
  mobileWidth?: number;
  mobileHeight?: number;
  url?: string;
};

export type VideoDemo = {
  videoId: string;
  width: number;
  height: number;
  name: string;
  icon: React.ReactNode;
};

// Eighteenth new component data

export const eighteenthNewHeaderEntry: HeaderEntry = {
  title: 'Access the world’s top AI models in one place',
  description: (
    <div>
      The best products need the{' '}
      <a href='https://lmarena.ai/?leaderboard' className='underline' target='_blank' rel='noopener noreferrer'>
        best models
      </a>
      . But today, the top 10 models are spread across OpenAI, Anthropic, Google, Llama, Grok and DeepSeek. WorkflowAI
      brings all the state-of-the-art models together — in one platform, with no setup required.
    </div>
  ),
  descriptionMaxWidth: 'max-w-[780px]',
  buttonText: 'Explore top models on the playground',
  url: 'https://workflowai.com/docs/agents/flight-info-extractor/3?versionId=89ed288ccfc7a3ef813119713d50683d&showDiffMode=true&show2ColumnLayout=false&taskRunId2=019620b6-0076-73b5-cb3a-d12cbbce7957&taskRunId3=019620b6-0072-7046-298f-c912681cedf6&taskRunId1=019620b6-3115-7045-ce28-5b33263c527b',
};

export const eighteenthNewImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration39.jpg',
  width: 1168,
  height: 592,
  mobileImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration39Mobile.jpg',
  mobileWidth: 1168,
  mobileHeight: 1307,
};

// Seventeenth new component data

export const seventeenthNewHeaderEntry: HeaderEntry = {
  title: 'Compare models side-by-side',
  description:
    'Compare the top models in one unified playground. Evaluate quality, cost, and speed — and pick what’s best for your product.',
  descriptionMaxWidth: 'max-w-[580px]',
  buttonText: 'Explore all 80 models on the playground',
  url: 'https://workflowai.com/docs/agents/flight-info-extractor/3?versionId=89ed288ccfc7a3ef813119713d50683d&showDiffMode=true&show2ColumnLayout=false&taskRunId2=019620b6-0076-73b5-cb3a-d12cbbce7957&taskRunId3=019620b6-0072-7046-298f-c912681cedf6&taskRunId1=019620b6-3115-7045-ce28-5b33263c527b',
};

export const seventeenthNewImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration38.jpg',
  width: 1168,
  height: 390,
  mobileImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration38Mobile.jpg',
  mobileWidth: 1168,
  mobileHeight: 2376,
};

// Sixteenth new component data

export const sixteenthNewHeaderEntry: HeaderEntry = {
  title: 'Find the best model',
  description:
    'Validate your AI decisions with real numbers. WorkflowAI benchmarks accuracy, speed, and cost — helping you select the best model with confidence.',
  descriptionMaxWidth: 'max-w-[780px]',
  buttonText: 'View Benchmarks',
  url: 'https://workflowai.com/docs/agents/flight-info-extractor/3/benchmarks',
};

export const sixteenthNewImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration37.jpg',
  width: 1168,
  height: 337,
  mobileImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration37Mobile.jpg',
  mobileWidth: 1168,
  mobileHeight: 670,
};

// Fifteenth new component data

export const fifteenthNewHeaderEntry: HeaderEntry = {
  title: 'See how your AI performs in the real world',
  description:
    'No more black-box behavior. WorkflowAI gives you full visibility into every input and output, so you can trust what’s happening in production, spot issues early, and make improvements faster.',
  descriptionMaxWidth: 'max-w-[750px]',
};

export const fifteenthNewImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration36.jpg',
  width: 1168,
  height: 337,
  mobileImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration36Mobile.jpg',
  mobileWidth: 1168,
  mobileHeight: 716,
};

// Fourteenth new component data

export const fourteenthNewHeaderEntry: HeaderEntry = {
  title: 'An AI that improves your AI',
  description:
    'Think of it as your built-in AI prompt engineer. It reviews real outputs, finds what went wrong, and writes the fix — so you don’t have to.',
  descriptionMaxWidth: 'max-w-[750px]',
};

export const fourteenthNewImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration35.jpg',
  width: 1168,
  height: 496,
  mobileImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration35Mobile.jpg',
  mobileWidth: 1168,
  mobileHeight: 659,
};

// Thirteenth new component data

export const thirteenthNewHeaderEntry: HeaderEntry = {
  title: 'Deploy updates instantly — without touching code',
  description:
    'Once the prompt is improved, anyone on the team can ship it to production with a single click. No back and forth, no downtime — just seamless updates that keep your AI performing at its best.',
  descriptionMaxWidth: 'max-w-[840px]',
};

export const thirteenthNewImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration34.jpg',
  width: 1168,
  height: 368,
  mobileImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration34Mobile.jpg',
  mobileWidth: 1168,
  mobileHeight: 1446,
};

// Twelfth new component data

export const twelfthNewHeaderEntry: HeaderEntry = {
  title: 'Hey Product Managers and Designers out there, here are some things you might like:',
  titleSizeClassName: 'max-w-[650px]',
};

export const twelfthNewFeaturesEntries: FeatureEntry[] = [
  {
    title: 'Go from idea to AI feature. No code needed.',
    description:
      'Stop waiting on bandwidth. WorkflowAI lets anyone on your team design, test, and deploy AI features using plain language - no code needed.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration1.jpg',
    imageHeight: 310,
    imageWidth: 524,
    buttonText: 'Start with your idea',
    buttonOnlyForDesktop: true,
    url: 'https://workflowai.com/_/agents?newTaskModalOpen=true&mode=new&redirectToPlaygrounds=true',
  },
  {
    title: 'No more switching tabs and spreadsheets to compare models.',
    description: 'WorkflowAI shows you outputs, costs, and latency side-by-side, all in one view.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration32.jpg',
    imageHeight: 310,
    imageWidth: 524,
    buttonText: 'Explore all 80 models on the playground',
    url: 'https://workflowai.com/docs/agents/flight-info-extractor/3?versionId=89ed288ccfc7a3ef813119713d50683d&showDiffMode=true&show2ColumnLayout=false&taskRunId2=019620b6-0076-73b5-cb3a-d12cbbce7957&taskRunId3=019620b6-0072-7046-298f-c912681cedf6&taskRunId1=019620b6-3115-7045-ce28-5b33263c527b',
  },
  {
    title: 'Tired of black-box AI? Now you can see inside.',
    description:
      'When the AI gets it wrong, you need to know why — fast. WorkflowAI logs every input and output automatically, so you can spot issues, understand what went wrong, and fix it without waiting on engineering.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration10.jpg',
    imageHeight: 310,
    imageWidth: 524,
    buttonText: 'Try this feature',
    url: 'https://workflowai.com/docs/agents/flight-info-extractor/3/runs?page=0',
  },
  {
    title: 'Edit prompts. Skip the tickets.',
    description:
      'Tired of creating tickets just to tweak a prompt? WorkflowAI lets you update prompts instantly, no engineering work required. Go from feedback to fix in seconds.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration33.jpg',
    imageHeight: 310,
    imageWidth: 524,
  },
];

// Eleventh new component data

export const eleventhNewHeaderEntry: HeaderEntry = {
  title: 'Engineers we got you too...',
  description: 'We’re engineers building for engineers.',
};

export const eleventhNewFeaturesEntries: FeatureEntry[] = [
  {
    title: 'One SDK to run them all (80, to be exact).',
    description:
      'Stop wasting time maintaining separate integrations for every LLM. WorkflowAI gives you unified, seamless access to all models through a single, clean API.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration7.jpg',
    qoute: {
      quote:
        '“Being provider-agnostic used to mean maintaining multiple complex integrations. With WorkflowAI, we can seamlessly switch between LLM providers without any extra integration effort or overhead, saving us engineering time and headaches.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author4.jpg',
      quoteAuthor: 'Aymeric Beaumet',
      authorsPosition: 'CTO',
      authorsCompany: 'M1',
      companyURL: 'https://www.hellom1.com/',
    },
  },
  {
    title: 'Consistent, structured outputs from your AI—every time.',
    description:
      'WorkflowAI ensures your AI responses always match your defined structure, simplifying integrations, reducing parsing errors, and making your data reliable and ready for use.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration8.jpg',
    qoute: {
      quote:
        '“Before WorkflowAI, parsing AI outputs was brittle and error-prone. Now we get structured outputs consistently, streamlining our workflows and significantly improving reliability.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author5.jpg',
      quoteAuthor: 'Xavier Durand',
      authorsPosition: 'CEO',
      authorsCompany: 'Chilli',
      companyURL: 'https://www.chilli.club',
    },
  },
];

// Tenth new component data

export const tenthNewFeaturesEntries: FeatureEntry[] = [
  {
    title: 'Write code only when you want to',
    description:
      'WorkflowAI gives you flexibility: quickly prototype new AI features via our intuitive web interface, or dive directly into code whenever you need deeper customization and control.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration5.jpg',
    buttonText: 'View SDK Documentation',
    url: 'https://docs.workflowai.com/python-sdk/get-started',
  },
];

export const tenthNewQuoteEntry: QuoteEntry = {
  quote: (
    <div>
      “WorkflowAI lets me rapidly prototype AI concepts right in the browser, but still allows full code-level
      integration when I need precision and custom logic.{' '}
      <span className='text-gray-700 font-semibold'>It’s the best of both worlds.</span>”
    </div>
  ),
  quoteMaxWidth: 'max-w-[600px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author2.jpg',
  quoteAuthor: 'Blake Yoder',
  authorsPosition: 'Head of Engineering',
  authorsCompany: 'Berry Street',
  companyURL: 'https://www.berrystreet.co',
};

// Ninth new component data

export const ninthNewFeaturesEntries: FeatureEntry[] = [
  {
    title: 'Integrate with the language you already use',
    description:
      'Use WorkflowAI in the language your team already works in — Python, TypeScript, or a simple HTTP API.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration15.jpg',
  },
  {
    title: 'Works natively with TypeScript',
    description:
      'Define your inputs and outputs with TypeScript interfaces, and get back fully typed, structured responses. No guesswork. No custom parsing.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration16.jpg',
    buttonText: 'View TypeScript code sample',
    url: 'https://workflowai.com/docs/agents/insurance-policy-information-extraction/2/code?selectedLanguage=TypeScript',
  },
  {
    title: 'Native Python integration',
    description:
      'Pydantic models give you structured outputs without the fragile parsing. Clean, type-safe data—ready to plug into your app.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration17.jpg',
    buttonText: 'View Python code sample',
    url: 'https://workflowai.com/docs/agents/insurance-policy-information-extraction/2/code?selectedLanguage=Python',
  },
  {
    title: 'Predictable JSON over HTTP',
    description:
      'Send a POST request and receive clean, structured JSON—ready for your app, workflows, or database. No parsing headaches, just reliable outputs.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration18.jpg',
    buttonText: 'Try the API',
    url: 'https://workflowai.com/docs/agents/insurance-policy-information-extraction/2/code?selectedLanguage=Rest',
  },
];

// Eighth new component data

export const eighthNewHeaderEntry: HeaderEntry = {
  title: 'Open Source. Self-Host. Customize. Contribute.',
  description:
    'WorkflowAI is fully open source — giving you the freedom to self-host, customize, or contribute. No hidden logic. No lock-in. Just powerful tooling you control.',
  descriptionMaxWidth: 'max-w-[780px]',
  buttonText: 'Star on GitHub',
  buttonIcon: GitHubSrc,
  url: 'https://github.com/WorkflowAI/workflowai',
};

export const eighthNewImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration31.jpg',
  width: 1168,
  height: 496,
};

// Seventh new component data

export const seventhNewHeaderEntry: HeaderEntry = {
  title: 'Get all of the above, without paying more',
  description:
    'You pay exactly what you’d pay the model providers — billed per token, with no minimums and no per-seat fees. No markups. We make our margin from provider discounts, not by charging you extra.',
  descriptionMaxWidth: 'max-w-[980px]',
  buttonText: 'Learn more about our business model',
  url: 'https://docs.workflowai.com/workflowai-cloud/pricing',
};

export const seventhNewQuoteEntry: QuoteEntry = {
  quote: `“The fact that WorkflowAI matches provider pricing was a no-brainer for us. We get the same models at the same cost, but with better tools, observability, and reliability. And since there are no per-seat fees, our whole team can jump in and help build great AI features. It’s like getting a whole AI platform for free.”`,
  quoteMaxWidth: 'max-w-[750px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author6.jpg',
  quoteAuthor: 'Antoine Martin',
  authorsPosition: 'CEO',
  authorsCompany: 'Amo',
  companyURL: 'https://amo.co',
};

// Sixth new component data

export const sixthNewHeaderEntry: HeaderEntry = {
  title: 'Want Proof? You can hear it from our users',
};

// Fifth new component data

export const fifthNewHeaderEntry: HeaderEntry = {
  logoURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingCompanyLogo2.png',
  logoLink: 'https://www.berrystreet.co',
  logoWidth: 188,
  logoHeight: 32,
  title: 'From 0 to 6 AI features in just 8 weeks',
  description:
    'Our customer Berry Street, a personalized nutrition therapy service went from 0 to 6 AI features in less than 2 months. Now their AI features are running over 49,000 times per week.',
  descriptionMaxWidth: 'max-w-[900px]',
};

export const fifthNewFeaturesEntries: FeatureEntry[] = [
  {
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration28.jpg',
    imageWidth: 372,
    imageHeight: 266,
    showImageWithoutPadding: true,
    qoute: {
      quote:
        '“Our users genuinely love the AI features — we hear it in feedback and see it in the numbers. With WorkflowAI, we shipped 6 AI features in 8 weeks, and they now run over 45,000 times a week. It completely changed how we think about building — AI is no longer a future investment, it’s a core part of our product today.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author9.jpg',
      quoteAuthor: 'Jesse Rose',
      authorsPosition: 'CEO',
      authorsCompany: 'Berry Street',
      companyURL: 'https://www.berrystreet.co',
    },
  },
  {
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration29.jpg',
    imageWidth: 372,
    imageHeight: 266,
    showImageWithoutPadding: true,
    qoute: {
      quote:
        '“Implementing directly with an AI provider would have taken us weeks — if not months — to get the reliability, observability, and structure we needed. With WorkflowAI, we had everything out of the box. We’ve saved countless engineering hours, and the product team can now update prompts and test new models on their own. That’s a huge shift.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author2.jpg',
      quoteAuthor: 'Blake Yoder',
      authorsPosition: 'Head of Engineering',
      authorsCompany: 'Berry Street',
      companyURL: 'https://www.berrystreet.co',
    },
  },
  {
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration30.jpg',
    imageWidth: 372,
    imageHeight: 266,
    showImageWithoutPadding: true,
    qoute: {
      quote:
        '“I’ve always had great ideas for AI features, but engineering resources were always the bottleneck. Now, with WorkflowAI, I’ve been able to ship AI features myself—no coding, no waiting. I can quickly go to market, gather customer feedback, and iterate fast.“',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author1.jpg',
      quoteAuthor: 'Perri Gould',
      authorsPosition: 'Head of Product',
      authorsCompany: 'Berry Street',
      companyURL: 'https://www.berrystreet.co',
    },
  },
];

// Fourth new component data

export const fourthNewHeaderEntry: HeaderEntry = {
  logoURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingCompanyLogo1.png',
  logoLink: 'https://www.hellom1.com/',
  logoWidth: 94,
  logoHeight: 32,
  title: 'M1 builds reliable, AI-first features faster with WorkflowAI',
  description:
    'M1, a fast-growing AI-first company, powers core features with WorkflowAI — from extracting meeting notes and todos to summarizing phone calls. With a 4.8 rating on the App Store and hundreds of glowing reviews, it’s clear that users aren’t just using these AI features — they love them.',
  descriptionMaxWidth: 'max-w-[900px]',
};

export const fourthNewFeaturesEntries: FeatureEntry[] = [
  {
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration25.jpg',
    imageWidth: 372,
    imageHeight: 266,
    showImageWithoutPadding: true,
    qoute: {
      quote:
        '“WorkflowAI turned our AI vision into reality. It compressed our roadmap from quarters to weeks — and now AI is at the center of our product experience.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author3.jpg',
      quoteAuthor: 'Maxime Germain',
      authorsPosition: 'CEO',
      authorsCompany: 'M1',
      companyURL: 'https://www.hellom1.com/',
    },
  },
  {
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration26.jpg',
    imageWidth: 372,
    imageHeight: 266,
    showImageWithoutPadding: true,
    qoute: {
      quote:
        '“WorkflowAI gives us benchmarking, structured outputs, and a unified SDK to access every model — all in one place. It lets us move fast without compromising on reliability or observability.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author4.jpg',
      quoteAuthor: 'Aymeric Beaumet',
      authorsPosition: 'CTO',
      authorsCompany: 'M1',
      companyURL: 'https://www.hellom1.com/',
    },
  },
  {
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration27.jpg',
    imageWidth: 372,
    imageHeight: 266,
    showImageWithoutPadding: true,
    qoute: {
      quote:
        '“The most exciting thing about WorkflowAI is how it empowers product and design — we can build and launch AI-powered features without relying on engineering. It’s like turning every PM into an AI builder.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author8.jpg',
      quoteAuthor: 'Justin Bureau',
      authorsPosition: 'Product Manager',
      authorsCompany: 'M1',
      companyURL: 'https://www.hellom1.com/',
    },
  },
];

// Third new component data

export const thirdNewHeaderEntry: HeaderEntry = {
  title: 'Infrastructure you can trust — backed by data',
};

// Second new component data

export const secondNewHeaderEntry: HeaderEntry = {
  title: '...all while keeping your data safe',
};

export const secondNewFeaturesEntries: FeatureEntry[] = [
  {
    title: 'No Model Training.',
    description:
      'All models are hosted in the U.S., and we have BAAs in place with every provider to ensure your data is never used for training.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration19.jpg',
  },
  {
    title: 'SOC-2 Compliant.',
    description:
      'We ensure security and privacy standards, giving you confidence that your data is safe and handled responsibly.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration20.jpg',
    buttonText: 'View our SOC-2 report',
    url: 'https://workflowai.blob.core.windows.net/workflowai-public/soc2.pdf',
  },
];

// First new component data

export const firstNewFeaturesEntries: HeaderEntry = {
  title: 'Build AI features your users will love.',
  description: 'AI is redefining every product.  What’s your AI roadmap?',
  buttonText: 'Start building for free',
  url: 'SignUp',
  buttonVariant: 'newDesignIndigo',
};

// Comparision new component data

export const comparisionHeaderEntry: HeaderEntry = {
  title: 'WorkflowAI is more reliable than OpenAI',
  description:
    'How? WorkflowAI is built with automatic provider failover — so even when OpenAI is down, your AI features stay up. Because your AI shouldn’t go down just because OpenAI does.',
  descriptionMaxWidth: 'max-w-[1050px]',
  buttonText: 'See how our failover system works',
  url: 'https://docs.workflowai.com/workflowai-cloud/reliability',
};

// Video demos

export const videoDemos: VideoDemo[] = [
  {
    videoId: '6dd8ba57257c1bbaa870f49a36d256ac',
    width: 1280,
    height: 720,
    name: 'Describe',
    icon: <ChatRegular className='w-4 h-4' />,
  },
  {
    videoId: '28d15ef03f8069f31bc1aa12dd848208',
    width: 1280,
    height: 720,
    name: 'Compare',
    icon: <DataUsageRegular className='w-4 h-4' />,
  },
  {
    videoId: 'd9b84a67c09a218f7f777459f5a7c355',
    width: 1280,
    height: 720,
    name: 'Deploy',
    icon: <CloudRegular className='w-4 h-4' />,
  },
  {
    videoId: '7d8a1b00e3d10b657c3910330ae83953',
    width: 1280,
    height: 720,
    name: 'Observe',
    icon: <ListBarTreeRegular className='w-4 h-4' />,
  },
  {
    videoId: '9983b7e0b7bca28ced765af6a74a5313',
    width: 1280,
    height: 720,
    name: 'Improve',
    icon: <ArrowTrendingRegular className='w-4 h-4' />,
  },
  {
    videoId: '0fb363416b744eaf3a269780148fcc0f',
    width: 1280,
    height: 720,
    name: 'Monitor',
    icon: <ClipboardTaskList16Regular className='w-4 h-4' />,
  },
];
