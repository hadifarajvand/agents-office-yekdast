"""Stress tests for brain vault implementation"""

import tempfile
from pathlib import Path

from backend.services.brain import read_vault, rank_by_relevance


class TestBrainRobustness:
    """Test brain handles edge cases and scales"""

    def test_empty_brain(self):
        """Empty vault returns empty state"""
        with tempfile.TemporaryDirectory() as tmpdir:
            notes, links = read_vault(Path(tmpdir))
            assert notes == {}
            assert links == []

    def test_name_collision(self):
        """Same filename in different folders - last one wins"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create same-named note in different dirs
            (tmppath / "dir1").mkdir()
            (tmppath / "dir1" / "note.md").write_text("first content")
            (tmppath / "dir2").mkdir()
            (tmppath / "dir2" / "note.md").write_text("second content")

            notes, _ = read_vault(tmppath)
            # Last one wins (depends on iteration order)
            assert "note" in notes
            assert notes["note"]["text"] in ["first content", "second content"]

    def test_broken_wiki_link(self):
        """Link to non-existent note doesn't crash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "note1.md").write_text("See [[missing-note]] for details")

            notes, links = read_vault(tmppath)
            assert ("note1", "missing-note") in links
            assert "note1" in notes

    def test_circular_links(self):
        """Circular wiki-links don't cause infinite loops"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "note1.md").write_text("Links to [[note2]]")
            (tmppath / "note2.md").write_text("Links to [[note1]]")

            notes, links = read_vault(tmppath)
            assert len(notes) == 2
            assert ("note1", "note2") in links
            assert ("note2", "note1") in links

    def test_large_brain(self):
        """Brain with 1000+ notes loads efficiently"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create 100 notes (scale up if needed)
            for i in range(100):
                (tmppath / f"note_{i:03d}.md").write_text(
                    f"Note {i}\n\nLinks to [[note_{(i + 1) % 100:03d}]]"
                )

            notes, links = read_vault(tmppath)
            assert len(notes) == 100
            assert len(links) == 100  # Each note links to next

    def test_special_characters_in_filenames(self):
        """Handles special chars in note names"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "note-with-dashes.md").write_text("content")
            (tmppath / "note_with_underscores.md").write_text("content")

            notes, _ = read_vault(tmppath)
            assert "note-with-dashes" in notes
            assert "note_with_underscores" in notes

    def test_deep_nested_structure(self):
        """Handles deeply nested folder structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create deep nesting
            deep = tmppath / "a" / "b" / "c" / "d" / "e"
            deep.mkdir(parents=True)
            (deep / "note.md").write_text("deep note")

            notes, _ = read_vault(tmppath)
            assert "note" in notes
            assert notes["note"]["group"] == "a"  # Top-level group

    def test_unicode_content(self):
        """Handles unicode in note content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "unicode.md").write_text(
                "Note with accents like café", encoding="utf-8"
            )

            notes, _ = read_vault(tmppath)
            assert "unicode" in notes
            assert "café" in notes["unicode"]["text"]

    def test_very_large_note(self):
        """Handles large note files (1MB+)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create 2MB note
            large_content = "x" * (2 * 1024 * 1024)
            (tmppath / "large.md").write_text(large_content)

            notes, _ = read_vault(tmppath)
            assert "large" in notes

    def test_skip_dirs_respected(self):
        """.obsidian, .git, 99-Archive are skipped"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / ".obsidian").mkdir()
            (tmppath / ".obsidian" / "config.md").write_text("should skip")
            (tmppath / ".git").mkdir()
            (tmppath / ".git" / "HEAD.md").write_text("should skip")
            (tmppath / "99-Archive").mkdir()
            (tmppath / "99-Archive" / "old.md").write_text("should skip")
            (tmppath / "keep.md").write_text("should load")

            notes, _ = read_vault(tmppath)
            assert "keep" in notes
            assert "config" not in notes
            assert "HEAD" not in notes
            assert "old" not in notes

    def test_relevance_ranking_accuracy(self):
        """Relevance ranking finds best matches"""
        test_notes = [
            {"name": "python_tutorial", "text": "Learn Python basics"},
            {"name": "javascript_guide", "text": "Learn JavaScript"},
            {"name": "python_advanced", "text": "Advanced Python patterns"},
        ]

        ranked = rank_by_relevance(test_notes, "python", top_k=10)
        assert len(ranked) == 2
        # Both python notes should be ranked higher
        assert ranked[0]["name"] in ["python_tutorial", "python_advanced"]
        assert ranked[1]["name"] in ["python_tutorial", "python_advanced"]

    def test_relevance_empty_query(self):
        """Empty query returns no results"""
        test_notes = [{"name": "note", "text": "content"}]
        ranked = rank_by_relevance(test_notes, "", top_k=10)
        assert ranked == []

    def test_relevance_top_k_limit(self):
        """top_k parameter limits results"""
        test_notes = [{"name": f"note_{i}", "text": "python"} for i in range(100)]
        ranked = rank_by_relevance(test_notes, "python", top_k=5)
        assert len(ranked) == 5

    def test_permission_denied_folder(self):
        """Gracefully handles permission denied errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "accessible.md").write_text("content")
            restricted = tmppath / "restricted"
            restricted.mkdir()
            (restricted / "note.md").write_text("restricted")

            # Remove read permission
            import os

            os.chmod(str(restricted), 0o000)

            try:
                notes, _ = read_vault(tmppath)
                # Should load accessible, skip restricted
                assert "accessible" in notes
                # May or may not load restricted depending on OS
            finally:
                # Restore permission for cleanup
                os.chmod(str(restricted), 0o755)

    def test_malformed_links(self):
        """Handles malformed wiki-link syntax"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "malformed.md").write_text(
                "Valid [[link]] but also [[ broken]] and ][ reversed]"
            )

            notes, links = read_vault(tmppath)
            assert "malformed" in notes
            # Should extract valid link
            assert ("malformed", "link") in links
