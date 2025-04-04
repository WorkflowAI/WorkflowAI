import { StaticImageData } from 'next/image';
import { ReactNode } from 'react';

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
  title: string;
  titleSizeClassName?: string;
  description?: string;
  descriptionMaxWidth?: string;
  buttonText?: string;
  url?: string;
};

export type FeatureEntry = {
  title: string;
  description: string;
  imageSrc: string | StaticImageData;
  buttonText?: string;
  url?: string | 'ScrollToSuggestedFeatures';
  qoute?: QuoteEntry;
};

export type ImageEntry = {
  imageSrc: string | StaticImageData;
  width: number;
  height: number;
  url?: string;
};

// First component data

export const firstHeaderEntry: HeaderEntry = {
  title: 'Build AI features in 1...2..3',
  titleSizeClassName: 'sm:text-[48px] text-[30px]',
  description:
    'WorkflowAI empowers product managers to create powerful AI features entirely through an intuitive web interface. No coding required.',
  descriptionMaxWidth: 'max-w-[700px]',
};

export const firstFeaturesEntries: FeatureEntry[] = [
  {
    title: 'If you can explain it, you can build it.',
    description: 'Write a quick sentence about what you want the AI to do  — that’s all you need to get started.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration1.jpg',
    buttonText: 'Start with your idea',
    url: 'https://workflowai.com/_/agents?newTaskModalOpen=true&mode=new&redirectToPlaygrounds=true',
  },
  {
    title: 'Drop your website. Get smart suggestions.',
    description:
      'WorkflowAI generates a production-ready prompt automatically—structured, optimized, and ready to test. You can tweak or deploy it as is.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration2.jpg',
    buttonText: 'Discover AI-powered use cases for my product',
    url: 'ScrollToSuggestedFeatures',
  },
  {
    title: 'AI-generated prompt',
    description:
      'Enter your product’s website and we’ll suggest high-impact AI features based on what you offer. Or explore our curated library of use cases.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration3.jpg',
  },
  {
    title: 'Ready to Ship',
    description:
      'Test your feature in seconds and iterate until it’s right. Once you’re happy, hand it off to engineering with everything they need to ship it fast.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration4.jpg',
    buttonText: 'Try Flight Information Extractor',
    url: 'https://workflowai.com/docs/agents/flight-info-extractor/3?versionId=89ed288ccfc7a3ef813119713d50683d&showDiffMode=true&show2ColumnLayout=false&taskRunId2=0195ee61-f33b-70a7-6e52-dcc855a12320&taskRunId3=0195ee61-f393-71d1-dc40-8dc035141299&taskRunId1=0195f2a1-0a8e-7231-7a3e-35154c7229e1',
  },
];

export const firstQuoteEntry: QuoteEntry = {
  quote: (
    <div>
      “I’ve always had great ideas for AI features, but engineering resources were always the bottleneck. Now, with
      WorkflowAI, I’ve been able to ship AI features myself—
      <span className='text-gray-700 font-semibold'>no coding, no waiting</span>. I can quickly go to market, gather
      customer feedback, and iterate fast.“
    </div>
  ),
  quoteMaxWidth: 'max-w-[800px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author1.jpg',
  quoteAuthor: 'Perri Gould',
  authorsPosition: 'Head of product',
  authorsCompany: 'Berry Street',
  companyURL: 'https://www.berrystreet.co',
};

// Second component data

export const secondFeaturesEntries: FeatureEntry[] = [
  {
    title: 'Write code only when you want to',
    description:
      'WorkflowAI gives you flexibility: quickly prototype new AI features via our intuitive web interface, or dive directly into code whenever you need deeper customization and control.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration5.jpg',
    buttonText: 'View SDK Documentation',
    url: 'https://docs.workflowai.com/python-sdk/get-started',
  },
];

export const secondQuoteEntry: QuoteEntry = {
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

// Third component data

export const thirdHeaderEntry: HeaderEntry = {
  title: 'Compare models side-by-side',
  description:
    'Use the playground to compare outputs, costs, and latency across 73 models — all available without any setup. Pay the same price as using the AI provider directly.',
  descriptionMaxWidth: 'max-w-[700px]',
  buttonText: 'Try comparing models on the playground',
  url: 'https://workflowai.com/docs/agents/insurance-policy-information-extraction/2?version[…]68b05a9707ea38c6b7=&showDiffMode=false&show2ColumnLayout=false&versionId=ae1b15cab4cd8268b05a9707ea38c6b7&taskRunId1=0195f2aa-89d5-71c4-39eb-ce2c2fc8652f&taskRunId3=0195f2aa-89db-7171-3d4f-ddfb35bac7dc&taskRunId2=0195f2aa-89d6-70b0-24a9-8e8a69ef0b2f',
};

export const thirdImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration6.jpg',
  width: 1163,
  height: 390,
  url: 'https://workflowai.com/docs/agents/insurance-policy-information-extraction/2?version[…]68b05a9707ea38c6b7=&showDiffMode=false&show2ColumnLayout=false&versionId=ae1b15cab4cd8268b05a9707ea38c6b7&taskRunId1=0195f2aa-89d5-71c4-39eb-ce2c2fc8652f&taskRunId3=0195f2aa-89db-7171-3d4f-ddfb35bac7dc&taskRunId2=0195f2aa-89d6-70b0-24a9-8e8a69ef0b2f',
};

export const thirdQuoteEntry: QuoteEntry = {
  quote: (
    <div>
      “Before WorkflowAI, we were locked into OpenAI because integrating other models was too complex. Now,{' '}
      <span className='text-gray-700 font-semibold'>switching is effortless</span>—we’ve easily tested alternatives and
      saved over 90% by using Google’s models.”
    </div>
  ),
  quoteMaxWidth: 'max-w-[800px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author3.jpg',
  quoteAuthor: 'Maxime Germain',
  authorsPosition: 'CEO',
  authorsCompany: 'InterfaceAI',
  companyURL: 'https://interfaceai.com',
};

// Fourth component data

export const fourthHeaderEntry: HeaderEntry = {
  title: 'One SDK to run them all (73, to be exact).',
};

export const fourthFeaturesEntries: FeatureEntry[] = [
  {
    title: 'One SDK, 73 LLMs—no integration headaches',
    description:
      'Stop wasting time maintaining separate integrations for every LLM. WorkflowAI gives you unified, seamless access to all models through a single, clean API—always matching the providers’ pricing.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration7.jpg',
    buttonText: 'Explore 73 models on the playground',
    url: 'https://workflowai.com/docs/agents/flight-info-extractor/3?versionId=89ed288ccfc7a3ef813119713d50683d&showDiffMode=true&show2ColumnLayout=false&taskRunId2=0195ee61-f33b-70a7-6e52-dcc855a12320&taskRunId3=0195ee61-f393-71d1-dc40-8dc035141299&taskRunId1=0195f2a1-0a8e-7231-7a3e-35154c7229e1',
    qoute: {
      quote:
        '“Being provider-agnostic used to mean maintaining multiple complex integrations. With WorkflowAI, we can seamlessly switch between LLM providers without any extra integration effort or overhead, saving us engineering time and headaches.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author4.jpg',
      quoteAuthor: 'Aymeric Beaumet',
      authorsPosition: 'CTO',
      authorsCompany: 'InterfaceAI',
      companyURL: 'https://interfaceai.com',
    },
  },
  {
    title: 'Consistent, structured outputs from your AI—every time',
    description:
      'WorkflowAI ensures your AI responses always match your defined structure, simplifying integrations, reducing parsing errors, and making your data reliable and ready for use.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration8.jpg',
    buttonText: 'Test structured output',
    url: 'https://workflowai.com/docs/agents/insurance-policy-information-extraction/2?version[…]68b05a9707ea38c6b7=&showDiffMode=false&show2ColumnLayout=false&versionId=ae1b15cab4cd8268b05a9707ea38c6b7&taskRunId1=0195f2aa-89d5-71c4-39eb-ce2c2fc8652f&taskRunId3=0195f2aa-89db-7171-3d4f-ddfb35bac7dc&taskRunId2=0195f2aa-89d6-70b0-24a9-8e8a69ef0b2f',
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

// Fifth component data

export const fifthHeaderEntry: HeaderEntry = {
  title: 'Same models. Same price. No markups.',
  description:
    'You pay exactly what you’d pay the model providers — billed per token, with no minimums and no per-seat fees. We make our margin on them, not you.',
  descriptionMaxWidth: 'max-w-[980px]',
  buttonText: 'Learn more about our business model',
  url: 'https://docs.workflowai.com/workflowai-cloud/pricing',
};

export const fifthQuoteEntry: QuoteEntry = {
  quote: `“The fact that WorkflowAI matches provider pricing was a no-brainer for us.
We get the same models at the same cost, but with better tools, observability, and reliability.
And since there are no per-seat fees, our whole team can jump in and help build great AI features.
It’s like getting a whole AI platform for free.”`,
  quoteMaxWidth: 'max-w-[750px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author6.jpg',
  quoteAuthor: 'Antoine Martin',
  authorsPosition: 'CEO',
  authorsCompany: 'Amo',
  companyURL: 'https://amo.co',
};

// Sixth component data

export const sixthHeaderEntry: HeaderEntry = {
  title: 'Find the best AI, every time',
  description:
    'Run automated benchmarks to quickly compare accuracy, price, and latency so you can confidently select the perfect model and prompt combination for every AI feature.',
  descriptionMaxWidth: 'max-w-[780px]',
};

export const sixthImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration9.jpg',
  width: 1163,
  height: 390,
};

export const sixthQuoteEntry: QuoteEntry = {
  quote: `“Being provider-agnostic used to mean maintaining multiple complex integrations. With WorkflowAI, we can seamlessly switch between LLM providers without any extra integration effort or overhead, saving us engineering time and headaches.”`,
  quoteMaxWidth: 'max-w-[850px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author4.jpg',
  quoteAuthor: 'Aymeric Beaumet',
  authorsPosition: 'CTO',
  authorsCompany: 'InterfaceAI',
  companyURL: 'https://interfaceai.com',
};

// Seventh component data

export const seventhHeaderEntry: HeaderEntry = {
  title: 'Understand How Your AI Performs',
  description: 'Everything you need to debug, iterate, and improve your AI features — all in one place.',
};

export const seventhFeaturesEntries: FeatureEntry[] = [
  {
    title: 'See what happened',
    description:
      'WorkflowAI logs every input and output automatically — giving you the visibility you need to iterate and improve quickly.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration10.jpg',
  },
  {
    title: 'Find the runs you care about',
    description:
      'Search past runs by input, output, model, or timestamp. Instantly surface the examples you need to debug, analyze, or improve.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration11.jpg',
  },
  {
    title: 'Improve the outcome',
    description:
      'Didn’t get the result you wanted? Retry the run in the playground — tweak the prompt or switch models to see what works better.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration12.jpg',
  },
  {
    title: 'Unlimited storage',
    description:
      'Store as many runs as you want. WorkflowAI handles scale for you — so you never lose visibility, even as your usage grows.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration13.jpg',
  },
];

export const seventhQuoteEntry: QuoteEntry = {
  quote: (
    <div>
      “AI is non-deterministic, so{' '}
      <span className='text-gray-700 font-semibold'>understanding what happens after deployment is crucial.</span>{' '}
      WorkflowAI automatically logs all outputs, enabling rapid issue diagnosis and prompt improvements.”
    </div>
  ),
  quoteMaxWidth: 'max-w-[750px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author7.jpg',
  quoteAuthor: 'Gabriela Garcia',
  authorsPosition: 'Product Manager',
  authorsCompany: 'Luni',
  companyURL: 'https://www.luni.app',
};

// Eighth component data

export const eighthHeaderEntry: HeaderEntry = {
  title: 'Bring the best prompt engineer onto your team',
  description: 'WorkflowAI can automatically re-write prompts based on your feedback.',
};

export const eighthImageEntry: ImageEntry = {
  imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration14.jpg',
  width: 1268,
  height: 496,
};

export const eighthQuoteEntry: QuoteEntry = {
  quote: `“It’s hard to go back to manual prompting after this. The agent just… gets it.”`,
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author6.jpg',
  quoteAuthor: 'Antoine Martin',
  authorsPosition: 'CEO',
  authorsCompany: 'Amo',
  companyURL: 'https://www.amo.co',
};

// Ninth component data

export const ninthHeaderEntry: HeaderEntry = {
  title: 'Integration that makes your engineering team happy',
  description:
    'WorkflowAI provides your engineering team with a seamless, developer-friendly integration process, turning AI features built by PMs into production-ready experiences quickly.',
  descriptionMaxWidth: 'max-w-[850px]',
};

export const ninthFeaturesEntries: FeatureEntry[] = [
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

export const ninthQuoteEntry: QuoteEntry = {
  quote:
    '“When PMs build new AI features using WorkflowAI, integrating them is straightforward and stress-free. Our engineers appreciate how quickly these features fit into our existing backend—without surprises.”',
  quoteMaxWidth: 'max-w-[850px]',
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author4.jpg',
  quoteAuthor: 'Aymeric Beaumet',
  authorsPosition: 'CTO',
  authorsCompany: 'InterfaceAI',
  companyURL: 'https://www.interfaceai.com',
};

// Tenth component data

export const tenthFeaturesEntries: FeatureEntry[] = [
  {
    title: 'Your Data Belongs to You',
    description:
      'We never use your data for LLM training—your information stays private and exclusively yours. All models are hosted in the U.S., and we have BAAs in place with every provider to ensure your data is never used for training.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration19.jpg',
  },
  {
    title: 'SOC-2 Compliant',
    description:
      'We ensure security and privacy standards, giving you confidence that your data is safe and handled responsibly.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration20.jpg',
    buttonText: 'View our SOC-2 report',
    url: 'https://workflowai.blob.core.windows.net/workflowai-public/soc2.pdf',
  },
];

// Eleventh component data

export const eleventhHeaderEntry: HeaderEntry = {
  title: 'Built-in high performance and automatic reliability',
  description:
    'WorkflowAI runs on dedicated high-performance infrastructure, adding only ~20ms latency per inference call. Automatically switches providers if one goes down—ensuring your AI features stay reliable.',
  descriptionMaxWidth: 'max-w-[780px]',
  buttonText: 'Learn more about our infrastructure',
  url: 'https://docs.workflowai.com/workflowai-cloud/reliability',
};

export const eleventhFeaturesEntries: FeatureEntry[] = [
  {
    title: 'OpenAI without WorkflowAI',
    description: 'OpenAI API goes down. Your AI features stop working.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration21.jpg',
  },
  {
    title: 'OpenAI with WorkflowAI',
    description:
      'OpenAI API goes down. WorkflowAI automatically routes requests to Azure OpenAI. Your AI features keep working.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration22.jpg',
  },
];

export const eleventhQuoteEntry: QuoteEntry = {
  quote: `“When OpenAI had a 5-hour outage in February, WorkflowAI automatically switched to AzureAI—providing identical OpenAI models without interruption. The seamless fallback and minimal latency meant zero downtime for our users, keeping our AI features reliably online.”`,
  authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author4.jpg',
  quoteAuthor: 'Aymeric Beaumet',
  authorsPosition: 'CTO',
  authorsCompany: 'InterfaceAI',
  companyURL: 'https://www.interfaceai.com',
};

// Twelfth component data

export const twelfthFeaturesEntries: FeatureEntry[] = [
  {
    title: 'Update prompts instantly — no code changes required — to accelerate AI improvements',
    description:
      'Empower your team to fine-tune prompts and deploy models effortlessly—delivering smarter, more reliable AI features faster.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration23.jpg',
    qoute: {
      quote:
        '“Every time we needed to tweak a prompt, we had to go through engineering, wait for a deployment, and hope it didn’t break something else. It slowed us down and made iteration painful. With WorkflowAI, we can refine prompts instantly and ship better AI features without bottlenecks.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author1.jpg',
      quoteAuthor: 'Perri Gould',
      authorsPosition: 'Head of product',
      authorsCompany: 'Berry Street',
      companyURL: 'https://www.berrystreet.co',
    },
  },
  {
    title: 'AI that stays current using built-in web search and browsing',
    description:
      'WorkflowAI integrates web search and browsing directly into your AI features, ensuring your LLM delivers timely, accurate, and highly relevant information.',
    imageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/LandingIllustration24.jpg',
    qoute: {
      quote:
        '“WorkflowAI lets me rapidly prototype AI concepts right in the browser, but still allows full code-level integration when I need precision and custom logic. It’s the best of both worlds.”',
      authorImageSrc: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/author8.jpg',
      quoteAuthor: 'Justin Bureau',
      authorsPosition: 'Product Manager',
      authorsCompany: 'InterfaceAI',
      companyURL: 'https://www.interfaceai.com',
    },
  },
];

// Thirteenth component data

export const thirteenthHeaderEntry: HeaderEntry = {
  title: 'What can AI do for your product?',
  description: 'Enter your product URL to get personalized suggestions, or browse by category for inspiration.',
};
