from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter

from apps.accounts.models import OAuthConnection


class RestrictSignupAccountAdapter(DefaultAccountAdapter):
    """Restringe el alta (signup) a una allowlist de emails.

    Sin esto, cualquiera puede registrarse con cualquier email (allauth con
    EMAIL_VERIFICATION='none') y se le crea org+workspace automaticamente.
    Config :code:`ALLOWED_SIGNUP_EMAILS` como lista separada por comas en env
    (ej. "cagriostroxd@gmail.com,oscar@mercadodigital.pro"). Si la variable no
    esta definida, el alta queda CERRADA (default seguro).
    """

    def is_open_for_signup(self, request):
        # El alta solo esta abierta si hay allowlist definida y el mail entra.
        # El gate real del email se hace en clean_email (por eso is_open=True
        # cuando la allowlist existe, para que allauth llegue a la validacion).
        from django.conf import settings
        allowed = settings.ALLOWED_SIGNUP_EMAILS
        return bool(allowed)

    def clean_email(self, email):
        email = super().clean_email(email)
        from django.conf import settings
        allowed = settings.ALLOWED_SIGNUP_EMAILS or []
        if allowed and email.lower() not in {a.lower() for a in allowed}:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                "Este email no está autorizado para registrarse. Contactá al administrador."
            )
        return email


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter that syncs Google social logins to OAuthConnection."""

    def populate_user(self, request, sociallogin, data):
        """Set user.name from Google profile (custom User model has 'name', not first/last)."""
        user = super().populate_user(request, sociallogin, data)
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip()
        if full_name and not user.name:
            user.name = full_name
        return user

    def save_user(self, request, sociallogin, form=None):
        """Create OAuthConnection after saving a new social signup."""
        user = super().save_user(request, sociallogin, form)
        self._sync_oauth_connection(user, sociallogin)
        return user

    def pre_social_login(self, request, sociallogin):
        """Sync OAuthConnection for returning users and auto-connected accounts."""
        super().pre_social_login(request, sociallogin)
        if sociallogin.is_existing:
            self._sync_oauth_connection(sociallogin.user, sociallogin)

    def _sync_oauth_connection(self, user, sociallogin):
        account = sociallogin.account
        if account.provider != "google":
            return
        provider_email = ""
        for ea in sociallogin.email_addresses:
            provider_email = ea.email
            break
        OAuthConnection.objects.update_or_create(
            provider=OAuthConnection.Provider.GOOGLE,
            provider_user_id=account.uid,
            defaults={"user": user, "provider_email": provider_email},
        )
