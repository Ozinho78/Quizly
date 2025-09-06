from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

def exception_handler_status500(exc, context):
    # Erst DRF-Default versuchen (gibt z. B. 400/404/403 etc. zurück)
    response = exception_handler(exc, context)

    if response is None:
        # Eigene 500-Antwort + kurzer Log
        # logger.exception(...) würde den Trace loggen; logger.error hält es knapper.
        logger.error('Unexpected error: %s', str(exc))
        return Response({'detail': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response


