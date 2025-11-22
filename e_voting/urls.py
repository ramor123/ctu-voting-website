from django.contrib import admin
from django.urls import path, include
from voting.views import landing  # IMPORTANT: Ensure you create landing view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', landing, name='landing'),  # LANDING PAGE ROOT
    path('account/', include('account.urls')),
    path('administrator/', include('administrator.urls')),
    path('voting/', include('voting.urls')),
    path('admin/', admin.site.urls),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)