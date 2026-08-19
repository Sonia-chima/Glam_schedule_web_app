from django.contrib import admin
from .models import Service, Client, Appointment

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_minutes']
    search_fields = ['name']

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'phone']
    search_fields = ['first_name', 'last_name', 'email']

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['client', 'service', 'date', 'time', 'status']
    list_filter = ['status', 'date']
    search_fields = ['client__first_name', 'client__last_name']