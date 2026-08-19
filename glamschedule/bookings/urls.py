from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('book/<int:service_id>/', views.book_appointment, name='book_appointment'),
    path('api/available-slots/', views.available_slots, name='available_slots'),
    path('confirmation/', views.confirmation, name='confirmation'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update-status/<int:appointment_id>/', views.update_status, name='update_status'),
    path('delete/<int:appointment_id>/', views.delete_appointment, name='delete_appointment'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('contact/', views.contact, name='contact'),
]