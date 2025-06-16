'use client';

import { RiCheckboxCircleFill } from '@remixicon/react';
import { Card } from './tremor/card';
import { Tracker } from './tremor/tracker';

// Simple seeded random number generator for consistent server/client rendering
const seededRandom = (seed: number) => {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
};

// Generate consistent sample data for the last 90 days
const generateStatusData = () => {
  const data = [];
  const today = new Date();
  
  for (let i = 89; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    
    // Use day of year as seed for consistent random values
    const dayOfYear = Math.floor((date.getTime() - new Date(date.getFullYear(), 0, 0).getTime()) / 86400000);
    const isDowntime = seededRandom(dayOfYear) < 0.02; // 2% chance of downtime
    
    data.push({
      tooltip: date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      }),
      status: isDowntime ? 'Downtime' : 'Operational',
    });
  }
  
  return data;
};

const data = generateStatusData();

const colorMapping = {
  Operational: 'emerald-500',
  Downtime: 'red-500',
  Inactive: 'gray-300',
} as const;

const combinedData = data.map((item) => {
  return {
    ...item,
    color: colorMapping[item.status as keyof typeof colorMapping],
  };
});

// Calculate uptime percentage
const operationalDays = data.filter(d => d.status === 'Operational').length;
const uptimePercentage = ((operationalDays / data.length) * 100).toFixed(1);

export default function StatusMonitor() {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
          WorkflowAI API
        </h3>
        <span
          tabIndex={0}
          className="inline-flex items-center gap-2 rounded-tremor-full px-3 py-1 text-tremor-default text-tremor-content-emphasis ring-1 ring-inset ring-tremor-ring dark:text-dark-tremor-content-emphasis dark:ring-dark-tremor-ring"
        >
          <span
            className="-ml-0.5 size-2 rounded-tremor-full bg-emerald-500"
            aria-hidden={true}
          />
          Operational
        </span>
      </div>
      <div className="mt-8 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <RiCheckboxCircleFill
            className="size-5 shrink-0 text-emerald-500"
            aria-hidden={true}
          />
          <p className="text-tremor-default font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
            run.workflowai.com
          </p>
        </div>
        <p className="text-tremor-default font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
          {uptimePercentage}% uptime
        </p>
      </div>
      <Tracker data={combinedData} className="mt-4 hidden w-full lg:flex" />
      <Tracker
        data={combinedData.slice(30, 90)}
        className="mt-3 hidden w-full sm:flex lg:hidden"
      />
      <Tracker
        data={combinedData.slice(60, 90)}
        className="mt-3 flex w-full sm:hidden"
      />
      <div className="mt-3 flex items-center justify-between text-tremor-default text-tremor-content dark:text-dark-tremor-content">
        <span className="hidden lg:block">90 days ago</span>
        <span className="hidden sm:block lg:hidden">60 days ago</span>
        <span className="sm:hidden">30 days ago</span>
        <span>Today</span>
      </div>
    </Card>
  );
} 