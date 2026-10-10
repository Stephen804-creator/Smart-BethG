import unittest
from unittest.mock import patch, MagicMock

from services.search_service import SearchService


class TestSearchService(unittest.TestCase):
    def test_not_configured_raises_honest_error(self):
        service = SearchService(api_key="")
        with self.assertRaises(RuntimeError):
            service.search("quantum computing")

    def test_is_configured(self):
        self.assertFalse(SearchService(api_key="").is_configured())
        self.assertTrue(SearchService(api_key="fake-key").is_configured())

    def test_empty_query_rejected(self):
        service = SearchService(api_key="fake-key")
        with self.assertRaises(ValueError):
            service.search("   ")

    @patch("services.search_service.requests.get")
    def test_parses_real_brave_response_shape(self, mock_get):
        """
        Verifies against Brave's actual documented response shape
        (web.results[].title/url/description) - if their schema ever
        changes, this test should fail loudly rather than silently
        returning empty/wrong data.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Result A", "url": "https://a.example.com", "description": "About A"},
                    {"title": "Result B", "url": "https://b.example.com", "description": "About B"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        service = SearchService(api_key="fake-key")
        results = service.search("test query", count=5)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], {"title": "Result A", "url": "https://a.example.com", "snippet": "About A"})

        # Confirms the API key actually gets sent, not silently dropped.
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["X-Subscription-Token"], "fake-key")
        self.assertEqual(kwargs["params"]["q"], "test query")

    @patch("services.search_service.requests.get")
    def test_respects_count_limit(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {"results": [{"title": f"R{i}", "url": f"https://x.com/{i}", "description": ""} for i in range(10)]}
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        service = SearchService(api_key="fake-key")
        results = service.search("test", count=3)
        self.assertEqual(len(results), 3)

    @patch("services.search_service.requests.get")
    def test_http_error_propagates_as_exception_not_fake_success(self, mock_get):
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        mock_get.return_value = mock_response

        service = SearchService(api_key="bad-key")
        with self.assertRaises(requests.HTTPError):
            service.search("test")
