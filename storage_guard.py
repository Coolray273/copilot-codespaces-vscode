import hashlib
import os

def generate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

print("\n[STORAGE GUARD] Running SHA-256 Duplication Check...")
files_to_check = ["R1_Master_Manifest.pdf", "R1_Master_Manifest.docx", "R1_Master_Manifest.txt"]
hashes = {}
problems = 0

for file in files_to_check:
    if os.path.exists(file):
        file_hash = generate_sha256(file)
        if file_hash in hashes.values():
            print(f"[ALERT] Duplication detected! {file} has the same hash as another file.")
            problems += 1
        else:
            hashes[file] = file_hash
            print(f"[SECURE] {file} verified. Unique Hash: {file_hash[:16]}...")
    else:
        print(f"[MISSING] {file} not found.")
        problems += 1

if problems:
    print(f"[STORAGE GUARD] FAILED: {problems} problem(s) found.")
    raise SystemExit(1)
print("[STORAGE GUARD] Zero-Duplication confirmed. Storage is 1:1.")
