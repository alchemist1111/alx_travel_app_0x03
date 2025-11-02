from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser
from .managers import UserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.core.exceptions import ValidationError

# User model
class User(AbstractUser):
    """Custom User model matching the SQL schema"""
    ROLE_CHOICES = [
        ("guest", "Guest"),
        ("host", "Host"),
        ("admin", "Admin"),
    ]
    user_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, db_index=True)
    username = None
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='guest')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Custom user manager
    objects = UserManager()
    
    # Use email as the unique identifier for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        """User table definition"""
        db_table = 'user'
        indexes = [
            models.Index(fields=['email'], name='idx_user_email'),
            models.Index(fields=['role'], name='idx_user_role')
        ]
    
    def __str__(self):
        return f'Name: {self.first_name} {self.last_name}, Email: {self.email}, and Role: {self.role}'
    
    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        """Return the user's first name."""
        return self.first_name    

# Listings model
class Listing(models.Model):
    """Property model matching the SQL schema"""
    property_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, db_index=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    name = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    pricepernight = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        """Listing table definition"""
        db_table = 'listing'
        indexes = [
            models.Index(fields=['property_id'], name='idx_listing_property_id'),
            models.Index(fields=['name'], name='idx_listing_name'),
            models.Index(fields=["host"], name="idx_listing_host"),
            models.Index(fields=['location'], name='idx_listing_location'),
            models.Index(fields=['pricepernight'], name='idx_listing_pricepernight')
        ]
    
    def __str__(self):
        return f'Property Name: {self.name}, Location: {self.location}, Price per Night: {self.pricepernight}'    

# Booking model
class Booking(models.Model):
    """Booking model matching the SQL schema"""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("canceled", "Canceled"),
    ]
    booking_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, db_index=True)
    property = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        """Booking table definition"""
        db_table = 'booking'
        indexes = [
            models.Index(fields=['booking_id'], name='idx_booking_booking_id'),
            models.Index(fields=['property'], name='idx_booking_property'),
            models.Index(fields=['user'], name='idx_booking_user')
        ]
    
    def clean(self):
        """Ensure start_date is before end_date."""
        if self.start_date >= self.end_date:
            raise  ValidationError("End date must be after start date.")
        
        overlapping_bookings = Booking.objects.filter(
            property=self.property,
            start_date__lt=self.end_date,
            end_date__gt=self.start_date
        )
        
        if overlapping_bookings.exists():
            raise ValidationError("This property is already booked for the selected dates.")
    
    
    @property
    def number_of_nights(self):
        """Calculating number of nights"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0    
    
    @property
    def total_price(self):
        """Calculating total price"""
        return self.number_of_nights * self.property.pricepernight   
    
    def __str__(self):
        return f'Booking by {self.user.get_full_name()} for {self.property.name} from {self.start_date} to {self.end_date} - Status: {self.status}'

# Review model
class Review(models.Model):
    """Review model matching the SQL schema"""
    review_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, db_index=True)
    property = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        """Review table definition"""
        db_table = 'review'
        indexes = [
            models.Index(fields=['review_id'], name='idx_review_review_id'),
            models.Index(fields=['property'], name='idx_review_property'),
            models.Index(fields=['user'], name='idx_review_user')
        ]
        unique_together = ('property', 'user')  # Ensure a user can only leave one review per property
        
    def __str__(self):
        return f'Review by {self.user.get_full_name()} for {self.property.name} - Rating: {self.rating}' 

# Payment model
class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    payment_id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, db_index=True)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    booking_reference = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, default='chapa')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Payment for {self.booking_reference} - Status: {self.status}"    
               
