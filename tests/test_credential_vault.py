import json
import unittest
from cryptography.fernet import Fernet

from database import get_connection
from services.credential_vault import CredentialVault, CredentialVaultError
from tests.base import SmartBethGTestCase


class TestCredentialVault(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.key = Fernet.generate_key()
        self.vault = CredentialVault(key=self.key)

    def test_token_is_encrypted_and_owner_scoped(self):
        reference = self.vault.store(101, "meta", "page-token-secret", scopes=["pages_manage_posts"])
        credential_id = reference.split(":", 1)[1]
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT encrypted_access_token, scopes_json FROM connector_credentials WHERE id=?",
                (credential_id,),
            ).fetchone()
            self.assertNotEqual(row["encrypted_access_token"], "page-token-secret")
            self.assertNotIn("page-token-secret", row["encrypted_access_token"])
            self.assertEqual(json.loads(row["scopes_json"]), ["pages_manage_posts"])
        finally:
            conn.close()
        self.assertEqual(self.vault.resolve(reference, 101, "meta"), "page-token-secret")
        with self.assertRaises(CredentialVaultError):
            self.vault.resolve(reference, 202, "meta")
        with self.assertRaises(CredentialVaultError):
            self.vault.resolve(reference, 101, "github")

    def test_revoked_token_cannot_be_resolved(self):
        reference = self.vault.store(101, "meta", "another-secret")
        self.assertTrue(self.vault.revoke(reference, 101, "meta"))
        self.assertFalse(self.vault.revoke(reference, 101, "meta"))
        with self.assertRaises(CredentialVaultError):
            self.vault.resolve(reference, 101, "meta")

    def test_missing_or_invalid_encryption_key_fails_closed(self):
        with self.assertRaises(CredentialVaultError):
            CredentialVault(key="")
        with self.assertRaises(CredentialVaultError):
            CredentialVault(key="not-a-fernet-key")


if __name__ == "__main__":
    unittest.main()
