import os
import re
from datetime import datetime, timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend

  # Import your new models
from .models import (
      User, UserRole, PatientProfile, DoctorProfile, Department,
      Appointment, AIChatSession, AIChatMessage, TriageCase, Invoice, AuditLog
  )
from .serializers import (
      UserSerializer, UserRegistrationSerializer, PatientProfileSerializer,
      DoctorProfileSerializer, DepartmentSerializer, AppointmentSerializer,
      AIChatSessionSerializer, AIChatMessageSerializer, TriageCaseSerializer,
      InvoiceSerializer, AuditLogSerializer,
      AppointmentCreateSerializer, TriageCaseCreateSerializer, AIChatSessionCreateSerializer
  )
from .permissions import (
      IsClinicStaff, IsPatientOwner, IsDoctorOwner,
      IsReceptionistOrAbove, CanCreateInvoice, user_role
  )

  # Emergency keywords (keep your existing logic but make it more robust)
EMERGENCY_KEYWORDS = [
      'chest pain', 'trouble breathing', 'shortness of breath', 'severe bleeding',
      'unconscious', 'fainting', 'stroke', 'seizure', 'severe allergic reaction',
      'difficulty breathing', 'serious injury', 'heart attack', 'cardiac arrest',
      'severe trauma', 'unresponsive', 'not breathing', 'choking', 'overdose'
  ]

BOOKING_KEYWORDS = ['appointment', 'consultation', 'book', 'schedule', 'see a doctor', 'doctor', 'clinic']
RECEPTION_KEYWORDS = ['billing', 'payment', 'reception', 'hospital', 'admin', 'registration', 'insurance', 'bill', 'invoice']


def _triage_response(message):
      """Enhanced triage response with better keyword matching and context awareness"""
      if not message or not isinstance(message, str):
          return {
              'urgency': 'low',
              'route': 'Reception help desk',
              'recommendation': 'Please provide more details about your concern.',
              'summary': 'Empty or invalid message received.'
          }

      lower_message = message.lower().strip()

      # Emergency check (highest priority)
      if any(keyword in lower_message for keyword in EMERGENCY_KEYWORDS):
          return {
              'urgency': 'emergency',
              'route': 'Emergency Department - Seek immediate care',
              'recommendation': 'Please seek immediate medical attention or call emergency services now.',
              'summary': 'Emergency symptoms detected. Immediate medical attention recommended.'
          }

      # Booking intent
      if any(keyword in lower_message for keyword in BOOKING_KEYWORDS):
          return {
              'urgency': 'medium',
              'route': 'Doctor appointment booking',
              'recommendation': 'I can help you schedule a consultation with the appropriate doctor.',
              'summary': 'Appointment request identified. A doctor consultation is recommended.'
          }

      # Reception/Admin inquiries
      if any(keyword in lower_message for keyword in RECEPTION_KEYWORDS):
          return {
              'urgency': 'low',
              'route': 'Reception desk',
              'recommendation': 'A reception staff member can help with registration, billing, and general inquiries.',
              'summary': 'Administrative inquiry identified.'
          }

      # Symptom-based checks (more comprehensive)
      symptom_patterns = {
          'high': [
              r'\b(severe|intense|excruciating)\s+(pain|headache|stomach|chest)\b',
              r'\b(vomiting|diarrhea)\s+(continuously|for\s+hours)\b',
              r'\b(high\s+fever|temperature\s+over\s+102|39\+\s*c)\b',
              r'\b(confusion|disorientation|slurred\s+speech)\b',
              r'\b(numbness|weakness)\s+(face|arm|leg|one\s+side)\b'
          ],
          'medium': [
              r'\b(fever|headache|cough|cold|body\s+pain|pain|nausea|sore\s+throat|rash|dizziness)\b',
              r'\b(stomach|abdominal|belly)\s+pain\b',
              r'\b(back\s+pain|neck\s+pain|joint\s+pain)\b',
              r'\b(anxiety|stress|depression|sleep|insomnia)\b'
          ],
          'low': [
              r'\b(question|info|information|help|advice|general)\b',
              r'\b(vaccine|vaccination|checkup|physical|routine)\b'
          ]
      }

      # Check patterns in order of severity
      for urgency_level, patterns in [('high', symptom_patterns['high']),
                                     ('medium', symptom_patterns['medium']),
                                     ('low', symptom_patterns['low'])]:
          for pattern in patterns:
              if re.search(pattern, lower_message):
                  route_map = {
                      'high': 'Urgent doctor consultation recommended',
                      'medium': 'Doctor appointment booking suggested',
                      'low': 'Reception help desk or self-care advice'
                  }
                  rec_map = {
                      'high': 'Please consider seeking medical attention soon for these symptoms.',
                      'medium': 'You should book a consultation to discuss symptoms with a doctor.',
                      'low': 'I can guide you to appropriate resources or suggest monitoring symptoms.'
                  }
                  return {
                      'urgency': urgency_level,
                      'route': route_map[urgency_level],
                      'recommendation': rec_map[urgency_level],
                      'summary': f'{urgency_level.capitalize()} priority symptoms detected.'
                  }

      # Default response
      return {
          'urgency': 'low',
          'route': 'Reception help desk',
          'recommendation': 'I can guide you to the appropriate staff member for your question.',
          'summary': 'General patient inquiry received.'
      }


def _build_ai_summary(symptoms, context='', route='Doctor appointment booking'):
      """Build a structured summary for AI triage"""
      cleaned_symptoms = (symptoms or '').strip()
      cleaned_context = (context or '').strip()
      cleaned_route = (route or '').strip() or 'Doctor appointment booking'

      summary_parts = []

      if cleaned_symptoms:
          summary_parts.append(f"Symptoms reported: {cleaned_symptoms}.")
      else:
          summary_parts.append('Symptoms reported: not specified.')

      if cleaned_context:
          summary_parts.append(f"Context/Patient notes: {cleaned_context}.")

      summary_parts.append(f"Suggested next step based on triage: {cleaned_route}.")

      summary = ' '.join(summary_parts)
      return {
          'summary': summary,
          'route': cleaned_route,
          'recommendation': 'Summary prepared for healthcare professional review. This is not medical advice.',
      }


  # =============================================================================
  # AUTHENTICATION VIEWS
  # =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
      return Response({'status': 'ok', 'message': 'Patient Management System API is running'})


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
      """
      Register a new user (patient or staff - staff roles assigned by admins)
      """
      serializer = UserRegistrationSerializer(data=request.data)
      if serializer.is_valid():
          user = serializer.save()
          refresh = RefreshToken.for_user(user)

          # Log the registration
          # AuditLog.objects.create(
          #     user=user,
          #     action='create',
          #     model_name='User',
          #     object_id=str(user.id),
          #     object_repr=str(user),
          #     ip_address=request.META.get('REMOTE_ADDR'),
          #     user_agent=request.META.get('HTTP_USER_AGENT', '')
          # )

          return Response({
              'user': UserSerializer(user).data,
              'access': str(refresh.access_token),
              'refresh': str(refresh),
          }, status=status.HTTP_201_CREATED)
      return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
      """
      Authenticate user and return JWT tokens
      """
      username = request.data.get('username')
      password = request.data.get('password')

      if not username or not password:
          return Response({'detail': 'Username and password are required.'},
                         status=status.HTTP_400_BAD_REQUEST)

      user = authenticate(username=username, password=password)
      if user is None:
          return Response({'detail': 'Invalid credentials.'},
                         status=status.HTTP_401_UNAUTHORIZED)

      if not user.is_active:
          return Response({'detail': 'Account is disabled.'},
                         status=status.HTTP_401_UNAUTHORIZED)

      refresh = RefreshToken.for_user(user)

      # Log the login
      # AuditLog.objects.create(
      #     user=user,
      #     action='login',
      #     model_name='User',
      #     object_id=str(user.id),
      #     object_repr=str(user),
      #     ip_address=request.META.get('REMOTE_ADDR'),
      #     user_agent=request.META.get('HTTP_USER_AGENT', '')
      # )

      return Response({
          'user': UserSerializer(user).data,
          'access': str(refresh.access_token),
          'refresh': str(refresh),
      }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
      """
      Logout user by blacklisting refresh token (optional)
      """
      try:
          refresh_token = request.data.get('refresh')
          if refresh_token:
              token = RefreshToken(refresh_token)
              token.blacklist()

          # Log the logout
          # AuditLog.objects.create(
          #     user=request.user,
          #     action='logout',
          #     model_name='User',
          #     object_id=str(request.user.id),
          #     object_repr=str(request.user),
          #     ip_address=request.META.get('REMOTE_ADDR'),
          #     user_agent=request.META.get('HTTP_USER_AGENT', '')
          # )

          return Response({'detail': 'Successfully logged out.'},
                         status=status.HTTP_200_OK)
      except Exception as e:
          return Response({'detail': 'Error logging out.'},
                         status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
      """
      Get current user's profile information
      """
      user = request.user
      profile_data = None

      try:
          if hasattr(user, 'patient_profile'):
              profile_data = PatientProfileSerializer(user.patient_profile).data
          elif hasattr(user, 'doctor_profile'):
              profile_data = DoctorProfileSerializer(user.doctor_profile).data
      except:
          pass

      return Response({
          'id': user.id,
          'username': user.username,
          'email': user.email,
          'first_name': user.first_name,
          'last_name': user.last_name,
          'role': user.role_profile.role if hasattr(user, 'role_profile') else None,
          'profile': profile_data,
          'is_active': user.is_active
      })


  # =============================================================================
  # AI TRIAGE VIEWS
  # =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def ai_triage(request):
      """
      Perform symptom triage and provide routing recommendations
      """
      message = request.data.get('message', '').strip()

      if not message:
          return Response({'detail': 'Message is required.'},
                         status=status.HTTP_400_BAD_REQUEST)

      result = _triage_response(message)

      # Optionally log the triage request (without storing sensitive data)
      # AuditLog.objects.create(
      #     user=None,  # Anonymous triage
      #     action='create',
      #     model_name='AITriageRequest',
      #     object_id=f"triage_{timezone.now().timestamp()}",
      #     object_repr=f"Triage request: {message[:50]}...",
      #     ip_address=request.META.get('REMOTE_ADDR'),
      #     user_agent=request.META.get('HTTP_USER_AGENT', '')
      # )

      return Response({
          'message': message,
          'urgency': result['urgency'],
          'route': result['route'],
          'recommendation': result['recommendation'],
          'summary': result['summary'],
          'timestamp': timezone.now().isoformat()
      }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def ai_summary(request):
      """
      Build a structured summary from symptoms and context
      """
      symptoms = request.data.get('symptoms', '').strip()
      context = request.data.get('context', '').strip()
      route = request.data.get('route', 'Doctor appointment booking').strip()

      if not symptoms:
          return Response({'detail': 'Symptoms are required.'},
                         status=status.HTTP_400_BAD_REQUEST)

      summary_result = _build_ai_summary(symptoms, context, route)
      return Response({
          'summary': summary_result['summary'],
          'route': summary_result['route'],
          'recommendation': summary_result['recommendation'],
      }, status=status.HTTP_200_OK)


  # =============================================================================
  # VIEWSETS FOR MAIN ENTITIES
  # =============================================================================

class PatientProfileViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing patient profiles
      """
      queryset = PatientProfile.objects.all()
      serializer_class = PatientProfileSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['gender', 'date_of_birth']
      search_fields = ['user__first_name', 'user__last_name', 'user__username', 'phone']
      ordering_fields = ['user__last_name', 'user__first_name', 'created_at']
      ordering = ['user__last_name', 'user__first_name']

      def get_queryset(self):
          user = self.request.user

          # Patients can only see their own profile
          if hasattr(user, 'patient_profile'):
              return PatientProfile.objects.filter(id=user.patient_profile.id)

          # Staff can see all patients (with appropriate permissions)
          if user_role(user) in {'doctor', 'receptionist', 'clinic_manager'}:
              return PatientProfile.objects.all()

          # Default: no access
          return PatientProfile.objects.none()

      def get_object(self):
          """
          Override to allow patients to access their own profile by ID or 'me'
          """
          if self.kwargs.get('pk') == 'me':
              if hasattr(self.request.user, 'patient_profile'):
                  return self.request.user.patient_profile
              else:
                  from rest_framework.exceptions import PermissionDenied
                  raise PermissionDenied("Patient profile not found")
          return super().get_object()

      @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
      def me(self, request):
          """Get current user's patient profile"""
          if hasattr(request.user, 'patient_profile'):
              serializer = self.get_serializer(request.user.patient_profile)
              return Response(serializer.data)
          return Response({'detail': 'Patient profile not found.'},
                         status=status.HTTP_404_NOT_FOUND)


class DoctorProfileViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing doctor profiles
      """
      queryset = DoctorProfile.objects.all()
      serializer_class = DoctorProfileSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['specialty', 'is_accepting_patients']
      search_fields = ['user__first_name', 'user__last_name', 'user__username', 'license_number']
      ordering_fields = ['user__last_name', 'user__first_name', 'created_at']
      ordering = ['user__last_name', 'user__first_name']

      def get_queryset(self):
          user = self.request.user

          # Doctors can see their own profile
          if hasattr(user, 'doctor_profile'):
              return DoctorProfile.objects.filter(id=user.doctor_profile.id)

          # Staff can see all doctors
          if user_role(user) in {'receptionist', 'clinic_manager'}:
              return DoctorProfile.objects.all()

          # Patients can see doctors (limited info)
          if user_role(user) == 'patient':
              return DoctorProfile.objects.filter(is_accepting_patients=True)

          return DoctorProfile.objects.none()

      @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
      def me(self, request):
          """Get current user's doctor profile"""
          if hasattr(request.user, 'doctor_profile'):
              serializer = self.get_serializer(request.user.doctor_profile)
              return Response(serializer.data)
          return Response({'detail': 'Doctor profile not found.'},
                         status=status.HTTP_404_NOT_FOUND)

      @action(detail=True, methods=['post'], permission_classes=[IsClinicStaff])
      def toggle_availability(self, request, pk=None):
          """Toggle doctor's availability for new patients"""
          doctor = self.get_object()
          doctor.is_accepting_patients = not doctor.is_accepting_patients
          doctor.save()
          return Response({
              'is_accepting_patients': doctor.is_accepting_patients,
              'message': f'Doctor is now {"accepting" if doctor.is_accepting_patients else "not accepting"} new patients.'
          })


class DepartmentViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing departments
      """
      queryset = Department.objects.filter(is_active=True)
      serializer_class = DepartmentSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [filters.SearchFilter, filters.OrderingFilter]
      search_fields = ['name', 'description']
      ordering_fields = ['name', 'created_at']
      ordering = ['name']

      def get_queryset(self):
          user = self.request.user
          if user_role(user) in {'doctor', 'receptionist', 'clinic_manager'}:
              return Department.objects.all()  # Staff can see inactive departments too
          return Department.objects.filter(is_active=True)  # Patients only see active


class AppointmentViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing appointments
      """
      queryset = Appointment.objects.all()
      serializer_class = AppointmentSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['status', 'doctor', 'department', 'appointment_datetime']
      search_fields = ['patient__user__first_name', 'patient__user__last_name',
                       'doctor__user__first_name', 'doctor__user__last_name',
                       'department__name']
      ordering_fields = ['appointment_datetime', 'created_at', 'status']
      ordering = ['appointment_datetime']

      def get_queryset(self):
          user = self.request.user

          # Patients can only see their own appointments
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  return Appointment.objects.filter(patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  return Appointment.objects.none()

          # Doctors can see their own appointments
          if user_role(user) == 'doctor':
              try:
                  doctor_profile = user.doctor_profile
                  return Appointment.objects.filter(doctor=doctor_profile)
              except DoctorProfile.DoesNotExist:
                  return Appointment.objects.none()

          # Receptionists and clinic managers can see all appointments
          if user_role(user) in {'receptionist', 'clinic_manager'}:
              return Appointment.objects.all()

          return Appointment.objects.none()

      def get_serializer_class(self):
          if self.action == 'create':
              return AppointmentCreateSerializer
          return AppointmentSerializer

      def perform_create(self, serializer):
          """Set the patient to current user if they're a patient"""
          user = self.request.user
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  serializer.save(patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  # If patient profile doesn't exist, let validation handle it
                  serializer.save()
          else:
              # Staff can create appointments for any patient
              serializer.save()

      @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
      def today(self, request):
          """Get today's appointments"""
          today = timezone.now().date()
          queryset = self.get_queryset().filter(appointment_datetime__date=today)
          serializer = self.get_serializer(queryset, many=True)
          return Response(serializer.data)

      @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
      def upcoming(self, request):
          """Get upcoming appointments"""
          now = timezone.now()
          queryset = self.get_queryset().filter(appointment_datetime__gte=now, status__in=['pending', 'confirmed'])
          serializer = self.get_serializer(queryset, many=True)
          return Response(serializer.data)

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def cancel(self, request, pk=None):
          """Cancel an appointment"""
          appointment = self.get_object()

          # Check permissions
          user = request.user
          if user_role(user) == 'patient':
              if appointment.patient.user != user:
                  return Response({'detail': 'You can only cancel your own appointments.'},
                                 status=status.HTTP_403_FORBIDDEN)
          elif user_role(user) == 'doctor':
              if appointment.doctor.user != user:
                  return Response({'detail': 'You can only cancel appointments for your patients.'},
                                 status=status.HTTP_403_FORBIDDEN)
          # Staff can cancel any appointment

          if appointment.status in ['completed', 'cancelled']:
              return Response({'detail': 'Cannot cancel completed or already cancelled appointment.'},
                             status=status.HTTP_400_BAD_REQUEST)

          appointment.status = 'cancelled'
          appointment.save()

          # Log the cancellation
          # AuditLog.objects.create(
          #     user=user,
          #     action='update',
          #     model_name='Appointment',
          #     object_id=str(appointment.id),
          #     object_repr=str(appointment),
          #     changes={'status': [appointment.status, 'cancelled']},
          #     ip_address=request.META.get('REMOTE_ADDR'),
          #     user_agent=request.META.get('HTTP_USER_AGENT', '')
          # )

          return Response({'status': 'Appointment cancelled successfully.'})

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def complete(self, request, pk=None):
          """Mark appointment as completed"""
          appointment = self.get_object()

          # Only doctors can mark appointments as completed
          if user_role(request.user) != 'doctor' or appointment.doctor.user != request.user:
              return Response({'detail': 'Only the assigned doctor can mark appointments as completed.'},
                             status=status.HTTP_403_FORBIDDEN)

          if appointment.status != 'confirmed':
              return Response({'detail': 'Only confirmed appointments can be marked as completed.'},
                             status=status.HTTP_400_BAD_REQUEST)

          appointment.status = 'completed'
          appointment.save()

          return Response({'status': 'Appointment marked as completed.'})


class AIChatSessionViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing AI chat sessions
      """
      queryset = AIChatSession.objects.all()
      serializer_class = AIChatSessionSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['session_type', 'is_active', 'urgency_level']
      search_fields = ['patient__user__first_name', 'patient__user__last_name', 'topic']
      ordering_fields = ['started_at', 'ended_at']
      ordering = ['-started_at']

      def get_queryset(self):
          user = self.request.user

          # Patients can only see their own sessions
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  return AIChatSession.objects.filter(patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  return AIChatSession.objects.none()

          # Doctors can see sessions for their patients
          if user_role(user) == 'doctor':
              try:
                  doctor_profile = user.doctor_profile
                  # Get patients who have appointments with this doctor
                  patient_ids = Appointment.objects.filter(doctor=doctor_profile).values_list('patient_id', flat=True)
                  return AIChatSession.objects.filter(patient_id__in=patient_ids)
              except DoctorProfile.DoesNotExist:
                  return AIChatSession.objects.none()

          # Receptionists and clinic managers can see all sessions
          if user_role(user) in {'receptionist', 'clinic_manager'}:
              return AIChatSession.objects.all()

          return AIChatSession.objects.none()

      def get_serializer_class(self):
          if self.action == 'create':
              return AIChatSessionCreateSerializer
          return AIChatSessionSerializer

      def perform_create(self, serializer):
          """Set the patient to current user if they're a patient"""
          user = self.request.user
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  serializer.save(patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  serializer.save()
          else:
              # Staff can create sessions for any patient
              serializer.save()

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def end_session(self, request, pk=None):
          """End an active chat session"""
          session = self.get_object()

          # Check permissions
          user = request.user
          if user_role(user) == 'patient':
              if session.patient.user != user:
                  return Response({'detail': 'You can only end your own chat sessions.'},
                                 status=status.HTTP_403_FORBIDDEN)
          elif user_role(user) == 'doctor':
              # Doctor can end sessions for their patients
              try:
                  doctor_profile = user.doctor_profile
                  # Check if patient has appointments with this doctor
                  has_appointment = Appointment.objects.filter(
                      doctor=doctor_profile,
                      patient=session.patient
                  ).exists()
                  if not has_appointment:
                      return Response({'detail': 'You can only end sessions for your patients.'},
                                     status=status.HTTP_403_FORBIDDEN)
              except DoctorProfile.DoesNotExist:
                  return Response({'detail': 'Doctor profile not found.'},
                                 status=status.HTTP_403_FORBIDDEN)
          # Staff can end any session

          if not session.is_active:
              return Response({'detail': 'Session is already ended.'},
                             status=status.HTTP_400_BAD_REQUEST)

          session.is_active = False
          session.ended_at = timezone.now()
          session.save()

          return Response({'status': 'Session ended successfully.'})

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def add_message(self, request, pk=None):
          """Add a message to a chat session"""
          session = self.get_object()

          # Validate that user can add message to this session
          user = request.user
          sender_role = user_role(user)

          # Determine allowed sender types based on user role
          allowed_senders = {
              'patient': ['patient'],
              'doctor': ['doctor', 'assistant'],  # Doctor can act as assistant or themselves
              'receptionist': ['assistant', 'reception'],
              'clinic_manager': ['assistant', 'reception']
          }

          requested_sender = request.data.get('sender', 'patient')
          if requested_sender not in allowed_senders.get(sender_role, []):
              return Response({
                  'detail': f'Your role ({sender_role}) cannot send messages as {requested_sender}.'
              }, status=status.HTTP_403_FORBIDDEN)

          # Additional permission checks
          if requested_sender == 'patient' and session.patient.user != user:
              return Response({'detail': 'You can only send patient messages for your own sessions.'},
                             status=status.HTTP_403_FORBIDDEN)

          if requested_sender == 'doctor':
              try:
                  doctor_profile = user.doctor_profile
                  # Check if this is the doctor's patient
                  has_appointment = Appointment.objects.filter(
                      doctor=doctor_profile,
                      patient=session.patient
                  ).exists()
                  if not has_appointment:
                      return Response({'detail': 'You can only send doctor messages for your patients.'},
                                     status=status.HTTP_403_FORBIDDEN)
              except DoctorProfile.DoesNotExist:
                  return Response({'detail': 'Doctor profile not found.'},
                                 status=status.HTTP_403_FORBIDDEN)

          serializer = AIChatMessageSerializer(data=request.data)
          if serializer.is_valid():
              serializer.save(session=session)
              return Response(serializer.data, status=status.HTTP_201_CREATED)
          return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AIChatMessageViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing AI chat messages
      """
      queryset = AIChatMessage.objects.all()
      serializer_class = AIChatMessageSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
      filterset_fields = ['session', 'sender', 'contains_phi']
      ordering_fields = ['created_at']
      ordering = ['created_at']

      def get_queryset(self):
          user = self.request.user

          # Patients can only see messages from their own sessions
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  return AIChatMessage.objects.filter(session__patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  return AIChatMessage.objects.none()

          # Doctors can see messages from sessions involving their patients
          if user_role(user) == 'doctor':
              try:
                  doctor_profile = user.doctor_profile
                  # Get sessions where patient has appointments with this doctor
                  patient_ids = Appointment.objects.filter(doctor=doctor_profile).values_list('patient_id', flat=True)
                  return AIChatMessage.objects.filter(session__patient_id__in=patient_ids)
              except DoctorProfile.DoesNotExist:
                  return AIChatMessage.objects.none()

          # Receptionists and clinic managers can see all messages
          if user_role(user) in {'receptionist', 'clinic_manager'}:
              return AIChatMessage.objects.all()

          return AIChatMessage.objects.none()

      def perform_create(self, serializer):
          """Validate sender permissions before saving"""
          user = self.request.user
          sender = serializer.validated_data.get('sender', 'patient')
          session = serializer.validated_data.get('session')

          # Validate that user can send as this sender type
          sender_role = user_role(user)
          allowed_senders = {
              'patient': ['patient'],
              'doctor': ['doctor', 'assistant'],
              'receptionist': ['assistant', 'reception'],
              'clinic_manager': ['assistant', 'reception']
          }

          if sender not in allowed_senders.get(sender_role, []):
              from rest_framework.exceptions import PermissionDenied
              raise PermissionDenied(f'Your role ({sender_role}) cannot send messages as {sender}.')

          # Additional checks for patient and doctor roles
          if sender == 'patient':
              if not hasattr(user, 'patient_profile') or session.patient.user != user:
                  raise PermissionDenied('You can only send patient messages for your own sessions.')

          if sender == 'doctor':
              if not hasattr(user, 'doctor_profile'):
                  raise PermissionDenied('Doctor profile not found.')
              # Verify this is the doctor's patient
              try:
                  doctor_profile = user.doctor_profile
                  has_appointment = Appointment.objects.filter(
                      doctor=doctor_profile,
                      patient=session.patient
                  ).exists()
                  if not has_appointment:
                      raise PermissionDenied('You can only send doctor messages for your patients.')
              except DoctorProfile.DoesNotExist:
                  raise PermissionDenied('Doctor profile not found.')

          serializer.save()


class TriageCaseViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing triage cases
      """
      queryset = TriageCase.objects.all()
      serializer_class = TriageCaseSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['urgency', 'patient']
      search_fields = ['patient__user__first_name', 'patient__user__last_name', 'chief_complaint']
      ordering_fields = ['created_at', 'urgency']
      ordering = ['-created_at']

      def get_queryset(self):
          user = self.request.user

          # Patients can only see their own triage cases
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  return TriageCase.objects.filter(patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  return TriageCase.objects.none()

          # Doctors can see triage cases for their patients
          if user_role(user) == 'doctor':
              try:
                  doctor_profile = user.doctor_profile
                  # Get patients who have appointments with this doctor
                  patient_ids = Appointment.objects.filter(doctor=doctor_profile).values_list('patient_id', flat=True)
                  return TriageCase.objects.filter(patient_id__in=patient_ids)
              except DoctorProfile.DoesNotExist:
                  return TriageCase.objects.none()

          # Receptionists and clinic managers can see all triage cases
          if user_role(user) in {'receptionist', 'clinic_manager'}:
              return TriageCase.objects.all()

          return TriageCase.objects.none()

      def get_serializer_class(self):
          if self.action == 'create':
              return TriageCaseCreateSerializer
          return TriageCaseSerializer

      def perform_create(self, serializer):
          """Set the patient to current user if they're a patient"""
          user = self.request.user
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  serializer.save(patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  serializer.save()
          else:
              # Staff can create triage cases for any patient
              serializer.save()

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def escalate(self, request, pk=None):
          """Escalate a triage case to a healthcare professional"""
          triage = self.get_object()

          # Only staff can escalate
          if user_role(request.user) not in {'doctor', 'receptionist', 'clinic_manager'}:
              return Response({'detail': 'Only clinic staff can escalate triage cases.'},
                             status=status.HTTP_403_FORBIDDEN)

          escalated_to_id = request.data.get('escalated_to')
          escalation_notes = request.data.get('escalation_notes', '')

          if escalated_to_id:
              try:
                  escalated_to = User.objects.get(id=escalated_to_id)
                  triage.escalated_to = escalated_to
              except User.DoesNotExist:
                  return Response({'detail': 'User not found.'},
                                 status=status.HTTP_400_BAD_REQUEST)
          else:
              triage.escalated_to = None

          triage.escalation_notes = escalation_notes
          triage.save()

          return Response({'status': 'Triage case escalated successfully.'})

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def review(self, request, pk=None):
          """Mark a triage case as reviewed"""
          triage = self.get_object()

          # Only staff can review
          if user_role(request.user) not in {'doctor', 'receptionist', 'clinic_manager'}:
              return Response({'detail': 'Only clinic staff can review triage cases.'},
                             status=status.HTTP_403_FORBIDDEN)

          triage.reviewed_by = request.user
          triage.reviewed_at = timezone.now()
          triage.save()

          return Response({'status': 'Triage case marked as reviewed.'})


class InvoiceViewSet(viewsets.ModelViewSet):
      """
      ViewSet for managing invoices
      """
      queryset = Invoice.objects.all()
      serializer_class = InvoiceSerializer
      permission_classes = [IsAuthenticated]
      filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
      filterset_fields = ['status', 'patient', 'appointment', 'issued_by']
      search_fields = ['patient__user__first_name', 'patient__user__last_name',
                       'description', 'invoice_number']
      ordering_fields = ['created_at', 'due_date', 'amount']
      ordering = ['-created_at']

      def get_queryset(self):
          user = self.request.user

          # Patients can only see their own invoices
          if user_role(user) == 'patient':
              try:
                  patient_profile = user.patient_profile
                  return Invoice.objects.filter(patient=patient_profile)
              except PatientProfile.DoesNotExist:
                  return Invoice.objects.none()

          # Doctors can see invoices for their patients (limited)
          if user_role(user) == 'doctor':
              try:
                  doctor_profile = user.doctor_profile
                  # Get patients who have appointments with this doctor
                  patient_ids = Appointment.objects.filter(doctor=doctor_profile).values_list('patient_id', flat=True)
                  return Invoice.objects.filter(patient_id__in=patient_ids)
              except DoctorProfile.DoesNotExist:
                  return Invoice.objects.none()

          # Receptionists and clinic managers can see all invoices
          if user_role(user) in {'receptionist', 'clinic_manager'}:
              return Invoice.objects.all()

          return Invoice.objects.none()

      def get_serializer_class(self):
          if self.action == 'create':
              # We'll create a specialized create serializer if needed
              return InvoiceSerializer
          return InvoiceSerializer

      def create(self, request, *args, **kwargs):
          """Only receptionists and clinic managers can create invoices"""
          if user_role(request.user) not in {'receptionist', 'clinic_manager'}:
              return Response({'detail': 'Only receptionists and clinic managers can issue invoices.'},
                             status=status.HTTP_403_FORBIDDEN)
          return super().create(request, *args, **kwargs)

      def perform_create(self, serializer):
          """Set the issuer to current user"""
          serializer.save(issued_by=self.request.user)

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def mark_paid(self, request, pk=None):
          """Mark invoice as paid"""
          invoice = self.get_object()

          # Only staff can mark invoices as paid
          if user_role(request.user) not in {'receptionist', 'clinic_manager'}:
              return Response({'detail': 'Only clinic staff can mark invoices as paid.'},
                             status=status.HTTP_403_FORBIDDEN)

          payment_method = request.data.get('payment_method', '')
          if payment_method:
              invoice.payment_method = payment_method

          invoice.status = 'paid'
          invoice.payment_date = timezone.now()
          invoice.save()

          return Response({'status': 'Invoice marked as paid.'})

      @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
      def mark_overdue(self, request, pk=None):
          """Mark invoice as overdue"""
          invoice = self.get_object()

          # Only staff can mark invoices as overdue
          if user_role(request.user) not in {'receptionist', 'clinic_manager'}:
              return Response({'detail': 'Only clinic staff can mark invoices as overdue.'},
                             status=status.HTTP_403_FORBIDDEN)

          if invoice.status == 'paid':
              return Response({'detail': 'Cannot mark paid invoice as overdue.'},
                             status=status.HTTP_400_BAD_REQUEST)

          invoice.status = 'overdue'
          invoice.save()

          return Response({'status': 'Invoice marked as overdue.'})


  # =============================================================================
  # DASHBOARD / REPORTING VIEWS
  # =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
      """
      Get dashboard statistics based on user role
      """
      user = request.user
      role = user_role(user)

      stats = {}

      if role == 'patient':
          try:
              patient_profile = user.patient_profile
              stats['upcoming_appointments'] = Appointment.objects.filter(
                  patient=patient_profile,
                  appointment_datetime__gte=timezone.now(),
                  status__in=['pending', 'confirmed']
              ).count()
              stats['total_appointments'] = Appointment.objects.filter(
                  patient=patient_profile
              ).count()
              stats['pending_invoices'] = Invoice.objects.filter(
                  patient=patient_profile,
                  status__in=['unpaid', 'partially_paid']
              ).count()
              stats['total_invoices'] = Invoice.objects.filter(
                  patient=patient_profile
              ).count()
          except PatientProfile.DoesNotExist:
              pass

      elif role == 'doctor':
          try:
              doctor_profile = user.doctor_profile
              stats['today_appointments'] = Appointment.objects.filter(
                  doctor=doctor_profile,
                  appointment_datetime__date=timezone.now().date(),
                  status__in=['pending', 'confirmed']
              ).count()
              stats['upcoming_appointments'] = Appointment.objects.filter(
                  doctor=doctor_profile,
                  appointment_datetime__gte=timezone.now(),
                  status__in=['pending', 'confirmed']
              ).count()
              stats['total_patients'] = PatientProfile.objects.filter(
                  appointments__doctor=doctor_profile
              ).distinct().count()
              stats['pending_triages'] = TriageCase.objects.filter(
                  patient__appointments__doctor=doctor_profile
              ).distinct().count()
          except DoctorProfile.DoesNotExist:
              pass

      elif role in {'receptionist', 'clinic_manager'}:
          stats['today_appointments'] = Appointment.objects.filter(
              appointment_datetime__date=timezone.now().date(),
              status__in=['pending', 'confirmed']
          ).count()
          stats['pending_appointments'] = Appointment.objects.filter(
              status='pending'
          ).count()
          stats['total_patients'] = PatientProfile.objects.count()
          stats['total_doctors'] = DoctorProfile.objects.count()
          stats['pending_invoices'] = Invoice.objects.filter(
              status__in=['unpaid', 'partially_paid']
          ).count()
          stats['overdue_invoices'] = Invoice.objects.filter(
              status='overdue'
          ).count()
          stats['pending_triages'] = TriageCase.objects.filter(
              urgency__in=['high', 'emergency']
          ).count()

      return Response(stats)


@api_view(['GET'])
@permission_classes([IsClinicStaff])
def system_overview(request):
      """
      Get system-wide statistics (staff only)
      """
      stats = {
          'total_users': User.objects.count(),
          'active_users': User.objects.filter(is_active=True).count(),
          'total_patients': PatientProfile.objects.count(),
          'total_doctors': DoctorProfile.objects.count(),
          'active_doctors': DoctorProfile.objects.filter(is_accepting_patients=True).count(),
          'total_departments': Department.objects.filter(is_active=True).count(),
          'total_appointments': Appointment.objects.count(),
          'appointments_today': Appointment.objects.filter(
              appointment_datetime__date=timezone.now().date()
          ).count(),
          'upcoming_appointments': Appointment.objects.filter(
              appointment_datetime__gte=timezone.now(),
              status__in=['pending', 'confirmed']
          ).count(),
          'completed_appointments': Appointment.objects.filter(
              status='completed'
          ).count(),
          'cancelled_appointments': Appointment.objects.filter(
              status='cancelled'
          ).count(),
          'total_invoices': Invoice.objects.count(),
          'paid_invoices': Invoice.objects.filter(status='paid').count(),
          'pending_invoices': Invoice.objects.filter(status__in=['unpaid', 'partially_paid']).count(),
          'overdue_invoices': Invoice.objects.filter(status='overdue').count(),
          'total_triage_cases': TriageCase.objects.count(),
          'high_urgency_triages': TriageCase.objects.filter(
              urgency__in=['high', 'emergency']
          ).count(),
      }
      return Response(stats)
