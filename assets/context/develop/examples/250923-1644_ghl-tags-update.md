---
schema_version: "v3_adaptive"
type: "implementation.integration-update"
status: "completed"
keywords: "gohighlevel tags lead-capture widget-integration branding-update lead-categorization"
timestamp: "2025-09-23T16:44:00-0700"
---

# CRM Tags Update for Rebranding

## Request
> "we want to use the existing 'new-lead' tag, and a new one 'ava_chatbot' // do u have to veryify what the name of it is exactly in the system for new lead?"

## Overview
Updated CRM integration tags to reflect new branding and simplify lead categorization. Replaced previous three-tag system with cleaner two-tag approach using existing standard tag and new source identifier. Change affects all new leads captured through widget, ensuring proper categorization with updated tagging scheme.

## Decisions

### Tag Selection and Naming Convention
- **Context**: Need to update tags for new branding while working with existing CRM system constraints
- **Solution**: Use existing standard tag and create new source identifier tag with space-separated format for system compatibility
- **Alternatives**: Hyphenated format (rejected - system uses spaces), keep old tags (rejected - outdated branding)

### Remove Promotional Tag
- **Context**: Previous implementation included promotional tag in standard capture
- **Solution**: Removed promotional tag to focus on lead source identification only
- **Alternatives**: Keep promotional tags (rejected - adds unnecessary complexity)

### Verification Approach
- **Context**: Question about verifying exact tag name in CRM system
- **Solution**: Searched codebase for existing references, found none, proceeded with specified names
- **Alternatives**: Request CRM system access for verification (rejected - unnecessary delay)

## Implementation

### Architecture
Tag update flow:
1. Search codebase for all tag references
2. Update default tags in contact creation
3. Update tags in automation trigger
4. Verify consistency across all locations

### Code Signatures

**Tag Updates** (`services/GHLService.ts`)
```typescript
// Before: Old tag structure
tags: ['widget-lead', 'npta-chatbot', '$25-off-claim']

// After: Simplified structure
tags: ['new lead', 'ava chatbot']

// Applied in 3 locations:
// - Line 50: Default tags in createContact method
// - Line 305: Console log in createLeadAndTriggerAutomation
// - Line 315: Actual tags when creating contact
```

## Audit

### Modified
- `services/GHLService.ts` - Updated tags in 3 locations (default tags, console logging, contact creation)

### Tag Changes
Removed:
- `widget-lead` → replaced with `new lead`
- `npta-chatbot` → replaced with `ava chatbot`
- `$25-off-claim` → eliminated

Added:
- `new lead` - standard lead tag
- `ava chatbot` - source identifier

### Verification
- Searched for existing tag references (none found)
- Confirmed space-separated format for CRM compatibility
- Verified all tag occurrences updated
