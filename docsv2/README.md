# my-app

This is a Next.js application generated with
[Create Fumadocs](https://github.com/fuma-nama/fumadocs).

## Setup from Scratch

### Prerequisites

Before setting up this project, make sure you have the following installed:

- **Node.js** (version 18.0 or later) - [Download here](https://nodejs.org/)
- **npm**, **pnpm**, or **yarn** package manager

### Installation

1. **Clone or download the project**
   ```bash
   # If using git
   git clone <repository-url>
   cd my-app
   
   # Or download and extract the project files
   ```

2. **Install dependencies**
   ```bash
   # Using npm
   npm install
   
   # Using pnpm (recommended)
   pnpm install
   
   # Using yarn
   yarn install
   ```

3. **Start the development server**
   ```bash
   npm run dev
   # or
   pnpm dev
   # or
   yarn dev
   ```

4. **Open your browser**
   
   Navigate to [http://localhost:3000](http://localhost:3000) to see the application running.

## Development

The development server will automatically reload when you make changes to your code. You can start editing the pages and see your changes in real-time.

## Explore

In the project, you can see:

- `lib/source.ts`: Code for content source adapter, [`loader()`](https://fumadocs.dev/docs/headless/source-api) provides the interface to access your content.
- `app/layout.config.tsx`: Shared options for layouts, optional but preferred to keep.

| Route                     | Description                                            |
| ------------------------- | ------------------------------------------------------ |
| `app/(home)`              | The route group for your landing page and other pages. |
| `app/docs`                | The documentation layout and pages.                    |
| `app/api/search/route.ts` | The Route Handler for search.                          |

### Fumadocs MDX

A `source.config.ts` config file has been included, you can customise different options like frontmatter schema.

Read the [Introduction](https://fumadocs.dev/docs/mdx) for further details.

## Learn More

To learn more about Next.js and Fumadocs, take a look at the following
resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js
  features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.
- [Fumadocs](https://fumadocs.vercel.app) - learn about Fumadocs
