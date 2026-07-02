import gzip
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "deploy_firebase_hosting.py"
SPEC = importlib.util.spec_from_file_location("deploy_firebase_hosting", SCRIPT_PATH)
deploy_firebase_hosting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy_firebase_hosting)


class FirebaseHostingHashTest(unittest.TestCase):
    def test_sha256_gz_hashes_uploaded_gzip_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.html"
            path.write_bytes(b"<html>deploy check</html>")

            digest, gzipped_bytes = deploy_firebase_hosting.sha256_gz(path)

            self.assertEqual(gzip.decompress(gzipped_bytes), path.read_bytes())
            self.assertEqual(digest, hashlib.sha256(gzipped_bytes).hexdigest())
            self.assertNotEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_sha256_gz_is_deterministic_for_unchanged_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.dart.js"
            path.write_bytes(b"console.log('stable');")

            first_digest, first_gzip = deploy_firebase_hosting.sha256_gz(path)
            second_digest, second_gzip = deploy_firebase_hosting.sha256_gz(path)

            self.assertEqual(second_digest, first_digest)
            self.assertEqual(second_gzip, first_gzip)


if __name__ == "__main__":
    unittest.main()
