from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(url='/medipal/', permanent=False)),  # redirect root → /medipal/
    path('medipal/', views.home, name='medipal'),                     # actual home view
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('profile/edit/', views.edit_patient_profile, name='edit_patient_profile'),
    path('logout/', views.logout_view, name='logout'),
    path('checker/', views.checker, name='checker'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/add-report/', views.add_patient_report, name='add_patient_report'),
    path('staff/manage-events/', views.manage_events, name='manage_events'),
]
