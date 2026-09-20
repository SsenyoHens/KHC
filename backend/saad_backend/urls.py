from django.urls import path, include
from rest_framework.routers import DefaultRouter
from patients import views
from django.contrib import admin

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'patients', views.PatientProfileViewSet, basename='patient')
router.register(r'doctors', views.DoctorProfileViewSet, basename='doctor')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'appointments', views.AppointmentViewSet, basename='appointment')
router.register(r'chatsessions', views.AIChatSessionViewSet, basename='chatsession')
router.register(r'chatmessages', views.AIChatMessageViewSet, basename='chatmessage')
router.register(r'triages', views.TriageCaseViewSet, basename='triage')
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')

api_urlpatterns = [
      # Authentication endpoints
      path('health/', views.health_check, name='health-check'),
      path('register/', views.register_user, name='register'),
      path('login/', views.login_user, name='login'),
      path('logout/', views.logout_user, name='logout'),
      path('me/', views.me, name='me'),

      # AI Triage endpoints
      path('ai/triage/', views.ai_triage, name='ai-triage'),
      path('ai/summary/', views.ai_summary, name='ai-summary'),

      # Dashboard endpoints
      path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
      path('dashboard/overview/', views.system_overview, name='system-overview'),

      # Include all ViewSet endpoints
      path('', include(router.urls)),
  ]

urlpatterns = [
      path('api/', include(api_urlpatterns)),
      # Optional: admin interface
      path('admin/', admin.site.urls),
  ]
