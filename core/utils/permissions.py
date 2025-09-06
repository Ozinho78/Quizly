from rest_framework.permissions import SAFE_METHODS, BasePermission  # Basis für eigene Permissions
from auth_app.models import Profile  # Profiltyp prüfen

class IsOwnerOrReadOnly(BasePermission):                              # nur Owner darf schreibend zugreifen
    message = 'Forbidden: not the owner of this profile.'             # 403-Fehlermeldung

    def has_object_permission(self, request, view, obj):              # objektbezogene Prüfung
        if request.method in SAFE_METHODS:                            # GET/HEAD/OPTIONS → immer erlaubt
            return True
        return getattr(obj, 'user_id', None) == getattr(request.user, 'id', None)  # PATCH/PUT/DELETE nur Owner


class IsBusinessUser(BasePermission):  # <<< NEW
    message = 'Forbidden: only business users can create offers.'  # 403-Fehlermeldung

    def has_permission(self, request, view):  # view-weite Prüfung
        # nicht eingeloggt → DRF behandelt als 401
        if not request.user or not request.user.is_authenticated:
            return False
        # true, wenn es ein Profil mit type='business' zum User gibt
        return Profile.objects.filter(user=request.user, type='business').exists()