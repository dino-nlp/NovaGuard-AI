# NOVAGUARD-AI/src/core/sarif_generator.py

import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set, Union

logger = logging.getLogger(__name__)

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA_URL = "https://json.schemastore.org/sarif-2.1.0.json"

# Mapping from common severity terms to SARIF levels
# SARIF levels: "error", "warning", "note", "none"
SEVERITY_MAP: Dict[str, str] = {
    "error": "error",
    "critical": "error",
    "high": "error",
    "warning": "warning",
    "medium": "warning",
    "note": "note",
    "information": "note",
    "info": "note",
    "low": "note",
    "none": "none",
}
DEFAULT_SARIF_LEVEL = "note" # Default if mapping fails or level is unspecified


class SarifGenerator:
    """
    Generates a SARIF v2.1.0 report from analysis findings.
    """

    def __init__(self,
                tool_name: str,
                tool_version: str,
                tool_information_uri: Optional[str] = None,
                organization_name: Optional[str] = None,
                repo_uri_for_artifacts: Optional[str] = None, # e.g., https://github.com/owner/repo
                commit_sha_for_artifacts: Optional[str] = None,
                workspace_root_for_relative_paths: Optional[Union[str, Path]] = None
                ):
        """
        Initializes the SarifGenerator.

        Args:
            tool_name: Name of the analysis tool (e.g., "NovaGuardAI").
            tool_version: Version of the tool.
            tool_information_uri: URI for more information about the tool.
            organization_name: Optional name of the organization running the tool.
            repo_uri_for_artifacts: Optional base URI for artifacts (e.g., GitHub repo URL).
                                    If provided, used to construct full URLs for file locations.
            commit_sha_for_artifacts: Optional commit SHA. Used with repo_uri_for_artifacts.
            workspace_root_for_relative_paths: Optional absolute path to the workspace root.
                                            Used to make artifact URIs relative if they are absolute.
        """
        self.tool_name = tool_name
        self.tool_version = tool_version
        self.tool_information_uri = tool_information_uri
        self.organization_name = organization_name
        
        self.repo_uri = repo_uri_for_artifacts
        self.commit_sha = commit_sha_for_artifacts

        self.workspace_root: Optional[Path] = None
        if workspace_root_for_relative_paths:
            self.workspace_root = Path(workspace_root_for_relative_paths).resolve()

        self.report: Dict[str, Any] = {
            "$schema": SARIF_SCHEMA_URL,
            "version": SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": self.tool_name,
                            "version": self.tool_version,
                            "rules": [], # Populated by _add_rule_metadata
                            # "notifications": [], # For tool-level warnings/errors
                            # "taxonomies": [], # If you categorize rules
                        }
                    },
                    "artifacts": [], # Populated by _add_artifact
                    "results": [],   # Populated by add_finding
                    "invocations": [ # Basic invocation information
                        {
                            "startTimeUtc": datetime.now(timezone.utc).isoformat(timespec='seconds'),
                            "executionSuccessful": True # Can be updated later
                        }
                    ]
                }
            ]
        }
        if self.tool_information_uri:
            self.report["runs"][0]["tool"]["driver"]["informationUri"] = self.tool_information_uri
        if self.organization_name:
            self.report["runs"][0]["tool"]["driver"]["organization"] = self.organization_name

        self.registered_rules: Set[str] = set()
        self.artifact_map: Dict[str, int] = {} # Maps file path string to its index in artifacts array

        logger.info(f"SarifGenerator initialized for tool: {self.tool_name} v{self.tool_version}")

    def _normalize_path(self, file_path_str: str) -> str:
        """
        Normalizes a file path string:
        - Converts to Path object for processing.
        - Makes it relative to workspace_root if workspace_root is set and path is absolute.
        - Uses forward slashes.
        """
        path_obj = Path(file_path_str)
        if self.workspace_root and path_obj.is_absolute():
            try:
                path_obj = path_obj.relative_to(self.workspace_root)
            except ValueError:
                logger.warning(f"File path {file_path_str} is absolute but not within workspace {self.workspace_root}. Using original path.")
        
        # Convert to string with forward slashes for SARIF URI compatibility
        return path_obj.as_posix()


    def _add_artifact(self, file_path_str_original: str) -> int:
        """
        Adds an artifact (file) to the report if not already present.
        Returns the index of the artifact in the 'artifacts' array.
        """
        normalized_file_path = self._normalize_path(file_path_str_original)

        if normalized_file_path in self.artifact_map:
            return self.artifact_map[normalized_file_path]

        artifact_location: Dict[str, Any] = {"uri": normalized_file_path}
        
        # If workspace_root is known, we can assume 'uri' is relative to it.
        # SARIF allows uriBaseId for this, e.g., "%SRCROOT%"
        if self.workspace_root:
            artifact_location["uriBaseId"] = "SRCROOT" # Or any other logical name like REPO_ROOT

        artifact_entry: Dict[str, Any] = {"location": artifact_location}
        
        # Add source language if known (example, can be extended)
        # if lang := self._guess_language(normalized_file_path):
        #    artifact_entry["sourceLanguage"] = lang

        self.report["runs"][0]["artifacts"].append(artifact_entry)
        new_index = len(self.report["runs"][0]["artifacts"]) - 1
        self.artifact_map[normalized_file_path] = new_index
        logger.debug(f"Added artifact '{normalized_file_path}' at index {new_index}")
        return new_index

    def _add_rule_metadata(self,
                        rule_id: str,
                        rule_name: Optional[str] = None,
                        short_description: Optional[str] = None,
                        full_description: Optional[str] = None,
                        help_uri: Optional[str] = None,
                        default_level: Optional[str] = None): # 'error', 'warning', 'note'
        """
        Adds metadata for a rule to the tool's driver if not already present.
        """
        if rule_id in self.registered_rules:
            return

        rule_md: Dict[str, Any] = {"id": rule_id}
        if rule_name:
            rule_md["name"] = rule_name
        
        # SARIF requires shortDescription
        rule_md["shortDescription"] = {"text": short_description or f"Finding reported by rule '{rule_id}'."}
        
        if full_description:
            rule_md["fullDescription"] = {"text": full_description}
        
        if help_uri:
            rule_md["helpUri"] = help_uri
        
        # Default configuration for the rule, including its intrinsic severity
        rule_md["defaultConfiguration"] = {
            "level": SEVERITY_MAP.get(str(default_level).lower(), DEFAULT_SARIF_LEVEL) if default_level else DEFAULT_SARIF_LEVEL
        }
        
        self.report["runs"][0]["tool"]["driver"]["rules"].append(rule_md)
        self.registered_rules.add(rule_id)
        logger.debug(f"Registered rule metadata for ID: '{rule_id}'")


    def add_finding(self,
                    file_path: str,
                    message_text: str,
                    rule_id: str,
                    level: str, # Expected: "error", "warning", "note", or synonyms
                    line_start: int,
                    line_end: Optional[int] = None,
                    col_start: Optional[int] = None,
                    col_end: Optional[int] = None,
                    code_snippet: Optional[str] = None,
                    rule_name: Optional[str] = None,
                    rule_short_description: Optional[str] = None,
                    rule_help_uri: Optional[str] = None,
                    # SARIF specific enrichments:
                    fingerprints: Optional[Dict[str, str]] = None, # For partialFingerprints
                    code_flows: Optional[List[Dict[str, Any]]] = None,
                    fixes: Optional[List[Dict[str, Any]]] = None # Suggested fixes
                ):
        """
        Adds a single finding (result) to the SARIF report.

        Args:
            file_path: Path to the file where the finding occurred (relative to workspace or absolute).
            message_text: The primary message describing the finding.
            rule_id: Identifier for the rule that was violated.
            level: Severity level (e.g., "error", "warning", "note").
            line_start: The 1-based starting line number of the finding.
            line_end: Optional 1-based ending line number.
            col_start: Optional 1-based starting column number.
            col_end: Optional 1-based ending column number.
            code_snippet: Optional snippet of code related to the finding.
            rule_name: Optional human-readable name for the rule (for metadata).
            rule_short_description: Optional short description for the rule (for metadata).
            rule_help_uri: Optional URI for more help on the rule (for metadata).
            fingerprints: Optional dictionary for result fingerprinting.
            code_flows: Optional list of SARIF code flow objects.
            fixes: Optional list of SARIF fix objects for suggested remediations.
        """
        # Ensure rule metadata exists
        self._add_rule_metadata(
            rule_id,
            rule_name=rule_name or rule_id.replace("_", " ").title(), # Default rule name
            short_description=rule_short_description,
            full_description=rule_short_description, # Can be more elaborate
            help_uri=rule_help_uri,
            default_level=level # Use the finding's level for the rule's default level for simplicity
        )

        artifact_index = self._add_artifact(file_path)
        normalized_file_path_for_location = self.report["runs"][0]["artifacts"][artifact_index]["location"]["uri"]


        sarif_level = SEVERITY_MAP.get(level.lower(), DEFAULT_SARIF_LEVEL)

        result: Dict[str, Any] = {
            "ruleId": rule_id,
            "level": sarif_level,
            "message": {"text": message_text},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": normalized_file_path_for_location, # Store normalized path here as well
                            "index": artifact_index
                        },
                        "region": {
                            "startLine": line_start,
                        }
                    }
                }
            ]
        }

        # Region details
        region = result["locations"][0]["physicalLocation"]["region"]
        if line_end is not None:
            region["endLine"] = line_end
        # else: # SARIF implies endLine defaults to startLine if not present
            # region["endLine"] = line_start 
        if col_start is not None:
            region["startColumn"] = col_start
        if col_end is not None:
            region["endColumn"] = col_end
        if code_snippet is not None:
            region["snippet"] = {"text": code_snippet}
        
        # Optional fields
        if fingerprints:
            result["partialFingerprints"] = fingerprints
        if code_flows:
            result["codeFlows"] = code_flows
        if fixes:
            # Ensure fixes reference the correct artifact index
            for fix_obj in fixes:
                for art_change in fix_obj.get("artifactChanges", []):
                    art_change["artifactLocation"]["index"] = artifact_index
                    # Could also set uri here if needed, but index is primary
            result["fixes"] = fixes
            
        self.report["runs"][0]["results"].append(result)
        logger.debug(f"Added finding for rule '{rule_id}' in file '{file_path}'")

    def set_invocation_status(self, successful: bool, end_time_utc: Optional[str] = None, error_message: Optional[str]=None):
        """Updates the invocation status, typically called at the end of the process."""
        if not self.report["runs"][0]["invocations"]: # Should not happen with current init
            self.report["runs"][0]["invocations"] = [{}] 
        
        invocation = self.report["runs"][0]["invocations"][0]
        invocation["executionSuccessful"] = successful
        if end_time_utc:
            invocation["endTimeUtc"] = end_time_utc
        else:
            invocation["endTimeUtc"] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        
        if not successful and error_message:
            # Tool execution notifications for overall errors
            if "notifications" not in self.report["runs"][0]["tool"]["driver"]:
                self.report["runs"][0]["tool"]["driver"]["notifications"] = []
            self.report["runs"][0]["tool"]["driver"]["notifications"].append({
                "level": "error",
                "message": {"text": error_message}
            })


    def get_sarif_report(self) -> Dict[str, Any]:
        """
        Finalizes and returns the complete SARIF report as a dictionary.
        """
        # If invocation end time wasn't explicitly set by set_invocation_status
        if "endTimeUtc" not in self.report["runs"][0]["invocations"][0]:
            self.report["runs"][0]["invocations"][0]["endTimeUtc"] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            
        logger.info(f"Finalizing SARIF report. Total results: {len(self.report['runs'][0]['results'])}")
        return self.report