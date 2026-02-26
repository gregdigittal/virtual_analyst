-- 0051_excel_agent_sessions.sql
-- Add agent session tracking columns to excel_ingestion_sessions

ALTER TABLE excel_ingestion_sessions
  ADD COLUMN IF NOT EXISTS agent_session_id TEXT,
  ADD COLUMN IF NOT EXISTS agent_messages JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS agent_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS pending_question JSONB,
  ADD COLUMN IF NOT EXISTS agent_state_json JSONB;

COMMENT ON COLUMN excel_ingestion_sessions.agent_session_id IS 'Claude Agent SDK session ID for resumption';
COMMENT ON COLUMN excel_ingestion_sessions.agent_messages IS 'Chat message history for frontend hydration';
COMMENT ON COLUMN excel_ingestion_sessions.agent_status IS 'running | paused | complete | error';
COMMENT ON COLUMN excel_ingestion_sessions.pending_question IS 'Current question awaiting user answer (null when not paused)';
COMMENT ON COLUMN excel_ingestion_sessions.agent_state_json IS 'Full agent state (classification, mapping, etc.) for session resumption';
