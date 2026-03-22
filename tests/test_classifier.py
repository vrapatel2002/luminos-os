"""
tests/test_classifier.py
Unit tests for the Phase 2 binary classifier pipeline.
No external dependencies — uses tempfile to create synthetic test binaries.
"""

import os
import sys
import tempfile
import unittest

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from classifier import classify_binary
from classifier.feature_extractor import extract_features
from classifier.zone_rules import classify


def _make_binary(content: bytes) -> str:
    """Write bytes to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix='.bin')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
    except Exception:
        os.close(fd)
        raise
    return path


class TestFeatureExtractor(unittest.TestCase):

    def test_elf_magic_detected(self):
        path = _make_binary(b'\x7fELF' + b'\x00' * 64)
        try:
            f = extract_features(path)
            self.assertTrue(f['is_elf'])
            self.assertFalse(f['is_pe'])
        finally:
            os.unlink(path)

    def test_pe_magic_detected(self):
        path = _make_binary(b'MZ' + b'\x00' * 64)
        try:
            f = extract_features(path)
            self.assertFalse(f['is_elf'])
            self.assertTrue(f['is_pe'])
        finally:
            os.unlink(path)

    def test_anticheat_string_detected(self):
        path = _make_binary(b'MZ' + b'\x00' * 32 + b'BattlEye' + b'\x00' * 32)
        try:
            f = extract_features(path)
            self.assertTrue(f['has_anticheat_strings'])
        finally:
            os.unlink(path)

    def test_kernel_driver_detected(self):
        path = _make_binary(b'MZ' + b'\x00' * 32 + b'ntoskrnl.exe' + b'\x00' * 32)
        try:
            f = extract_features(path)
            self.assertTrue(f['has_kernel_driver_imports'])
        finally:
            os.unlink(path)

    def test_win32_import_detected(self):
        path = _make_binary(b'MZ' + b'\x00' * 32 + b'kernel32.dll' + b'\x00' * 32)
        try:
            f = extract_features(path)
            self.assertTrue(f['has_win32_imports'])
        finally:
            os.unlink(path)

    def test_vulkan_detected(self):
        path = _make_binary(b'MZ' + b'\x00' * 32 + b'vulkan-1.dll' + b'\x00' * 32)
        try:
            f = extract_features(path)
            self.assertTrue(f['has_vulkan'])
        finally:
            os.unlink(path)

    def test_opengl_detected(self):
        path = _make_binary(b'MZ' + b'\x00' * 32 + b'opengl32.dll' + b'\x00' * 32)
        try:
            f = extract_features(path)
            self.assertTrue(f['has_opengl'])
        finally:
            os.unlink(path)

    def test_file_size_mb(self):
        data = b'\x7fELF' + b'\x00' * (1024 * 1024 - 4)  # exactly 1 MB
        path = _make_binary(data)
        try:
            f = extract_features(path)
            self.assertAlmostEqual(f['file_size_mb'], 1.0, places=3)
        finally:
            os.unlink(path)


class TestZoneRules(unittest.TestCase):

    def test_elf_is_zone1(self):
        features = {
            'is_elf': True, 'is_pe': False,
            'has_win32_imports': False, 'has_kernel_driver_imports': False,
            'has_anticheat_strings': False,
        }
        result = classify(features)
        self.assertEqual(result['zone'], 1)
        self.assertEqual(result['confidence'], 0.99)

    def test_pe_kernel_driver_is_zone3(self):
        features = {
            'is_elf': False, 'is_pe': True,
            'has_win32_imports': False, 'has_kernel_driver_imports': True,
            'has_anticheat_strings': False,
        }
        result = classify(features)
        self.assertEqual(result['zone'], 3)
        self.assertEqual(result['confidence'], 0.95)

    def test_pe_anticheat_is_zone3(self):
        features = {
            'is_elf': False, 'is_pe': True,
            'has_win32_imports': False, 'has_kernel_driver_imports': False,
            'has_anticheat_strings': True,
        }
        result = classify(features)
        self.assertEqual(result['zone'], 3)
        self.assertEqual(result['confidence'], 0.90)

    def test_pe_win32_is_zone2(self):
        features = {
            'is_elf': False, 'is_pe': True,
            'has_win32_imports': True, 'has_kernel_driver_imports': False,
            'has_anticheat_strings': False,
        }
        result = classify(features)
        self.assertEqual(result['zone'], 2)
        self.assertEqual(result['confidence'], 0.85)

    def test_pe_no_imports_is_zone2(self):
        features = {
            'is_elf': False, 'is_pe': True,
            'has_win32_imports': False, 'has_kernel_driver_imports': False,
            'has_anticheat_strings': False,
        }
        result = classify(features)
        self.assertEqual(result['zone'], 2)
        self.assertEqual(result['confidence'], 0.70)

    def test_unknown_is_zone1_fallback(self):
        features = {
            'is_elf': False, 'is_pe': False,
            'has_win32_imports': False, 'has_kernel_driver_imports': False,
            'has_anticheat_strings': False,
        }
        result = classify(features)
        self.assertEqual(result['zone'], 1)
        self.assertEqual(result['confidence'], 0.50)

    def test_kernel_driver_takes_priority_over_anticheat(self):
        """Kernel driver rule (Zone 3, 0.95) must fire before anticheat rule."""
        features = {
            'is_elf': False, 'is_pe': True,
            'has_win32_imports': True, 'has_kernel_driver_imports': True,
            'has_anticheat_strings': True,
        }
        result = classify(features)
        self.assertEqual(result['zone'], 3)
        self.assertEqual(result['confidence'], 0.95)


class TestClassifyBinaryEndToEnd(unittest.TestCase):
    """Full pipeline: fake binary file → classify_binary() → zone decision."""

    def test_fake_elf_zone1(self):
        path = _make_binary(b'\x7fELF' + b'\x00' * 128)
        try:
            result = classify_binary(path)
            self.assertEqual(result['zone'], 1)
        finally:
            os.unlink(path)

    def test_fake_pe_zone2(self):
        path = _make_binary(b'MZ' + b'\x00' * 128)
        try:
            result = classify_binary(path)
            self.assertEqual(result['zone'], 2)
        finally:
            os.unlink(path)

    def test_fake_pe_battleye_zone3(self):
        path = _make_binary(b'MZ' + b'\x00' * 64 + b'BattlEye' + b'\x00' * 64)
        try:
            result = classify_binary(path)
            self.assertEqual(result['zone'], 3)
        finally:
            os.unlink(path)

    def test_fake_pe_ntoskrnl_zone3(self):
        path = _make_binary(b'MZ' + b'\x00' * 64 + b'ntoskrnl.exe' + b'\x00' * 64)
        try:
            result = classify_binary(path)
            self.assertEqual(result['zone'], 3)
        finally:
            os.unlink(path)

    def test_result_has_required_keys(self):
        path = _make_binary(b'\x7fELF' + b'\x00' * 64)
        try:
            result = classify_binary(path)
            self.assertIn('zone', result)
            self.assertIn('confidence', result)
            self.assertIn('reason', result)
        finally:
            os.unlink(path)

    def test_nonexistent_file_raises(self):
        with self.assertRaises((FileNotFoundError, OSError)):
            classify_binary('/tmp/luminos_nonexistent_file_xyz.bin')


if __name__ == '__main__':
    unittest.main(verbosity=2)
