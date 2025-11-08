# CORE Type Resolver

**Purpose:** Resolve CORE coordinates to domain-specific semantic types

**Status:** Validated (3/3 test success, 0.82-0.88 confidence)

---

## Role

This agent interprets 6-dimensional CORE coordinates and resolves them to semantic types within a specified domain.

**Input:**
- CORE coordinates (6D interrogative + metadata)
- Domain context

**Output:**
- Semantic type name
- Reasoning (coordinate-to-type mapping)
- Confidence score (0-1)

---

## CORE Coordinate System

### Interrogative Dimensions (0-1 scale)
- **what:** Object/subject identification
- **how:** Method/process/implementation
- **where:** Location/context/scope
- **why:** Purpose/rationale/motivation
- **who:** Actors/agents/parties
- **when:** Temporal position/timing

### Metadata Dimensions
- **valence:** good | bad | neutral | mixed
- **abstraction:** concrete | abstract | meta
- **epistemic:** known | hypothetical | unknown
- **temporal:** past | present | future
- **structural:** atomic | composite | relational

---

## Domain Templates

### Technical Documentation
- **API Reference:** {what: 0.95, where: 0.8, how: 0.6, concrete, atomic}
- **Tutorial:** {how: 0.95, when: 0.8, what: 0.7, concrete, composite}
- **Concept:** {why: 0.9, what: 0.85, abstract, relational}
- **Example:** {what: 0.9, how: 0.85, concrete, composite}
- **Troubleshooting:** {what: 0.8, how: 0.85, why: 0.7, bad valence}

### Software Development Changelogs
- **Decision:** {what: 0.85, why: 0.75, good valence, known}
- **Implementation:** {how: 0.95, what: 0.6, concrete, past, composite}
- **Bug Report:** {what: 0.85, why: 0.8, bad valence, past, atomic}
- **Pattern:** {how: 0.9, why: 0.85, abstract, relational, good}
- **Architecture Decision:** {what: 0.85, why: 0.9, abstract, composite}

### Legal Documents
- **Statute:** {what: 0.9, abstract, known, present, atomic}
- **Precedent:** {what: 0.85, why: 0.75, who: 0.7, past, concrete}
- **Obligation:** {what: 0.9, who: 0.9, future, concrete, atomic}
- **Argument:** {why: 0.95, hypothetical, abstract, relational}

### Personal Journal
- **Daily Event:** {what: 0.7, when: 0.9, concrete, past, atomic}
- **Reflection:** {why: 0.9, abstract, present, mixed valence}
- **Relationship Entry:** {who: 0.85, why: 0.9, relational, abstract}
- **Goal:** {what: 0.8, how: 0.7, future, concrete}

---

## Validated Examples

### Example 1: Bug Report
```
CORE: {what: 0.85, why: 0.8, where: 0.7, when: 0.7,
      valence: bad, temporal: past, concrete, atomic}
Domain: Software Development Changelogs

Resolution:
Type: Bug Report
Reasoning: High what/why + bad valence + past = what broke and root cause
Confidence: 0.88
```

### Example 2: Obligation
```
CORE: {what: 0.9, who: 0.9, when: 0.7,
      temporal: future, concrete, known, atomic}
Domain: Legal Documents

Resolution:
Type: Obligation
Reasoning: High what/who + future + concrete = specific parties with duties
Confidence: 0.85
```

### Example 3: Relationship Entry
```
CORE: {why: 0.9, who: 0.85, when: 0.6,
      valence: mixed, abstract, hypothetical, relational}
Domain: Personal Journal

Resolution:
Type: Relationship Entry
Reasoning: High why/who + relational = interpersonal dynamics and reasons
Confidence: 0.82
```

---

## Usage

### Direct Invocation
```bash
# Via Task tool
Task(
  subagent_type="general-purpose",
  model="haiku",
  description="Resolve CORE to type",
  prompt="""
  You are interpreting CORE coordinates to determine content type.

  COORDINATES: {what: 0.85, why: 0.8, ...}
  DOMAIN: [domain name]

  POSSIBLE TYPES: [domain type list with signatures]

  QUESTION: Given these coordinates, what type would have this signature?

  Type: [answer]
  Reasoning: [one sentence]
  Confidence: [0-1]
  """
)
```

### Prompt Template
```
You are interpreting CORE coordinates to determine content type.

The coordinates below describe a hypothetical [content type].
Your task is to interpret what type it represents.

COORDINATES (this is your input data):
- what=[0-1], how=[0-1], where=[0-1], why=[0-1], who=[0-1], when=[0-1]
- valence=[good|bad|neutral|mixed]
- abstraction=[concrete|abstract|meta]
- epistemic=[known|hypothetical|unknown]
- temporal=[past|present|future]
- structural=[atomic|composite|relational]

DOMAIN: [domain name]

POSSIBLE TYPES:
- Type A: description (signature hints)
- Type B: description (signature hints)
- Type C: description (signature hints)

QUESTION: Given these coordinates, what type of [domain] content would have this signature?

Type: [your answer]
Reasoning: [match coordinates to type, one sentence]
Confidence: [0-1]
```

---

## Resolution Strategy

### Pattern Matching
1. **Identify dominant dimensions** (values > 0.7)
2. **Check metadata alignment** (valence, temporal, structural)
3. **Match to domain templates** (closest signature)
4. **Validate with reasoning** (explain coordinate-to-type mapping)

### Confidence Factors
- **High (0.8-1.0):** Clear dimensional pattern, strong domain match
- **Medium (0.6-0.8):** Partial pattern match, some ambiguity
- **Low (0.0-0.6):** Weak signals, multiple possible types

### Disambiguation
When coordinates match multiple types:
1. Use metadata as tiebreaker (valence, temporal, structural)
2. Prioritize dominant dimensions (highest values)
3. Consider domain context (what's typical)

---

## Integration Points

### With CORE Classifier
```
Document chunk � CORE Classifier � Coordinates
                                    �
                        Type Resolver � Semantic type
```

### With Metadata Gateway
```
Markdown � Parser � CORE coords � Type Resolver � Metadata store
                                                      �
                                              {section_type: "Bug Report",
                                               core: {...},
                                               ...}
```

### With Introspection System
```
imem introspect --domain software
  � Lists available types with CORE signatures
  � Agent uses for query construction
```

---

## Test Results

**Date:** 2025-11-06
**Test:** 3 agents, 3 domains, Haiku model
**Success Rate:** 100% (3/3)
**Average Confidence:** 0.85

**Validation:**
-  Coordinates interpreted correctly as input
-  Domain context applied appropriately
-  Type matching used dimensional patterns
-  Reasoning explained coordinate-to-type logic
-  Confidence scores realistic and justified

---

## Future Enhancements

1. **Multi-domain resolution:** Resolve same coords across multiple domains
2. **Confidence calibration:** Fine-tune based on validation dataset
3. **Hybrid types:** Handle chunks with mixed signatures
4. **Custom domains:** Allow user-defined domain templates
5. **Batch resolution:** Process multiple coords efficiently

---

## References

- [FlexSchema Overview](../../../.designate/methodologies/flexschema/overview.md)
- [CORE Dimensions](../../../.designate/methodologies/flexschema/core-dimensions.md)
- [Hindley-Milner Conversation](../../../.designate/.inbox/fleet/tiny-models/Claude-Hindley-Milner type system explained.md)
