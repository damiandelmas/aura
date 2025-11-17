---
pattern_layer: "design-decision-abstraction"
original_doc: "251031-1730_embedding-model-migration-status.md"
abstraction_level: "universal-patterns"
---

# Pattern: Smart Detector with Registry Fallback

## Core Design Pattern
Migrate to a new default resource configuration while maintaining backward compatibility with legacy systems through automatic detection and adaptive routing.

## Problem Statement
Need to standardize on a single resource version/configuration while ensuring existing systems continue operating without manual intervention or migration delays.

## Pattern Architecture

### Three-Layer Detection Stack
1. **Query Layer**: Access existing resource, extract configuration identifier
2. **Registry Layer**: Central lookup table maps identifier to configuration details
3. **Loading Layer**: Load appropriate resource variant based registry result

### Auto-Detection Mechanism
```
Access Resource → Extract Config ID → Registry Lookup → Load Appropriate Version → Execute Zero Manual Switching
```

## Design Decision: Default + Fallback

**Context**: Need to standardize on a single version while maintaining backward compatibility

**Solution**:
- Set newer version as default for new instances
- Auto-detect which version an existing instance uses based on stored configuration
- Load appropriate version transparently

**Rationale**:
- New systems benefit from improved efficiency
- Existing systems preserve functionality without intervention
- Gradual migration path (scheduled re-indexing of legacy instances)

## Key Principles

1. **Configuration as Source of Truth**: Resource metadata declares its own version/configuration requirements
2. **Registry Pattern**: Centralized configuration lookup enables consistent resolution across the system
3. **Graduated Migration**:
   - Immediate: New instances use optimized version
   - Automatic: Legacy instances detected and routed correctly
   - Scheduled: Legacy instances migrated on planned timeline
4. **Zero Manual Switching**: System handles version differences transparently

## Implementation Dimensions

### Configuration Metadata
- Resource stores configuration identifier in accessible location
- Configuration includes all necessary parameters for loading

### Registry Structure
- Maps configuration identifiers to full resource specifications
- Single source of truth for version details

### Loading Strategy
- Conditional logic based on registry lookup
- Support for multiple resource versions simultaneously
- Fallback to previous version for legacy instances

## Variant Testing
- Create temporary parallel instance for A/B comparison
- Validate new version behavior against legacy version
- Gather metrics for deprecation timing

## Deployment Considerations

### Immediate Actions
- Update default configuration in registry
- Deploy updated loading logic
- Configure new instances to use new version

### Deferred Actions
- Track legacy instances using old version
- Schedule migration windows for re-indexing/migration
- Monitor performance during transition period

## Cross-Project Applicability

This pattern applies whenever:
- Multiple versions of a resource/service must coexist
- Legacy systems cannot be updated immediately
- New systems should use improved defaults
- Transparent version detection is feasible from stored metadata

Replace domain-specific terms as follows:
- "embedding model" → resource type
- "vector configuration" → stored configuration metadata
- "SentenceTransformer" → resource loader
- "collection" → resource/service instance
- "re-indexing" → resource migration/update
