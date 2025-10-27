---
schema_version: "v3_adaptive"
type: "deployment.vercel"
status: "completed"
keywords: "vercel-deployment react-hooks-fix git-push production-build environment-variables mobile-routes build-error"
timestamp: "2025-08-11T19:33:00-0800"
---

# Vercel Production Deployment Process

## Request
> "lets deploy to vercel"

## Overview
Successfully deployed NPTA chatbot to production from the feature branch. Encountered a build error where an animation function was being invoked conditionally, violating framework rules about execution order. Fixed by ensuring the function runs unconditionally while using its result conditionally. The deployment includes three routes: the main widget with a floating interface, a fullscreen mobile view, and a desktop demo view with a phone frame for presentations.

## Decisions

### Fix Framework Execution Order Violation
- **Context**: Build failed due to function being called conditionally, violating framework rules about execution order
- **Solution**: Move function call outside conditional logic, use result conditionally instead
- **Alternatives**: Refactor to separate components (rejected - unnecessary complexity), ignore and deploy anyway (rejected - would fail production build)
- **Rationale**: Framework static analysis enforces execution order rules at build time, no way to bypass
- **Implications**: Pattern applies to any framework with execution order requirements (not just this one)

### Deploy from Feature Branch
- **Context**: Working on feature branch, wanted to verify before merging
- **Solution**: Deploy directly from branch to platform

## Constraints

### Framework Functions Must Run Unconditionally
- **What**: Framework-managed functions cannot be called inside ternary operators or conditionals
- **Discovery**: Build-time static analysis caught the violation during platform deployment
- **Workaround**: Call function unconditionally, use result conditionally
- **Impact**: Build passed after restructuring invocation pattern

## Failures

### Initial Deployment Attempt
- **Attempted**: Deploy directly without local build verification
- **Why Failed**: Build-time static analysis rejected conditional function invocation
- **Lesson**: Always run production build locally before deploying to catch framework violations early

## Implementation

### Architecture
Deployment flow:
1. Git push → GitHub
2. Vercel build → Hooks error detected
3. Fix hooks violation → Git push
4. Vercel --prod → Success

### Code Signatures

**React Hooks Fix** (`components/bubble.tsx`)
```typescript
// Before: conditional hook call ❌
<Markdown>{skipAnimation ? content : useAnimatedText(content)}</Markdown>

// After: unconditional call, conditional use ✅
const animatedContent = useAnimatedText(content);
<Markdown>{skipAnimation ? content : animatedContent}</Markdown>
```

**Deployment Commands**
```bash
git add app/mobile-view/ components/bubble.tsx
git commit -m "Add iPhone frame mobile-view for desktop demos"
git push origin 5_npta-styling

# Initial deploy fails with hooks error
vercel --yes

# Fix and redeploy
git add components/bubble.tsx
git commit -m "Fix React hooks rule violation"
git push origin 5_npta-styling
vercel --prod --yes
```

**Build Verification**
```
✓ Compiled successfully
✓ Linting and checking validity of types
✓ Collecting page data
✓ Generating static pages (7/7)
✓ Finalizing page optimization
```

## Audit

### Modified
- `components/bubble.tsx` - Fixed React hooks violation (moved useAnimatedText call outside ternary)
- `app/mobile-view/page.tsx` - Created iPhone frame view for desktop demos
- `.vercel/` - Auto-generated Vercel configuration

### Git Operations
- 5 commits pushed to `5_npta-styling` branch
- Branch deployed directly to Vercel
- Production URL generated

### Configuration
Environment variables required:
- `OPENAI_API_KEY` - For chat functionality
- `NEXT_PUBLIC_CHAT_API_URL` - Optional custom API endpoint

### Routes Deployed
- `/` - Main widget (floating bubble, desktop/mobile responsive)
- `/mobile` - Fullscreen mobile view
- `/mobile-view` - iPhone 14 Pro frame (375x812px) for desktop demos

### Production URL
`https://5npta-styling-98eowtbd4-damiandelmas-gmailcoms-projects.vercel.app`
