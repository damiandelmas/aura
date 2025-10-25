---
schema_version: "v3_adaptive"
type: "implementation.security"
status: "completed"
keywords: "rate-limiting upstash-redis vercel-kv content-moderation openai-api jailbreak-detection input-validation security-guardrails"
timestamp: "2025-08-19T13:04:00-0800"
---

# NPTA Chatbot Security Guardrails Implementation

## Request
> "'/home/axp/projects/jesse-benson/projects/npta_shopify-widget/development/250818-1317_gaurdrails/FINAL-IMPLEMENTATION-PLAN.md' read this. '/home/axp/projects/jesse-benson/projects/npta_shopify-widget/5_npta-styling/app/api/chat/route.ts' read that. // how confident are you? what DO I NEED TO DO to enable u to implemnt?"

## Overview
Implemented comprehensive security guardrails for the NPTA chatbot using proven rate limiting patterns from framework documentation. Added four validation layers that run before messages reach the AI model: request throttling to prevent abuse, input sanitization with character limits, prompt injection detection using pattern matching, and content filtering for harmful material. All security violations return error responses without processing the request further.

## Decisions

### Use Vercel's Official AI SDK Rate Limiting
- **Context**: User wanted proven, battle-tested security patterns instead of custom implementations
- **Solution**: Copied exact implementation from framework documentation using persistent storage
- **Alternatives**: Custom rate limiting (rejected - reinventing wheel), in-memory solutions (rejected - no persistence across deployments)
- **Rationale**: Production security requires proven patterns, not experimental code
- **Implications**: Tied to framework ecosystem, but gains reliability and community support

### Upstash Redis via Vercel Marketplace
- **Context**: Platform moved key-value storage to marketplace integration
- **Solution**: Used auto-provisioned database integration
- **Alternatives**: Manual setup (rejected - more complex)

### Hard Block Security Approach
- **Context**: User preferred binary security responses
- **Solution**: All violations return HTTP errors with no chatbot response

## Implementation

### Architecture
Security pipeline in POST handler before AI call:
1. Rate limiting (Upstash Redis) → 429
2. Input validation (Zod) → 400
3. Jailbreak detection (regex) → 400
4. Content moderation (OpenAI) → 400
5. Continue to Requesty

### Code Signatures

**Dependencies**
```bash
npm install @vercel/kv @upstash/ratelimit zod
```

**Rate Limiting** (`app/api/chat/route.ts`)
```typescript
import { kv } from '@vercel/kv';
import { Ratelimit } from '@upstash/ratelimit';

const ratelimit = new Ratelimit({
  redis: kv,
  limiter: Ratelimit.fixedWindow(20, '60s')
});
```

**Input Validation** (`app/api/chat/route.ts`)
```typescript
const messageSchema = z.object({
  message: z.string().min(1).max(2000),
  userId: z.string().optional()
});
```

**Jailbreak Detection** (`app/api/chat/route.ts`)
```typescript
const jailbreakPatterns = [
  /ignore.*(previous|above|instruction)/i,
  /pretend.*not.*(ai|assistant)/i,
  /developer mode|god mode/i
];
```

**Content Moderation** (`app/api/chat/route.ts`)
```typescript
async function moderateContent(text: string): Promise<boolean> {
  const response = await fetch('https://api.openai.com/v1/moderations', {
    headers: { 'Authorization': `Bearer ${process.env.OPENAI_API_KEY}` },
    body: JSON.stringify({ input: text })
  });
  return (await response.json()).results[0].flagged;
}
```

**Security Pipeline Flow** (`app/api/chat/route.ts`)
```typescript
export async function POST(req: Request) {
  const { success } = await ratelimit.limit(ip);
  if (!success) return new Response('Rate limit exceeded', { status: 429 });

  const validation = messageSchema.safeParse({ message: messageText });
  if (!validation.success) return new Response('Invalid input', { status: 400 });

  if (jailbreakPatterns.some(p => p.test(messageText))) {
    return new Response('Invalid request detected', { status: 400 });
  }

  const flagged = await moderateContent(messageText);
  if (flagged) return new Response('Content policy violation', { status: 400 });

  // Continue with Requesty logic...
}
```

## Audit

### Modified
- `app/api/chat/route.ts` - Added security guardrails (rate limiting, input validation, jailbreak detection, content moderation)
- `.env.local` - Added Upstash Redis and OpenAI API credentials (see .env.example)
- `package.json` - Added @vercel/kv, @upstash/ratelimit, zod dependencies

### Configuration
Environment variables required:
- `KV_REST_API_URL` - Upstash Redis endpoint
- `KV_REST_API_TOKEN` - Upstash Redis token
- `OPENAI_API_KEY` - For content moderation

### Testing Verified
- Rate limiting: 429 responses after 20 requests/minute
- Jailbreak detection: Blocks "Ignore all previous instructions"
- Input validation: 400 for empty messages
- Content moderation: Ready for harmful content detection
