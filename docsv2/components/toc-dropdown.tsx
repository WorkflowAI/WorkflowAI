'use client';

import { ChevronDown } from 'lucide-react';
import { useState } from 'react';

export function TOCDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState('Integration #1');

  const options = ['Integration #1', 'Integration #2'];

  return (
    <div className="relative mb-4">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-lg border bg-fd-background px-3 py-2 text-sm font-medium text-fd-foreground shadow-sm transition-colors hover:bg-fd-muted/50 focus:outline-none focus:ring-2 focus:ring-fd-ring focus:ring-offset-2"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span>{selected}</span>
        <ChevronDown
          className={`h-4 w-4 transition-transform ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>

      {isOpen && (
        <div className="absolute z-10 mt-1 w-full rounded-md border bg-fd-popover shadow-lg">
          <ul
            className="py-1"
            role="listbox"
            aria-label="Options"
          >
            {options.map((option) => (
              <li key={option}>
                <button
                  type="button"
                  className="flex w-full items-center px-3 py-2 text-sm text-fd-popover-foreground hover:bg-fd-accent hover:text-fd-accent-foreground focus:bg-fd-accent focus:text-fd-accent-foreground focus:outline-none"
                  onClick={() => {
                    setSelected(option);
                    setIsOpen(false);
                  }}
                  role="option"
                  aria-selected={selected === option}
                >
                  {option}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
} 