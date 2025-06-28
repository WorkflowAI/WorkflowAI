import { type NextRequest, NextResponse } from 'next/server';
import { getLLMText } from '@/lib/get-llm-text';
import { source } from '@/lib/source';

export const revalidate = false;

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ slug?: string[] }> }
) {
  try {
    const { slug } = await params;

    // Find the page using the slug
    const page = source.getPage(slug);
    if (!page) {
      return new NextResponse('Page not found', { status: 404 });
    }

    // Get AI-friendly content
    const aiContent = await getLLMText(page);

    return new NextResponse(aiContent, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
      },
    });
  } catch (error) {
    console.error('Error generating AI content:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
