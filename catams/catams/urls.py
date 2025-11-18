from django.contrib import admin
from django.urls import path, include
from timesheets import views_portal
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('portal/hr/create-account/', views_portal.hr_create_account, name='hr_create_account'),
    path('portal/messages/', include('messaging.urls')),
    path('accounts/logout/', views.logout_now),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # login/logout/password views
    path('portal/', include('timesheets.portal_urls')),
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('portal/ta/request/', views_portal.ta_request, name='ta_request'),
]
