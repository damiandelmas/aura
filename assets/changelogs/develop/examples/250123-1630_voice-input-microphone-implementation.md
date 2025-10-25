---
schema_version: "v3_adaptive"
type: "implementation.voice-input"
status: "completed"
keywords: "voice-recognition speech-api microphone-button toggle-functionality hydration-safe mobile-alignment flexbox-centering browser-compatibility"
timestamp: "2025-01-23T16:30:00-0800"
---

# Voice Input Microphone Implementation

## Request
> "how difficult is it to have a microphone button instead of the arrow so u can speak to it?"

## Overview
Implemented voice recognition system that transforms the send button into an intelligent microphone when appropriate. Created dedicated voice recognition hook for clean separation of concerns, implemented smart button state management that switches between microphone and send based on user context, and solved mobile alignment challenges through flexbox layout. The system includes toggle behavior with visual feedback and graceful fallbacks for unsupported browsers.

## Decisions

### Separate Voice Recognition Hook
- **Context**: Initial attempt to add voice logic directly to main component created bloated code
- **Solution**: Created dedicated hook with clean API and error handling

### Smart Button State Management
- **Context**: User wanted microphone when ready for voice, send arrow when ready to type, needed intelligent context detection
- **Solution**: Conditional rendering based on three conditions - speech support available, empty input field, and input not focused
- **Alternatives**: Always show microphone (rejected - confusing when typing), separate buttons (rejected - clutters UI), toggle behavior only (rejected - doesn't match user intent)
- **Rationale**: Three-condition check creates intuitive UX where microphone only appears when it actually makes sense to use it
- **Implications**: Pattern applicable to any context-sensitive UI element that should appear/disappear based on user state

### Toggle vs One-Shot Voice Recognition
- **Context**: Initial implementation auto-stopped after speech detection, user needed manual control
- **Solution**: Click to start/stop toggle behavior with visual feedback
- **Alternatives**: Continuous listening (rejected - privacy concerns), push-to-talk (rejected - awkward on mobile)

### Flexbox Mobile Alignment
- **Context**: Absolute positioning with complex CSS calculations failed to center button properly
- **Solution**: Flexbox container with natural alignment

## Constraints

### Browser Speech API Support
- **What**: Web Speech API only available in Chrome and Edge browsers, not Firefox or older browsers
- **Discovery**: Feature detection revealed limited browser support during cross-browser testing
- **Workaround**: Conditional rendering with graceful fallback to text input only
- **Impact**: Voice input unavailable for Firefox users, requires user-friendly messaging

### HTTPS Required in Production
- **What**: Speech API requires secure context (HTTPS) except on localhost
- **Discovery**: Works perfectly in development but fails on HTTP production deployments
- **Workaround**: Deploy to HTTPS-enabled platform
- **Impact**: Cannot use voice features on insecure connections, blocks some deployment options

### Network Connectivity Required
- **What**: Speech processing happens in cloud services, not locally on device
- **Discovery**: Voice recognition fails without internet connection during offline testing
- **Workaround**: Show error message to user when network fails, fall back to text input
- **Impact**: Offline usage not possible for voice input feature

## Failures

### Absolute Positioning for Mobile Alignment
- **Attempted**: Multiple CSS approaches with absolute positioning including `top: 1/2 -translate-y-1/2`, custom centering classes, arbitrary pixel values
- **Why Failed**: Centered against wrong reference element, selector specificity conflicts, no reliable reference point for dynamic textarea height
- **Lesson**: Flexbox with `items-center` provides natural alignment without manual calculations

### Auto-Stop After Speech Detection
- **Attempted**: Automatically stop listening after first speech result to simplify UX
- **Why Failed**: User wanted manual control to speak multiple times without re-clicking button each time
- **Lesson**: Provide explicit start/stop toggle rather than assuming user intent, let user control when to stop

## Implementation

### Architecture
Voice input flow:
1. Detect browser speech support on component mount
2. Show microphone when: supported AND empty input AND not focused
3. User clicks microphone → start listening with visual feedback
4. Speech detected → insert text into input field
5. User clicks again → stop listening
6. Typing or focusing input → switch to send button

### Code Signatures

**Voice Recognition Hook** (`hooks/useSimpleVoice.ts`)
```typescript
export function useSimpleVoice({ onResult, onError }) {
  const [isListening, setIsListening] = useState(false);

  // Feature detection
  const isSupported = typeof window !== 'undefined' &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);

  // API configuration
  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  // Return clean interface
  return { isListening, isSupported, startListening, stopListening };
}
```

**Smart Button Logic** (`components/bubble.tsx`)
```typescript
// Intelligent button state switching
{isLoading ? (
  <StopButton />
) : speechSupported && input.length === 0 && !inputFocus ? (
  <MicrophoneButton />
) : (
  <SendButton />
)}
```

**Mobile Flexbox Layout** (`components/bubble.tsx`)
```tsx
// Natural alignment without absolute positioning
<div className="flex items-center gap-2">
  <textarea className="w-full rounded-3xl py-[1rem]" />
  <button className="flex-shrink-0 h-10 w-10 rounded-full">
    <MicrophoneIcon />
  </button>
</div>
```

**Visual Feedback Animations** (`app/globals.css`)
```css
@keyframes mic-listening {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

@keyframes mic-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}
```

## Patterns

### Flexbox Over Absolute Positioning
- **Pattern**: Use flexbox for alignment instead of absolute positioning with manual calculations
- **When**: Centering elements vertically within dynamic-height containers
- **Approach**: Wrap in flex container with `items-center`, use `flex-shrink-0` on fixed-size elements
- **Benefit**: Natural alignment without CSS calculations, automatically responsive to container size changes

## Audit

### Created
- `hooks/useSimpleVoice.ts` - Voice recognition hook with browser detection and error handling
- CSS animations in `app/globals.css` - Added mic-listening ripple effect and mic-breathe icon animation

### Modified
- `components/bubble.tsx` - Integrated voice hook, added smart button logic, restructured mobile composer with flexbox layout
- Added hydration-safe speech support detection
- Implemented conditional button rendering based on user context
- Integrated modern microphone SVG icon with animation states
