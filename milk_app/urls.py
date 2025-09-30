from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name = 'home'),
    path('customers/', views.CustomerListView.as_view(), name = 'customers'),
    path('new_customer/', views.CustomerCreateView.as_view(), name = 'new_customer'),
    path('customer/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='update_customer'),
    path('customer/<int:pk>/delete/', views.delete_customer, name='delete_customer'),
    path('customer/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    
    # Milk Entry URLs
    path('entries/', views.MilkEntryListView.as_view(), name = 'entries'),
    path('new_entry/', views.MilkEntryCreateView.as_view(), name = 'new_entry'),
    path('entry/<int:pk>/edit/', views.MilkEntryUpdateView.as_view(), name='update_entry'),
    path('entry/<int:pk>/', views.MilkEntryDetailView.as_view(), name='entry_detail'),
    path('entry/<int:pk>/delete/', views.delete_entry, name='delete_entry'),
    
    # Payment Summary (NEW)
    path('payment-summary/', views.payment_summary, name='payment_summary'),
]
