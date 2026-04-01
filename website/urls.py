from django.urls import path

from . import views
from .chatbot_views import chatbot_api, chatbot_health

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('products/', views.products, name='products'),
    path('contact/', views.contact, name='contact'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('subscribe/', views.subscribe, name='subscribe'),
    
    # Chatbot API endpoints
    path('api/chatbot/', chatbot_api, name='chatbot_api'),
    path('api/chatbot/health/', chatbot_health, name='chatbot_health'),
]
