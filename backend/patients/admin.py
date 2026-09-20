from django.contrib import admin

from .models import Invoice, PatientProfile, UserRole


admin.site.register(UserRole)
admin.site.register(PatientProfile)
admin.site.register(Invoice)