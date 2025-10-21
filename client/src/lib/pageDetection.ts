export enum Page {
  Homepage = 'homepage',
  Leaderboard = 'leaderboard',
  Playground = 'playground',
  Versions = 'versions',
  Runs = 'runs',
  Schemas = 'schemas',
  Migration = 'migration',
  Code = 'code',
  Deployments = 'deployments',
  Benchmarks = 'benchmarks',
  Reviews = 'reviews',
  Tasks = 'agents',
  Cost = 'cost',
  Feedback = 'feedback',
  SideBySide = 'side-by-side',
}

export const pageRegexMap: Record<Page, RegExp> = {
  [Page.Homepage]: /^\/$/,
  [Page.Leaderboard]: /^\/leaderboard(?:\/.*)?$/,
  [Page.Playground]: /\/agents\/[^/]+\/[^/]+$/,
  [Page.Schemas]: /\/agents\/[^/]+\/[^/]+\/schemas$/,
  [Page.Versions]: /\/agents\/[^/]+\/[^/]+\/versions$/,
  [Page.Runs]: /\/agents\/[^/]+\/[^/]+\/runs$/,
  [Page.Benchmarks]: /\/agents\/[^/]+\/[^/]+\/benchmarks$/,
  [Page.Reviews]: /\/agents\/[^/]+\/[^/]+\/reviews$/,
  [Page.Migration]: /\/agents\/[^/]+\/[^/]+\/migration$/,
  [Page.Code]: /\/agents\/[^/]+\/[^/]+\/code$/,
  [Page.Deployments]: /\/agents\/[^/]+\/[^/]+\/deployments$/,
  [Page.Tasks]: /\/agents$/,
  [Page.Cost]: /\/agents\/[^/]+\/[^/]+\/cost$/,
  [Page.Feedback]: /\/agents\/[^/]+\/[^/]+\/feedback$/,
  [Page.SideBySide]: /\/agents\/[^/]+\/[^/]+\/side-by-side$/,
};

export function detectPage(pathname: string): Page | undefined {
  return Object.keys(pageRegexMap).find((page) => pageRegexMap[page as Page].test(pathname)) as Page;
}

export function detectPageIsUsingNewDesign(pathname: string): boolean {
  const pagesUsingNewDesign = [
    Page.Migration,
    Page.Code,
    Page.Cost,
    Page.Versions,
    Page.Deployments,
    Page.Playground,
    Page.Reviews,
    Page.Benchmarks,
    Page.Runs,
    Page.Schemas,
    Page.Feedback,
    Page.SideBySide,
  ];
  return pagesUsingNewDesign.some((page) => pageRegexMap[page].test(pathname));
}

export function detectPageIsRequiringTaskSchema(pathname: string): boolean {
  const pagesNotRequiringTaskSchema = [Page.Schemas];
  return !pagesNotRequiringTaskSchema.some((page) => pageRegexMap[page].test(pathname));
}
