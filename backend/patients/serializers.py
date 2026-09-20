
from django.contrib.auth.models import User
from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
      PatientProfile, DoctorProfile, Department,
      Appointment, AIChatSession, AIChatMessage,
      TriageCase, Invoice, UserRole, AuditLog
  )


  # =============================================================================
  # USER & PROFILE SERIALIZERS
  # =============================================================================

class UserSerializer(serializers.ModelSerializer):
      full_name = serializers.SerializerMethodField()
      role = serializers.SerializerMethodField()

      class Meta:
          model = User
          fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'role', 'is_active']
          read_only_fields = ['id', 'is_active']

      def get_full_name(self, obj):
          return obj.get_full_name()

      def get_role(self, obj):
          try:
              return obj.role_profile.role
          except UserRole.DoesNotExist:
              return None


class UserRegistrationSerializer(serializers.ModelSerializer):
      password = serializers.CharField(write_only=True, min_length=8)
      role = serializers.ChoiceField(
          choices=UserRole.ROLE_CHOICES,
          default='patient',
          write_only=True
      )

      # Patient-specific fields (only required for patient role)
      phone = serializers.CharField(required=False, allow_blank=True)
      date_of_birth = serializers.DateField(required=False, allow_null=True)
      gender = serializers.ChoiceField(
          choices=PatientProfile.GENDER_CHOICES,
          required=False,
          allow_blank=True
      )

      # Doctor-specific fields (only required for doctor role)
      specialty = serializers.ChoiceField(
          choices=DoctorProfile.SPECIALTY_CHOICES,
          required=False,
          allow_blank=True
      )
      license_number = serializers.CharField(required=False, allow_blank=True)
      doctor_phone = serializers.CharField(required=False, allow_blank=True)
      bio = serializers.CharField(required=False, allow_blank=True)

      class Meta:
          model = User
          fields = [
              'username', 'email', 'password', 'first_name', 'last_name',
              'role',  # User role selection
              # Patient fields
              'phone', 'date_of_birth', 'gender',
              # Doctor fields
              'specialty', 'license_number', 'doctor_phone', 'bio'
          ]
          extra_kwargs = {
              'password': {'write_only': True}
          }

      def validate(self, attrs):
          role = attrs.get('role')

          # Validate role-specific fields
          if role == 'patient':
              # Patient-specific validations (if any)
              pass
          elif role == 'doctor':
              # Doctor must have specialty and license
              if not attrs.get('specialty'):
                  raise serializers.ValidationError({"specialty": "Specialty is required for doctors."})
              if not attrs.get('license_number'):
                  raise serializers.ValidationError({"license_number": "License number is required for doctors."})

          return attrs

      def create(self, validated_data):
          role = validated_data.pop('role')
          password = validated_data.pop('password')

          # Extract role-specific data
          patient_data = {
              'phone': validated_data.pop('phone', ''),
              'date_of_birth': validated_data.pop('date_of_birth', None),
              'gender': validated_data.pop('gender', '')
          }

          doctor_data = {
              'specialty': validated_data.pop('specialty', None),
              'license_number': validated_data.pop('license_number', ''),
              'phone': validated_data.pop('doctor_phone', ''),
              'bio': validated_data.pop('bio', ''),
              'is_accepting_patients': True
          }

          # Create user
          user = User.objects.create_user(**validated_data)
          user.set_password(password)
          user.save()

          # Create role profile
          UserRole.objects.create(user=user, role=role)

          # Create profile based on role
          if role == 'patient':
              PatientProfile.objects.create(user=user, **patient_data)
          elif role == 'doctor':
              DoctorProfile.objects.create(user=user, **doctor_data)

          return user


class PatientProfileSerializer(serializers.ModelSerializer):
      user = UserSerializer(read_only=True)
      age = serializers.SerializerMethodField(read_only=True)

      class Meta:
          model = PatientProfile
          fields = [
              'id', 'user', 'phone', 'date_of_birth', 'gender',
              'address', 'emergency_contact_name', 'emergency_contact_phone',
              'age', 'created_at', 'updated_at'
          ]
          read_only_fields = ['id', 'created_at', 'updated_at']

      def get_age(self, obj):
          return obj.age


class DoctorProfileSerializer(serializers.ModelSerializer):
      user = UserSerializer(read_only=True)

      class Meta:
          model = DoctorProfile
          fields = [
              'id', 'user', 'specialty', 'license_number', 'phone',
              'bio', 'is_accepting_patients', 'created_at', 'updated_at'
          ]
          read_only_fields = ['id', 'created_at', 'updated_at']


class DepartmentSerializer(serializers.ModelSerializer):
      class Meta:
          model = Department
          fields = ['id', 'name', 'description', 'is_active', 'created_at']
          read_only_fields = ['id', 'created_at']


  # =============================================================================
  # APPOINTMENT SERIALIZERS
  # =============================================================================

class AppointmentSerializer(serializers.ModelSerializer):
      patient = PatientProfileSerializer(read_only=True)
      doctor = DoctorProfileSerializer(read_only=True)
      department = DepartmentSerializer(read_only=True)

      # For write operations - accept IDs
      patient_id = serializers.PrimaryKeyRelatedField(
          queryset=PatientProfile.objects.all(),
          source='patient',
          write_only=True
      )
      doctor_id = serializers.PrimaryKeyRelatedField(
          queryset=DoctorProfile.objects.all(),
          source='doctor',
          write_only=True
      )
      department_id = serializers.PrimaryKeyRelatedField(
          queryset=Department.objects.filter(is_active=True),
          source='department',
          write_only=True
      )

      # Display fields
      patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
      doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
      department_name = serializers.CharField(source='department.name', read_only=True)
      appointment_datetime_display = serializers.SerializerMethodField()

      class Meta:
          model = Appointment
          fields = [
              'id', 'patient', 'patient_id', 'patient_name',
              'doctor', 'doctor_id', 'doctor_name',
              'department', 'department_id', 'department_name',
              'appointment_datetime', 'appointment_datetime_display',
              'duration_minutes', 'status', 'notes',
              'created_at', 'updated_at'
          ]
          read_only_fields = ['id', 'created_at', 'updated_at']

      def get_appointment_datetime_display(self, obj):
          return obj.appointment_datetime.strftime("%Y-%m-%d %H:%M")

      def validate(self, attrs):
          # The model's clean() method will handle validation
          # But we can add additional serializer-level validation if needed
          return attrs

      def create(self, validated_data):
          # Let the model's clean() and save() methods handle validation
          return super().create(validated_data)

      def update(self, instance, validated_data):
          # Let the model's clean() and save() methods handle validation
          return super().update(instance, validated_data)


  # =============================================================================
  # AI CHAT SERIALIZERS
  # =============================================================================

class AIChatMessageSerializer(serializers.ModelSerializer):
      sender_name = serializers.SerializerMethodField()

      class Meta:
          model = AIChatMessage
          fields = [
              'id', 'session', 'sender', 'sender_name',
              'message', 'contains_phi', 'created_at'
          ]
          read_only_fields = ['id', 'created_at']

      def get_sender_name(self, obj):
          if obj.sender == 'patient':
              try:
                  return obj.session.patient.user.get_full_name()
              except:
                  return 'Unknown Patient'
          elif obj.sender == 'assistant':
              return 'AI Assistant'
          return obj.sender.get('_display', obj.sender)


class AIChatSessionSerializer(serializers.ModelSerializer):
      patient = PatientProfileSerializer(read_only=True)
      messages = AIChatMessageSerializer(many=True, read_only=True)
      message_count = serializers.SerializerMethodField()

      class Meta:
          model = AIChatSession
          fields = [
              'id', 'patient', 'session_type', 'started_at', 'ended_at',
              'is_active', 'ai_summary', 'urgency_level', 'message_count',
              'messages', 'created_at'
          ]
          read_only_fields = ['id', 'started_at', 'created_at']

      def get_message_count(self, obj):
          return obj.messages.count()


  # =============================================================================
  # TRIAGE CASE SERIALIZERS
  # =============================================================================

class TriageCaseSerializer(serializers.ModelSerializer):
      patient = PatientProfileSerializer(read_only=True)
      escalated_to_user = UserSerializer(source='escalated_to', read_only=True)
      reviewed_by_user = UserSerializer(source='reviewed_by', read_only=True)

      # For write operations
      patient_id = serializers.PrimaryKeyRelatedField(
          queryset=PatientProfile.objects.all(),
          source='patient',
          write_only=True
      )
      escalated_to_id = serializers.PrimaryKeyRelatedField(
          queryset=User.objects.all(),
          source='escalated_to',
          write_only=True,
          required=False,
          allow_null=True
      )
      reviewed_by_id = serializers.PrimaryKeyRelatedField(
          queryset=User.objects.all(),
          source='reviewed_by',
          write_only=True,
          required=False,
          allow_null=True
      )

      class Meta:
          model = TriageCase
          fields = [
              'id', 'patient', 'patient_id',
              'chief_complaint', 'symptoms',
              # Vital signs
              'temperature', 'blood_pressure_systolic', 'blood_pressure_diastolic',
              'heart_rate', 'respiratory_rate', 'oxygen_saturation',
              'urgency', 'ai_assessment', 'confidence_score',
              # Escalation tracking
              'escalated_to', 'escalated_to_id', 'escalation_notes',
              'reviewed_by', 'reviewed_by_id', 'reviewed_at',
              'created_at'
          ]
          read_only_fields = ['id', 'created_at']


  # =============================================================================
  # INVOICE SERIALIZERS
  # =============================================================================

class InvoiceSerializer(serializers.ModelSerializer):
      patient = PatientProfileSerializer(read_only=True)
      appointment = AppointmentSerializer(read_only=True)
      issued_by = UserSerializer(read_only=True)

      # For write operations
      patient_id = serializers.PrimaryKeyRelatedField(
          queryset=PatientProfile.objects.all(),
          source='patient',
          write_only=True
      )
      appointment_id = serializers.PrimaryKeyRelatedField(
          queryset=Appointment.objects.all(),
          source='appointment',
          write_only=True,
          required=False,
          allow_null=True
      )
      issued_by_id = serializers.PrimaryKeyRelatedField(
          queryset=User.objects.all(),
          source='issued_by',
          write_only=True,
          required=False
      )

      # Calculated fields
      total_amount = serializers.SerializerMethodField()

      class Meta:
          model = Invoice
          fields = [
              'id', 'invoice_number', 'patient', 'patient_id',
              'appointment', 'appointment_id',
              'description', 'amount', 'tax_amount', 'total_amount',
              'status', 'due_date', 'issued_by', 'issued_by_id',
              'payment_method', 'payment_date',
              'created_at', 'updated_at'
          ]
          read_only_fields = ['id', 'invoice_number', 'created_at', 'updated_at']

      def get_total_amount(self, obj):
          return float(obj.total_amount)  # Convert Decimal to float for JSON

      def validate(self, attrs):
          # Set issued_by to current user if not provided
          if 'issued_by' not in attrs and self.context.get('request'):
              attrs['issued_by'] = self.context['request'].user
          return attrs


  # =============================================================================
  # SPECIALIZED SERIALIZERS (for specific use cases)
  # =============================================================================

class AppointmentCreateSerializer(serializers.ModelSerializer):
      """Simplified serializer for creating appointments"""

      class Meta:
          model = Appointment
          fields = [
              'patient', 'doctor', 'department',
              'appointment_datetime', 'duration_minutes', 'notes'
          ]

      def validate_appointment_datetime(self, value):
          if value < timezone.now():
              raise serializers.ValidationError("Appointment cannot be in the past.")
          return value


class TriageCaseCreateSerializer(serializers.ModelSerializer):
      """Serializer for creating triage cases (patient-facing)"""

      class Meta:
          model = TriageCase
          fields = [
              'patient', 'chief_complaint', 'symptoms',
              'temperature', 'blood_pressure_systolic', 'blood_pressure_diastolic',
              'heart_rate', 'respiratory_rate', 'oxygen_saturation'
          ]

      def validate_patient(self, value):
          # Ensure patients can only create triage cases for themselves
          request = self.context.get('request')
          if request and hasattr(request, 'user'):
              try:
                  patient_profile = request.user.patient_profile
                  if value != patient_profile:
                      raise serializers.ValidationError("You can only create triage cases for yourself.")
              except PatientProfile.DoesNotExist:
                  raise serializers.ValidationError("Patient profile not found.")
          return value


class AIChatSessionCreateSerializer(serializers.ModelSerializer):
      """Serializer for creating AI chat sessions"""

      class Meta:
          model = AIChatSession
          fields = ["id", 'patient', 'session_type']

      def validate_patient(self, value):
          # Ensure patients can only create sessions for themselves
          request = self.context.get('request')
          if request and hasattr(request, 'user'):
              try:
                  patient_profile = request.user.patient_profile
                  if value != patient_profile:
                      raise serializers.ValidationError("You can only create chat sessions for yourself.")
              except PatientProfile.DoesNotExist:
                  raise serializers.ValidationError("Patient profile not found.")
          return value


  # =============================================================================
  # AUDIT LOG SERIALIZER (for admin viewing)
  # =============================================================================

class AuditLogSerializer(serializers.ModelSerializer):
      user = UserSerializer(read_only=True)

      class Meta:
          model = AuditLog
          fields = [
              'id', 'user', 'action', 'model_name', 'object_id',
              'object_repr', 'changes', 'ip_address', 'user_agent', 'timestamp'
          ]
          read_only_fields = ['id', 'timestamp']
