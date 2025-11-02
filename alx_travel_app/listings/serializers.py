from rest_framework import serializers
from .models import Listing, Booking, Review, User, Payment

# User Serializer
class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    class Meta:
        model = User
        fields = ['user_id', 'first_name', 'last_name', 'email', 'phone_number', 'role', 'Password', 'created_at', 'updated_at']
        read_only_fields = ['user_id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}"
    
    # Field-level validation for email uniqueness
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already in use.")
        return value
    
    # Object-level validation for names
    def validate(self, data):
        if not data.get('first_name') or not data.get('last_name'):
            raise serializers.ValidationError("Both first name and last name are required.")
        return data
    
# Property Listing Serializer
class PropertyListingSerializer(serializers.ModelSerializer):
    """Serializer for Listing model"""
    host_name = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        """Property List serializer definition"""
        model = Listing
        fields = ['property_id', 
                  'host', 
                  'host_name', 
                  'name', 
                  'description', 
                  'location', 
                  'pricepernight', 
                  'average_rating', 
                  'review_count', 
                  'created_at', 
                  'updated_at'
        ]
    def get_host_name(self, obj):
        """Get host's name"""
        return obj.host.get_full_name()
    
    def get_average_rating(self, obj):
        """Calculate the average rating for a property"""
        reviews = obj.reviews.all()
        if reviews:
            return round(sum(r.rating for r in reviews) / len(reviews), 1)
        return None
    
    def get_review_count(self, obj):
        """Count total reviews"""
        return obj.reviews.count() 
    
# Property Detail Serializer
class PropertyDetailSerializer(serializers.ModelSerializer):
    """Serializer for Property detail view (complete data)"""
    host = UserSerializer(read_only=True)
    host_id = serializers.UUIDField(write_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    total_nights_booked = serializers.SerializerMethodField()
    
    class Meta:
        """Property Detail serializer definition"""
        model = Listing
        fields = [
            "property_id",
            "name",
            "description",
            "location",
            "pricepernight",
            "host",
            "host_id",
            "average_rating",
            "review_count",
            "total_nights_booked",
            "created_at",
            "updated_at",
        ] 
        read_only_fields = ["property_id", "created_at", "updated_at"]
    
    def average_rating(self):
        return PropertyListingSerializer.get_average_rating(self, self.instance)
    
    def review_count(self):
        return PropertyListingSerializer.get_review_count(self, self.instance)
    
    def get_total_nights_booked(self, obj):
        """Calculate total nights booked for the property"""
        bookings = obj.bookings.filter(status='confirmed')
        return sum(booking.number_of_nights for booking in bookings)
    
    def validate_host_id(self, value):
        """Validate host's id"""
        try:
            host = User.objects.get(user_id=value)
            if host.role not in ["host", "admin"]:
                raise serializers.ValidationError(
                    "User must be a host or admin to create properties."
                )
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Host not found.") from exc
        return value 


# Booking List Serializer
class BookingListSerializer(serializers.ModelSerializer):
    """Serializer for the booking model"""
    property_name = serializers.CharField(source="property.name", read_only=True)
    property_location = serializers.CharField(
        source="property.location", read_only=True
    )
    guest_name = serializers.CharField(source="user.get_full_name", read_only=True)
    total_nights = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    
    class Meta:
        """Booking serializer definition"""
        model = Booking
        fields = [
            "booking_id",
            "property_name",
            "property_location",
            "guest_name",
            "start_date",
            "end_date",
            "total_nights",
            "total_price",
            "status",
            "created_at",
        ]


# Booking Detail Serializer
class BookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for Booking detail view and creation"""
    property_id = serializers.UUIDField(write_only=True)
    property = PropertyListingSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)
    user = UserSerializer(read_only=True)
    total_nights = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()     
    
    class Meta:
        """Booking Detail serializer definition"""
        model = Booking
        fields = [
            "booking_id",
            "property",
            "property_id",
            "user",
            "user_id",
            "start_date",
            "end_date",
            "total_nights",
            "total_price",
            "status",
            "created_at",
        ] 
        read_only_fields = ["booking_id", "created_at"]   
    
    
    def validate(self, attrs):
        """Object-level validation for booking dates and availability"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        property_id = attrs.get("property_id")
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError('End date must be after start date.') 
            
            # Check for overlapping bookings if property is provided
            if property_id:
                overlapping_bookings = Booking.objects.filter(
                    property_id=property_id,
                    start_date__lt=end_date,
                    end_date__gt=start_date,
                    status='confirmed'
                )  
                
                # Exclude current booking if updating
                if self.instance:
                    overlapping_bookings = overlapping_bookings.exclude(booking_id=self.instance.booking_id)
                
                if overlapping_bookings.exists():
                    raise serializers.ValidationError('This property is already booked for the selected dates.')
                
        return attrs 


# Review Serializer
class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model"""
    property_name = serializers.CharField(source="property.name", read_only=True)
    reviewer_name = serializers.CharField(source="user.get_full_name", read_only=True)
    property_id = serializers.UUIDField(write_only=True)
    user_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Review
        fields = [
            "review_id",
            "property_name",
            "reviewer_name",
            "property_id",
            "user_id",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["review_id", "created_at"]   


# Serializer for payments
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'                                        