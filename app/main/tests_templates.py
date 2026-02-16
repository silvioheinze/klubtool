"""
Unit tests that verify all page templates exist.
Prevents regressions when templates are renamed or removed.
"""
from django.test import TestCase
from django.template.loader import get_template


class BaseTemplateTests(TestCase):
    """Test base and shared templates exist."""

    def test_base_template_exists(self):
        get_template('_base.html')


class PagesTemplatesTests(TestCase):
    """Test templates for pages app."""

    def test_help_template_exists(self):
        get_template('help.html')

    def test_home_template_exists(self):
        get_template('home.html')

    def test_documentation_template_exists(self):
        get_template('documentation.html')

    def test_personal_calendar_list_partial_template_exists(self):
        get_template('pages/personal_calendar_list_partial.html')

    def test_calendar_month_partial_template_exists(self):
        get_template('pages/calendar_month_partial.html')

    def test_personal_calendar_export_pdf_template_exists(self):
        get_template('pages/personal_calendar_export_pdf.html')


class UserTemplatesTests(TestCase):
    """Test templates for user app."""

    def test_confirm_delete_template_exists(self):
        get_template('user/confirm_delete.html')

    def test_signup_template_exists(self):
        get_template('user/signup.html')

    def test_settings_template_exists(self):
        get_template('user/settings.html')

    def test_login_template_exists(self):
        get_template('user/login.html')

    def test_edit_template_exists(self):
        get_template('user/edit.html')

    def test_list_template_exists(self):
        get_template('user/list.html')

    def test_role_list_template_exists(self):
        get_template('user/role_list.html')

    def test_role_form_template_exists(self):
        get_template('user/role_form.html')

    def test_role_confirm_delete_template_exists(self):
        get_template('user/role_confirm_delete.html')

    def test_admin_user_form_template_exists(self):
        get_template('user/admin_user_form.html')

    def test_admin_settings_template_exists(self):
        get_template('user/admin_settings.html')


class AccountTemplatesTests(TestCase):
    """Test templates for django-allauth account (overrides)."""

    def test_login_template_exists(self):
        get_template('account/login.html')

    def test_signup_template_exists(self):
        get_template('account/signup.html')

    def test_logout_template_exists(self):
        get_template('account/logout.html')

    def test_password_change_template_exists(self):
        get_template('account/password_change.html')

    def test_email_confirm_template_exists(self):
        get_template('account/email_confirm.html')


class MotionTemplatesTests(TestCase):
    """Test templates for motion app."""

    def test_motion_list_template_exists(self):
        get_template('motion/motion_list.html')

    def test_motion_detail_template_exists(self):
        get_template('motion/motion_detail.html')

    def test_motion_form_template_exists(self):
        get_template('motion/motion_form.html')

    def test_motion_confirm_delete_template_exists(self):
        get_template('motion/motion_confirm_delete.html')

    def test_motion_vote_template_exists(self):
        get_template('motion/motion_vote.html')

    def test_motion_attachment_template_exists(self):
        get_template('motion/motion_attachment.html')

    def test_motion_status_change_template_exists(self):
        get_template('motion/motion_status_change.html')

    def test_motion_status_confirm_delete_template_exists(self):
        get_template('motion/motion_status_confirm_delete.html')

    def test_motion_group_decision_template_exists(self):
        get_template('motion/motion_group_decision.html')

    def test_motion_group_decision_confirm_delete_template_exists(self):
        get_template('motion/motion_group_decision_confirm_delete.html')

    def test_motion_vote_confirm_delete_template_exists(self):
        get_template('motion/motion_vote_confirm_delete.html')

    def test_motion_export_pdf_template_exists(self):
        get_template('motion/motion_export_pdf.html')

    def test_inquiry_list_template_exists(self):
        get_template('motion/inquiry_list.html')

    def test_inquiry_detail_template_exists(self):
        get_template('motion/inquiry_detail.html')

    def test_inquiry_form_template_exists(self):
        get_template('motion/inquiry_form.html')

    def test_inquiry_confirm_delete_template_exists(self):
        get_template('motion/inquiry_confirm_delete.html')

    def test_inquiry_attachment_template_exists(self):
        get_template('motion/inquiry_attachment.html')

    def test_inquiry_status_change_template_exists(self):
        get_template('motion/inquiry_status_change.html')

    def test_inquiry_status_confirm_delete_template_exists(self):
        get_template('motion/inquiry_status_confirm_delete.html')


class LocalTemplatesTests(TestCase):
    """Test templates for local app."""

    def test_local_list_template_exists(self):
        get_template('local/local_list.html')

    def test_local_detail_template_exists(self):
        get_template('local/local_detail.html')

    def test_local_form_template_exists(self):
        get_template('local/local_form.html')

    def test_local_confirm_delete_template_exists(self):
        get_template('local/local_confirm_delete.html')

    def test_council_name_form_template_exists(self):
        get_template('local/council_name_form.html')

    def test_council_list_template_exists(self):
        get_template('local/council_list.html')

    def test_council_detail_template_exists(self):
        get_template('local/council_detail.html')

    def test_council_form_template_exists(self):
        get_template('local/council_form.html')

    def test_council_confirm_delete_template_exists(self):
        get_template('local/council_confirm_delete.html')

    def test_term_list_template_exists(self):
        get_template('local/term_list.html')

    def test_term_detail_template_exists(self):
        get_template('local/term_detail.html')

    def test_term_form_template_exists(self):
        get_template('local/term_form.html')

    def test_term_confirm_delete_template_exists(self):
        get_template('local/term_confirm_delete.html')

    def test_term_seat_distribution_list_template_exists(self):
        get_template('local/term_seat_distribution_list.html')

    def test_term_seat_distribution_form_template_exists(self):
        get_template('local/term_seat_distribution_form.html')

    def test_term_seat_distribution_template_exists(self):
        get_template('local/term_seat_distribution.html')

    def test_party_list_template_exists(self):
        get_template('local/party_list.html')

    def test_party_detail_template_exists(self):
        get_template('local/party_detail.html')

    def test_party_form_template_exists(self):
        get_template('local/party_form.html')

    def test_party_confirm_delete_template_exists(self):
        get_template('local/party_confirm_delete.html')

    def test_session_detail_template_exists(self):
        get_template('local/session_detail.html')

    def test_session_form_template_exists(self):
        get_template('local/session_form.html')

    def test_session_confirm_delete_template_exists(self):
        get_template('local/session_confirm_delete.html')

    def test_session_export_pdf_template_exists(self):
        get_template('local/session_export_pdf.html')

    def test_council_committees_export_pdf_template_exists(self):
        get_template('local/council_committees_export_pdf.html')

    def test_committee_list_template_exists(self):
        get_template('local/committee_list.html')

    def test_committee_detail_template_exists(self):
        get_template('local/committee_detail.html')

    def test_committee_form_template_exists(self):
        get_template('local/committee_form.html')

    def test_committee_confirm_delete_template_exists(self):
        get_template('local/committee_confirm_delete.html')

    def test_committee_meeting_form_template_exists(self):
        get_template('local/committee_meeting_form.html')

    def test_committee_meeting_detail_template_exists(self):
        get_template('local/committee_meeting_detail.html')

    def test_committee_meeting_confirm_delete_template_exists(self):
        get_template('local/committee_meeting_confirm_delete.html')

    def test_committee_member_form_template_exists(self):
        get_template('local/committee_member_form.html')

    def test_session_attachment_form_template_exists(self):
        get_template('local/session_attachment_form.html')

    def test_session_invitation_form_template_exists(self):
        get_template('local/session_invitation_form.html')

    def test_session_cancel_confirm_template_exists(self):
        get_template('local/session_cancel_confirm.html')

    def test_session_minutes_form_template_exists(self):
        get_template('local/session_minutes_form.html')

    def test_committee_meeting_attachment_form_template_exists(self):
        get_template('local/committee_meeting_attachment_form.html')


class GroupTemplatesTests(TestCase):
    """Test templates for group app."""

    def test_group_list_template_exists(self):
        get_template('group/group_list.html')

    def test_group_detail_template_exists(self):
        get_template('group/group_detail.html')

    def test_group_form_template_exists(self):
        get_template('group/group_form.html')

    def test_group_confirm_delete_template_exists(self):
        get_template('group/group_confirm_delete.html')

    def test_group_calendar_partial_template_exists(self):
        get_template('group/group_calendar_partial.html')

    def test_group_meetings_list_partial_template_exists(self):
        get_template('group/group_meetings_list_partial.html')

    def test_member_detail_template_exists(self):
        get_template('group/member_detail.html')

    def test_member_form_template_exists(self):
        get_template('group/member_form.html')

    def test_member_confirm_delete_template_exists(self):
        get_template('group/member_confirm_delete.html')

    def test_meeting_list_template_exists(self):
        get_template('group/meeting_list.html')

    def test_meeting_detail_template_exists(self):
        get_template('group/meeting_detail.html')

    def test_meeting_form_template_exists(self):
        get_template('group/meeting_form.html')

    def test_meeting_confirm_delete_template_exists(self):
        get_template('group/meeting_confirm_delete.html')

    def test_meeting_agenda_export_pdf_template_exists(self):
        get_template('group/meeting_agenda_export_pdf.html')

    def test_meeting_minutes_export_pdf_template_exists(self):
        get_template('group/meeting_minutes_export_pdf.html')

    def test_meeting_cancel_confirm_template_exists(self):
        get_template('group/meeting_cancel_confirm.html')

    def test_member_invite_template_exists(self):
        get_template('group/member_invite.html')

    def test_group_meetings_export_pdf_template_exists(self):
        get_template('group/group_meetings_export_pdf.html')


class ErrorTemplatesTests(TestCase):
    """Test error page templates exist."""

    def test_403_template_exists(self):
        get_template('403.html')
