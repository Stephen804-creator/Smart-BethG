from tests.base import SmartBethGTestCase
from services.auth_service import (
    create_user,
    authenticate_user,
    get_user_by_id,
    find_or_create_oauth_user,
)


class TestAuthService(SmartBethGTestCase):
    def test_create_user_success(self):
        user = create_user("alice", "password123")
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "alice")

    def test_create_user_rejects_short_password(self):
        with self.assertRaises(ValueError):
            create_user("alice", "short")

    def test_create_user_rejects_blank_username(self):
        with self.assertRaises(ValueError):
            create_user("   ", "password123")

    def test_duplicate_username_returns_none(self):
        create_user("alice", "password123")
        result = create_user("alice", "differentpassword")
        self.assertIsNone(result)

    def test_authenticate_success(self):
        create_user("alice", "password123")
        user = authenticate_user("alice", "password123")
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "alice")

    def test_authenticate_wrong_password_fails(self):
        create_user("alice", "password123")
        self.assertIsNone(authenticate_user("alice", "wrongpassword"))

    def test_authenticate_unknown_user_fails(self):
        self.assertIsNone(authenticate_user("nobody", "password123"))

    def test_get_user_by_id_roundtrip(self):
        created = create_user("alice", "password123")
        fetched = get_user_by_id(created["id"])
        self.assertEqual(fetched["username"], "alice")

    def test_get_user_by_id_unknown_returns_none(self):
        self.assertIsNone(get_user_by_id(999999))

    def test_oauth_user_created_on_first_login(self):
        user = find_or_create_oauth_user("person@gmail.com", "google", "sub-1", allow_create=True)
        self.assertEqual(user["username"], "person@gmail.com")

    def test_oauth_user_is_stable_across_logins(self):
        first = find_or_create_oauth_user("person@gmail.com", "google", "sub-1")
        second = find_or_create_oauth_user("person@gmail.com", "google", "sub-1")
        self.assertEqual(first["id"], second["id"])

    def test_oauth_links_to_existing_password_account_by_email(self):
        pw_user = create_user("person@gmail.com", "password123")
        oauth_user = find_or_create_oauth_user("person@gmail.com", "google", "sub-2", allow_create=True)
        self.assertEqual(pw_user["id"], oauth_user["id"])
        # Password login must still work after linking.
        self.assertIsNotNone(authenticate_user("person@gmail.com", "password123"))

    def test_oauth_creation_is_blocked_when_registration_is_closed(self):
        with self.assertRaises(PermissionError):
            find_or_create_oauth_user("new-person@example.test", "google", "sub-closed")

    def test_oauth_missing_email_raises(self):
        with self.assertRaises(ValueError):
            find_or_create_oauth_user("", "google", "sub-3", allow_create=True)
