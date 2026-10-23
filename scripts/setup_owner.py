"""Run locally. Prints a password HASH, never the password. Store output as a hosting secret."""
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sentinel.security import password_hash
password = getpass.getpass('Owner password (at least 16 characters): ')
if len(password)<16:
    raise SystemExit('Use at least 16 characters')
if password!=getpass.getpass('Confirm: '):
    raise SystemExit('Passwords do not match')
print(password_hash(password))
