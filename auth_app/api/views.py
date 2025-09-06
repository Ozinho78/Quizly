from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from auth_app.api.serializers import RegisterSerializer


class RegisterView(APIView):
    """
    API endpoint for registering a new user.
    """

    def post(self, request):
        """
        Handle POST requests to create a new user.
        """
        serializer = RegisterSerializer(data=request.data)  # init serializer with request data

        if serializer.is_valid():  # validate input
            serializer.save()  # create user
            return Response({'detail': 'User created successfully!'}, status=status.HTTP_201_CREATED)

        # return validation errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
