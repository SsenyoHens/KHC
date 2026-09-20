from rest_framework import permissions
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

def user_role(user):
      """
      Helper function to get the user's role from the UserRole model.
      Returns None if user has no role profile or is not authenticated.
      """
      if not user or not user.is_authenticated:
          return None

      try:
          return user.role_profile.role
      except (ObjectDoesNotExist, AttributeError):
          return None


class IsClinicStaff(permissions.BasePermission):
      """
      Allow access only to clinic staff members:
      - Doctors
      - Receptionists
      - Clinic Managers
      """

      def has_permission(self, request, view):
          if not request.user or not request.user.is_authenticated:
              return False

          role = user_role(request.user)
          return role in {'doctor', 'receptionist', 'clinic_manager'}


class IsPatientOwner(permissions.BasePermission):
      """
      Allow access only if the object belongs to the requesting patient.
      Works with various model types by checking the patient relationship.
      """

      def has_object_permission(self, request, view, obj):
          if not request.user or not request.user.is_authenticated:
              return False

          # Users must be patients to own patient-related objects
          if user_role(request.user) != 'patient':
              return False

          try:
              patient_profile = request.user.patient_profile
          except ObjectDoesNotExist:
              return False

          # Check different object types
          if hasattr(obj, 'patient'):
              # Appointment, TriageCase, Invoice
              return obj.patient_id == patient_profile.id

          elif hasattr(obj, 'user'):
              # PatientProfile
              return obj.user_id == request.user.id

          elif hasattr(obj, 'session') and hasattr(obj.session, 'patient'):
              # AIChatMessage
              return obj.session.patient_id == patient_profile.id

          elif hasattr(obj, 'patient'):
              # AIChatSession
              return obj.patient_id == patient_profile.id

          # For objects that don't have clear patient relationship, deny access
          return False


class IsDoctorOwner(permissions.BasePermission):
      """
      Allow access only if the object belongs to the requesting doctor.
      Works with various model types by checking the doctor relationship.
      """

      def has_object_permission(self, request, view, obj):
          if not request.user or not request.user.is_authenticated:
              return False

          # Users must be doctors to own doctor-related objects
          if user_role(request.user) != 'doctor':
              return False

          try:
              doctor_profile = request.user.doctor_profile
          except ObjectDoesNotExist:
              return False

          # Check different object types
          if hasattr(obj, 'doctor'):
              # Appointment
              return obj.doctor_id == doctor_profile.id

          elif hasattr(obj, 'user'):
              # DoctorProfile
              return obj.user_id == request.user.id

          elif hasattr(obj, 'session') and hasattr(obj.session, 'patient'):
              # AIChatMessage - check if doctor has relationship with patient
              try:
                  # Doctor can access if they have any appointments with this patient
                  from ..models import Appointment  # Adjust import path as needed
                  return Appointment.objects.filter(
                      doctor=doctor_profile,
                      patient=obj.session.patient
                  ).exists()
              except:
                  return False

          elif hasattr(obj, 'patient'):
              # AIChatSession or TriageCase - check if doctor has relationship with patient
              try:
                  from ..models import Appointment  # Adjust import path as needed
                  return Appointment.objects.filter(
                      doctor=doctor_profile,
                      patient=obj.patient
                  ).exists()
              except:
                  return False

          # For objects that don't have clear doctor relationship, deny access
          return False


class IsReceptionistOrAbove(permissions.BasePermission):
      """
      Allow access only to receptionists and clinic managers.
      """

      def has_permission(self, request, view):
          if not request.user or not request.user.is_authenticated:
              return False

          role = user_role(request.user)
          return role in {'receptionist', 'clinic_manager'}


class CanCreateInvoice(permissions.BasePermission):
      """
      Allow invoice creation only to receptionists and clinic managers.
      (Same as IsReceptionistOrAbove but more explicitly named for clarity)
      """

      def has_permission(self, request, view):
          if not request.user or not request.user.is_authenticated:
              return False

          role = user_role(request.user)
          return role in {'receptionist', 'clinic_manager'}


class IsOwnerOrClinicStaff(permissions.BasePermission):
      """
      Allow access if the user is the object owner OR is clinic staff.
      Useful for endpoints where owners can access their own data and staff can access all.
      """

      def has_object_permission(self, request, view, obj):
          # Clinic staff can access everything
          if IsClinicStaff().has_permission(request, view):
              return True

          # Otherwise, check if user owns the object
          # Try patient ownership first
          if IsPatientOwner().has_object_permission(request, view, obj):
              return True

          # Then try doctor ownership
          if IsDoctorOwner().has_object_permission(request, view, obj):
              return True

          return False


class IsSelfOrClinicStaff(permissions.BasePermission):
      """
      Allow access if the user is accessing their own profile OR is clinic staff.
      Used for profile endpoints where users can view/edit their own data.
      """

      def has_object_permission(self, request, view, obj):
          # Clinic staff can access everything
          if IsClinicStaff().has_permission(request, view):
              return True

          # Users can only access their own user object
          if hasattr(obj, 'user'):
              return obj.user == request.user

          # For profile objects, check if it belongs to the user
          if hasattr(obj, 'user'):
              return obj.user == request.user

          return False


  # Optional: Additional permissions for specific use cases

class CanEditOwnAppointment(permissions.BasePermission):
      """
      Allow patients to edit only their own appointments (with restrictions).
      Staff can edit appointments according to their roles.
      """

      def has_object_permission(self, request, view, obj):
          # Clinic staff can edit appointments based on their roles
          if IsClinicStaff().has_permission(request, view):
              role = user_role(request.user)
              if role == 'doctor':
                  # Doctors can only edit appointments for their patients
                  try:
                      doctor_profile = request.user.doctor_profile
                      return obj.doctor_id == doctor_profile.id
                  except ObjectDoesNotExist:
                      return False
              elif role in {'receptionist', 'clinic_manager'}:
                  # Receptionists and managers can edit any appointment
                  return True
              return False

          # Patients can only edit their own pending appointments
          if user_role(request.user) == 'patient':
              try:
                  patient_profile = request.user.patient_profile
                  # Patients can only edit their own appointments that are not completed/cancelled
                  return (obj.patient_id == patient_profile.id and
                         obj.status in ['pending', 'confirmed'])
              except ObjectDoesNotExist:
                  return False

          return False


class CanViewOwnMedicalData(permissions.BasePermission):
      """
      Allow patients to view their own medical data (triage cases, chat sessions).
      Staff can view data according to their roles and patient relationships.
      """

      def has_object_permission(self, request, view, obj):
          # Clinic staff can access based on their roles
          if IsClinicStaff().has_permission(request, view):
              role = user_role(request.user)
              if role == 'doctor':
                  # Doctors can access data for their patients
                  try:
                      doctor_profile = request.user.doctor_profile
                      if hasattr(obj, 'patient'):
                          return obj.patient_id == doctor_profile.patient_set.values_list('id', flat=True)
                      elif hasattr(obj, 'session') and hasattr(obj.session, 'patient'):
                          return obj.session.patient_id == doctor_profile.patient_set.values_list('id', flat=True)
                  except ObjectDoesNotExist:
                      return False
              elif role in {'receptionist', 'clinic_manager'}:
                  # Receptionists and managers can access all medical data
                  return True
              return False

          # Patients can only access their own medical data
          if user_role(request.user) == 'patient':
              try:
                  patient_profile = request.user.patient_profile
                  if hasattr(obj, 'patient'):
                      return obj.patient_id == patient_profile.id
                  elif hasattr(obj, 'session') and hasattr(obj.session, 'patient'):
                      return obj.session.patient_id == patient_profile.id
              except ObjectDoesNotExist:
                  return False

          return False
