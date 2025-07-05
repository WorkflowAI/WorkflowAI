import * as amplitude from '@amplitude/analytics-browser';
import { BookFilled, ChatFilled, People16Filled } from '@fluentui/react-icons';
import { Plus } from 'lucide-react';
import Image from 'next/image';
import { useCallback } from 'react';
import GitHubSrc from '@/components/Images/GitHubIcon.png';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useAuth, useAuthUI } from '@/lib/AuthContext';
import { NEW_PROXY_AGENT_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useRedirectWithParams } from '@/lib/queryString';
import { signUpRoute } from '@/lib/routeFormatter';
import { CreditsSection } from './CreditsSection';
import { UserMenu } from './userMenu';

export function SidebarLinks() {
  return (
    <div className='flex flex-row justify-between sm:px-2.5 px-5 pb-2.5 pt-2.5 border-t border-gray-100 w-full overflow-hidden flex-shrink-0'>
      <SimpleTooltip
        content={`Join our community\non Discord`}
        tooltipDelay={100}
        tooltipClassName='m-1 whitespace-pre-wrap text-center'
      >
        <Button
          variant='newDesignText'
          toRoute='https://discord.gg/auuf8DREZh'
          rel='noopener noreferrer'
          target='_blank'
          icon={
            <Image
              src='https://workflowai.blob.core.windows.net/workflowai-public/DiscordIcon.png'
              alt='Discord'
              className='w-[18px] h-[18px]'
              width={32}
              height={32}
            />
          }
          size='none'
          className='text-gray-700 hover:text-gray-700 hover:opacity-80 flex-shrink-0 w-7 h-7'
        />
      </SimpleTooltip>
      <SimpleTooltip content='Contact us at team@workflowai.support' tooltipDelay={100} tooltipClassName='m-1'>
        <Button
          variant='newDesignText'
          toRoute='mailto:team@workflowai.support'
          rel='noopener noreferrer'
          icon={<ChatFilled className='w-4 h-4' />}
          size='none'
          className='text-gray-700 hover:text-gray-700 hover:opacity-80 flex-shrink-0 w-7 h-7'
        />
      </SimpleTooltip>
      <SimpleTooltip content='Join our Community on GitHub' tooltipDelay={100} tooltipClassName='m-1'>
        <Button
          variant='newDesignText'
          toRoute='https://github.com/WorkflowAI/WorkflowAI/discussions'
          target='_blank'
          icon={<People16Filled className='w-[18px] h-[18px] text-gray-700' />}
          size='none'
          className='text-gray-700 hover:text-gray-700 hover:opacity-80 flex-shrink-0 w-7 h-7'
        />
      </SimpleTooltip>
      <SimpleTooltip content='Documentation' tooltipDelay={100}>
        <Button
          variant='newDesignText'
          toRoute='https://docs.workflowai.com/'
          target='_blank'
          rel='noopener noreferrer'
          icon={<BookFilled className='w-4 h-4' />}
          size='none'
          className='text-gray-700 hover:text-gray-700 hover:opacity-80 flex-shrink-0 w-7 h-7'
        />
      </SimpleTooltip>
      <SimpleTooltip content='Star on GitHub' tooltipDelay={100}>
        <Button
          variant='newDesignText'
          icon={<Image src={GitHubSrc} alt='GitHub' className='w-4 h-4' />}
          toRoute='https://github.com/WorkflowAI/workflowai'
          target='_blank'
          rel='noopener noreferrer'
          size='none'
          className='text-gray-700 hover:text-gray-700 hover:opacity-80 flex-shrink-0 w-7 h-7'
        />
      </SimpleTooltip>
    </div>
  );
}

type SidebarBottomBarProps = {
  isLoggedOut: boolean;
};

export function SidebarBottomBar(props: SidebarBottomBarProps) {
  const { isLoggedOut } = props;

  const { isSignedIn, user, orgState } = useAuth();
  const { openModal: openProxyNewAgentModal } = useQueryParamModal(NEW_PROXY_AGENT_MODAL_OPEN);
  const routeForSignUp = signUpRoute();

  const onNewTask = useCallback(() => {
    amplitude.track('user.clicked.new_task');
    openProxyNewAgentModal();
  }, [openProxyNewAgentModal]);

  const { openUserProfile, openOrganizationProfile, signOut } = useAuthUI();

  const redirectWithParams = useRedirectWithParams();

  const switchOrganizations = useCallback(() => {
    redirectWithParams({
      path: '/organization/select',
    });
  }, [redirectWithParams]);

  return (
    <>
      {isLoggedOut ? (
        <>
          <div className='px-2.5 w-full'>
            <Button
              className='w-full mt-3'
              variant='newDesignIndigo'
              icon={<Plus className='h-4 w-4' strokeWidth={2} />}
              onClick={onNewTask}
            >
              Add Agent
            </Button>
          </div>
          <div className='pb-6 px-2.5'>
            <Button className='w-full mt-3' variant='newDesignIndigo' toRoute={routeForSignUp}>
              Create Account
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className='pb-3 px-2.5'>
            <Button
              className='w-full mt-3'
              variant='newDesignIndigo'
              icon={<Plus className='h-4 w-4' strokeWidth={2} />}
              onClick={onNewTask}
            >
              Add Agent
            </Button>
          </div>

          <div className='px-2.5 pb-2.5'>
            <div className='flex flex-col items-center w-full border rounded-[2px] border-gray-300 shadow-sm'>
              <UserMenu
                user={user}
                orgState={orgState}
                openUserProfile={openUserProfile}
                openOrganizationProfile={openOrganizationProfile}
                switchOrganizations={switchOrganizations}
                signOut={signOut}
              />
              <CreditsSection isSignedIn={!!isSignedIn} />
            </div>
          </div>
        </>
      )}
      <SidebarLinks />
    </>
  );
}
