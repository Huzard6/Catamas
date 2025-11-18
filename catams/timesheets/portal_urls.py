from . import views_portal as v
from django.urls import path
from . import views_portal as v

urlpatterns = [
    path('ta/', v.ta_dashboard, name='ta_dashboard'),
    path('ta/courses/', v.ta_courses, name='ta_courses'),
    path('ta/apply/', v.ta_new, name='ta-apply-legacy'),
    path('ta/unit/<int:unit_id>/summary/', v.ta_unit_summary, name='ta_unit_summary'),
    path('ta/unit/<int:unit_id>/adjust-hours/', v.ta_adjust_hours, name='ta_adjust_hours'),
    path('uc/unit/<int:unit_id>/adjust-hours/', v.uc_adjust_hours, name='uc-adjust-hours'),
    path('uc/courses/', v.lecturer_courses, name='uc-courses'),
path('ta/requests/', v.ta_ts_inbox, name='ta-ts-inbox'),


# Casual application routes (via TA/UC chain)
path('casual/apply/', v.casual_apply_new, name='casual-apply'),
path('casual/applications/', v.casual_my_apps, name='casual-my-apps'),
path('ta/casual-requests/', v.ta_casual_inbox, name='ta-casual-inbox'),
path('ta/casual/<int:pk>/comment/', v.ta_casual_comment, name='ta-casual-comment'),
path('ta/casual/<int:pk>/forward/', v.ta_casual_forward, name='ta-casual-forward'),
    path('ta/ts/<int:pk>/comment/', v.ta_ts_comment, name='ta-ts-comment'),
    path('ta/ts/<int:pk>/forward/', v.ta_ts_forward, name='ta-ts-forward'),
path('unit-coordinator/casual-requests/', v.uc_casual_inbox, name='uc-casual-inbox'),
path('unit-coordinator/casual/<int:pk>/forward/', v.uc_casual_forward, name='uc-casual-forward'),
path('unit-coordinator/casual/<int:pk>/reject/', v.uc_casual_reject, name='uc-casual-reject'),
path('hr/casual-requests/', v.hr_casual_inbox, name='hr-casual-inbox'),
path('hr/casual/<int:pk>/approve/', v.hr_casual_approve, name='hr-casual-approve'),
path('hr/casual/<int:pk>/reject/', v.hr_casual_reject, name='hr-casual-reject'),


# TA application routes
path('ta/new/', v.ta_new, name='ta-new'),
path('ta/my/', v.ta_my, name='ta-my'),
    path('ta/applications/', v.ta_my, name='ta-applications-legacy'),
path('unit-coordinator/ta-requests/', v.uc_ta_inbox, name='uc-ta-inbox'),
path('unit-coordinator/ta/<int:pk>/forward/', v.uc_ta_forward, name='uc-ta-forward'),
path('unit-coordinator/ta/<int:pk>/reject/', v.uc_ta_reject, name='uc-ta-reject'),
path('hr/ta-requests/', v.hr_ta_inbox, name='hr-ta-inbox'),
path('hr/ta/<int:pk>/approve/', v.hr_ta_approve, name='hr-ta-approve'),
path('hr/ta/<int:pk>/reject/', v.hr_ta_reject, name='hr-ta-reject'),

    path('api/unit/<int:unit_id>/', v.unit_api, name='unit-api'),
    path('', v.home, name='portal-home'),
    # tutor
    path('casual/requests/', v.tutor_requests, name='casual-requests'),
    path('casual/new/', v.tutor_new, name='casual-new'),
    path('casual/<int:pk>/send/', v.tutor_send, name='casual-send'),
    path('casual/<int:pk>/', v.tutor_detail, name='casual-detail'),
    path('casual/<int:pk>/edit/', v.tutor_edit, name='casual-edit'),
    path('casual/<int:pk>/resubmit/', v.tutor_resubmit, name='casual-resubmit'),
    path('casual/<int:pk>/delete/', v.tutor_delete, name='casual-delete'),
    # lecturer
    path('unit-coordinator/requests/', v.lecturer_inbox, name='lecturer-inbox'),
    path('unit-coordinator/courses/', v.lecturer_courses, name='lecturer-courses'),
    path('unit-coordinator/<int:pk>/approve/', v.lecturer_approve, name='lecturer-approve'),
    path('unit-coordinator/<int:pk>/reject/', v.lecturer_reject, name='lecturer-reject'),
    # hr
    path('hr/requests/', v.hr_inbox, name='hr-inbox'),
    path('hr/<int:pk>/approve/', v.hr_approve, name='hr-approve'),
    path('hr/<int:pk>/reject/', v.hr_reject, name='hr-reject'),
    path('hr/courses/', v.hr_courses, name='hr-courses'),
    path('hr/change-requests/<int:pk>/reject/', v.hr_change_reject, name='hr-change-reject'),
    path('hr/change-requests/<int:pk>/approve/', v.hr_change_approve, name='hr-change-approve'),
    path('hr/change-requests/', v.hr_changes_list, name='hr-changes'),
    path('casual/change-requests/<int:pk>/reject/', v.casual_change_reject, name='casual-change-reject'),
    path('casual/change-requests/<int:pk>/approve/', v.casual_change_approve, name='casual-change-approve'),
    path('casual/change-requests/', v.casual_changes_list, name='casual-changes'),
    path('uc/changes/<int:pk>/delete/', v.uc_change_delete, name='uc-change-delete'),
    path('uc/changes/<int:pk>/send/', v.uc_change_send, name='uc-change-send'),
    path('uc/changes/new/', v.uc_change_new, name='uc-change-new'),
    path('uc/changes/', v.uc_changes_list, name='uc-changes'),
    path('hr/courses/new/', v.hr_course_edit, name='hr-course-new'),
    path('hr/courses/<int:pk>/edit/', v.hr_course_edit, name='hr-course-edit'),
    path('hr/courses/<int:pk>/delete/', v.hr_course_delete, name='hr-course-delete'),
    path('hr/accounts/', v.hr_accounts, name='hr-accounts'),
    path('uc/unit/<int:unit_id>/summary/', v.uc_unit_summary, name='uc-unit-summary'),
]
urlpatterns += [
    path('me/', v.my_profile, name='portal_my_profile'),
    path('api/me/phd', v.api_me_phd, name='portal_api_me_phd'),
]
