from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth import get_user_model

User = get_user_model()

# --- Wichtig: erst den bereits registrierten User-Admin deregistrieren ---
try:
    # Entfernt den von Django eingebauten UserAdmin, damit wir neu registrieren können
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    # Falls noch nicht registriert (z. B. in manchen Reload-Szenarien) einfach ignorieren
    pass
  
@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Customizes the built-in User admin to show the primary key (ID).

    This makes it easy to read the user's database ID directly in the
    changelist and the detail page without opening a shell.
    """
    # show ID column in the users list
    list_display = (
        'id',          # <-- primary key visible in list
        'username',
        'email',
        'is_staff',
        'is_active',
        'date_joined',
    )

    # allow filtering and searching as usual
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_superuser', 'is_active')

    # make 'id' visible and read-only on the detail page
    readonly_fields = ('id',)

    # extend fieldsets to include the read-only 'id' at the top
    fieldsets = (
        (None, {'fields': ('id', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': (
            'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
        )}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
