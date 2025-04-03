// eslint-disable-next-line no-restricted-imports
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { NextMiddleware, NextRequest, NextResponse } from 'next/server';
import { looksLikeURL } from './app/landing/sections/SuggestedFeatures/utils';
import { cleanURL } from './app/landing/sections/SuggestedFeatures/utils';
import { DISABLE_AUTHENTICATION } from './lib/constants';

function buildMiddleware(): NextMiddleware {
  if (DISABLE_AUTHENTICATION) {
    return () => {};
  }

  const isProtectedRoute = createRouteMatcher(['/api/clerk(.*)']);
  return clerkMiddleware((auth, req: NextRequest) => {
    // Set the x-request-url header
    const requestHeaders = new Headers(req.headers);
    requestHeaders.set('x-request-url', req.url);

    // Clone the request with the new headers
    // This response object will be returned unless a redirect happens later.
    const response = NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });

    //Check if the path starts with a domain-like string

    const path = req.nextUrl.pathname;
    const parts = path.split('/');
    let domainCandidate = parts[1];

    // For scenarios like www.workflowai.com/http://example.com/path, we want to use example.com as the domain
    if (domainCandidate.startsWith('http') || domainCandidate.startsWith('https')) {
      domainCandidate = parts[2];
    }

    // Only redirect if the first part looks like a URL and needs cleaning
    if (looksLikeURL(domainCandidate)) {
      const companyURL = cleanURL(domainCandidate);
      if (companyURL !== domainCandidate || parts.length > 2) {
        return NextResponse.redirect(new URL(`/${companyURL}`, req.url));
      }
    }

    if (!auth().userId && isProtectedRoute(req)) {
      return auth().redirectToSignIn();
    }

    // Return the response with the added header if no redirect occurred
    return response;
  });
}

export default buildMiddleware();

export const config = {
  // The following matcher runs middleware on all routes
  // except static assets.
  matcher: [
    '/((?!.*\\..*|_next).*)',
    '/',
    '/(api|trpc)(.*)',
    // Add a new matcher specifically for domain-like paths, where the second part is a domain like: www.example.com and rest is a path
    '/:domain/:path*',
    '/(http|https)/:domain/:path*',
  ],
};
