from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('xrpl/', include('xrpl_api.urls')),  # Include the xrpl_api app's URLs
]