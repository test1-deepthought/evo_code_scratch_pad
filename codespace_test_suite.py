"""
Comprehensive Codespace/CODE Tier Test Suite
Tests the code_scratch_pad tool's capabilities
"""
import unittest
import sys
import os


class TestCodeScratchPad(unittest.TestCase):
    """Test the scratch pad functionality"""

    def test_python_version(self):
        """Verify Python is available and recent enough"""
        major, minor = sys.version_info[:2]
        self.assertGreaterEqual((major, minor), (3, 8))

    def test_math_imports(self):
        """Verify core math libraries are importable"""
        import math
        self.assertAlmostEqual(math.pi, 3.141592653589793)

    def test_sympy_available(self):
        """Verify sympy is importable for symbolic math"""
        import sympy
        x = sympy.Symbol('x')
        expr = sympy.integrate(x**2, x)
        self.assertEqual(expr, x**3 / 3)

    def test_numpy_available(self):
        """Verify numpy is available for array operations"""
        import numpy as np
        arr = np.array([1, 2, 3])
        self.assertEqual(arr.sum(), 6)

    def test_file_system_access(self):
        """Verify we can read/write files"""
        test_content = "codespace test content"
        with open("/tmp/test_codespace.txt", "w") as f:
            f.write(test_content)
        with open("/tmp/test_codespace.txt", "r") as f:
            read_back = f.read()
        self.assertEqual(read_back, test_content)
        os.remove("/tmp/test_codespace.txt")

    def test_subprocess(self):
        """Verify we can run subprocesses"""
        import subprocess
        result = subprocess.run(["echo", "hello"], capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "hello")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCodeScratchPad)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
