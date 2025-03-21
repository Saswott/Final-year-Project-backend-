from django.http import HttpResponse

def home(request):  # Ensure request is an argument
    return HttpResponse("Hello, world!")

