---
schema_version: "v3_adaptive"
type: "implementation.ai-tools"
status: "completed"
keywords: "email-update ai-tools crm-integration duplicate-contacts tool-execution context-injection session-management lead-capture"
timestamp: "2025-01-21T14:45:00-0800"
---

# Email Update Tool Implementation

## Request
> "when someone asks if they got the email thing. then you ask — did i get that emial thing. she correctly says to look in inbox and spam foloder and then asks — did u get that or do u need help sorting that out? // we have to (1) tell her not to offer to help or (2) be able to reset the lead capture component. ? what do u think?"

## Overview
Implemented email update tool using the AI tools pattern, matching existing name correction functionality. Discovered and resolved critical issue where the platform was rejecting email updates due to duplicate contact prevention, requiring a smart contact detection and linking system. Also fixed fundamental problem where AI showed success messages even when tools failed - now always uses actual tool results for user feedback.

## Decisions

### Use AI Tools Pattern
- **Context**: Email updates weren't working like name updates
- **Solution**: Created AI tool matching existing name correction pattern

### Smart Contact Detection and Linking
- **Context**: Platform was rejecting email updates with duplicate contact errors when user's corrected email already existed on different contact record
- **Solution**: Search for existing contact before updating; if found, link current session to that contact instead of updating current contact record
- **Alternatives**: Force updates (rejected - violates platform rules), reject all updates (rejected - poor UX), manual resolution (rejected - requires support intervention)
- **Rationale**: Maintains data integrity while providing seamless user experience without exposing complexity to user
- **Implications**: Pattern applicable to any scenario where user-provided identifiers might conflict with existing records

### Fix Tool Execution Response Handling
- **Context**: AI was showing success messages even when tools failed, causing user confusion
- **Solution**: Always use tool result message regardless of success/failure status
- **Alternatives**: Complex error injection (rejected - overcomplicated), ignore failures (rejected - misleading)

## Constraints

### Platform Duplicate Prevention Rules
- **What**: CRM platform rejects contact updates when email already exists on different contact
- **Discovery**: Encountered during testing - platform returned "This location does not allow duplicated contacts" error
- **Workaround**: Search for existing contact first, link session if found instead of updating
- **Impact**: Requires additional API call but prevents update failures and maintains user experience

### Email Validation Requirements
- **What**: Must validate email format before platform API calls
- **Discovery**: Invalid emails cause platform API errors without clear user feedback
- **Workaround**: Regex validation before any platform operations
- **Impact**: Better user experience with immediate validation feedback

## Failures

### Wrong API Endpoint for Contact Search
- **Attempted**: Used `/contacts/search` endpoint for email lookup
- **Why Failed**: Endpoint doesn't exist in API, returned 404 errors
- **Lesson**: Correct endpoint is `/contacts/?query=` with location filter parameter

### Assumed Tool Success in Responses
- **Attempted**: AI generated success messages independently of actual tool execution results
- **Why Failed**: Users saw "success" confirmations even when tools failed, creating confusion and support issues
- **Lesson**: Always use tool result message as the actual response, never generate assumed success messages

## Implementation

### Architecture
Email correction flow:
1. User indicates email is wrong
2. AI asks for correct email (two-step pattern)
3. Tool validates format with regex
4. Tool searches for existing contact with that email
5. If exists → link session to existing contact
6. If new → update current contact
7. Trigger automation workflow
8. Return tool result message to user

### Code Signatures

**Email Update Tool** (`services/AIToolsService.ts`)
```typescript
async function updateUserEmailTool(params, context): Promise<ToolResult> {
  // Validate email format
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return { success: false, message: "Please provide a valid email address" };
  }

  // Check for existing contact
  const existingContact = await GHLService.findContactByEmail(email);

  if (existingContact && existingContact.id !== ghlContactId) {
    // Link to existing instead of updating
    await ReferenceService.linkGHLContact(sessionId, existingContact.id);
    await GHLService.triggerWorkflow(workflowId, existingContact.id);
    return { success: true, message: "Perfect! I've updated your email..." };
  }

  // Safe to update current contact
  await GHLService.updateContact(ghlContactId, { email });
  await GHLService.triggerWorkflow(workflowId, ghlContactId);
  return { success: true, message: "Perfect! I've updated your email..." };
}
```

**Contact Search** (`services/GHLService.ts`)
```typescript
static async findContactByEmail(email: string): Promise<Contact | null> {
  const response = await fetch(
    `/contacts/?locationId=${LOCATION_ID}&query=${encodeURIComponent(email)}`
  );
  const { contacts } = await response.json();

  // Find exact email match
  return contacts.find(c => c.email?.toLowerCase() === email.toLowerCase()) || null;
}
```

**Tool Response Fix** (`app/api/chat/route.ts`)
```typescript
// Before: AI assumed success ❌
// AI generated its own response regardless of tool result

// After: Use actual tool result ✅
for (const toolCall of toolCalls) {
  const result = await executeTool(toolCall, { sessionId });
  fullResponse = result.message;  // Always use tool message
  break;
}
```

**System Prompt Pattern** (`prompts/variants/current.md`)
```markdown
## USER INFORMATION CORRECTIONS

**Email Corrections (Two-Step):**
1. User says email is wrong → Ask "What's your correct email?"
2. User provides email → Use update_user_email tool
3. Tool provides response → Continue conversation
```

## Audit

### Created/Modified
- `services/AIToolsService.ts` - Added updateUserEmailTool function and update_user_email tool definition
- `services/GHLService.ts` - Added findContactByEmail and triggerWorkflow methods
- `app/api/chat/route.ts` - Fixed tool execution to always use actual tool results instead of AI assumptions
- `prompts/variants/current.md` - Added email correction instructions with two-step pattern

### Integration Points
- Email update tool integrates with existing CRM contact management system
- Smart contact linking prevents duplicate contact errors
- Automatic workflow triggering ensures follow-up emails are sent
- Two-step interaction pattern matches existing name correction flow for consistency
