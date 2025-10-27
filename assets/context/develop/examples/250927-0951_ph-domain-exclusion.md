---
schema_version: "v3_adaptive"
type: "bug-fix.domain-exclusion"
status: "completed"
keywords: "domain-detection multi-store shopify-theme bundle-script exclusion hostname-check"
timestamp: "2025-09-27T09:51:00-0700"
---

# Shopify Multi-Domain Chatbot Exclusion

## Request
> "Right now we have a shopify website npta.ca and npta.ph for some reason, when we added it to the shopify codebase. its on both the ca and ph site. we dont want it on the ph site."

## Overview
Added domain detection to bundle script to prevent chatbot initialization on secondary domain while keeping it active on primary domain. Both domains share the same theme code, so implemented client-side hostname checking at script entry point.

## Decisions

### Domain Check in Bundle Script
- **Context**: Both domains share the same theme with bundle script included
- **Solution**: Added hostname check at bundle script initialization
- **Alternatives**: Theme conditional logic (rejected - requires theme access), separate themes per domain (rejected - maintenance burden)

## Implementation

### Code Signatures

**Domain Check** (`app/bundle/route.ts`)
```javascript
// Only initialize on primary domain
if (!window.location.hostname.includes('npta.ca')) {
  console.log('Skipping initialization on', window.location.hostname);
  return;
}
```

## Audit

### Modified
- `app/bundle/route.ts` - Added domain detection guard at initialization

### Build
- Production build verified successful
- Ready for deployment
