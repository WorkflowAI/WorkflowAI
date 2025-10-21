'use client';

import * as amplitude from '@amplitude/analytics-browser';
import { useCallback } from 'react';
import { NEW_TASK_MODAL_OPEN } from '@/lib/globalModal';
import { useQueryParamModal } from '@/lib/globalModal';
import { useIsMobile } from '@/lib/hooks/useIsMobile';
import { signUpRoute } from '@/lib/routeFormatter';
import { useOrFetchUptime } from '@/store/fetchers';
import { ModelBanner } from '../[tenant]/components/ModelBanner';
import { useModelToAdvertise } from '../[tenant]/components/useModelToAdvertise';
import { LandingMigrationBanner } from './components/LandingMigrationBanner';
import { LandingPageContainer } from './container/LandingPageContainer';
import { CompaniesMoneyComponent } from './sections/Components/CompaniesMoneyComponent';
import { ComparePriceComponent } from './sections/Components/ComparePriceComponent';
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

  const { modelsToAdvertise, dismiss } = useModelToAdvertise();

  return (
    <div className='flex flex-col w-full h-full'>
      <LandingMigrationBanner />
      {!!modelsToAdvertise && (
        <ModelBanner models={modelsToAdvertise} onClose={dismiss} routeForSignUp={routeForSignUp} />
      )}
      <LandingPageContainer scrollToPricing={scrollToPricing}>
        <HeaderComponent className='mt-10' showSuggestedFeaturesModal={onNewTask} routeForSignUp={routeForSignUp} />
        <VideosComponent className='sm:mt-10 mt-7' />
        <CompaniesMoneyComponent className='sm:mt-20 mt-14' />

        <SubheaderComponent entry={LandingStaticData.headerEntry18} className='sm:mt-20 mt-14' />
        <ImageComponent entry={LandingStaticData.imageEntry18} className='mt-10' isMobile={isMobile} />

        <SubheaderComponent entry={LandingStaticData.headerEntry17} className='sm:mt-20 mt-14' />
        <ImageComponent entry={LandingStaticData.imageEntry17} className='mt-10' isMobile={isMobile} />

        <SubheaderComponent entry={LandingStaticData.headerEntry16} className='sm:mt-20 mt-14' />
        <ImageComponent entry={LandingStaticData.imageEntry16} className='mt-10' isMobile={isMobile} />

        <SubheaderComponent entry={LandingStaticData.headerEntry15} className='sm:mt-20 mt-14' />
        <ImageComponent entry={LandingStaticData.imageEntry15} className='mt-10' isMobile={isMobile} />

        <SubheaderComponent entry={LandingStaticData.headerEntry14} className='sm:mt-20 mt-14' />
        <ImageComponent entry={LandingStaticData.imageEntry14} className='mt-10' isMobile={isMobile} />

        <SubheaderComponent entry={LandingStaticData.headerEntry13} className='sm:mt-20 mt-14' />
        <ImageComponent entry={LandingStaticData.imageEntry13} className='mt-10' isMobile={isMobile} />

        <SubheaderComponent entry={LandingStaticData.headerEntry12} className='sm:mt-20 mt-14' />
        <GridComponent
          entries={LandingStaticData.featuresEntries12}
          className='mt-10'
          scrollToSuggestedFeatures={scrollToSuggestedFeatures}
        />

        <SubheaderComponent entry={LandingStaticData.headerEntry11} className='sm:mt-20 mt-14' />
        <GridComponent
          entries={LandingStaticData.featuresEntries11}
          className='mt-10'
          scrollToSuggestedFeatures={scrollToSuggestedFeatures}
        />

        <RowsComponent entries={LandingStaticData.featuresEntries10} className='sm:mt-20 mt-14' />
        <QuoteComponent entry={LandingStaticData.quoteEntry10} className='mt-10' />

        <GridComponent
          entries={LandingStaticData.featuresEntries9}
          className='sm:mt-20 mt-14'
          scrollToSuggestedFeatures={scrollToSuggestedFeatures}
        />

        <SubheaderComponent entry={LandingStaticData.headerEntry8} className='sm:mt-20 mt-14' />
        <ImageComponent entry={LandingStaticData.imageEntry8} className='mt-10' isMobile={isMobile} />

        <SubheaderComponent entry={LandingStaticData.headerEntry7} className='sm:mt-20 mt-14' id='pricing' />
        <PriceComponent className='mt-10' />
        <QuoteComponent entry={LandingStaticData.quoteEntry7} className='mt-10' />

        <SubheaderComponent entry={LandingStaticData.headerEntry19} className='sm:mt-20 mt-14' />
        <ComparePriceComponent className='mt-10' />

        <SubheaderComponent entry={LandingStaticData.headerEntry6} className='sm:mt-20 mt-12' />

        <SubheaderComponent entry={LandingStaticData.headerEntry5} className='sm:mt-20 mt-12' />
        <GridComponent entries={LandingStaticData.featuresEntries5} className='mt-12' showThreeColumns />

        <SubheaderComponent entry={LandingStaticData.headerEntry4} className='sm:mt-40 mt-28' />
        <GridComponent entries={LandingStaticData.featuresEntries4} className='mt-10' showThreeColumns />

        <SubheaderComponent entry={LandingStaticData.headerEntry3} className='sm:mt-20 mt-12' />

        <SubheaderComponent entry={LandingStaticData.comparisionHeaderEntry} className='sm:mt-20 mt-12' />
        <ComparisionComponent className='mt-10' workflowUptime={workflowUptime} openaiUptime={openaiUptime} />
        <GraphComponent className='mt-16 sm:mt-10' workflowUptime={workflowUptime} />

        <SubheaderComponent entry={LandingStaticData.headerEntry2} className='sm:mt-20 mt-14' />
        <GridComponent
          entries={LandingStaticData.featuresEntries2}
          className='mt-10'
          scrollToSuggestedFeatures={scrollToSuggestedFeatures}
        />

        <InvestorLogosComponent className='sm:mt-20 mt-14' />

        <SubheaderComponent
          entry={LandingStaticData.featuresEntries1}
          className='sm:mt-20 mt-14 sm:mb-20 mb-14'
          routeForSignUp={routeForSignUp}
        />
      </LandingPageContainer>
    </div>
  );
}
