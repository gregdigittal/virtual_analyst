-- Migration: 0061_afs_needs_review
-- Purpose: Add needs_review flag to afs_sections for rolled-forward sections
-- that require human review before publication.
-- AFS-P6: Roll-forward with update flags.

ALTER TABLE afs_sections
  ADD COLUMN IF NOT EXISTS needs_review boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN afs_sections.needs_review IS
  'True when a section was rolled forward from a prior period and requires human review before publication.';

-- down: ALTER TABLE afs_sections DROP COLUMN IF EXISTS needs_review;
