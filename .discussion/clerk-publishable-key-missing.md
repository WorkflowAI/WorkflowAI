# 🔐 Clerk Authentication Issue: Missing publishableKey

**Discussion with <@U0618AW12SH>**

## 🐛 Problem Description

When running `cd docsv2 && yarn install`, the Next.js server fails to start with the following error:

```
Error: @clerk/nextjs: Missing publishableKey. You can get your key at https://dashboard.clerk.com/last-active?path=api-keys.

This error happened while generating the page. Any console logs will be displayed in the terminal window.
Source
client/src/middleware.ts (14:24) @ buildMiddleware
```

## 🔍 Root Cause Analysis

After investigating the codebase, here's what I found:

1. **Missing Environment Configuration**: The project expects a `.env` file, but one doesn't exist in the workspace
2. **Middleware Configuration**: The `client/src/middleware.ts` file uses `clerkMiddleware` from `@clerk/nextjs/server`
3. **Environment Variables**: The system expects `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` to be set
4. **Authentication Toggle**: There's a `DISABLE_AUTHENTICATION` flag that should allow bypassing Clerk

## 📁 Relevant Files

- `client/src/middleware.ts` (lines 1-69) - Contains the Clerk middleware configuration
- `.env.sample` - Shows expected environment variables
- `docker-compose.yml` (line 138) - References `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `client.Dockerfile` (lines 43-44) - Environment variable configuration

## 🔧 Proposed Solutions

### Option 1: Create Local Environment File (Recommended)
```bash
# Copy the sample environment file
cp .env.sample .env

# The default configuration should work with NEXT_PUBLIC_DISABLE_AUTHENTICATION=true
```

### Option 2: Set up Clerk Authentication
If you want to use Clerk authentication:

1. Create a Clerk account at [dashboard.clerk.com](https://dashboard.clerk.com)
2. Get your publishable key from the API Keys section
3. Update `.env` file:
   ```env
   NEXT_PUBLIC_DISABLE_AUTHENTICATION=false
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_key_here
   CLERK_SECRET_KEY=sk_test_your_secret_key_here
   ```

### Option 3: Modify docsv2 Configuration
The issue might be that `docsv2/` is a separate Next.js project that doesn't inherit the main project's environment configuration.

Check if `docsv2/` needs its own `.env` file or if it should reference the parent directory's configuration.

## 🤔 Questions for Discussion

1. **Project Structure**: Should `docsv2/` be completely independent or should it share environment configuration with the main `client/` project?

2. **Authentication Requirements**: Does the docs site need authentication, or should it run with `DISABLE_AUTHENTICATION=true`?

3. **Development Workflow**: Should developers need to set up Clerk for local development, or should the docs run without authentication by default?

4. **Environment Management**: Should we:
   - Create a separate `.env` file for `docsv2/`?
   - Modify the startup script to handle missing environment variables gracefully?
   - Update the documentation to explain the setup process?

## 🚀 Immediate Fix

To get the docs server running quickly:

```bash
# Create a minimal .env file
echo "NEXT_PUBLIC_DISABLE_AUTHENTICATION=true" > .env

# Then try running the docs server again
cd docsv2 && yarn install
```

## 📝 Next Steps

1. Discuss the preferred approach with <@U0618AW12SH>
2. Implement the chosen solution
3. Update documentation if needed
4. Test the fix across different environments

---

**Priority**: High - Blocks local development
**Impact**: Developers cannot start the docs server
**Estimated Fix Time**: 15-30 minutes depending on chosen approach