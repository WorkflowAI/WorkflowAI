'use client';

import * as amplitude from '@amplitude/analytics-browser';
import { useCallback } from 'react';
import { NEW_TASK_MODAL_OPEN } from '@/lib/globalModal';
import { useQueryParamModal } from '@/lib/globalModal';
import { useIsMobile } from '@/lib/hooks/useIsMobile';
import { signUpRoute } from '@/lib/routeFormatter';
import { useOrFetchUptime } from '@/store/fetchers';
import { LandingPageContainer } from './container/LandingPageContainer';
import { CompaniesMoneyComponent } from './sections/Components/CompaniesMoneyComponent';
import { ComparisionComponent } from './sections/Components/ComparisionComponent';
import { GraphComponent } from './sections/Components/GraphComponent';
import { GridComponent } from './sections/Components/GridComponent';
import { HeaderComponent } from './sections/Components/HeaderComponent';
import { ImageComponent } from './sections/Components/ImageComponent';
import { InvestorLogosComponent } from './sections/Components/InvestorLogosComponent';
import { PriceComponent } from './sections/Components/PriceComponent';
import { QuoteComponent } from './sections/Components/QuoteComponent';
import { RowsComponent } from './sections/Components/RowsComponent';
import { SubheaderComponent } from './sections/Components/SubheaderComponent';
import { VideosComponent } from './sections/Components/Video/VideosComponent';
import * as LandingStaticData from './sections/StaticData/LandingStaticData';

export function LandingPage() {
  const { openModal: openNewTaskModal } = useQueryParamModal(NEW_TASK_MODAL_OPEN);

  const routeForSignUp = signUpRoute();

  const { workflowUptime, openaiUptime } = useOrFetchUptime();

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

  const isMobile = useIsMobile();

  const onNewTask = useCallback(() => {
    if (isMobile) {
      window.open(
        'https://workflowai.com/docs/agents/flight-info-extractor/3?versionId=89ed288ccfc7a3ef813119713d50683d&showDiffMode=true&show2ColumnLayout=false&taskRunId2=019620b6-0076-73b5-cb3a-d12cbbce7957&taskRunId3=019620b6-0072-7046-298f-c912681cedf6&taskRunId1=019620b6-3115-7045-ce28-5b33263c527b',
        '_blank'
      );
      return;
    }

    amplitude.track('user.clicked.new_task');
    openNewTaskModal({
      mode: 'new',
      redirectToPlaygrounds: 'true',
    });
  }, [openNewTaskModal, isMobile]);

  return (
    <LandingPageContainer scrollToPricing={scrollToPricing}>
      <HeaderComponent className='mt-10' showSuggestedFeaturesModal={onNewTask} routeForSignUp={routeForSignUp} />
      <VideosComponent className='sm:mt-10 mt-7' />
      <CompaniesMoneyComponent className='sm:mt-20 mt-14' />

      <SubheaderComponent entry={LandingStaticData.eighteenthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <ImageComponent entry={LandingStaticData.eighteenthNewImageEntry} className='mt-10' isMobile={isMobile} />

      <SubheaderComponent entry={LandingStaticData.seventeenthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <ImageComponent entry={LandingStaticData.seventeenthNewImageEntry} className='mt-10' isMobile={isMobile} />

      <SubheaderComponent entry={LandingStaticData.sixteenthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <ImageComponent entry={LandingStaticData.sixteenthNewImageEntry} className='mt-10' isMobile={isMobile} />

      <SubheaderComponent entry={LandingStaticData.fifteenthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <ImageComponent entry={LandingStaticData.fifteenthNewImageEntry} className='mt-10' isMobile={isMobile} />

      <SubheaderComponent entry={LandingStaticData.fourteenthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <ImageComponent entry={LandingStaticData.fourteenthNewImageEntry} className='mt-10' isMobile={isMobile} />

      <SubheaderComponent entry={LandingStaticData.thirteenthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <ImageComponent entry={LandingStaticData.thirteenthNewImageEntry} className='mt-10' isMobile={isMobile} />

      <SubheaderComponent entry={LandingStaticData.twelfthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <GridComponent
        entries={LandingStaticData.twelfthNewFeaturesEntries}
        className='mt-10'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />

      <SubheaderComponent entry={LandingStaticData.eleventhNewHeaderEntry} className='sm:mt-20 mt-14' />
      <GridComponent
        entries={LandingStaticData.eleventhNewFeaturesEntries}
        className='mt-10'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />

      <RowsComponent entries={LandingStaticData.tenthNewFeaturesEntries} className='sm:mt-20 mt-14' />
      <QuoteComponent entry={LandingStaticData.tenthNewQuoteEntry} className='mt-10' />

      <GridComponent
        entries={LandingStaticData.ninthNewFeaturesEntries}
        className='sm:mt-20 mt-14'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />

      <SubheaderComponent entry={LandingStaticData.eighthNewHeaderEntry} className='sm:mt-20 mt-14' />
      <ImageComponent entry={LandingStaticData.eighthNewImageEntry} className='mt-10' isMobile={isMobile} />

      <SubheaderComponent entry={LandingStaticData.seventhNewHeaderEntry} className='sm:mt-20 mt-14' id='pricing' />
      <PriceComponent className='mt-10' />
      <QuoteComponent entry={LandingStaticData.seventhNewQuoteEntry} className='mt-10' />

      <SubheaderComponent entry={LandingStaticData.sixthNewHeaderEntry} className='sm:mt-20 mt-12' />

      <SubheaderComponent entry={LandingStaticData.fifthNewHeaderEntry} className='sm:mt-20 mt-12' />
      <GridComponent entries={LandingStaticData.fifthNewFeaturesEntries} className='mt-12' showThreeColumns />

      <SubheaderComponent entry={LandingStaticData.fourthNewHeaderEntry} className='sm:mt-40 mt-28' />
      <GridComponent entries={LandingStaticData.fourthNewFeaturesEntries} className='mt-10' showThreeColumns />

      <SubheaderComponent entry={LandingStaticData.thirdNewHeaderEntry} className='sm:mt-20 mt-12' />

      <SubheaderComponent entry={LandingStaticData.comparisionHeaderEntry} className='sm:mt-20 mt-12' />
      <ComparisionComponent className='mt-10' workflowUptime={workflowUptime} openaiUptime={openaiUptime} />
      <GraphComponent className='mt-16 sm:mt-10' workflowUptime={workflowUptime} />

      <SubheaderComponent entry={LandingStaticData.secondNewHeaderEntry} className='sm:mt-20 mt-14' />
      <GridComponent
        entries={LandingStaticData.secondNewFeaturesEntries}
        className='mt-10'
        scrollToSuggestedFeatures={scrollToSuggestedFeatures}
      />

      <InvestorLogosComponent className='sm:mt-20 mt-14' />

      <SubheaderComponent
        entry={LandingStaticData.firstNewFeaturesEntries}
        className='sm:mt-20 mt-14 sm:mb-20 mb-14'
        routeForSignUp={routeForSignUp}
      />
    </LandingPageContainer>
  );
}
