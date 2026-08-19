from django.shortcuts import render, redirect, get_object_or_404
from .models import Service, Appointment, Client
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from datetime import datetime, date as date_obj, time as time_obj


# Available operating slots for Glam Studio
OPERATING_SLOTS = [
    ('09:00', '09:00 AM'),
    ('10:00', '10:00 AM'),
    ('11:00', '11:00 AM'),
    ('12:00', '12:00 PM'),
    ('13:00', '01:00 PM'),
    ('14:00', '02:00 PM'),
    ('15:00', '03:00 PM'),
    ('16:00', '04:00 PM'),
    ('17:00', '05:00 PM'),
    ('18:00', '06:00 PM'),
]


# Home page - shows all services
def home(request):
    services = Service.objects.all()
    return render(request, 'bookings/home.html', {'services': services})


# API: Get booked & available slots for a given date
def available_slots(request):
    date_str = request.GET.get('date')
    service_id = request.GET.get('service_id')

    if not date_str:
        return JsonResponse({'error': 'Date parameter is required.'}, status=400)

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

    today = date_obj.today()
    is_past = selected_date < today

    # Query active appointments on selected date
    # Appointments with status pending or confirmed occupy the slot
    active_appts = Appointment.objects.filter(
        date=selected_date,
        status__in=['pending', 'confirmed']
    )

    booked_times = set()
    for appt in active_appts:
        booked_times.add(appt.time.strftime('%H:%M'))

    slots_data = []
    for slot_time, slot_label in OPERATING_SLOTS:
        is_booked = is_past or (slot_time in booked_times)
        slots_data.append({
            'time': slot_time,
            'label': slot_label,
            'available': not is_booked,
            'status': 'Past' if is_past else ('Booked' if is_booked else 'Available')
        })

    return JsonResponse({
        'date': date_str,
        'slots': slots_data,
        'is_past': is_past
    })


# Booking page - client fills a form to book an appointment
def book_appointment(request, service_id):
    service = get_object_or_404(Service, id=service_id)

    # Initial data prefill if user is logged in
    initial_client = None
    if request.user.is_authenticated:
        initial_client = getattr(request.user, 'client_profile', None)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        date_str = request.POST.get('date', '').strip()
        time_str = request.POST.get('time', '').strip()
        notes = request.POST.get('notes', '').strip()

        # Validate required fields
        if not all([first_name, last_name, email, phone, date_str, time_str]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'bookings/book_appointment.html', {
                'service': service,
                'operating_slots': OPERATING_SLOTS,
                'form_data': request.POST,
                'today_date': date_obj.today().strftime('%Y-%m-%d')
            })

        # Validate date
        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return render(request, 'bookings/book_appointment.html', {
                'service': service,
                'operating_slots': OPERATING_SLOTS,
                'form_data': request.POST,
                'today_date': date_obj.today().strftime('%Y-%m-%d')
            })

        if booking_date < date_obj.today():
            messages.error(request, 'You cannot book an appointment for a past date.')
            return render(request, 'bookings/book_appointment.html', {
                'service': service,
                'operating_slots': OPERATING_SLOTS,
                'form_data': request.POST,
                'today_date': date_obj.today().strftime('%Y-%m-%d')
            })

        # Validate time format
        try:
            if len(time_str) == 5:
                booking_time = datetime.strptime(time_str, '%H:%M').time()
            else:
                booking_time = datetime.strptime(time_str, '%H:%M:%S').time()
        except ValueError:
            messages.error(request, 'Invalid time selected.')
            return render(request, 'bookings/book_appointment.html', {
                'service': service,
                'operating_slots': OPERATING_SLOTS,
                'form_data': request.POST,
                'today_date': date_obj.today().strftime('%Y-%m-%d')
            })

        # Check for slot collision / double booking prevention
        # An appointment cannot be booked if another active (pending or confirmed) appointment exists at that date & time
        conflict_exists = Appointment.objects.filter(
            date=booking_date,
            time=booking_time,
            status__in=['pending', 'confirmed']
        ).exists()

        if conflict_exists:
            formatted_time = booking_time.strftime('%I:%M %p')
            messages.error(
                request,
                f"Sorry, the time slot at {formatted_time} on {booking_date.strftime('%B %d, %Y')} is already booked. Please choose an available time slot."
            )
            return render(request, 'bookings/book_appointment.html', {
                'service': service,
                'operating_slots': OPERATING_SLOTS,
                'form_data': request.POST,
                'today_date': date_obj.today().strftime('%Y-%m-%d')
            })

        # Get or create the client
        client, created = Client.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone
            }
        )

        # Update client info if updated
        client.first_name = first_name
        client.last_name = last_name
        client.phone = phone
        if request.user.is_authenticated and not client.user:
            client.user = request.user
        client.save()

        # Create the appointment
        Appointment.objects.create(
            client=client,
            service=service,
            date=booking_date,
            time=booking_time,
            notes=notes,
            status='pending'
        )

        messages.success(request, f'Appointment booked successfully for {service.name}!')
        return redirect('confirmation')

    context = {
        'service': service,
        'operating_slots': OPERATING_SLOTS,
        'today_date': date_obj.today().strftime('%Y-%m-%d'),
        'initial_client': initial_client
    }
    return render(request, 'bookings/book_appointment.html', context)


# Confirmation page
def confirmation(request):
    return render(request, 'bookings/confirmation.html')


# Dashboard - shows appointments (all for staff, client-specific for regular users)
@login_required(login_url='login')
def dashboard(request):
    is_staff_user = request.user.is_staff or request.user.is_superuser

    if is_staff_user:
        # Staff can see all appointments
        status_filter = request.GET.get('status', '').strip()
        search_query = request.GET.get('q', '').strip()

        appointments = Appointment.objects.select_related('client', 'service').all()

        if status_filter in ['pending', 'confirmed', 'cancelled', 'completed']:
            appointments = appointments.filter(status=status_filter)

        if search_query:
            appointments = appointments.filter(
                Q(client__first_name__icontains=search_query) |
                Q(client__last_name__icontains=search_query) |
                Q(client__email__icontains=search_query) |
                Q(service__name__icontains=search_query)
            )
    else:
        # Regular client sees their own appointments
        appointments = Appointment.objects.select_related('client', 'service').filter(
            Q(client__user=request.user) | Q(client__email=request.user.email)
        )
        status_filter = ''
        search_query = ''

    return render(request, 'bookings/dashboard.html', {
        'appointments': appointments,
        'is_staff': is_staff_user,
        'current_status': status_filter,
        'search_query': search_query,
    })


# Update appointment status (for staff)
@login_required(login_url='login')
def update_status(request, appointment_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'You do not have permission to update appointment status.')
        return redirect('dashboard')

    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, id=appointment_id)
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in Appointment.STATUS_CHOICES]

        if new_status in valid_statuses:
            appointment.status = new_status
            appointment.save()
            messages.success(request, f'Appointment status updated to {appointment.get_status_display()}.')
        else:
            messages.error(request, 'Invalid status selected.')

    return redirect('dashboard')


# Delete or Cancel appointment
@login_required(login_url='login')
def delete_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    is_staff_user = request.user.is_staff or request.user.is_superuser
    is_owner = (
        (appointment.client.user == request.user) or
        (appointment.client.email == request.user.email)
    )

    if not (is_staff_user or is_owner):
        messages.error(request, 'You do not have permission to delete this appointment.')
        return redirect('dashboard')

    if request.method == 'POST':
        appointment.delete()
        messages.success(request, 'Appointment deleted successfully!')

    return redirect('dashboard')


# User Signup
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        next_url = request.POST.get('next', '')

        # Validations
        if not all([username, first_name, last_name, email, password, confirm_password]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'bookings/signup.html', {'form_data': request.POST, 'next': next_url})

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'bookings/signup.html', {'form_data': request.POST, 'next': next_url})

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
            return render(request, 'bookings/signup.html', {'form_data': request.POST, 'next': next_url})

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username is already taken. Please choose another.')
            return render(request, 'bookings/signup.html', {'form_data': request.POST, 'next': next_url})

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists. Please log in.')
            return redirect('login')

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Create or update Client profile
        client, created = Client.objects.get_or_create(
            email=email,
            defaults={
                'user': user,
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone
            }
        )
        if not created:
            client.user = user
            client.first_name = first_name
            client.last_name = last_name
            if phone:
                client.phone = phone
            client.save()

        login(request, user)
        messages.success(request, f'Welcome to Allure Glam Studio, {first_name}! Your account is ready.')

        if next_url and next_url != 'None':
            return redirect(next_url)
        return redirect('dashboard')

    return render(request, 'bookings/signup.html', {'next': next_url})


# User Login
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        login_input = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next', '')

        if not login_input or not password:
            messages.error(request, 'Please enter your username/email and password.')
            return render(request, 'bookings/login.html', {'next': next_url})

        # Allow login by email or username
        username_to_auth = login_input
        if '@' in login_input:
            try:
                user_obj = User.objects.get(email__iexact=login_input)
                username_to_auth = user_obj.username
            except User.DoesNotExist:
                user_obj = None

        user = authenticate(request, username=username_to_auth, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            if next_url and next_url != 'None':
                return redirect(next_url)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username/email or password.')
            return render(request, 'bookings/login.html', {'next': next_url, 'username_input': login_input})

    return render(request, 'bookings/login.html', {'next': next_url})


# User Logout
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('home')


# Contact page
def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()

        # Send email to business owner
        try:
            send_mail(
                subject=f'New Message from {name} — Allure Glam Studio',
                message=f'Name: {name}\nEmail: {email}\n\nMessage:\n{message}',
                from_email=settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') and settings.EMAIL_HOST_USER else 'noreply@glamschedule.com',
                recipient_list=['soniampamah@gmail.com'],
                fail_silently=True
            )
        except Exception:
            pass

        messages.success(request, f"Thank you {name}! We'll get back to you shortly.")
        return redirect('contact')

    return render(request, 'bookings/contact.html')