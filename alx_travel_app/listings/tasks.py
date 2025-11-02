from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils.timezone import now
from .models import Booking

@shared_task
def send_booking_confirmation_email(booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        subject = f"Booking Confirmation for {booking.user.username}"
        message = f"Dear {booking.user.username},\n\nYour booking has been confirmed. Details:\n\nBooking ID: {booking.id}\nBooking Date: {booking.date}\n\nThank you for using our service."
        from_email = settings.DEFAULT_FROM_EMAIL

        # Send email asynchronously using the Django email backend
        send_mail(subject, message, from_email, [booking.user.email])
        
        return f"Confirmation email sent to {booking.user.email}"
    
    except Booking.DoesNotExist:
        return "Booking not found!"
