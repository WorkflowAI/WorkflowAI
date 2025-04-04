'use client';

import { useCallback } from 'react';
import { LandingPageContainer } from './container/LandingPageContainer';
import { URLHeaderComponent } from './sections/Components/HeaderComponent';
import { SuggestedFeaturesComponent } from './sections/SuggestedFeatures/SuggestedFeaturesComponent';

type URLLandingPageProps = {
  companyURL?: string;
};

export function URLLandingPage(props: URLLandingPageProps) {
  const { companyURL } = props;

  const scrollToPricing = useCallback(() => {
    const pricingSection = document.getElementById('pricing');
    if (pricingSection) {
      pricingSection.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  return (
    <LandingPageContainer scrollToPricing={scrollToPricing}>
      <URLHeaderComponent className='mt-20' />
      <SuggestedFeaturesComponent className='mt-2 mb-28' companyURL={companyURL} hideSidebar={true} />
    </LandingPageContainer>
  );
}
