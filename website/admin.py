from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, PatientProfile, Appointment, PatientReport  # explicitly import all models you want to register

# -----------------------------
# Custom admin for CustomUser
# -----------------------------
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'fname', 'lname', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password', 'fname', 'mname', 'lname', 'number', 'role')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'number', 'password1', 'password2', 'fname', 'mname', 'lname', 'role', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ('email', 'fname', 'lname')
    ordering = ('email',)

class PatientReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'staff', 'diagnosis', 'services_provided', 'barangay', 'date_created')
    search_fields = ('patient__fname', 'patient__lname', 'diagnosis', 'services_provided', 'barangay')


class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('uid', 'fname', 'lname', 'gender', 'blood_type', 'user')
    search_fields = ('uid', 'fname', 'lname', 'user__username')
# -----------------------------
# Register models
# -----------------------------
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(PatientProfile, PatientProfileAdmin)
admin.site.register(Appointment)
admin.site.register(PatientReport, PatientReportAdmin)

