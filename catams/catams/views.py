
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_now(request):
    # Allow GET logout for simplicity in this demo project
    logout(request)
    return redirect('/accounts/login/')
