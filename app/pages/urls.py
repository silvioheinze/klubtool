from django.urls import path
from .views import DocumentationPageView, HelpPageView, HomePageView, personal_calendar_export_ics, personal_calendar_export_pdf

urlpatterns = [
    path("documentation", DocumentationPageView.as_view(), name="documentation"),
    path("help", HelpPageView.as_view(), name="help"),
    path("", HomePageView.as_view(), name="home"),
    path("calendar/export.ics", personal_calendar_export_ics, name="personal-calendar-export-ics"),
    path("calendar/export.pdf", personal_calendar_export_pdf, name="personal-calendar-export-pdf"),
]