import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from middlewares.security_enforcement import SecurityEnforcementMiddleware

class SecurityEnforcementMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=HttpResponse("OK"))
        self.middleware = SecurityEnforcementMiddleware(self.get_response)

    @patch('utils.json_request.log_request')
    def test_valid_json_request(self, mock_log):
        data = {"key": "value"}
        request = self.factory.post(
            '/api/test',
            data=json.dumps(data),
            content_type='application/json'
        )
        response = self.middleware(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
        self.assertEqual(request.json, data)
        mock_log.assert_not_called()

    @patch('utils.json_request.log_request')
    def test_invalid_content_type(self, mock_log):
        data = {"key": "value"}
        request = self.factory.post(
            '/api/test',
            data=json.dumps(data),
            content_type='text/plain'
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 415)
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        self.assertEqual(kwargs['reasons'], "INVALID_CONTENT_TYPE")

    @patch('utils.json_request.log_request')
    def test_dangerous_literal(self, mock_log):
        data = {"cmd": "rm -rf /"}
        request = self.factory.post(
            '/api/test',
            data=json.dumps(data),
            content_type='application/json'
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Dangerous content", response.content)
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        self.assertEqual(kwargs['reasons'], "DANGEROUS_LITERAL")

    @patch('utils.json_request.log_request')
    def test_inconsistent_type_numeric_string(self, mock_log):
        data = {"id": "12345"}
        request = self.factory.post(
            '/api/test',
            data=json.dumps(data),
            content_type='application/json'
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Inconsistent type", response.content)
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        self.assertIn("INCONSISTENT_TYPE", kwargs['reasons'])
        
    def test_excluded_path(self):
        # /admin/ is excluded by default in settings.py (mocked or loaded)
        # We need to ensure settings are loaded or mocked. 
        # Django tests usually load settings.
        
        request = self.factory.post(
            '/admin/login',
            data='form data',
            content_type='application/x-www-form-urlencoded'
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
