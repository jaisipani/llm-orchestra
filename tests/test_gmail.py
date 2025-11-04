"""Tests for Gmail service."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.services.gmail_service import GmailService


class TestGmailService:
    """Test cases for GmailService."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Create mock Google credentials."""
        return Mock()
    
    @pytest.fixture
    def gmail_service(self, mock_credentials):
        """Create GmailService with mocked API."""
        with patch('src.services.gmail_service.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            service = GmailService(mock_credentials)
            service.service = mock_service
            return service
    
    def test_send_email_success(self, gmail_service):
        """Test sending an email successfully."""
        # Mock API response
        gmail_service.service.users().messages().send().execute.return_value = {
            'id': 'msg_123',
            'threadId': 'thread_456'
        }
        
        result = gmail_service.send_email(
            to="test@example.com",
            subject="Test",
            body="Test body"
        )
        
        assert result['id'] == 'msg_123'
        assert result['threadId'] == 'thread_456'
    
    def test_send_email_multiple_recipients(self, gmail_service):
        """Test sending email to multiple recipients."""
        gmail_service.service.users().messages().send().execute.return_value = {
            'id': 'msg_123'
        }
        
        result = gmail_service.send_email(
            to=["test1@example.com", "test2@example.com"],
            subject="Test",
            body="Test body"
        )
        
        assert result['id'] == 'msg_123'
    
    def test_search_emails(self, gmail_service):
        """Test searching for emails."""
        # Mock search results
        gmail_service.service.users().messages().list().execute.return_value = {
            'messages': [
                {'id': 'msg_1'},
                {'id': 'msg_2'}
            ]
        }
        
        # Mock getting individual messages
        gmail_service.service.users().messages().get().execute.return_value = {
            'id': 'msg_1',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject'},
                    {'name': 'From', 'value': 'test@example.com'}
                ]
            }
        }
        
        results = gmail_service.search_emails("test query")
        
        assert len(results) == 2
    
    def test_delete_email(self, gmail_service):
        """Test deleting an email."""
        gmail_service.service.users().messages().trash().execute.return_value = {}
        
        result = gmail_service.delete_email('msg_123')
        
        assert result is True
    
    def test_get_profile(self, gmail_service):
        """Test getting user profile."""
        gmail_service.service.users().getProfile().execute.return_value = {
            'emailAddress': 'user@example.com',
            'messagesTotal': 100
        }
        
        profile = gmail_service.get_profile()
        
        assert profile['emailAddress'] == 'user@example.com'
        assert profile['messagesTotal'] == 100
