from django.http import HttpResponse, HttpResponseForbidden

def home(request):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':  # example check
        return HttpResponseForbidden("Not allowed")
    return HttpResponse("")
