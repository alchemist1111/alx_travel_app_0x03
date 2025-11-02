from rest_framework import viewsets, status
from rest_framework import permissions
from .models import Listing, Booking, Payment
from .serializers import BookingListSerializer, PropertyListingSerializer, PaymentSerializer
import requests
from django.conf import settings
from rest_framework.response import Response
from rest_framework.decorators import action
from .tasks import send_booking_confirmation_email

# Create your views here.
class ListingViewSet(viewsets.ModelViewSet):
    """
    CRUD for Listings
    GET /api/listings/
    POST /api/listings/
    GET /api/listings/{id}/
    PUT/PATCH /api/listings/{id}/
    DELETE /api/listings/{id}/
    """
    queryset = Listing.objects.all().order_by("-id")
    serializer_class = PropertyListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def perform_create(self, serializer):
        # If Listings are owned, wire this up (safe if there's no owner field)
        serializer.save(owner=getattr(self.request, "user", None))
        
class BookingViewSet(viewsets.ModelViewSet):
    """
    CRUD for Bookings
    GET /api/bookings/
    POST /api/bookings/
    GET /api/bookings/{id}/
    PUT/PATCH /api/bookings/{id}/
    DELETE /api/bookings/{id}/
    """
    queryset = Booking.objects.all().order_by("-id")
    serializer_class = BookingListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def perform_create(self, serializer):
        # Save the booking and automatically associate the user
        booking = serializer.save(user=self.request.user)
        
        # Trigger the background task for sending the confirmation email
        send_booking_confirmation_email.delay(booking.id)
        
        return booking 
        

# Payment viewset
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='initiate')
    def initiate_payment(self, request):
        """Initiate payment with Chapa"""
        booking_id = request.data.get('booking_id')
        
        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND) 
        
        # Create payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            booking_reference=f'BK-{booking.booking_id}' 
        )   
        
        # Prepare chapa payment request
        chapa_url = "https://api.chapa.co/v1/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.env('CHAPA_SECRET_KEY')}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": str(booking.total_price),
            "currency": "ETB",
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "tx_ref": payment.reference,
            "callback_url": request.build_absolute_uri('/api/payments/verify/'),
            "return_url": request.data.get('return_url', 'http://localhost:3000/payment/success'),
            "customization": {
                "title": f"Payment for {booking.listing.title}",
                "description": f"Booking from {booking.check_in_date} to {booking.check_out_date}"
            }
        }
        
        try:
            response = requests.post(chapa_url, json=payload, headers=headers)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('status') == 'success':
                payment.transaction_id = response_data['data']['tx_ref']
                payment.save()
                
                return Response({
                    'payment_url': response_data['data']['checkout_url'],
                    'reference': payment.reference,
                    'status': 'success'
                }, status=status.HTTP_200_OK)
            
            else:
                payment.status = 'failed'
                payment.save()
                
                return Response({
                    'error': response_data.get('message', 'Payment initiation failed')
                }, status=status.HTTP_400_BAD_REQUEST)  
        
        except requests.exceptions.RequestException as e:
            payment.status = 'failed'
            payment.save()
            
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
    @action(detail=False, methods=['get'], url_path='verify')
    def verify_payment(self, request):
        """Verify payment status with Chapa"""
        tx_ref = request.query_params.get('tx_ref')
        
        if not tx_ref:
            return Response({'error': 'Transaction reference is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        
        try:
            payment = Payment.objects.get(booking_reference=tx_ref)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        # Verify with Chapa
        chapa_url = f"https://api.chapa.co/v1/transaction/verify/{tx_ref}"
        headers = {
            "Authorization": f"Bearer {settings.env('CHAPA_SECRET_KEY')}"
        }

        try:
            response = requests.get(chapa_url, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 'success':
                chapa_status = response_data['data']['status']

                if chapa_status == 'success':
                    payment.status = 'completed'
                    payment.booking.status = 'confirmed'
                    payment.booking.save()
                else:
                    payment.status = 'failed'

                payment.save()

                return Response({
                    'reference': payment.booking_reference,
                    'status': payment.status,
                    'amount': str(payment.amount)
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Verification failed'}, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)              
               
