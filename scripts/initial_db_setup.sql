-- Extension for UUID generation if not already enabled
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users Table
CREATE TABLE Users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    github_user_id VARCHAR(255) UNIQUE, -- Store GitHub's unique user ID
    github_access_token_encrypted TEXT, -- Encrypted GitHub OAuth access token
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Projects Table
CREATE TABLE Projects (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES Users(id) ON DELETE CASCADE NOT NULL,
    github_repo_id VARCHAR(255) NOT NULL, -- Store GitHub's unique repository ID
    repo_name VARCHAR(255) NOT NULL, -- e.g., "owner/repo_name"
    main_branch VARCHAR(255) NOT NULL,
    language VARCHAR(100), -- Primary programming language
    custom_project_notes TEXT, -- User-defined notes for context
    github_webhook_id VARCHAR(255), -- ID of the webhook created on GitHub
    is_active BOOLEAN DEFAULT TRUE, -- To easily enable/disable analysis for a project
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, github_repo_id) -- A user cannot add the same repo multiple times
);

-- PRAnalysisRequests Table
-- Stores a record for each PR analysis initiated
CREATE TABLE PRAnalysisRequests (
    id SERIAL PRIMARY KEY,
    project_id INT REFERENCES Projects(id) ON DELETE CASCADE NOT NULL,
    github_pr_number INT NOT NULL, -- Pull Request number from GitHub
    pr_title TEXT,
    pr_github_url VARCHAR(2048),
    head_sha VARCHAR(40) NOT NULL, -- SHA of the latest commit in the PR
    status VARCHAR(20) CHECK (status IN ('pending', 'processing', 'completed', 'failed')) DEFAULT 'pending',
    error_message TEXT, -- Store error if analysis failed
    requested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, -- When the webhook was received / task created
    started_at TIMESTAMPTZ, -- When the worker picked up the task
    completed_at TIMESTAMPTZ, -- When analysis finished
    UNIQUE(project_id, github_pr_number, head_sha) -- Avoid duplicate analysis for the same PR state
);

-- AnalysisFindings Table
-- Stores individual findings from an analysis
CREATE TABLE AnalysisFindings (
    id SERIAL PRIMARY KEY,
    pr_analysis_request_id INT REFERENCES PRAnalysisRequests(id) ON DELETE CASCADE NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    line_start INT,
    line_end INT,
    severity VARCHAR(50) CHECK (severity IN ('Error', 'Warning', 'Note', 'Info')) NOT NULL,
    message TEXT NOT NULL, -- Description of the finding
    suggestion TEXT, -- LLM-generated suggestion
    agent_name VARCHAR(100), -- Name of the agent that produced this finding (e.g., DeepLogicBugHunterAI_MVP1)
    user_feedback VARCHAR(50) CHECK (user_feedback IN ('Helpful', 'Not Helpful', 'Uncategorized')) DEFAULT 'Uncategorized', -- Optional user feedback
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Function to automatically update 'updated_at' timestamp
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for 'updated_at'
CREATE TRIGGER set_timestamp_users
BEFORE UPDATE ON Users
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

CREATE TRIGGER set_timestamp_projects
BEFORE UPDATE ON Projects
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

-- You might not need an updated_at for PRAnalysisRequests and AnalysisFindings
-- as they are typically created and not updated, but can be added if needed.

-- Indexes for performance
CREATE INDEX idx_projects_user_id ON Projects(user_id);
CREATE INDEX idx_pranalysisrequests_project_id ON PRAnalysisRequests(project_id);
CREATE INDEX idx_pranalysisrequests_status ON PRAnalysisRequests(status);
CREATE INDEX idx_analysisfindings_pr_request_id ON AnalysisFindings(pr_analysis_request_id);
CREATE INDEX idx_users_github_user_id ON Users(github_user_id);
CREATE INDEX idx_projects_github_repo_id ON Projects(github_repo_id);