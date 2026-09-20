from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


  # Keep your UserRole model - it's good!
class UserRole(models.Model):
      ROLE_CHOICES = [
          ('patient', 'Patient'),
          ('doctor', 'Doctor'),
          ('receptionist', 'Receptionist'),
          ('clinic_manager', 'Clinic Manager'),
      ]

      user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role_profile')
      role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='patient')

      def __str__(self):
          return f'{self.user.get_full_name() or self.user.username} - {self.get_role_display()}'

      class Meta:
          verbose_name_plural = "User Roles"


  # Enhanced PatientProfile
class PatientProfile(models.Model):
      GENDER_CHOICES = [
          ('M', 'Male'),
          ('F', 'Female'),
          ('O', 'Other'),
          ('P', 'Prefer not to say'),
      ]

      user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
      # Use User's first_name, last_name, email instead of duplicating
      phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.")
      phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
      date_of_birth = models.DateField(null=True, blank=True)
      gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
      address = models.TextField(blank=True)
      emergency_contact_name = models.CharField(max_length=255, blank=True)
      emergency_contact_phone = models.CharField(max_length=17, blank=True, validators=[phone_regex])
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)

      def __str__(self):
          return f'{self.user.get_full_name()} ({self.user.username})'

      @property
      def age(self):
          if self.date_of_birth:
              return timezone.now().date().year - self.date_of_birth.year
          return None

      class Meta:
          ordering = ['user__last_name', 'user__first_name']


  # NEW: Doctor Profile Model
class DoctorProfile(models.Model):
      SPECIALTY_CHOICES = [
          ('cardiology', 'Cardiology'),
          ('dermatology', 'Dermatology'),
          ('endocrinology', 'Endocrinology'),
          ('gastroenterology', 'Gastroenterology'),
          ('neurology', 'Neurology'),
          ('oncology', 'Oncology'),
          ('orthopedics', 'Orthopedics'),
          ('pediatrics', 'Pediatrics'),
          ('psychiatry', 'Psychiatry'),
          ('pulmonology', 'Pulmonology'),
          ('radiology', 'Radiology'),
          ('surgery', 'Surgery'),
          ('general_practice', 'General Practice'),
      ]

      user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
      specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES)
      license_number = models.CharField(max_length=50, unique=True)
      phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed.")
      phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
      bio = models.TextField(blank=True)
      is_accepting_patients = models.BooleanField(default=True)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)

      def __str__(self):
          return f'Dr. {self.user.get_full_name()} - {self.get_specialty_display()}'

      class Meta:
          ordering = ['user__last_name']


  # NEW: Department/Clinic Model
class Department(models.Model):
      name = models.CharField(max_length=100, unique=True)
      description = models.TextField(blank=True)
      is_active = models.BooleanField(default=True)
      created_at = models.DateTimeField(auto_now_add=True)

      def __str__(self):
          return self.name

      class Meta:
          ordering = ['name']


  # Enhanced Appointment Model
class Appointment(models.Model):
      STATUS_CHOICES = [
          ('pending', 'Pending'),
          ('confirmed', 'Confirmed'),
          ('completed', 'Completed'),
          ('cancelled', 'Cancelled'),
          ('no_show', 'No Show'),
      ]

      patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='appointments')
      doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name='appointments', null=True, blank=True)
      department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='appointments', null=True, blank=True)

      # Combine date and time for better querying
      appointment_datetime = models.DateTimeField(default=timezone.now)
      duration_minutes = models.PositiveIntegerField(default=30)  # Standard appointment length

      status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
      notes = models.TextField(blank=True)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)

      def __str__(self):
          return f'{self.patient.user.get_full_name()} with Dr. {self.doctor.user.get_full_name()} on {self.appointment_datetime.strftime("%Y-%m-%d %H:%M")}'

      def clean(self):
          # Prevent past appointments (unless editing completed ones)
          if self.appointment_datetime < timezone.now() and self.status not in ['completed', 'cancelled']:
              raise ValidationError("Appointment cannot be in the past.")

          # Check for overlapping appointments for the same doctor
          overlapping = Appointment.objects.filter(
              doctor=self.doctor,
              appointment_datetime__lt=self.appointment_datetime + timezone.timedelta(minutes=self.duration_minutes),
              appointment_datetime__gte=self.appointment_datetime - timezone.timedelta(minutes=self.duration_minutes),
              status__in=['pending', 'confirmed']
          ).exclude(pk=self.pk)

          if overlapping.exists():
              raise ValidationError("Doctor already has an appointment at this time.")

      def save(self, *args, **kwargs):
          self.clean()
          super().save(*args, **kwargs)

      class Meta:
          ordering = ['appointment_datetime']
          verbose_name_plural = "Appointments"


  # Enhanced AIChatSession
class AIChatSession(models.Model):
      SESSION_TYPES = [
          ('triage', 'Symptom Triage'),
          ('general', 'General Inquiry'),
          ('follow_up', 'Follow-up'),
          ('medication_query', 'Medication Question'),
      ]

      patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='chat_sessions')
      session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='general')
      started_at = models.DateTimeField(auto_now_add=True)
      ended_at = models.DateTimeField(null=True, blank=True)
      is_active = models.BooleanField(default=True)
      # Store AI summary/diagnosis (with disclaimer that it's not medical advice)
      ai_summary = models.TextField(blank=True, help_text="AI-generated summary - NOT medical advice")
      urgency_level = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium')

      def __str__(self):
          return f'{self.patient.user.get_full_name()} - {self.get_session_type_display()} ({self.started_at.strftime("%Y-%m-%d %H:%M")})'

      class Meta:
          ordering = ['-started_at']


  # Enhanced AIChatMessage
class AIChatMessage(models.Model):
      SENDER_CHOICES = [
          ('patient', 'Patient'),
          ('assistant', 'Assistant'),
          # Note: Doctor/reception would typically be in separate system/chat
      ]

      session = models.ForeignKey(AIChatSession, on_delete=models.CASCADE, related_name='messages')
      sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
      message = models.TextField()
      created_at = models.DateTimeField(auto_now_add=True)
      # Flag if message contains PHI that needs special handling
      contains_phi = models.BooleanField(default=False)

      def __str__(self):
          return f'{self.sender}: {self.message[:50]}...'

      class Meta:
          ordering = ['created_at']


  # Enhanced TriageCase (more structured)
class TriageCase(models.Model):
      URGENCY_CHOICES = [
          ('low', 'Low'),
          ('medium', 'Medium'),
          ('high', 'High'),
          ('emergency', 'Emergency'),
      ]

      patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='triage_cases')
      # Structured symptom tracking (better than free text for analytics)
      chief_complaint = models.CharField(max_length=255)
      symptoms = models.TextField(help_text="Detailed symptom description")
      # Vital signs (basic)
      temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="In Celsius")
      blood_pressure_systolic = models.PositiveIntegerField(null=True, blank=True)
      blood_pressure_diastolic = models.PositiveIntegerField(null=True, blank=True)
      heart_rate = models.PositiveIntegerField(null=True, blank=True, help_text="BPM")
      respiratory_rate = models.PositiveIntegerField(null=True, blank=True)
      oxygen_saturation = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Percentage")

      urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
      ai_assessment = models.TextField(blank=True, help_text="AI preliminary assessment - NOT diagnosis")
      confidence_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, help_text="AI confidence 0.00-1.00")
      escalated_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='escalated_triages')
      escalation_notes = models.TextField(blank=True)
      created_at = models.DateTimeField(auto_now_add=True)
      reviewed_at = models.DateTimeField(null=True, blank=True)
      reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_triages')

      def __str__(self):
          return f'{self.patient.user.get_full_name()} - {self.get_urgency_display()} ({self.created_at.strftime("%Y-%m-%d")})'

      class Meta:
          ordering = ['-created_at']


  # Enhanced Invoice Model
class Invoice(models.Model):
      STATUS_CHOICES = [
          ('unpaid', 'Unpaid'),
          ('partially_paid', 'Partially Paid'),
          ('paid', 'Paid'),
          ('void', 'Void'),
          ('overdue', 'Overdue'),
      ]

      PAYMENT_METHOD_CHOICES = [
          ('credit_card', 'Credit Card'),
          ('debit_card', 'Debit Card'),
          ('bank_transfer', 'Bank Transfer'),
          ('insurance', 'Insurance'),
          ('cash', 'Cash'),
          ('other', 'Other'),
      ]

      patient = models.ForeignKey(PatientProfile, on_delete=models.PROTECT, related_name='invoices')
      appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
      invoice_number = models.CharField(max_length=50, unique=True, editable=False, null=True, blank=True)
      description = models.CharField(max_length=255)
      amount = models.DecimalField(max_digits=10, decimal_places=2)
      tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
      status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
      due_date = models.DateField(null=True, blank=True)
      issued_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='issued_invoices')
      payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
      payment_date = models.DateTimeField(null=True, blank=True)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)

      def save(self, *args, **kwargs):
          if not self.invoice_number:
              # Generate invoice number: INV-YYYYMMDD-XXXX
              today = timezone.now().date()
              count = Invoice.objects.filter(created_at__date=today).count() + 1
              self.invoice_number = f"INV-{today.strftime('%Y%m%d')}-{count:04d}"
          super().save(*args, **kwargs)

      @property
      def total_amount(self):
          return self.amount + self.tax_amount

      def __str__(self):
          return f'{self.invoice_number} - {self.patient.user.get_full_name()}'

      class Meta:
          ordering = ['-created_at']


  # NEW: Audit Log Model (important for medical systems)
class AuditLog(models.Model):
      ACTION_CHOICES = [
          ('create', 'Created'),
          ('read', 'Accessed/Viewed'),
          ('update', 'Updated'),
          ('delete', 'Deleted'),
          ('login', 'User Login'),
          ('logout', 'User Logout'),
      ]

      user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
      action = models.CharField(max_length=10, choices=ACTION_CHOICES)
      model_name = models.CharField(max_length=100)
      object_id = models.CharField(max_length=50, help_text="Primary key of the object")
      object_repr = models.CharField(max_length=200, help_text="String representation of the object")
      changes = models.JSONField(null=True, blank=True, help_text="What changed (for updates)")
      ip_address = models.GenericIPAddressField(null=True, blank=True)
      user_agent = models.TextField(blank=True)
      timestamp = models.DateTimeField(auto_now_add=True)

      def __str__(self):
          return f'{self.user} {self.action} {self.model_name} {self.object_id} at {self.timestamp}'

      class Meta:
          ordering = ['-timestamp']
          indexes = [
              models.Index(fields=['user', 'timestamp']),
              models.Index(fields=['model_name', 'object_id']),
          ]
