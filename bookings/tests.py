from django.test import TestCase, Client as TestClient
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Service, Client, Appointment
from datetime import date, time, timedelta


class GlamScheduleTests(TestCase):
    def setUp(self):
        self.client = TestClient()
        self.service = Service.objects.create(
            name='Bridal Glam',
            description='Full luxury bridal makeup experience.',
            duration_minutes=90,
            price=25000.00
        )
        self.staff_user = User.objects.create_user(
            username='admin_sonia',
            email='sonia@glam.com',
            password='password123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='client_jane',
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
            password='password123'
        )
        self.target_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
        self.target_time = '10:00'

    def test_signup_view(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'phone': '1234567890',
            'password': 'secretpassword',
            'confirm_password': 'secretpassword',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        self.assertTrue(Client.objects.filter(email='newuser@example.com').exists())

    def test_login_and_logout(self):
        # Login
        response = self.client.post(reverse('login'), {
            'username': 'client_jane',
            'password': 'password123'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

        # Logout
        response = self.client.get(reverse('logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_slot_availability_api(self):
        # Initial check: slot is available
        response = self.client.get(reverse('available_slots'), {
            'date': self.target_date,
            'service_id': self.service.id
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        slot_10 = next(s for s in data['slots'] if s['time'] == self.target_time)
        self.assertTrue(slot_10['available'])

        # Book the slot
        client_obj = Client.objects.create(
            first_name='Alice',
            last_name='Wonder',
            email='alice@example.com',
            phone='123456'
        )
        Appointment.objects.create(
            client=client_obj,
            service=self.service,
            date=self.target_date,
            time='10:00:00',
            status='pending'
        )

        # Re-check: slot is now booked
        response2 = self.client.get(reverse('available_slots'), {
            'date': self.target_date,
            'service_id': self.service.id
        })
        data2 = response2.json()
        slot_10_after = next(s for s in data2['slots'] if s['time'] == self.target_time)
        self.assertFalse(slot_10_after['available'])
        self.assertEqual(slot_10_after['status'], 'Booked')

    def test_double_booking_prevention(self):
        # First booking succeeds
        response1 = self.client.post(reverse('book_appointment', args=[self.service.id]), {
            'first_name': 'Client1',
            'last_name': 'One',
            'email': 'client1@example.com',
            'phone': '111222333',
            'date': self.target_date,
            'time': self.target_time,
            'notes': 'First booking'
        }, follow=True)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(Appointment.objects.filter(date=self.target_date, time='10:00:00').count(), 1)

        # Second booking at the EXACT SAME time and date should be REJECTED
        response2 = self.client.post(reverse('book_appointment', args=[self.service.id]), {
            'first_name': 'Client2',
            'last_name': 'Two',
            'email': 'client2@example.com',
            'phone': '999888777',
            'date': self.target_date,
            'time': self.target_time,
            'notes': 'Conflicting booking'
        }, follow=True)
        self.assertEqual(response2.status_code, 200)
        # Verify Appointment count is still 1
        self.assertEqual(Appointment.objects.filter(date=self.target_date, time='10:00:00').count(), 1)
        # Verify error message was delivered
        messages = list(response2.context['messages'])
        self.assertTrue(any('already booked' in str(m) for m in messages))

    def test_dashboard_access_and_filtering(self):
        # Anonymous user gets redirected to login
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

        # Create appointment for Jane
        client_jane = Client.objects.create(
            user=self.regular_user,
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
            phone='555555'
        )
        appt1 = Appointment.objects.create(
            client=client_jane,
            service=self.service,
            date=self.target_date,
            time='12:00:00',
            status='pending'
        )

        # Regular user logged in sees their appointment
        self.client.login(username='client_jane', password='password123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(appt1, response.context['appointments'])

        # Staff user logged in sees all appointments
        self.client.login(username='admin_sonia', password='password123')
        response_staff = self.client.get(reverse('dashboard'))
        self.assertEqual(response_staff.status_code, 200)
        self.assertIn(appt1, response_staff.context['appointments'])

    def test_staff_update_status(self):
        client_obj = Client.objects.create(
            first_name='Eva',
            last_name='Green',
            email='eva@example.com',
            phone='777888'
        )
        appt = Appointment.objects.create(
            client=client_obj,
            service=self.service,
            date=self.target_date,
            time='14:00:00',
            status='pending'
        )

        self.client.login(username='admin_sonia', password='password123')
        response = self.client.post(reverse('update_status', args=[appt.id]), {
            'status': 'confirmed'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'confirmed')
