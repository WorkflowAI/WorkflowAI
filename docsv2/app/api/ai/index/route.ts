import { NextResponse } from 'next/server';
import { source } from '@/lib/source';

export const revalidate = false;

export async function GET() {
  try {
    const pages = source.getPages();

    const pageList = pages.map((page) => ({
      title: page.data.title,
      url: page.url,
      description: page.data.description || '',
      ai_url: `${page.url}?reader=ai`,
    }));

    const response = {
      total_pages: pageList.length,
      pages: pageList,
      usage: {
        description: "Use /api/ai/index to get this page list, and add ?reader=ai to any page URL to get AI-readable content",
        examples: [
          "/api/ai/index - Get list of all pages",
          "/why-workflowai?reader=ai - Get AI-readable content for 'Why WorkflowAI' page",
          "/quickstarts/openai-python?reader=ai - Get AI-readable content for OpenAI Python quickstart",
        ]
      }
    };

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
      },
    });
  } catch (error) {
    console.error('Error generating page index:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
