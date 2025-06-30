# WorkflowAI Documentation

This is the documentation site for WorkflowAI, built with [Fumadocs](https://github.com/fuma-nama/fumadocs) and Next.js.

## Development Setup

### Prerequisites

Before setting up this project, make sure you have the following installed:

- **Node.js** (version 18.0 or later) - [Download here](https://nodejs.org/)
- **Yarn** package manager (this project uses yarn workspaces)

### Local Development

⚠️ **Important**: This documentation site is part of a yarn workspace. You must run the development server from the **root directory** of the WorkflowAI project, not from the `docsv2` directory.

1. **Navigate to the project root**

   ```bash
   cd /path/to/WorkflowAI  # Go to the root directory, not docsv2
   ```

2. **Install dependencies** (if not already done)

   ```bash
   yarn install
   ```

3. **Start the documentation development server**

   ```bash
   yarn workspace docs dev
   ```

4. **Open your browser**

   Navigate to [http://localhost:3000](http://localhost:3000) to see the documentation site.

### Common Issues

**Problem**: Getting `@clerk/nextjs: Missing publishableKey` error
**Solution**: Make sure you're using `yarn workspace docs dev` from the root directory, not `npm run dev` from the docsv2 directory. The workspace command properly isolates the documentation project from the main client application.

**Problem**: `Couldn't find any pages or app directory` error
**Solution**: Ensure you're running the command from the WorkflowAI root directory, not from inside the docsv2 folder.

## Development

The development server will automatically reload when you make changes to your code. You can start editing the pages and see your changes in real-time.

### Adding New Documentation

1. Create `.mdx` files in `content/docs/`
2. Update the `meta.json` files to include your new pages in the navigation
3. Use the existing pages as templates for formatting and structure

## Project Structure

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

## Building for Production

```bash
# From the root directory
yarn workspace docs build
yarn workspace docs start
```

## Learn More

To learn more about Next.js and Fumadocs, take a look at the following
resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js
  features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.
- [Fumadocs](https://fumadocs.vercel.app) - learn about Fumadocs
