# Note on schema packaging

This pack includes **full text** for the major schemas that were drafted explicitly in-chat:
- MODEL_CONFIG_V1 (ARTIFACT_MODEL_CONFIG_SCHEMA.json)
- MACRO_REGIME_V1 (ARTIFACT_MACRO_REGIME_SCHEMA.json)
- SENTIMENT_V1 (ARTIFACT_SENTIMENT_SCHEMA.json)
- ORG_STRUCTURE_V1 (ARTIFACT_ORG_STRUCTURE_SCHEMA.json)

Some additional schemas were described at a high level but not fully enumerated line-by-line in the chat.
Those are still listed in CURSOR_MASTER_PROMPT.md; Cursor should implement them following the design patterns
used in the included schemas (integrity_block, ids, refs, etc.).
