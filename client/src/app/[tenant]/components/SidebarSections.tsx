import {
  ArrowSyncFilled,
  ArrowSyncRegular,
  ArrowSwapFilled,
  ArrowSwapRegular,
  ClipboardTaskListLtr20Filled,
  ClipboardTaskListLtr20Regular,
  CloudFilled,
  CloudRegular,
  CodeFilled,
  CodeRegular,
  DataUsageFilled,
  DataUsageRegular,
  ListBarTreeFilled,
  ListBarTreeRegular,
  PersonFeedbackFilled,
  PersonFeedbackRegular,
  PlayCircleFilled,
  PlayCircleRegular,
  SettingsFilled,
  SettingsRegular,
  ThumbLikeDislikeFilled,
  ThumbLikeDislikeRegular,
  TimelineRegular,
} from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useCallback, useMemo } from 'react';
import { TaskRunsActivityIndicator } from '@/components/TaskIterationBadge/TaskRunsActivityIndicator';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { TASK_SETTINGS_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { Page, pageRegexMap } from '@/lib/pageDetection';
import {
  playgroundFromHistoryRouteBuilder,
  taskApiRoute,
  taskBenchmarksRoute,
  taskCostRoute,
  taskDeploymentsRoute,
  taskFeedbackRoute,
  taskMigrationRoute,
  taskReviewsRoute,
  taskRunsRoute,
  taskSchemasRoute,
  taskSideBySideRoute,
  taskVersionsRoute,
} from '@/lib/routeFormatter';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';

enum SectionItemStyle {
  Link = 'link',
  Button = 'button',
}

export type SectionItem = {
  title: string;
  routeBuilder?:
    | ((tenant: TenantID, taskId: TaskID) => string)
    | ((tenant: TenantID, taskId: TaskID, taskSchemaId: TaskSchemaID) => string)
    | (() => string);
  globalModal?: string;
  icon?: React.ReactElement;
  iconSelected?: React.ReactElement;
  matchRegex?: RegExp;
  isEnabled: boolean;
  isHidden: boolean;
  style: SectionItemStyle;
};

type Section = {
  title: string;
  items: SectionItem[];
  showActivityIndicator: boolean;
};

const iconClassName =
  'w-5 h-5 text-gray-500 group-hover:text-indigo-700 transition group-[.selected]:text-indigo-700 shrink-0';

export function generateSections(showActivityIndicator: boolean, isInDemoMode: boolean, isProxy: boolean): Section[] {
  return [
    {
      title: 'ITERATE',
      showActivityIndicator: false,
      items: [
        {
          title: 'Schemas',
          icon: <ArrowSwapRegular className={iconClassName} />,
          iconSelected: <ArrowSwapFilled className={iconClassName} />,
          routeBuilder: taskSchemasRoute,
          // Should match /tasks/:taskId/:taskSchemaId/schemas
          matchRegex: pageRegexMap[Page.Schemas],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Playground',
          icon: <PlayCircleRegular className={iconClassName} />,
          iconSelected: <PlayCircleFilled className={iconClassName} />,
          routeBuilder: playgroundFromHistoryRouteBuilder,
          // Should match /tasks/:taskId/:taskSchemaId/ + searchParams from history
          matchRegex: pageRegexMap[Page.Playground],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Versions',
          icon: <TimelineRegular className={iconClassName} />,
          iconSelected: <TimelineRegular className={iconClassName} />,
          routeBuilder: taskVersionsRoute,
          // Should match /tasks/:taskId/:taskSchemaId/versions
          matchRegex: pageRegexMap[Page.Versions],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Runs',
          icon: <ListBarTreeRegular className={iconClassName} />,
          iconSelected: <ListBarTreeFilled className={iconClassName} />,
          routeBuilder: taskRunsRoute,
          // Should match /tasks/:taskId/:taskSchemaId/runs
          matchRegex: pageRegexMap[Page.Runs],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Settings',
          icon: <SettingsRegular className={iconClassName} />,
          iconSelected: <SettingsFilled className={iconClassName} />,
          globalModal: TASK_SETTINGS_MODAL_OPEN,
          isEnabled: !isInDemoMode,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
      ].filter(Boolean) as SectionItem[],
    },
    {
      title: 'COMPARE',
      showActivityIndicator: false,
      items: [
        {
          title: 'Side by Side',
          icon: <DataUsageRegular className={iconClassName} />,
          iconSelected: <DataUsageFilled className={iconClassName} />,
          routeBuilder: taskSideBySideRoute,
          // Should match /tasks/:taskId/:taskSchemaId/sideBySide
          matchRegex: pageRegexMap[Page.SideBySide],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        !isProxy && {
          title: 'Reviews',
          icon: <ThumbLikeDislikeRegular className={iconClassName} />,
          iconSelected: <ThumbLikeDislikeFilled className={iconClassName} />,
          routeBuilder: taskReviewsRoute,
          // Should match /tasks/:taskId/:taskSchemaId/reviews
          matchRegex: pageRegexMap[Page.Reviews],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        !isProxy && {
          title: 'Benchmarks',
          icon: <DataUsageRegular className={iconClassName} />,
          iconSelected: <DataUsageFilled className={iconClassName} />,
          routeBuilder: taskBenchmarksRoute,
          // Should match /tasks/:taskId/:taskSchemaId/benchmarks/automatic or manual
          matchRegex: pageRegexMap[Page.Benchmarks],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
      ].filter(Boolean) as SectionItem[],
    },
    {
      title: 'INTEGRATE',
      showActivityIndicator: false,
      items: [
        {
          title: 'Migration',
          icon: <ArrowSyncRegular className={iconClassName} />,
          iconSelected: <ArrowSyncFilled className={iconClassName} />,
          routeBuilder: taskMigrationRoute,
          // Should match /tasks/:taskId/:taskSchemaId/migration
          matchRegex: pageRegexMap[Page.Migration],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Code',
          icon: <CodeRegular className={iconClassName} />,
          iconSelected: <CodeFilled className={iconClassName} />,
          routeBuilder: taskApiRoute,
          // Should match /tasks/:taskId/:taskSchemaId/code
          matchRegex: pageRegexMap[Page.Code],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Deployments',
          icon: <CloudRegular className={iconClassName} />,
          iconSelected: <CloudFilled className={iconClassName} />,
          routeBuilder: taskDeploymentsRoute,
          // Should match /tasks/:taskId/:taskSchemaId/deployments
          matchRegex: pageRegexMap[Page.Deployments],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
      ].filter(Boolean) as SectionItem[],
    },
    {
      title: 'MONITOR',
      showActivityIndicator: showActivityIndicator,
      items: [
        {
          title: 'User Feedback',
          icon: <PersonFeedbackRegular className={iconClassName} />,
          iconSelected: <PersonFeedbackFilled className={iconClassName} />,
          routeBuilder: taskFeedbackRoute,
          matchRegex: pageRegexMap[Page.Feedback],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Runs',
          icon: <ListBarTreeRegular className={iconClassName} />,
          iconSelected: <ListBarTreeFilled className={iconClassName} />,
          routeBuilder: taskRunsRoute,
          // Should match /tasks/:taskId/:taskSchemaId/runs
          matchRegex: pageRegexMap[Page.Runs],
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
        {
          title: 'Cost',
          routeBuilder: taskCostRoute,
          matchRegex: pageRegexMap[Page.Cost],
          icon: <ClipboardTaskListLtr20Regular className={iconClassName} />,
          iconSelected: <ClipboardTaskListLtr20Filled className={iconClassName} />,
          isEnabled: true,
          isHidden: false,
          style: SectionItemStyle.Link,
        },
      ].filter(Boolean) as SectionItem[],
    },
  ];
}

type SectionCommonProps = {
  pathname: string;
  routeBuilderWrapper: (routeBuilder: SectionItem['routeBuilder']) => string;
};

function SectionButton(props: SectionItem & SectionCommonProps) {
  const {
    title,
    icon,
    iconSelected,
    routeBuilder,
    globalModal,
    matchRegex,
    isEnabled,
    style,
    routeBuilderWrapper,
    pathname,
  } = props;
  const { openModal } = useQueryParamModal(globalModal ?? '');

  const isDisabled = ((!routeBuilder || !matchRegex) && !globalModal) || !isEnabled;

  const link = useMemo(() => {
    if (isDisabled || !!globalModal) {
      return undefined;
    }
    return routeBuilderWrapper(routeBuilder);
  }, [routeBuilder, routeBuilderWrapper, isDisabled, globalModal]);

  const onClick = useCallback(() => {
    if (!!globalModal) {
      openModal();
    }
  }, [globalModal, openModal]);

  const selected = useMemo(() => !!matchRegex?.exec(pathname), [matchRegex, pathname]);

  if (style === 'button') {
    return (
      <div className='flex px-2 py-1'>
        <Button disabled={isDisabled} toRoute={link} onClick={onClick} variant='newDesign' className='w-full text-xs'>
          {title}
          {globalModal}
        </Button>
      </div>
    );
  }

  return (
    <SimpleTooltip content={isDisabled ? 'Log in to unlock all features' : undefined}>
      <div
        className={cx(
          'border-l-[2px] transition-colors duration-200 ease-in-out pl-1.5 sm:ml-0 ml-2 z-10 hover:bg-indigo-50 hover:bg-opacity-50',
          {
            'border-transparent': !selected,
            'border-indigo-700': selected,
            'hover:border-indigo-700': !isDisabled,
            'bg-indigo-50 bg-opacity-50': selected,
            'opacity-30': isDisabled,
          }
        )}
      >
        <Button
          disabled={isDisabled}
          toRoute={link}
          onClick={onClick}
          variant='link'
          className={cx(
            'flex flex-row gap-2 w-full h-8 justify-start items-center !no-underline p-0 mt-0 text-[13px] text-gray-600 font-normal hover:text-indigo-700 transition-colors duration-200 ease-in-out group',
            {
              'text-indigo-700 font-medium selected': selected,
            }
          )}
        >
          <div className={`opacity-${isDisabled ? 50 : 100}`}>
            {!selected && !!icon && icon}
            {!!selected && !!iconSelected && iconSelected}
          </div>
          {title}
        </Button>
      </div>
    </SimpleTooltip>
  );
}

export function SectionBlock(props: Section & SectionCommonProps) {
  const { title, items, routeBuilderWrapper, pathname, showActivityIndicator } = props;

  const filteredItems = useMemo(() => {
    return items.filter((item) => !item.isHidden);
  }, [items]);

  return (
    <div className='flex flex-col'>
      <div className='flex text-xs text-indigo-600 font-semibold py-2 sm:pl-2.5 pl-4 sm:pr-3.5 pr-4 items-center justify-between border-t border-b border-gray-100'>
        {title}
        {showActivityIndicator && <TaskRunsActivityIndicator isActive={true} />}
      </div>
      <div className='flex flex-col'>
        {filteredItems.map((item) => (
          <SectionButton key={item.title} routeBuilderWrapper={routeBuilderWrapper} pathname={pathname} {...item} />
        ))}
      </div>
    </div>
  );
}
