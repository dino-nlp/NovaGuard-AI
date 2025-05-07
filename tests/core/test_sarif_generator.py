# NOVAGUARD-AI/tests/core/test_sarif_generator.py

import unittest
from pathlib import Path
from datetime import datetime, timezone
import sys

# Thêm src vào sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.sarif_generator import (
    SarifGenerator,
    SARIF_VERSION,
    SARIF_SCHEMA_URL,
    SEVERITY_MAP, # Mặc dù không test trực tiếp SEVERITY_MAP, nó được dùng bởi SarifGenerator
    DEFAULT_SARIF_LEVEL
)

class TestSarifGenerator(unittest.TestCase):

    def setUp(self):
        self.tool_name = "TestTool"
        self.tool_version = "1.0.0"
        self.workspace_root_str = "/mock/workspace"
        self.workspace_root_path = Path(self.workspace_root_str)
        self.generator = SarifGenerator(
            tool_name=self.tool_name,
            tool_version=self.tool_version,
            workspace_root_for_relative_paths=self.workspace_root_str
        )
        self.maxDiff = None # Để thấy diff đầy đủ khi assertEqual dicts lớn

    def test_initialization_basic_structure(self):
        """Test the basic structure of an initialized SARIF report."""
        report = self.generator.get_sarif_report() # Gọi get_sarif_report để endTimeUtc được set
        self.assertEqual(report["$schema"], SARIF_SCHEMA_URL)
        self.assertEqual(report["version"], SARIF_VERSION)
        self.assertEqual(len(report["runs"]), 1)

        run = report["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], self.tool_name)
        self.assertEqual(run["tool"]["driver"]["version"], self.tool_version)
        self.assertListEqual(run["tool"]["driver"]["rules"], [])
        self.assertListEqual(run["artifacts"], [])
        self.assertListEqual(run["results"], [])

        self.assertEqual(len(run["invocations"]), 1)
        invocation = run["invocations"][0]
        self.assertTrue("startTimeUtc" in invocation)
        self.assertTrue("endTimeUtc" in invocation) # get_sarif_report sẽ set nếu chưa có
        self.assertTrue(invocation["executionSuccessful"])

    def test_initialization_with_all_options(self):
        """Test initialization with all optional parameters."""
        repo_uri = "https://github.com/user/repo"
        commit_sha = "abcdef123456"
        info_uri = "https://tool.example.com"
        org_name = "TestOrg"

        generator = SarifGenerator(
            tool_name="DetailedTool",
            tool_version="2.0",
            tool_information_uri=info_uri,
            organization_name=org_name,
            repo_uri_for_artifacts=repo_uri,
            commit_sha_for_artifacts=commit_sha,
            workspace_root_for_relative_paths=self.workspace_root_str
        )
        report = generator.get_sarif_report()
        driver = report["runs"][0]["tool"]["driver"]
        self.assertEqual(driver["name"], "DetailedTool")
        self.assertEqual(driver["informationUri"], info_uri)
        self.assertEqual(driver["organization"], org_name)
        # Các test khác cho repo_uri và commit_sha sẽ được thể hiện qua cách artifact URI được tạo (nếu có)
        # SarifGenerator hiện tại không trực tiếp dùng repo_uri và commit_sha để xây dựng artifact URI trong _add_artifact
        # mà chỉ lưu chúng. Điều này có thể được cải thiện trong tương lai.

    def test_add_simple_finding(self):
        """Test adding a minimal finding."""
        file_p = "src/main.py"
        rule_id = "RULE001"
        self.generator.add_finding(
            file_path=str(self.workspace_root_path / file_p), # Đường dẫn tuyệt đối
            message_text="Simple error",
            rule_id=rule_id,
            level="error",
            line_start=10
        )
        report = self.generator.get_sarif_report()
        
        # Artifact
        self.assertEqual(len(report["runs"][0]["artifacts"]), 1)
        artifact = report["runs"][0]["artifacts"][0]
        self.assertEqual(artifact["location"]["uri"], file_p) # Đã được normalize
        self.assertEqual(artifact["location"]["uriBaseId"], "SRCROOT")

        # Rule
        self.assertEqual(len(report["runs"][0]["tool"]["driver"]["rules"]), 1)
        rule = report["runs"][0]["tool"]["driver"]["rules"][0]
        self.assertEqual(rule["id"], rule_id)
        self.assertEqual(rule["defaultConfiguration"]["level"], "error")

        # Result
        self.assertEqual(len(report["runs"][0]["results"]), 1)
        result = report["runs"][0]["results"][0]
        self.assertEqual(result["ruleId"], rule_id)
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["message"]["text"], "Simple error")
        self.assertEqual(result["locations"][0]["physicalLocation"]["artifactLocation"]["index"], 0)
        self.assertEqual(result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], file_p)
        self.assertEqual(result["locations"][0]["physicalLocation"]["region"]["startLine"], 10)

    def test_add_finding_with_all_details(self):
        """Test adding a finding with all optional details."""
        file_p = "lib/utils.js"
        abs_file_p = str(self.workspace_root_path / file_p)
        self.generator.add_finding(
            file_path=abs_file_p,
            message_text="Complex finding with details",
            rule_id="JS002",
            level="warning",
            line_start=5,
            line_end=6,
            col_start=1,
            col_end=10,
            code_snippet="let x = y;",
            rule_name="JavaScript Complex Rule",
            rule_short_description="A complex rule.",
            rule_help_uri="https://example.com/rules/JS002",
            fingerprints={"fp1": "v1_abc"},
            fixes=[{
                "description": {"text": "Replace y with z."},
                "artifactChanges": [{
                    "artifactLocation": {"uri": file_p}, # SarifGenerator sẽ tự set index
                    "replacements": [{
                        "deletedRegion": {"startLine": 5, "endLine": 5, "startColumn": 9, "endColumn": 10}, # 'y;'
                        "insertedContent": {"text": "z;"}
                    }]
                }]
            }]
        )
        report = self.generator.get_sarif_report()
        result = report["runs"][0]["results"][0]
        rule = report["runs"][0]["tool"]["driver"]["rules"][0]

        self.assertEqual(rule["name"], "JavaScript Complex Rule")
        self.assertEqual(rule["shortDescription"]["text"], "A complex rule.")
        self.assertEqual(rule["helpUri"], "https://example.com/rules/JS002")
        self.assertEqual(rule["defaultConfiguration"]["level"], "warning")

        region = result["locations"][0]["physicalLocation"]["region"]
        self.assertEqual(region["endLine"], 6)
        self.assertEqual(region["startColumn"], 1)
        self.assertEqual(region["endColumn"], 10)
        self.assertEqual(region["snippet"]["text"], "let x = y;")

        self.assertEqual(result["partialFingerprints"], {"fp1": "v1_abc"})
        self.assertIsNotNone(result["fixes"])
        self.assertEqual(len(result["fixes"]), 1)
        self.assertEqual(result["fixes"][0]["description"]["text"], "Replace y with z.")
        # Kiểm tra artifact index trong fix đã được set đúng
        self.assertEqual(result["fixes"][0]["artifactChanges"][0]["artifactLocation"]["index"], 0)


    def test_artifact_deduplication_and_uri_normalization(self):
        """Test that artifacts are deduplicated and paths normalized."""
        path1_abs = str(self.workspace_root_path / "src/file1.py")
        path2_abs = str(self.workspace_root_path / "src/file2.py")
        
        self.generator.add_finding(path1_abs, "msg1", "R1", "note", 1)
        self.generator.add_finding(path1_abs, "msg2", "R2", "note", 2) # Same file
        self.generator.add_finding(path2_abs, "msg3", "R3", "note", 3) # Different file
        # Test with an already relative path
        self.generator.add_finding("src/file3.py", "msg4", "R4", "note", 4)


        report = self.generator.get_sarif_report()
        artifacts = report["runs"][0]["artifacts"]
        self.assertEqual(len(artifacts), 3) # file1.py, file2.py, file3.py
        
        # Check URIs are relative and use forward slashes
        self.assertEqual(artifacts[0]["location"]["uri"], "src/file1.py")
        self.assertEqual(artifacts[0]["location"]["uriBaseId"], "SRCROOT")
        self.assertEqual(artifacts[1]["location"]["uri"], "src/file2.py")
        self.assertEqual(artifacts[1]["location"]["uriBaseId"], "SRCROOT")
        self.assertEqual(artifacts[2]["location"]["uri"], "src/file3.py")
        self.assertEqual(artifacts[2]["location"]["uriBaseId"], "SRCROOT")


        results = report["runs"][0]["results"]
        self.assertEqual(results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["index"], 0)
        self.assertEqual(results[1]["locations"][0]["physicalLocation"]["artifactLocation"]["index"], 0)
        self.assertEqual(results[2]["locations"][0]["physicalLocation"]["artifactLocation"]["index"], 1)
        self.assertEqual(results[3]["locations"][0]["physicalLocation"]["artifactLocation"]["index"], 2)

    def test_rule_metadata_deduplication(self):
        """Test that rule metadata is deduplicated."""
        self.generator.add_finding("f.py", "m1", "RULE_A", "error", 1, rule_name="Rule A Name")
        self.generator.add_finding("f.py", "m2", "RULE_A", "error", 2) # Same rule, different finding
        self.generator.add_finding("f.py", "m3", "RULE_B", "warning", 3, rule_name="Rule B Name")

        report = self.generator.get_sarif_report()
        rules = report["runs"][0]["tool"]["driver"]["rules"]
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0]["id"], "RULE_A")
        self.assertEqual(rules[0]["name"], "Rule A Name")
        self.assertEqual(rules[1]["id"], "RULE_B")
        self.assertEqual(rules[1]["name"], "Rule B Name")

    def test_severity_level_mapping(self):
        """Test mapping of input severity levels to SARIF levels."""
        levels_to_test = {
            "error": "error", "CRITICAL": "error", "high": "error",
            "warning": "warning", "Medium": "warning",
            "note": "note", "information": "note", "LoW": "note", "info": "note",
            "unknown_level": DEFAULT_SARIF_LEVEL, # Should map to default
            "": DEFAULT_SARIF_LEVEL # Empty string also to default
        }
        for i, (input_level, expected_sarif_level) in enumerate(levels_to_test.items()):
            rule_id = f"SEV_TEST_{i}"
            self.generator.add_finding("test.txt", "msg", rule_id, input_level, 1)
            report = self.generator.get_sarif_report()
            result = next(r for r in report["runs"][0]["results"] if r["ruleId"] == rule_id)
            self.assertEqual(result["level"], expected_sarif_level, f"Input level '{input_level}' mapped incorrectly.")
            # Also check rule defaultConfiguration level
            rule_meta = next(r for r in report["runs"][0]["tool"]["driver"]["rules"] if r["id"] == rule_id)
            self.assertEqual(rule_meta["defaultConfiguration"]["level"], expected_sarif_level)


    def test_path_normalization_no_workspace_root(self):
        """Test path handling when no workspace_root is provided."""
        gen_no_root = SarifGenerator(self.tool_name, self.tool_version)
        abs_path = "/absolute/path/to/file.py"
        rel_path = "relative/path/file.py"
        
        gen_no_root.add_finding(abs_path, "m", "R", "note", 1)
        gen_no_root.add_finding(rel_path, "m", "R", "note", 1)
        
        report = gen_no_root.get_sarif_report()
        artifacts = report["runs"][0]["artifacts"]
        
        self.assertEqual(artifacts[0]["location"]["uri"], abs_path.replace("\\", "/")) # Absolute path kept
        self.assertNotIn("uriBaseId", artifacts[0]["location"])
        self.assertEqual(artifacts[1]["location"]["uri"], rel_path.replace("\\", "/")) # Relative path kept
        self.assertNotIn("uriBaseId", artifacts[1]["location"])


    def test_set_invocation_status(self):
        """Test setting the invocation status."""
        self.generator.set_invocation_status(successful=False, error_message="A major error occurred")
        report = self.generator.get_sarif_report()
        
        invocation = report["runs"][0]["invocations"][0]
        self.assertFalse(invocation["executionSuccessful"])
        self.assertTrue("endTimeUtc" in invocation)
        
        notifications = report["runs"][0]["tool"]["driver"]["notifications"]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["level"], "error")
        self.assertEqual(notifications[0]["message"]["text"], "A major error occurred")

    def test_empty_report_structure(self):
        """Test that an empty report (no findings) still has valid basic structure."""
        # setUp already creates a generator. Just get the report.
        report = self.generator.get_sarif_report()
        self.assertEqual(report["version"], SARIF_VERSION)
        self.assertEqual(len(report["runs"]), 1)
        self.assertEqual(len(report["runs"][0]["results"]), 0)
        self.assertEqual(len(report["runs"][0]["artifacts"]), 0)
        self.assertEqual(len(report["runs"][0]["tool"]["driver"]["rules"]), 0)
        self.assertTrue(report["runs"][0]["invocations"][0]["executionSuccessful"])


if __name__ == '__main__':
    unittest.main()