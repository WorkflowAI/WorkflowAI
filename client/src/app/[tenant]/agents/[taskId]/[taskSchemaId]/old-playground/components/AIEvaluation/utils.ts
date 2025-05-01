export function getAccentColor(state: string | undefined): string {
  switch (state) {
    case 'positive':
      return '#15803D';
    case 'negative':
      return '#B91C1C';
    default:
      return '#6B7280';
  }
}

export function getBorderColor(state: string | undefined): string {
  switch (state) {
    case 'positive':
      return '#22C55E';
    case 'negative':
      return '#EF4444';
    default:
      return '#6B7280';
  }
}

export function getBackgroundColor(state: string | undefined): string {
  switch (state) {
    case 'positive':
      return '#F0FDF4';
    case 'negative':
      return '#FEF2F2';
    default:
      return '#F9FAFB';
  }
}

export function getTriangleClasses(state: string | undefined): string {
  switch (state) {
    case 'unsure':
      return '';
    default:
      return `before:content-[""] before:absolute before:right-[var(--triangle-offset)] before:top-[-8px] before:w-0 before:h-0
           before:border-l-[8px] before:border-l-transparent
           before:border-r-[8px] before:border-r-transparent
           before:border-b-[8px] before:border-b-[var(--border-color)]
           after:content-[""] after:absolute after:right-[var(--triangle-offset)] after:top-[-7px] after:w-0 after:h-0
           after:border-l-[8px] after:border-l-transparent
           after:border-r-[8px] after:border-r-transparent
           after:border-b-[8px] after:border-b-[var(--background-color)]`;
  }
}
