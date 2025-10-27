---
schema_version: "v3_adaptive"
type: "implementation.url-redirect"
status: "completed"
keywords: "vercel-alias mobile-redirect subdomain url-branding cross-domain deployment-strategy"
timestamp: "2025-09-23T18:49:00-0700"
---

# Mobile Subdomain Redirect Implementation

## Request
> "'/home/axp/projects/jesse-benson/projects/npta_shopify-widget/5_npta-styling/.design/mobile-page/mobile-subdomain-architecture.md' review this. lets get this going"

## Overview
Discovered simpler approach to mobile URL branding without requiring external DNS access or theme modifications. Instead of complex subdomain architecture, leveraged platform's alias domain feature to create cleaner URL for mobile redirects while maintaining existing integration URL. Both URLs point to same deployment, enabling zero-downtime migration without external coordination.

## Decisions

### Platform Alias Instead of Custom Subdomain
- **Context**: Setting up custom subdomain would require DNS access and coordination with client
- **Solution**: Created platform alias as cleaner mobile redirect URL
- **Alternatives**: Theme redirect pages (rejected - requires theme access), actual subdomain setup (rejected - external dependencies), direct deployment URLs (rejected - not user-friendly)
- **Rationale**: Platform aliases provide professional URLs without external dependencies or coordination

### Dual URL Support for Backward Compatibility
- **Context**: External party controls theme integration, changing source requires coordination
- **Solution**: Both original and alias URLs point to same deployment
- **Alternatives**: Force immediate migration (rejected - creates downtime risk), separate deployments (rejected - maintenance burden)

## Implementation

### Architecture
URL migration strategy:
1. Add alias domain in platform settings
2. Update mobile redirect URL in bundle script
3. Deploy changes
4. Both URLs work immediately
5. Migrate integration URL when convenient

### Code Signatures

**Bundle Script Update** (`app/bundle/route.ts`)
```javascript
// Button click handler
widgetButton.addEventListener('click', function() {
  if (isMobile()) {
    // Mobile: Navigate to cleaner alias URL
    let mobileUrl = 'https://npta-chat.vercel.app/mobile';
    if (utmParams) {
      mobileUrl += '?' + new URLSearchParams(utmParams).toString();
    }
    window.location.href = mobileUrl;
  }
});
```

**Platform Configuration**
- Added alias domain in deployment settings
- SSL certificates auto-provisioned
- Both URLs serve identical content

## Audit

### Modified
- `app/bundle/route.ts` - Updated mobile redirect URL to use alias domain

### Deployment
- Git commit and production deploy
- Alias domain configured in platform dashboard
- Zero downtime migration

### URLs
- Original: `5npta-styling.vercel.app` (theme integration)
- Alias: `npta-chat.vercel.app` (mobile redirect)
- Both active simultaneously
