import pytest  # required to define shared fixtures


def pytest_configure():
    '''
    Ensures Django knows this is a test run; place for any global test tweaks.
    '''
    # Intentionally left simple; extend if you need global settings overrides.
    # For example, to force secure cookies off in tests, you could tweak settings here.
    # from django.conf import settings
    # settings.SESSION_COOKIE_SECURE = False
    # settings.CSRF_COOKIE_SECURE = False
    pass