"""Tests for cc_approver.__main__ module."""
from unittest.mock import patch

class TestMain:
    def test_main_import(self):
        """Test that __main__ imports correctly."""
        with patch('cc_approver.cli.main') as mock_main:
            import cc_approver.__main__
            # Should have imported main from cli
            assert hasattr(cc_approver.__main__, 'main')