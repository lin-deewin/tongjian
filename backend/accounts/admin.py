from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User

class CreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email',)

class ChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'

@admin.register(User)
class ReaderAdmin(UserAdmin):
    form, add_form = ChangeForm, CreationForm
    ordering = ('email',)
    search_fields = ('email',)
    list_display = ('email', 'is_active', 'is_staff', 'date_joined')
    fieldsets = ((None, {'fields': ('email', 'password')}),
                 ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                 ('时间', {'fields': ('last_login', 'date_joined')}))
    add_fieldsets = ((None, {'fields': ('email', 'password1', 'password2', 'is_staff')}),)
