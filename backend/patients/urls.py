from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    health_check,
    ai_triage,
    login_user,
    me,
    register_user,
    ai_summary,
    PatientProfileListCreateView,
    AppointmentListCreateView,
    AIChatSessionListCreateView,
    AIChatMessageListCreateView,
    TriageCreateView,
    InvoiceListCreateView,
)

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('register/', register_user, name='register-user'),
    path('login/', login_user, name='login-user'),
    path('me/', me, name='me'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('ai-triage/', ai_triage, name='ai-triage'),
    path('ai-summary/', ai_summary, name='ai-summary'),
    path('patients/', PatientProfileListCreateView.as_view(), name='patients-list-create'),
    path('appointments/', AppointmentListCreateView.as_view(), name='appointments-list-create'),
    path('chat-sessions/', AIChatSessionListCreateView.as_view(), name='chat-sessions-list-create'),
    path('chat-messages/', AIChatMessageListCreateView.as_view(), name='chat-messages-list-create'),
    path('triage/', TriageCreateView.as_view(), name='triage-create'),
    path('billing/invoices/', InvoiceListCreateView.as_view(), name='invoice-list-create'),
]
