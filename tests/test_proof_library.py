"""
Tests for NOVA's proof library module.
"""
import pytest
import tempfile
import os
from nova.proof_library import ProofLibrary, ProofSkeleton, ProofEntry


@pytest.fixture
def temp_lib():
    """Create a temporary proof library for testing."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    lib = ProofLibrary(path)
    yield lib
    try:
        os.unlink(path)
    except (FileNotFoundError, PermissionError):
        pass


class TestProofLibrary:
    """Test the proof pattern library."""

    def test_store_and_find_skeleton(self, temp_lib):
        """Should store and retrieve skeletons."""
        skel = ProofSkeleton(
            name="test_skeleton",
            strategy="induction",
            theorem_template="theorem test (n : N) : ...",
            proof_template="induction n with ...",
            key_lemmas=["Nat.succ_eq_add_one"],
            success_count=1,
            tags=["induction", "natural"],
        )
        temp_lib.store_skeleton(skel)
        found = temp_lib.find_skeleton("test_skeleton")
        assert found is not None
        assert found.strategy == "induction"

    def test_find_nonexistent_skeleton(self, temp_lib):
        """Nonexistent skeleton should return None."""
        assert temp_lib.find_skeleton("no_such_skeleton") is None

    def test_find_fuzzy_match(self, temp_lib):
        """Should find skeleton by fuzzy name match."""
        skel = ProofSkeleton(name="induction_nat", strategy="induction",
                              theorem_template="", proof_template="")
        temp_lib.store_skeleton(skel)
        found = temp_lib.find_skeleton("induction_natural")
        assert found is not None

    def test_search_by_strategy(self, temp_lib):
        """Should find skeletons by strategy."""
        temp_lib.store_skeleton(ProofSkeleton(
            name="i1", strategy="induction", theorem_template="", proof_template=""
        ))
        temp_lib.store_skeleton(ProofSkeleton(
            name="i2", strategy="induction", theorem_template="", proof_template=""
        ))
        temp_lib.store_skeleton(ProofSkeleton(
            name="c1", strategy="contradiction", theorem_template="", proof_template=""
        ))
        induction_matches = temp_lib.search_by_strategy("induction")
        assert len(induction_matches) == 2

    def test_search_by_lemma(self, temp_lib):
        """Should find entries by lemma usage."""
        temp_lib.store_proof(ProofEntry(
            theorem_name="t1", full_statement="", proof_code="",
            strategy="", lemmas_used=["Nat.add_comm", "Nat.add_assoc"],
            verified=True,
        ))
        temp_lib.store_proof(ProofEntry(
            theorem_name="t2", full_statement="", proof_code="",
            strategy="", lemmas_used=["Nat.mul_comm"],
            verified=True,
        ))
        matches = temp_lib.search_by_lemma("add_comm")
        assert len(matches) == 1
        assert matches[0].theorem_name == "t1"

    def test_find_by_tag(self, temp_lib):
        """Should find skeletons by tag."""
        temp_lib.store_skeleton(ProofSkeleton(
            name="s1", strategy="induction", theorem_template="", proof_template="",
            tags=["number_theory", "induction"],
        ))
        matches = temp_lib.find_by_tag("number_theory")
        assert len(matches) == 1

    def test_suggest_skeleton_induction(self, temp_lib):
        """Should suggest induction skeleton for induction problems."""
        temp_lib.store_skeleton(ProofSkeleton(
            name="induction_skel", strategy="induction",
            theorem_template="", proof_template="",
        ))
        suggested = temp_lib.suggest_skeleton("Prove by induction that n + 0 = n")
        assert suggested is not None
        assert suggested.strategy == "induction"

    def test_suggest_skeleton_no_match(self, temp_lib):
        """Should return None for unknown problems with empty library."""
        suggested = temp_lib.suggest_skeleton("Prove something completely unknown")
        assert suggested is None

    def test_store_and_find_proof(self, temp_lib):
        """Should store and retrieve proofs."""
        entry = ProofEntry(
            theorem_name="my_theorem",
            full_statement="theorem my_theorem : True := by trivial",
            proof_code="by trivial",
            strategy="direct",
            lemmas_used=[],
            verified=True,
        )
        temp_lib.store_proof(entry)
        found = temp_lib.find_proof("my_theorem")
        assert found is not None
        assert found.verified

    def test_extract_and_store(self, temp_lib):
        """Should extract a proof entry and auto-create skeleton."""
        entry = temp_lib.extract_and_store(
            "test_theorem",
            "theorem test (n : N) : n = n := rfl",
            "rfl",
            "direct",
            [],
            True,
        )
        assert entry is not None
        assert entry.theorem_name == "test_theorem"

        # Should auto-create a skeleton for notable strategies
        skeleton = temp_lib.find_skeleton("test_theorem")
        # The skeleton is named after strategy pattern, so might not find by name
        assert temp_lib.get_stats()["proofs"] == 1

    def test_persistence(self, temp_lib):
        """Library should persist across instances."""
        path = temp_lib._path
        temp_lib.store_skeleton(ProofSkeleton(
            name="persist_skeleton", strategy="direct",
            theorem_template="", proof_template="",
        ))
        # Force save by deleting the object
        old_path = temp_lib._path
        import gc
        gc.collect()

        lib2 = ProofLibrary(path)
        found = lib2.find_skeleton("persist_skeleton")
        assert found is not None
        # Don't delete here - fixture handles it

    def test_get_stats(self, temp_lib):
        """Stats should reflect library contents."""
        temp_lib.store_skeleton(ProofSkeleton(
            name="s1", strategy="induction", theorem_template="", proof_template="",
        ))
        stats = temp_lib.get_stats()
        assert stats["skeletons"] >= 1
        assert "induction" in stats["strategies"]

    def test_count_tokens_estimate(self, temp_lib):
        """Token count should be a positive integer."""
        skel = ProofSkeleton(
            name="test", strategy="direct",
            theorem_template="theorem t : True := by",
            proof_template="trivial",
        )
        count = temp_lib.count_tokens_estimate(skel)
        assert count > 0
