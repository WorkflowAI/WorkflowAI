/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./content/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  safelist: [
    'bg-emerald-500',
    'bg-red-500',
    'bg-gray-300',
    'text-emerald-500',
    'text-red-500',
  ],
  theme: {
    extend: {
      colors: {
        // Tremor colors
        'tremor-brand': {
          'faint': '#eff6ff', // blue-50
          'muted': '#bfdbfe', // blue-200  
          'subtle': '#60a5fa', // blue-400
          'DEFAULT': '#3b82f6', // blue-500
          'emphasis': '#1d4ed8', // blue-700
          'inverted': '#ffffff', // white
        },
        'tremor-background': {
          'muted': '#f9fafb', // gray-50
          'subtle': '#f3f4f6', // gray-100
          'DEFAULT': '#ffffff', // white
          'emphasis': '#374151', // gray-700
        },
        'tremor-border': {
          'DEFAULT': '#e5e7eb', // gray-200
        },
        'tremor-ring': {
          'DEFAULT': '#e5e7eb', // gray-200
        },
        'tremor-content': {
          'subtle': '#9ca3af', // gray-400
          'DEFAULT': '#6b7280', // gray-500
          'emphasis': '#374151', // gray-700
          'strong': '#111827', // gray-900
          'inverted': '#ffffff', // white
        },
        // Dark mode colors
        'dark-tremor-brand': {
          'faint': '#0B1229', // custom
          'muted': '#172554', // blue-900
          'subtle': '#1e40af', // blue-800
          'DEFAULT': '#3b82f6', // blue-500
          'emphasis': '#60a5fa', // blue-400
          'inverted': '#030712', // gray-950
        },
        'dark-tremor-background': {
          'muted': '#131a2b', // custom
          'subtle': '#1f2937', // gray-800
          'DEFAULT': '#111827', // gray-900
          'emphasis': '#d1d5db', // gray-300
        },
        'dark-tremor-border': {
          'DEFAULT': '#374151', // gray-700
        },
        'dark-tremor-ring': {
          'DEFAULT': '#374151', // gray-700
        },
        'dark-tremor-content': {
          'subtle': '#4b5563', // gray-600
          'DEFAULT': '#6b7280', // gray-500
          'emphasis': '#e5e7eb', // gray-200
          'strong': '#f9fafb', // gray-50
          'inverted': '#000000', // black
        },
      },
      borderRadius: {
        'tremor-small': '0.375rem',
        'tremor-default': '0.5rem',
        'tremor-full': '9999px',
      },
      fontSize: {
        'tremor-label': ['0.75rem', { lineHeight: '1rem' }],
        'tremor-default': ['0.875rem', { lineHeight: '1.25rem' }],
        'tremor-title': ['1.125rem', { lineHeight: '1.75rem' }],
        'tremor-metric': ['1.875rem', { lineHeight: '2.25rem' }],
      },
      boxShadow: {
        'tremor-card': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'dark-tremor-card': '0 1px 3px 0 rgb(0 0 0 / 0.3), 0 1px 2px -1px rgb(0 0 0 / 0.3)',
      },
      keyframes: {
        hide: {
          from: { opacity: "1" },
          to: { opacity: "0" },
        },
        slideDownAndFade: {
          from: { opacity: "0", transform: "translateY(-6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideLeftAndFade: {
          from: { opacity: "0", transform: "translateX(6px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        slideUpAndFade: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideRightAndFade: {
          from: { opacity: "0", transform: "translateX(-6px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        accordionOpen: {
          from: { height: "0px" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        accordionClose: {
          from: {
            height: "var(--radix-accordion-content-height)",
          },
          to: { height: "0px" },
        },
        dialogOverlayShow: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        dialogContentShow: {
          from: {
            opacity: "0",
            transform: "translate(-50%, -45%) scale(0.95)",
          },
          to: { opacity: "1", transform: "translate(-50%, -50%) scale(1)" },
        },
      },
      animation: {
        hide: "hide 150ms cubic-bezier(0.16, 1, 0.3, 1)",
        slideDownAndFade:
          "slideDownAndFade 150ms cubic-bezier(0.16, 1, 0.3, 1)",
        slideLeftAndFade:
          "slideLeftAndFade 150ms cubic-bezier(0.16, 1, 0.3, 1)",
        slideUpAndFade: "slideUpAndFade 150ms cubic-bezier(0.16, 1, 0.3, 1)",
        slideRightAndFade:
          "slideRightAndFade 150ms cubic-bezier(0.16, 1, 0.3, 1)",
        // Accordion
        accordionOpen: "accordionOpen 150ms cubic-bezier(0.87, 0, 0.13, 1)",
        accordionClose: "accordionClose 150ms cubic-bezier(0.87, 0, 0.13, 1)",
        // Dialog
        dialogOverlayShow:
          "dialogOverlayShow 150ms cubic-bezier(0.16, 1, 0.3, 1)",
        dialogContentShow:
          "dialogContentShow 150ms cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  darkMode: 'class',
  plugins: [],
} 