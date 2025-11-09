"""
Notification helpers and utilities.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

from ..models import Notification

logger = logging.getLogger(__name__)


def notify(user, message, level="info", notification_type="system"):
    """
    Create a notification for a user and optionally send email.
    
    Args:
        user: User instance to notify
        message: Notification message text
        level: Notification level (info, warning, error)
        notification_type: Type of notification (kept for backwards compatibility, not used in DB)
    
    Returns:
        Notification instance
    """
    # Map level string to Notification constants
    level_map = {
        "info": Notification.LEVEL_INFO,
        "warning": Notification.LEVEL_WARNING,
        "error": Notification.LEVEL_ERROR,
        "success": Notification.LEVEL_INFO,  # Map success to info
    }
    db_level = level_map.get(level, Notification.LEVEL_INFO)
    
    # Create database notification
    notification = Notification.objects.create(
        user=user,
        message=message,
        level=db_level,
    )
    
    # Send email if enabled
    if getattr(settings, "NOTIFICATIONS_SEND_EMAIL", True):
        try:
            subject = f"[{level.upper()}] Notification from WMS"
            
            # Prepare email content
            email_body = f"""
Hello {user.get_full_name() or user.username},

You have a new notification:

{message}

---
This is an automated message from the Warehouse Management System.
            """.strip()
            
            send_mail(
                subject=subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email] if user.email else [],
                fail_silently=True,
            )
            
            logger.info(f"Notification email sent to {user.username}: {message[:50]}...")
            
        except Exception as e:
            logger.error(f"Failed to send notification email: {e}")
    
    return notification


def notify_multiple(users, message, level="info", notification_type="system"):
    """
    Create notifications for multiple users.
    
    Args:
        users: QuerySet or list of User instances
        message: Notification message text
        level: Notification level
        notification_type: Type of notification
    
    Returns:
        List of Notification instances
    """
    notifications = []
    for user in users:
        notification = notify(user, message, level, notification_type)
        notifications.append(notification)
    
    return notifications


def mark_as_read(notification_id, user):
    """
    Mark a notification as read.
    
    Args:
        notification_id: ID of notification
        user: User instance (for permission check)
    
    Returns:
        Boolean indicating success
    """
    try:
        notification = Notification.objects.get(pk=notification_id, user=user)
        notification.is_read = True
        notification.save()
        return True
    except Notification.DoesNotExist:
        return False


def mark_all_as_read(user):
    """
    Mark all notifications for a user as read.
    
    Args:
        user: User instance
    
    Returns:
        Number of notifications marked as read
    """
    count = Notification.objects.filter(user=user, is_read=False).update(is_read=True)
    return count


def get_unread_count(user):
    """
    Get count of unread notifications for a user.
    
    Args:
        user: User instance
    
    Returns:
        Integer count
    """
    return Notification.objects.filter(user=user, is_read=False).count()


def get_recent_notifications(user, limit=10):
    """
    Get recent notifications for a user.
    
    Args:
        user: User instance
        limit: Maximum number of notifications to retrieve
    
    Returns:
        QuerySet of Notification instances
    """
    return Notification.objects.filter(user=user).order_by("-created_at")[:limit]
