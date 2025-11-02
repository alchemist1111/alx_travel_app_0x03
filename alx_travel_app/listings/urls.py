from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ListingViewSet, BookingViewSet, PaymentViewSet

routers = DefaultRouter()

routers.register(r'listings', ListingViewSet, basename='listing')
routers.register(r'bookings', BookingViewSet, basename='booking')
routers.register(r'payments', PaymentViewSet, basename='payment')


urlpatterns = [
    path('', include(routers.urls)),
]