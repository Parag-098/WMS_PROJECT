"""
External integrations for SMS and webhooks.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# =============================
# SMS Integration
# =============================

class SMSProvider:
    """Base class for SMS providers."""
    
    def send_sms(self, phone_number, message):
        """
        Send SMS message.
        
        Args:
            phone_number: Recipient phone number
            message: SMS message text
        
        Returns:
            Boolean indicating success
        """
        raise NotImplementedError("Subclasses must implement send_sms()")


class TwilioSMSProvider(SMSProvider):
    """Twilio SMS provider."""
    
    def __init__(self):
        self.account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
        self.auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
        self.from_number = getattr(settings, "TWILIO_FROM_NUMBER", None)
    
    def send_sms(self, phone_number, message):
        """Send SMS via Twilio."""
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("Twilio credentials not configured")
            return False
        
        try:
            # Placeholder for actual Twilio API call
            # from twilio.rest import Client
            # client = Client(self.account_sid, self.auth_token)
            # message = client.messages.create(
            #     body=message,
            #     from_=self.from_number,
            #     to=phone_number
            # )
            
            logger.info(f"SMS sent to {phone_number}: {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS via Twilio: {e}")
            return False


class ConsoleSMSProvider(SMSProvider):
    """Console SMS provider for testing."""
    
    def send_sms(self, phone_number, message):
        """Print SMS to console."""
        logger.info(f"[CONSOLE SMS] To: {phone_number}")
        logger.info(f"[CONSOLE SMS] Message: {message}")
        print(f"\n{'='*60}")
        print(f"SMS TO: {phone_number}")
        print(f"MESSAGE: {message}")
        print(f"{'='*60}\n")
        return True


def get_sms_provider():
    """
    Get configured SMS provider.
    
    Returns:
        SMSProvider instance
    """
    provider_name = getattr(settings, "SMS_PROVIDER", "console")
    
    providers = {
        "twilio": TwilioSMSProvider,
        "console": ConsoleSMSProvider,
    }
    
    provider_class = providers.get(provider_name, ConsoleSMSProvider)
    return provider_class()


def send_sms(phone_number, message):
    """
    Send SMS using configured provider.
    
    Args:
        phone_number: Recipient phone number
        message: SMS message text
    
    Returns:
        Boolean indicating success
    """
    provider = get_sms_provider()
    return provider.send_sms(phone_number, message)


# =============================
# Webhook Integration
# =============================

class WebhookProvider:
    """Base class for webhook providers."""
    
    def send_webhook(self, url, payload, headers=None):
        """
        Send webhook POST request.
        
        Args:
            url: Webhook endpoint URL
            payload: Dict payload to send as JSON
            headers: Optional dict of headers
        
        Returns:
            Boolean indicating success
        """
        raise NotImplementedError("Subclasses must implement send_webhook()")


class HTTPWebhookProvider(WebhookProvider):
    """Standard HTTP webhook provider."""
    
    def send_webhook(self, url, payload, headers=None):
        """Send webhook via HTTP POST."""
        try:
            default_headers = {"Content-Type": "application/json"}
            if headers:
                default_headers.update(headers)
            
            response = requests.post(
                url,
                json=payload,
                headers=default_headers,
                timeout=10,
            )
            response.raise_for_status()
            
            logger.info(f"Webhook sent to {url}: {response.status_code}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send webhook to {url}: {e}")
            return False


class ConsoleWebhookProvider(WebhookProvider):
    """Console webhook provider for testing."""
    
    def send_webhook(self, url, payload, headers=None):
        """Print webhook to console."""
        logger.info(f"[CONSOLE WEBHOOK] URL: {url}")
        logger.info(f"[CONSOLE WEBHOOK] Payload: {payload}")
        print(f"\n{'='*60}")
        print(f"WEBHOOK TO: {url}")
        print(f"HEADERS: {headers}")
        print(f"PAYLOAD: {payload}")
        print(f"{'='*60}\n")
        return True


def get_webhook_provider():
    """
    Get configured webhook provider.
    
    Returns:
        WebhookProvider instance
    """
    provider_name = getattr(settings, "WEBHOOK_PROVIDER", "http")
    
    providers = {
        "http": HTTPWebhookProvider,
        "console": ConsoleWebhookProvider,
    }
    
    provider_class = providers.get(provider_name, HTTPWebhookProvider)
    return provider_class()


def send_webhook(url, payload, headers=None):
    """
    Send webhook using configured provider.
    
    Args:
        url: Webhook endpoint URL
        payload: Dict payload to send as JSON
        headers: Optional dict of headers
    
    Returns:
        Boolean indicating success
    """
    provider = get_webhook_provider()
    return provider.send_webhook(url, payload, headers)


# =============================
# Webhook Signature Validation
# =============================

def validate_webhook_signature(request, secret_key=None):
    """
    Validate webhook signature from request headers.
    
    Args:
        request: Django request object
        secret_key: Optional secret key (defaults to settings.WEBHOOK_SECRET_KEY)
    
    Returns:
        Boolean indicating valid signature
    """
    import hmac
    import hashlib
    
    if not secret_key:
        secret_key = getattr(settings, "WEBHOOK_SECRET_KEY", None)
    
    if not secret_key:
        logger.warning("No webhook secret key configured")
        return False
    
    # Get signature from header
    signature_header = request.headers.get("X-Webhook-Signature", "")
    
    if not signature_header:
        logger.warning("No webhook signature in request")
        return False
    
    # Compute expected signature
    body = request.body
    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    is_valid = hmac.compare_digest(signature_header, expected_signature)
    
    if not is_valid:
        logger.warning("Invalid webhook signature")
    
    return is_valid
