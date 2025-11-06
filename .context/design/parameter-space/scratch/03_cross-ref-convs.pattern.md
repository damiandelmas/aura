# Cross-Referencing Conversations for Authority Validation

Cross-referencing with conversation genealogy validates claims against actual source discussions.

## Authority Validation Pipeline

**AI Changelog Claims:**
```
has_rationale: true = "AI wrote reasoning"
temporal_position: "current_thrust" = "AI thinks this is current"
category: "implementation.security" = "AI categorized as security work"
```

**Cross-Reference with Conversation (session_id):**
- User messages = What human actually requested/discussed
- Problem statements = What human was trying to solve
- User feedback = "Yes that worked" vs "That didn't solve it"
- Follow-up questions = Indicates incomplete solution

**Authority Hedging Examples:**

```python
# AI claims comprehensive decision
has_rationale=true AND has_alternatives=true
# But conversation shows:
user_messages = ["just make it work", "quick fix needed"]
# Authority score: DISCOUNT (rushed implementation)

# AI claims current solution
temporal_position="current_thrust"
# But later conversation shows:
user_messages = ["that didn't work", "try different approach"]
# Authority score: DISCOUNT (failed implementation)

# AI claims security implementation
category="implementation.security"
# Conversation confirms:
user_messages = ["need to secure the API", "add authentication"]
# Authority score: BOOST (user-validated scope)
```

## The Real Authority Score

```python
authority = (
    ai_structural_completeness * 0.3 +
    user_validation_factor * 0.5 +      # From conversation analysis
    temporal_non_contradiction * 0.2     # No later "that failed" messages
)
```

Conversation becomes the ground truth that validates or contradicts AI's confident claims.

## Semantic Authority Validation

Semantic search filters user messages against every decision, qualifies their confidence/authority score, then serves that chunk with hints or softened language in contextual templates.

**Pipeline:**

1. **Semantic search**: User messages against every Decision chunk
2. **Confidence scoring**: High similarity = user discussed this topic
3. **Authority adjustment**: User validation boosts, contradiction discounts
4. **Contextual serving**: Template hints based on confidence level

**Example Output Templates:**

**High Authority (user-validated):**
```
## Use JWT Authentication
✅ **Confirmed approach** (discussed extensively in conversation)
- Context: API needs secure user sessions
- Solution: Implement JWT with 24hr expiration
```

**Medium Authority (AI-inferred):**
```
## Database Connection Pooling
⚠️ **Implementation detail** (limited user discussion)
- Context: Performance optimization needed
- Solution: Use connection pool with max 10 connections
```

**Low Authority (AI-speculative):**
```
## Error Handling Strategy
❓ **AI-suggested approach** (not explicitly discussed)
- Context: Need consistent error responses
- Solution: Centralized error middleware
*Note: Consider validating this approach*
```

**The Intelligence:**
- User message similarity scores become authority multipliers
- Template renders confidence levels visually
- System admits uncertainty instead of overconfident AI claims

**Result**: Honest, validated knowledge retrieval that distinguishes between "user wanted this" vs "AI thought this was good."

## Detecting Premature Claims

The problem: Early speculation captured in single chunk, lack of actual data to overturn it.

**Evidence from System:**

1. **Speculation in Single Chunk**
   - Constraint made without supporting evidence
   - `temporal_position: "current_thrust"` + `continuation_count: 0` = never revisited
   - No temporal evolution showing validation

2. **Lack of Genealogy**
   - Changelogs have session_id links
   - But source conversations not indexed
   - Can't trace claim back to originating discussion

3. **No Contradicting Data Yet**
   - Referenced features not yet populated
   - Temporal tracking shows never superseded
   - Remains as orphaned assertion

**The Pattern:**
- Early decision made in conversation
- Speculation captured as constraint in changelog
- No contradicting data yet (features not populated)
- Temporal tracking shows never superseded

**When This Gets Resolved:**
1. Conversations get indexed → genealogy reconstructs origin
2. Referenced features get populated → validate claim with actual content
3. If wrong → new changelog marks old constraint as superseded
4. Temporal primitive shows evolution: speculation → validation → revision

## Three Approaches to Flag Premature Claims

### Approach 1: Confidence Decay Model

```python
confidence_score = (
    user_authority * 0.4 +           # Semantic similarity to user messages
    temporal_stability * 0.3 +       # Age without contradiction
    evidence_support * 0.3           # Other chunks that validate claim
)

# Flag when:
if confidence_score < 0.6:
    template = "⚠️ **Unvalidated claim** (limited evidence)"
```

### Approach 2: Isolation Detection

```python
isolation_flags = {
    'genealogy_orphan': len(genealogy) == 0,      # No conversation trace
    'continuation_zero': continuation_count == 0,  # Never revisited
    'sibling_sparse': len(siblings) < 2,          # Minimal context
    'temporal_stale': days_since_creation > 30    # Old without update
}

# Flag when multiple isolation indicators
if sum(isolation_flags.values()) >= 2:
    template = "🔍 **Needs validation** (isolated speculation)"
```

### Approach 3: Evidence Requirement Scoring

```python
claim_strength = {
    'definitive': ["already", "always", "never", "all"],
    'speculative': ["should", "might", "probably", "likely"],
    'qualified': ["in this case", "for now", "currently"]
}

evidence_required = (
    claim_strength_score * 0.4 +     # Stronger claims need more evidence
    scope_breadth * 0.3 +             # Broader scope needs more validation
    user_authority_deficit * 0.3      # Low user discussion needs evidence
)
```

**Each approach catches different failure modes:**

- **Decay**: Flags old unvalidated decisions
- **Isolation**: Flags orphaned speculation
- **Evidence**: Flags overconfident claims without support
