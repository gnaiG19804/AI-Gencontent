import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get('content-type') || '';
    const n8nUrl = process.env.NEXT_PUBLIC_N8N_WEBHOOK_URL;

    if (!n8nUrl) {
      return NextResponse.json({ error: 'N8n webhook URL not configured.' }, { status: 500 });
    }

    let payload: any;
    let headers: Record<string, string> = {};

    if (contentType.includes('multipart/form-data')) {
      // Handle File Upload (FormData)
      const formData = await request.formData();
      // Forward the formData directly
      payload = formData;
      // Fetch will set the correct Content-Type with boundary for FormData automatically
    } else {
      // Handle JSON
      payload = JSON.stringify(await request.json());
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(n8nUrl, {
      method: 'POST',
      headers: headers, // Empty for FormData, 'application/json' for JSON
      body: payload,
    });

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: `N8n responded with ${response.status}: ${errorText}` },
        { status: response.status }
      );
    }

    const data = await response.json().catch(() => ({ success: true }));
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('N8n Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal Server Error' },
      { status: 500 }
    );
  }
}
