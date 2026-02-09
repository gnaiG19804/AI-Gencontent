import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json(
        { error: 'No file received.' },
        { status: 400 }
      );
    }

    const n8nUrl = process.env.NEXT_PUBLIC_N8N_WEBHOOK_URL;

    if (!n8nUrl) {
      return NextResponse.json(
        { error: 'N8n webhook URL not configured.' },
        { status: 500 }
      );
    }

    // Forward the file to n8n
    const n8nFormData = new FormData();
    n8nFormData.append('file', file);
    // Forward other fields if present
    formData.forEach((value, key) => {
      if (key !== 'file') {
        n8nFormData.append(key, value);
      }
    });

    const response = await fetch(n8nUrl, {
      method: 'POST',
      body: n8nFormData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('N8n error:', response.status, errorText);
      return NextResponse.json(
        { error: `N8n responded with ${response.status}: ${errorText}` },
        { status: response.status }
      );
    }

    const data = await response.json().catch(() => ({ success: true }));

    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Upload proxy error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal Server Error' },
      { status: 500 }
    );
  }
}
