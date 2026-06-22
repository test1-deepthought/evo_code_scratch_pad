"""
Tests for NOVA's knowledge graph module.
"""
import pytest
import tempfile
import os
from nova.knowledge_graph import KnowledgeGraph, Fact, ProofRecord, Pattern


@pytest.fixture
def temp_kg():
    """Create a temporary knowledge graph for testing."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    kg = KnowledgeGraph(path)
    yield kg
    os.unlink(path)


class TestKnowledgeGraph:
    """Test the persistent knowledge graph."""

    def test_assert_and_query(self, temp_kg):
        """Fact should be stored and queryable."""
        temp_kg.assert_fact("subject1", "pred1", "obj1", source="test")
        results = temp_kg.query(subject="subject1")
        assert len(results) == 1
        assert results[0].predicate == "pred1"

    def test_assert_dedup(self, temp_kg):
        """Asserting the same triple should replace, not duplicate."""
        temp_kg.assert_fact("s", "p", "o")
        temp_kg.assert_fact("s", "p", "o")
        results = temp_kg.query(predicate="p")
        assert len(results) == 1

    def test_query_by_predicate(self, temp_kg):
        """Should query by predicate."""
        temp_kg.assert_fact("s1", "color", "red")
        temp_kg.assert_fact("s2", "color", "blue")
        temp_kg.assert_fact("s3", "size", "big")
        results = temp_kg.query(predicate="color")
        assert len(results) == 2

    def test_query_by_object(self, temp_kg):
        """Should query by object."""
        temp_kg.assert_fact("s1", "p1", "target")
        temp_kg.assert_fact("s2", "p2", "other")
        results = temp_kg.query(object_="target")
        assert len(results) == 1

    def test_clear_predicate(self, temp_kg):
        """Should clear facts by predicate."""
        temp_kg.assert_fact("s", "p1", "o1")
        temp_kg.assert_fact("s", "p2", "o2")
        temp_kg.clear("p1")
        assert len(temp_kg.query(predicate="p1")) == 0
        assert len(temp_kg.query(predicate="p2")) == 1

    def test_clear_all(self, temp_kg):
        """Should clear all facts."""
        temp_kg.assert_fact("s1", "p", "o")
        temp_kg.assert_fact("s2", "p", "o")
        temp_kg.clear()
        assert len(temp_kg.query(predicate="p")) == 0

    def test_next_turn(self, temp_kg):
        """Turn counter should increment."""
        assert temp_kg.next_turn() == 1
        assert temp_kg.next_turn() == 2

    def test_export_prolog_facts(self, temp_kg):
        """Should export facts as Prolog strings."""
        temp_kg.assert_fact("subject", "predicate", "object", source="test")
        export = temp_kg.export_prolog_facts()
        assert "fact('subject', 'predicate', 'object'" in export
        assert "test" in export

    def test_export_empty(self, temp_kg):
        """Empty KG should export empty string."""
        assert temp_kg.export_prolog_facts() == ""

    def test_proof_storage(self, temp_kg):
        """Should store and retrieve proofs."""
        record = ProofRecord(
            theorem="test_theorem",
            proof_code="by trivial",
            strategy="direct",
            lemmas_used=[],
            verified=True,
        )
        temp_kg.store_proof(record)
        retrieved = temp_kg.get_proof("test_theorem")
        assert retrieved is not None
        assert retrieved.theorem == "test_theorem"
        assert retrieved.verified

    def test_pattern_storage(self, temp_kg):
        """Should store and retrieve patterns."""
        pat = Pattern(
            name="test_pattern",
            description="A test pattern",
            prolog_template="test(X) :- X.",
        )
        temp_kg.store_pattern(pat)
        retrieved = temp_kg.get_pattern("test_pattern")
        assert retrieved is not None
        assert retrieved.name == "test_pattern"

    def test_pattern_success_rate(self):
        """Success rate should be computed correctly."""
        pat = Pattern(name="t", description="", success_count=3, failure_count=1)
        assert pat.success_rate == 0.75

    def test_persistence(self, temp_kg):
        """Facts should persist across KG instances."""
        path = temp_kg._path
        temp_kg.assert_fact("persist", "test", "value")
        del temp_kg

        kg2 = KnowledgeGraph(path)
        results = kg2.query(predicate="test")
        assert len(results) == 1
        assert results[0].subject == "persist"
        os.unlink(path)

    def test_stats(self, temp_kg):
        """Stats should reflect current state."""
        temp_kg.assert_fact("s", "p", "o")
        stats = temp_kg.stats
        assert stats["facts"] >= 1
        assert stats["turn"] >= 0
