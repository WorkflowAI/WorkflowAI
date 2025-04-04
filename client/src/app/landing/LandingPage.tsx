'use client';

import { useCallback, useState } from 'react';
import { Dialog } from '@/components/ui/Dialog';
import { DialogContent } from '@/components/ui/Dialog';
import { LandingPageContainer } from './container/LandingPageContainer';
import { GridComponent } from './sections/Components/GridComponent';
import { HeaderComponent } from './sections/Components/HeaderComponent';
import { ImageComponent } from './sections/Components/ImageComponent';
import { InvestorLogosComponent } from './sections/Components/InvestorLogosComponent';
import { PriceComponent } from './sections/Components/PriceComponent';
import { QuoteComponent } from './sections/Components/QuoteComponent';
import { RowsComponent } from './sections/Components/RowsComponent';
import { SubheaderComponent } from './sections/Components/SubheaderComponent';
import { VideoDemoComponent } from './sections/Components/VideoDemoComponent';
import * as LandingStaticData from './sections/StaticData/LandingStaticData';
import {
  SuggestedFeaturesComponent,
  SuggestedFeaturesComponentModal,
} from './sections/SuggestedFeatures/SuggestedFeaturesComponent';

export function LandingPage() {
  const [companyURL, setCompanyURL] = useState<string | undefined>(undefined);
  const [showSuggestedFeaturesModal, setShowSuggestedFeaturesModal] = useState<boolean>(false);

  const scrollToPricing = useCallback(() => {
    const pricingSection = document.getElementById('pricing');
    if (pricingSection) {
      pricingSection.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  const scrollToSuggestedFeatures = useCallback(() => {
    const suggestedFeaturesSection = document.getElementById('suggested-features');
    if (suggestedFeaturesSection) {
      suggestedFeaturesSection.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  return (
    <LandingPageContainer scrollToPricing={scrollToPricing}>
      <HeaderComponent
        className='mt-20'
        scrollToPricing={scrollToPricing}
        showSuggestedFeaturesModal={() => setShowSuggestedFeaturesModal(true)}
      />
      <VideoDemoComponent className='sm:mt-20 mt-14' />
      <InvestorLogosComponent className='mt-20' />

      <SubheaderComponent entry={LandingStaticData.firstHeaderEntry} className='sm:mt-40 mt-28' />
      <GridComponent
        entries={LandingStaticData.firstFeaturesEntries}
        className='mt-12'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />
      <QuoteComponent entry={LandingStaticData.firstQuoteEntry} className='mt-12' />

      <RowsComponent entries={LandingStaticData.secondFeaturesEntries} className='sm:mt-40 mt-28' />
      <QuoteComponent entry={LandingStaticData.secondQuoteEntry} className='mt-12' />

      <SubheaderComponent entry={LandingStaticData.thirdHeaderEntry} className='sm:mt-40 mt-28' />
      <ImageComponent entry={LandingStaticData.thirdImageEntry} className='mt-12' />
      <QuoteComponent entry={LandingStaticData.thirdQuoteEntry} className='mt-12' />

      <SubheaderComponent entry={LandingStaticData.fourthHeaderEntry} className='sm:mt-40 mt-28' />
      <GridComponent
        entries={LandingStaticData.fourthFeaturesEntries}
        className='mt-12'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />

      <SubheaderComponent entry={LandingStaticData.fifthHeaderEntry} className='sm:mt-40 mt-28' id='pricing' />
      <PriceComponent className='mt-12' />
      <QuoteComponent entry={LandingStaticData.fifthQuoteEntry} className='mt-12' />

      <SubheaderComponent entry={LandingStaticData.sixthHeaderEntry} className='sm:mt-40 mt-28' />
      <ImageComponent entry={LandingStaticData.sixthImageEntry} className='mt-12' />
      <QuoteComponent entry={LandingStaticData.sixthQuoteEntry} className='mt-12' />

      <SubheaderComponent entry={LandingStaticData.seventhHeaderEntry} className='sm:mt-40 mt-28' />
      <GridComponent
        entries={LandingStaticData.seventhFeaturesEntries}
        className='mt-12'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />
      <QuoteComponent entry={LandingStaticData.seventhQuoteEntry} className='mt-12' />

      <SubheaderComponent entry={LandingStaticData.eighthHeaderEntry} className='sm:mt-40 mt-28' />
      <ImageComponent entry={LandingStaticData.eighthImageEntry} className='mt-12' />
      <QuoteComponent entry={LandingStaticData.eighthQuoteEntry} className='mt-12' />

      <SubheaderComponent entry={LandingStaticData.ninthHeaderEntry} className='sm:mt-40 mt-28' />
      <GridComponent
        entries={LandingStaticData.ninthFeaturesEntries}
        className='mt-12'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />
      <QuoteComponent entry={LandingStaticData.ninthQuoteEntry} className='mt-12' />

      <GridComponent
        entries={LandingStaticData.tenthFeaturesEntries}
        className='sm:mt-40 mt-28'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />

      <SubheaderComponent entry={LandingStaticData.eleventhHeaderEntry} className='sm:mt-40 mt-28' />
      <GridComponent
        entries={LandingStaticData.eleventhFeaturesEntries}
        className='mt-12'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />
      <QuoteComponent entry={LandingStaticData.eleventhQuoteEntry} className='mt-12' />

      <GridComponent
        entries={LandingStaticData.twelfthFeaturesEntries}
        className='mt-12'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />

      <SubheaderComponent
        entry={LandingStaticData.thirteenthHeaderEntry}
        className='sm:mt-40 mt-28'
        id='suggested-features'
      />
      <SuggestedFeaturesComponent className='mt-12 mb-28' companyURL={companyURL} setCompanyURL={setCompanyURL} />

      <Dialog open={showSuggestedFeaturesModal} onOpenChange={() => setShowSuggestedFeaturesModal(false)}>
        <DialogContent className='sm:min-w-[90vw] sm:h-[90vh] h-full min-w-full p-0'>
          <SuggestedFeaturesComponentModal
            companyURL={companyURL}
            setCompanyURL={setCompanyURL}
            onClose={() => setShowSuggestedFeaturesModal(false)}
          />
        </DialogContent>
      </Dialog>
    </LandingPageContainer>
  );
}
