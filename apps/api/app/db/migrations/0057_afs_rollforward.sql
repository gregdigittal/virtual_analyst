-- 0057_afs_rollforward.sql — AFS Phase 6: roll-forward tracking

ALTER TABLE afs_sections ADD COLUMN IF NOT EXISTS rolled_forward_from text;
-- rolled_forward_from stores the prior section_id this section was copied from.
-- NULL means the section was created fresh (not rolled forward).
