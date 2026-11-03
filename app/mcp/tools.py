"""MCP tools for district events, motions, and inquiries."""

import base64
import binascii
import ipaddress
import json
import socket
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import QueryDict
from django.utils import timezone

from district.forms import (
    CommitteeMeetingAttachmentForm,
    CommitteeMeetingForm,
    DistrictEventForm,
    SessionAttachmentForm,
)
from district.models import (
    Committee,
    CommitteeMeeting,
    CommitteeMeetingAttachment,
    CommitteeParticipationSubstitute,
    District,
    DistrictEvent,
    Session,
    SessionAttachment,
)
from district.upload_tokens import (
    build_attachment_upload_url,
    build_committee_meeting_upload_payload,
    upload_url_response_fields,
)
from district.upload_validation import normalize_upload_filename, validate_upload_extension
from district.views import (
    _can_user_edit_committee_meeting,
    _complete_committee_meeting_if_protocol_uploaded,
    _get_user_accessible_council_ids,
    _invite_committee_meeting_if_invitation_uploaded,
    user_can_delete_session_attachment,
    user_can_manage_district_events,
    user_is_district_member,
)
from group.models import Group
from motion.forms import InquiryAttachmentForm, InquiryForm, MotionAttachmentForm, MotionForm
from motion.models import Inquiry, InquiryAttachment, Motion, MotionAttachment
from motion.views import (
    _get_user_accessible_group_ids,
    user_can_delete_inquiry_attachment,
    user_can_delete_motion_attachment,
    user_can_view_inquiry,
)

_ATTACHMENT_PARENT_TYPES = ('session', 'motion', 'inquiry', 'committee_meeting')
_UPLOAD_MAX_BYTES_SESSION = 50 * 1024 * 1024
_UPLOAD_MAX_BYTES_MOTION_INQUIRY = 10 * 1024 * 1024
_FILE_URL_MAX_REDIRECTS = 5
_FILE_URL_TIMEOUT_SECONDS = 60

_UPLOAD_FILE_SOURCE_SCHEMA = {
    'file_url': {
        'type': 'string',
        'format': 'uri',
        'description': 'HTTPS URL; the server downloads the file (preferred for large files)',
    },
    'content_base64': {
        'type': 'string',
        'description': 'File content as base64 (optional data: URL prefix allowed); use file_url for large files',
    },
}


class McpToolError(Exception):
    """Raised when a tool call fails; message is returned to the client."""

    def __init__(self, message, *, is_error=True):
        super().__init__(message)
        self.is_error = is_error


def list_tools():
    """Return MCP tool descriptors."""
    return [
        {
            'name': 'list_districts',
            'description': 'List districts the authenticated user can access, with event-management permission.',
            'inputSchema': {'type': 'object', 'properties': {}},
        },
        {
            'name': 'list_district_events',
            'description': 'List district events for a district the user belongs to.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'district_id': {'type': 'integer', 'description': 'District primary key'},
                    'upcoming_only': {
                        'type': 'boolean',
                        'description': 'If true, only return future events (default false)',
                    },
                },
                'required': ['district_id'],
            },
        },
        {
            'name': 'get_district_event',
            'description': 'Get one district event by id.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'event_id': {'type': 'integer', 'description': 'District event primary key'},
                },
                'required': ['event_id'],
            },
        },
        {
            'name': 'create_district_event',
            'description': 'Create a district event (district managers only).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'district_id': {'type': 'integer'},
                    'title': {'type': 'string'},
                    'scheduled_date': {
                        'type': 'string',
                        'description': 'ISO 8601 datetime, e.g. 2026-09-15T18:00:00+02:00',
                    },
                    'end_date': {
                        'type': 'string',
                        'description': 'Optional ISO 8601 end datetime (must be after scheduled_date)',
                    },
                    'location': {'type': 'string', 'description': 'Optional place or venue'},
                    'description': {'type': 'string'},
                    'external_link': {'type': 'string', 'format': 'uri'},
                },
                'required': ['district_id', 'title', 'scheduled_date'],
            },
        },
        {
            'name': 'update_district_event',
            'description': 'Update a district event (district managers only).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'event_id': {'type': 'integer'},
                    'title': {'type': 'string'},
                    'scheduled_date': {'type': 'string', 'description': 'ISO 8601 datetime'},
                    'end_date': {'type': 'string', 'description': 'Optional ISO 8601 end datetime'},
                    'location': {'type': 'string', 'description': 'Optional place or venue'},
                    'description': {'type': 'string'},
                    'external_link': {'type': 'string', 'format': 'uri'},
                },
                'required': ['event_id'],
            },
        },
        {
            'name': 'delete_district_event',
            'description': 'Delete a district event (district managers only).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'event_id': {'type': 'integer'},
                },
                'required': ['event_id'],
            },
        },
        {
            'name': 'list_motions',
            'description': 'Search and list motions (Anträge) with optional filters. Same access as the web list.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'search': {'type': 'string', 'description': 'Search title, text, rationale, or group name'},
                    'status': {'type': 'string', 'description': 'Motion status filter'},
                    'session_id': {'type': 'integer'},
                    'party_id': {'type': 'integer'},
                    'motion_type': {'type': 'string', 'enum': ['general', 'resolution']},
                    'tags': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Tag names'},
                    'limit': {'type': 'integer', 'description': 'Max results (default 20, max 50)'},
                    'offset': {'type': 'integer', 'description': 'Pagination offset (default 0)'},
                },
            },
        },
        {
            'name': 'list_inquiries',
            'description': 'Search and list inquiries (Anfragen) with optional filters. Same access as the web list.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'search': {'type': 'string', 'description': 'Search title, text, or group name'},
                    'status': {'type': 'string', 'description': 'Inquiry status filter'},
                    'session_id': {'type': 'integer'},
                    'party_id': {'type': 'integer'},
                    'tags': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Tag names'},
                    'limit': {'type': 'integer', 'description': 'Max results (default 20, max 50)'},
                    'offset': {'type': 'integer', 'description': 'Pagination offset (default 0)'},
                },
            },
        },
        {
            'name': 'get_motion',
            'description': 'Get one motion by id (same view access as the web UI).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'motion_id': {'type': 'integer', 'description': 'Motion primary key'},
                },
                'required': ['motion_id'],
            },
        },
        {
            'name': 'create_motion',
            'description': 'Create a motion (draft). Same permissions as the web create form.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'session_id': {'type': 'integer'},
                    'group_id': {'type': 'integer', 'description': 'Optional; defaults to first accessible group'},
                    'text': {'type': 'string'},
                    'rationale': {'type': 'string'},
                    'motion_type': {'type': 'string', 'enum': ['general', 'resolution']},
                    'committee_id': {'type': 'integer'},
                    'party_ids': {'type': 'array', 'items': {'type': 'integer'}},
                    'tags': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Tag names (or pass a comma-separated string)',
                    },
                },
                'required': ['title', 'session_id'],
            },
        },
        {
            'name': 'update_motion',
            'description': 'Update a motion. Omitted fields stay unchanged; status cannot be changed.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'motion_id': {'type': 'integer'},
                    'title': {'type': 'string'},
                    'session_id': {'type': 'integer'},
                    'group_id': {'type': 'integer'},
                    'text': {'type': 'string'},
                    'rationale': {'type': 'string'},
                    'motion_type': {'type': 'string', 'enum': ['general', 'resolution']},
                    'committee_id': {'type': 'integer'},
                    'party_ids': {'type': 'array', 'items': {'type': 'integer'}},
                    'intervention_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'User PKs of group members (Wortmeldung)',
                    },
                    'tags': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['motion_id'],
            },
        },
        {
            'name': 'get_inquiry',
            'description': 'Get one inquiry by id (same view access as the web UI).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'inquiry_id': {'type': 'integer', 'description': 'Inquiry primary key'},
                },
                'required': ['inquiry_id'],
            },
        },
        {
            'name': 'create_inquiry',
            'description': 'Create an inquiry (draft). Same permissions as the web create form.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'session_id': {'type': 'integer'},
                    'group_id': {'type': 'integer', 'description': 'Optional; defaults to first accessible group'},
                    'text': {'type': 'string'},
                    'answer': {'type': 'string'},
                    'party_ids': {'type': 'array', 'items': {'type': 'integer'}},
                    'intervention_ids': {'type': 'array', 'items': {'type': 'integer'}},
                    'tags': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['title', 'session_id'],
            },
        },
        {
            'name': 'update_inquiry',
            'description': 'Update an inquiry. Omitted fields stay unchanged; status cannot be changed.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'inquiry_id': {'type': 'integer'},
                    'title': {'type': 'string'},
                    'session_id': {'type': 'integer'},
                    'group_id': {'type': 'integer'},
                    'text': {'type': 'string'},
                    'answer': {'type': 'string'},
                    'party_ids': {'type': 'array', 'items': {'type': 'integer'}},
                    'intervention_ids': {'type': 'array', 'items': {'type': 'integer'}},
                    'tags': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['inquiry_id'],
            },
        },
        {
            'name': 'upload_session_attachment',
            'description': 'Upload a file attachment to a council session (superuser only). Provide file_url or content_base64.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'session_id': {'type': 'integer'},
                    'filename': {'type': 'string', 'description': 'Original filename including extension'},
                    **_UPLOAD_FILE_SOURCE_SCHEMA,
                    'file_type': {
                        'type': 'string',
                        'enum': ['agenda', 'budget', 'invitation', 'minutes', 'other'],
                        'description': 'Defaults to other',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['session_id', 'filename'],
            },
        },
        {
            'name': 'upload_motion_attachment',
            'description': 'Upload a file attachment to a motion (same permissions as web upload). Provide file_url or content_base64.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'motion_id': {'type': 'integer'},
                    'filename': {'type': 'string'},
                    **_UPLOAD_FILE_SOURCE_SCHEMA,
                    'file_type': {
                        'type': 'string',
                        'enum': ['document', 'image', 'spreadsheet', 'presentation', 'other'],
                        'description': 'Defaults to document',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['motion_id', 'filename'],
            },
        },
        {
            'name': 'upload_inquiry_attachment',
            'description': 'Upload a file attachment to an inquiry (same permissions as web upload). Provide file_url or content_base64.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'inquiry_id': {'type': 'integer'},
                    'filename': {'type': 'string'},
                    **_UPLOAD_FILE_SOURCE_SCHEMA,
                    'file_type': {
                        'type': 'string',
                        'enum': ['document', 'image', 'spreadsheet', 'presentation', 'other'],
                        'description': 'Defaults to document',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['inquiry_id', 'filename'],
            },
        },
        {
            'name': 'upload_committee_meeting_attachment',
            'description': (
                'Upload a file attachment to a committee meeting '
                '(same permissions as web upload: superuser or qualifying group leader). '
                'Provide file_url or content_base64.'
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'committee_meeting_id': {'type': 'integer'},
                    'filename': {'type': 'string', 'description': 'Original filename including extension'},
                    **_UPLOAD_FILE_SOURCE_SCHEMA,
                    'file_type': {
                        'type': 'string',
                        'enum': ['agenda', 'invitation', 'minutes', 'other'],
                        'description': 'Defaults to other',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['committee_meeting_id', 'filename'],
            },
        },
        {
            'name': 'create_committee_meeting_upload_url',
            'description': (
                'Create a one-time HTTPS PUT URL for uploading a committee meeting attachment '
                '(same permissions as web upload: superuser or qualifying group leader). '
                'Does not accept file content; use the returned upload_url with HTTP PUT.'
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'committee_meeting_id': {'type': 'integer'},
                    'filename': {'type': 'string', 'description': 'Original filename including extension'},
                    'file_type': {
                        'type': 'string',
                        'enum': ['agenda', 'invitation', 'minutes', 'other'],
                        'description': 'Defaults to other',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['committee_meeting_id', 'filename'],
            },
        },
        {
            'name': 'list_committees',
            'description': 'List committees (Gremien) in a district with their ids.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'district_id': {'type': 'integer', 'description': 'District primary key'},
                },
                'required': ['district_id'],
            },
        },
        {
            'name': 'list_committee_meetings',
            'description': 'List committee meetings in a district, optionally filtered by committee and date range.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'district_id': {'type': 'integer'},
                    'committee_id': {'type': 'integer', 'description': 'Optional committee filter'},
                    'from_date': {'type': 'string', 'description': 'Inclusive start date YYYY-MM-DD'},
                    'to_date': {'type': 'string', 'description': 'Inclusive end date YYYY-MM-DD'},
                },
                'required': ['district_id'],
            },
        },
        {
            'name': 'list_sessions',
            'description': 'List council sessions in a district, optionally filtered by date range.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'district_id': {'type': 'integer'},
                    'from_date': {'type': 'string', 'description': 'Inclusive start date YYYY-MM-DD'},
                    'to_date': {'type': 'string', 'description': 'Inclusive end date YYYY-MM-DD'},
                },
                'required': ['district_id'],
            },
        },
        {
            'name': 'get_committee_meeting',
            'description': 'Get committee meeting details: agenda, participants, attachments, and status.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer', 'description': 'Committee meeting primary key'},
                },
                'required': ['id'],
            },
        },
        {
            'name': 'update_committee_meeting',
            'description': (
                'Update a committee meeting. Omitted fields stay unchanged; status cannot be changed.'
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'committee_meeting_id': {'type': 'integer'},
                    'title': {'type': 'string'},
                    'location': {'type': 'string'},
                    'agenda': {
                        'type': 'string',
                        'description': 'Meeting agenda (stored as description)',
                    },
                },
                'required': ['committee_meeting_id'],
            },
        },
        {
            'name': 'list_attachments',
            'description': 'List file attachments for a session, motion, inquiry, or committee meeting.',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'parent_type': {
                        'type': 'string',
                        'enum': list(_ATTACHMENT_PARENT_TYPES),
                    },
                    'parent_id': {'type': 'integer'},
                },
                'required': ['parent_type', 'parent_id'],
            },
        },
        {
            'name': 'delete_attachment',
            'description': (
                'Permanently delete an attachment by id. Only call after explicit user confirmation. '
                'Does not revert session or meeting status.'
            ),
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'parent_type': {
                        'type': 'string',
                        'enum': list(_ATTACHMENT_PARENT_TYPES),
                    },
                    'attachment_id': {'type': 'integer'},
                },
                'required': ['parent_type', 'attachment_id'],
            },
        },
    ]


def _serialize_event(event, request=None):
    url = event.get_absolute_url()
    if request is not None:
        url = request.build_absolute_uri(url)
    payload = {
        'id': event.pk,
        'title': event.title,
        'scheduled_date': event.scheduled_date.isoformat(),
        'district_id': event.district_id,
        'description': event.description,
        'external_link': event.external_link,
        'location': event.location,
        'is_active': event.is_active,
        'url': url,
    }
    if event.end_date:
        payload['end_date'] = event.end_date.isoformat()
    else:
        payload['end_date'] = None
    return payload


def _parse_scheduled_date(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise McpToolError(f'Invalid scheduled_date: {value!r}') from exc
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _get_district_or_error(user, district_id):
    try:
        district = District.objects.get(pk=district_id, is_active=True)
    except District.DoesNotExist as exc:
        raise McpToolError(f'District {district_id} not found.') from exc
    if not user_is_district_member(user, district):
        raise McpToolError('You do not have access to this district.')
    return district


def _require_manage(user, district):
    if not user_can_manage_district_events(user, district):
        raise McpToolError('You do not have permission to manage events in this district.')


def _validate_event_fields(data, *, district, instance=None):
    form_data = {
        'title': data.get('title', getattr(instance, 'title', '')),
        'scheduled_date': data.get('scheduled_date', getattr(instance, 'scheduled_date', '')),
        'description': data.get('description', getattr(instance, 'description', '')),
        'external_link': data.get('external_link', getattr(instance, 'external_link', '')),
        'location': data.get('location', getattr(instance, 'location', '')),
        'district': district.pk,
    }
    if 'end_date' in data:
        end_val = data.get('end_date')
        if end_val in (None, ''):
            form_data['end_date'] = ''
        elif isinstance(end_val, datetime):
            form_data['end_date'] = end_val
        else:
            form_data['end_date'] = _parse_scheduled_date(end_val).strftime('%Y-%m-%dT%H:%M')
    elif instance is not None and instance.pk:
        form_data['end_date'] = instance.end_date.strftime('%Y-%m-%dT%H:%M') if instance.end_date else ''
    else:
        form_data['end_date'] = ''
    if 'scheduled_date' in data and not isinstance(form_data['scheduled_date'], datetime):
        form_data['scheduled_date'] = _parse_scheduled_date(form_data['scheduled_date']).strftime('%Y-%m-%dT%H:%M')

    form = DistrictEventForm(data=form_data, instance=instance)
    if not form.is_valid():
        raise McpToolError(json.dumps(form.errors, ensure_ascii=False))
    return form


def _tags_to_string(tags):
    """Convert tags argument (list or comma string) to form field value."""
    if tags is None:
        return ''
    if isinstance(tags, list):
        return ', '.join(str(tag).strip() for tag in tags if str(tag).strip())
    return str(tags)


def _default_group_for_user(user):
    """First accessible active group for the user (all groups for superuser)."""
    group_ids = _get_user_accessible_group_ids(user)
    if group_ids is None:
        return Group.objects.filter(is_active=True).order_by('name').first()
    if group_ids:
        return Group.objects.filter(pk__in=group_ids, is_active=True).order_by('name').first()
    return None


def _ensure_group_accessible(user, group_id):
    """Raise if the user may not use this group."""
    group_ids = _get_user_accessible_group_ids(user)
    if group_ids is not None and group_id not in group_ids:
        raise McpToolError('You do not have access to this group.')


def _resolve_group_id(user, group_id):
    """Return group PK, using default when omitted; validate access."""
    if group_id is None:
        default_group = _default_group_for_user(user)
        if default_group is None:
            raise McpToolError('group_id is required when you have no accessible group.')
        return default_group.pk
    try:
        group_id = int(group_id)
    except (TypeError, ValueError) as exc:
        raise McpToolError('Invalid group_id.') from exc
    _ensure_group_accessible(user, group_id)
    return group_id


def _user_can_create_motion_or_inquiry(user):
    if user.is_superuser or user.has_role_permission('motion.create'):
        return True
    group_ids = _get_user_accessible_group_ids(user)
    return group_ids is not None and len(group_ids) > 0


def _user_can_list_motions_or_inquiries(user):
    """Same access as MotionListView / InquiryListView."""
    if user.is_superuser or user.has_role_permission('motion.view'):
        return True
    group_ids = _get_user_accessible_group_ids(user)
    return group_ids is not None and len(group_ids) > 0


def _require_list_motions_or_inquiries(user):
    if not _user_can_list_motions_or_inquiries(user):
        raise McpToolError('You do not have permission to list motions or inquiries.')


def _parse_pagination(arguments):
    try:
        limit = int(arguments.get('limit', 20))
    except (TypeError, ValueError) as exc:
        raise McpToolError('Invalid limit.') from exc
    try:
        offset = int(arguments.get('offset', 0))
    except (TypeError, ValueError) as exc:
        raise McpToolError('Invalid offset.') from exc
    if limit < 1:
        raise McpToolError('limit must be at least 1.')
    if limit > 50:
        raise McpToolError('limit must not exceed 50.')
    if offset < 0:
        raise McpToolError('offset must not be negative.')
    return limit, offset


def _validate_choice(value, choices, field_name):
    if value is None or value == '':
        return None
    valid = {choice for choice, _label in choices}
    if value not in valid:
        raise McpToolError(f'Invalid {field_name}: {value!r}.')
    return value


def _apply_tag_name_filter(queryset, tags):
    if not tags:
        return queryset
    if isinstance(tags, str):
        tag_names = [name.strip() for name in tags.split(',') if name.strip()]
    else:
        tag_names = [str(name).strip() for name in tags if str(name).strip()]
    if not tag_names:
        return queryset
    for tag_name in tag_names:
        queryset = queryset.filter(tags__name__iexact=tag_name)
    return queryset.distinct()


def _motion_base_queryset(user):
    base = Motion.objects.all().select_related(
        'session', 'group', 'committee', 'submitted_by',
    ).prefetch_related('parties', 'interventions', 'tags').order_by('-submitted_date')
    if user.is_superuser or user.has_role_permission('motion.view'):
        return base
    group_ids = _get_user_accessible_group_ids(user)
    return base.filter(group__pk__in=group_ids) if group_ids else base.none()


def _inquiry_base_queryset(user):
    base = Inquiry.objects.filter(is_active=True).select_related(
        'session', 'group', 'submitted_by',
    ).prefetch_related('parties', 'interventions', 'tags').order_by('-submitted_date')
    if user.is_superuser or user.has_role_permission('motion.view'):
        return base
    group_ids = _get_user_accessible_group_ids(user)
    return base.filter(group__pk__in=group_ids) if group_ids else base.none()


def _filter_motions_queryset(queryset, arguments):
    search = arguments.get('search')
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(text__icontains=search)
            | Q(rationale__icontains=search)
            | Q(group__name__icontains=search)
        )
    status = _validate_choice(arguments.get('status'), Motion.STATUS_CHOICES, 'status')
    if status:
        queryset = queryset.filter(status=status)
    motion_type = _validate_choice(
        arguments.get('motion_type'),
        Motion.MOTION_TYPE_CHOICES,
        'motion_type',
    )
    if motion_type:
        queryset = queryset.filter(motion_type=motion_type)
    if arguments.get('session_id') is not None:
        queryset = queryset.filter(session_id=arguments['session_id'])
    if arguments.get('party_id') is not None:
        queryset = queryset.filter(parties=arguments['party_id'])
    queryset = _apply_tag_name_filter(queryset, arguments.get('tags'))
    return queryset


def _filter_inquiries_queryset(queryset, arguments):
    search = arguments.get('search')
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(text__icontains=search)
            | Q(group__name__icontains=search)
        )
    status = _validate_choice(arguments.get('status'), Inquiry.STATUS_CHOICES, 'status')
    if status:
        queryset = queryset.filter(status=status)
    if arguments.get('session_id') is not None:
        queryset = queryset.filter(session_id=arguments['session_id'])
    if arguments.get('party_id') is not None:
        queryset = queryset.filter(parties=arguments['party_id'])
    queryset = _apply_tag_name_filter(queryset, arguments.get('tags'))
    return queryset


def _paginated_list(queryset, *, limit, offset, serialize_fn, request, result_key):
    count = queryset.count()
    page = queryset[offset:offset + limit]
    return {
        'count': count,
        'offset': offset,
        'limit': limit,
        result_key: [serialize_fn(obj, request) for obj in page],
    }


def _user_can_view_motion(user, motion_pk):
    if user.is_superuser or user.has_role_permission('motion.view'):
        return True
    if motion_pk is None:
        return False
    try:
        motion_pk = int(motion_pk)
    except (TypeError, ValueError):
        return False
    group_id = Motion.objects.filter(pk=motion_pk).values_list('group_id', flat=True).first()
    if group_id is None:
        return False
    group_ids = _get_user_accessible_group_ids(user)
    return group_ids is not None and group_id in group_ids


def _user_can_update_motion(user, motion):
    if user.is_superuser or user.has_role_permission('motion.edit'):
        return True
    if motion.group_id is None:
        return False
    group_ids = _get_user_accessible_group_ids(user)
    return group_ids is not None and motion.group_id in group_ids


def _user_can_update_inquiry(user, inquiry):
    if user.is_superuser or user.has_role_permission('motion.edit'):
        return True
    if inquiry.group_id is None:
        return False
    group_ids = _get_user_accessible_group_ids(user)
    return group_ids is not None and inquiry.group_id in group_ids


def _decode_base64_content(content_base64):
    if not content_base64 or not isinstance(content_base64, str):
        raise McpToolError('content_base64 is required.')
    payload = content_base64.strip()
    if ',' in payload and payload.lower().startswith('data:'):
        payload = payload.split(',', 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise McpToolError('Invalid base64 content.') from exc


def _is_blocked_ip(ip):
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        return True
    if ip.is_unspecified:
        return True
    return False


def _ensure_file_url_host_allowed(hostname):
    if not hostname:
        raise McpToolError('Invalid file_url.')
    try:
        addr_infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise McpToolError(f'Could not resolve file_url host: {hostname}') from exc
    if not addr_infos:
        raise McpToolError(f'Could not resolve file_url host: {hostname}')
    for info in addr_infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            raise McpToolError('file_url host is not allowed.')


def _validate_https_file_url(file_url):
    if not file_url or not isinstance(file_url, str):
        raise McpToolError('file_url is required.')
    parsed = urlparse(file_url.strip())
    if parsed.scheme != 'https':
        raise McpToolError('file_url must use https.')
    if parsed.username or parsed.password:
        raise McpToolError('file_url must not contain credentials.')
    if not parsed.hostname:
        raise McpToolError('Invalid file_url.')
    _ensure_file_url_host_allowed(parsed.hostname)
    return file_url.strip()


def _read_response_body_limited(response, max_bytes):
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise McpToolError(f'File exceeds maximum size of {max_bytes} bytes.')
        chunks.append(chunk)
    return b''.join(chunks)


def _fetch_file_from_url(file_url, max_bytes):
    url = _validate_https_file_url(file_url)
    for _redirect in range(_FILE_URL_MAX_REDIRECTS + 1):
        response = requests.get(
            url,
            allow_redirects=False,
            timeout=_FILE_URL_TIMEOUT_SECONDS,
            stream=True,
        )
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location')
            if not location:
                raise McpToolError('Invalid redirect from file_url.')
            url = urljoin(url, location)
            continue
        if response.status_code != 200:
            raise McpToolError(f'file_url returned HTTP {response.status_code}.')
        try:
            return _read_response_body_limited(response, max_bytes)
        finally:
            response.close()
    raise McpToolError('Too many redirects from file_url.')


def _resolve_upload_content_bytes(arguments, max_bytes):
    file_url = arguments.get('file_url')
    content_base64 = arguments.get('content_base64')
    has_url = bool(file_url and str(file_url).strip())
    has_b64 = bool(content_base64 and str(content_base64).strip())
    if has_url and has_b64:
        raise McpToolError('Provide either file_url or content_base64, not both.')
    if not has_url and not has_b64:
        raise McpToolError('Either file_url or content_base64 is required.')
    if has_url:
        return _fetch_file_from_url(str(file_url).strip(), max_bytes)
    content_bytes = _decode_base64_content(content_base64)
    if len(content_bytes) > max_bytes:
        raise McpToolError(f'File exceeds maximum size of {max_bytes} bytes.')
    return content_bytes


def _build_uploaded_file(filename, content_bytes):
    if not filename or not isinstance(filename, str):
        raise McpToolError('filename is required.')
    return SimpleUploadedFile(filename, content_bytes)


def _attachment_file_size(attachment):
    try:
        return attachment.file.size
    except (OSError, ValueError):
        return None


def _serialize_attachment(attachment, request=None):
    file_url = attachment.file.url
    if request is not None:
        file_url = request.build_absolute_uri(file_url)
    payload = {
        'id': attachment.pk,
        'filename': attachment.filename,
        'file_type': attachment.file_type,
        'description': attachment.description or '',
        'url': file_url,
        'file_size': _attachment_file_size(attachment),
    }
    return payload


def _parse_date_filter(value, field_name):
    if value is None or value == '':
        return None
    text = str(value).strip()
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError as exc:
        raise McpToolError(f'Invalid {field_name}: use YYYY-MM-DD.') from exc


def _apply_scheduled_date_filters(queryset, arguments):
    from_date = _parse_date_filter(arguments.get('from_date'), 'from_date')
    to_date = _parse_date_filter(arguments.get('to_date'), 'to_date')
    if from_date:
        queryset = queryset.filter(scheduled_date__date__gte=from_date)
    if to_date:
        queryset = queryset.filter(scheduled_date__date__lte=to_date)
    return queryset


def _accessible_council_ids_in_district(user, district_id):
    district = _get_district_or_error(user, district_id)
    accessible = _get_user_accessible_council_ids(user)
    if not accessible:
        return set()
    council = getattr(district, 'council', None)
    if council is None or not council.is_active or council.pk not in accessible:
        return set()
    return {council.pk}


def _validate_attachment_parent_type(parent_type):
    if parent_type not in _ATTACHMENT_PARENT_TYPES:
        raise McpToolError(
            f'Invalid parent_type: {parent_type!r}. '
            f'Use one of: {", ".join(_ATTACHMENT_PARENT_TYPES)}.'
        )


def _user_can_view_session(user, session):
    if user.is_superuser:
        return True
    if session.council_id is None:
        return False
    return session.council_id in _get_user_accessible_council_ids(user)


def _user_can_view_committee_meeting(user, meeting):
    if user.is_superuser:
        return True
    council_id = (
        CommitteeMeeting.objects.filter(pk=meeting.pk)
        .values_list('committee__council_id', flat=True)
        .first()
    )
    if council_id is None:
        return False
    return council_id in _get_user_accessible_council_ids(user)


def _user_can_delete_committee_meeting_attachment(user, attachment):
    if user.is_superuser or attachment.uploaded_by_id == user.pk:
        return True
    return _can_user_edit_committee_meeting(user, attachment.committee_meeting)


def _serialize_committee_ref(committee):
    return {
        'id': committee.pk,
        'name': committee.name,
        'abbreviation': committee.abbreviation or '',
    }


def _serialize_committee_meeting_list_item(meeting, request=None):
    return {
        'id': meeting.pk,
        'committee': _serialize_committee_ref(meeting.committee),
        'scheduled_date': meeting.scheduled_date.isoformat(),
        'location': meeting.location or '',
        'status': meeting.status,
        'attachments': [
            _serialize_attachment(attachment, request)
            for attachment in meeting.attachments.all()
        ],
    }


def _serialize_session_list_item(session, request=None):
    return {
        'id': session.pk,
        'title': session.title,
        'scheduled_date': session.scheduled_date.isoformat(),
        'location': session.location or '',
        'status': session.status,
        'attachments': [
            _serialize_attachment(attachment, request)
            for attachment in session.attachments.all()
        ],
    }


def _serialize_committee_meeting_detail(meeting, request=None):
    role_order = Case(
        When(role='chairperson', then=Value(1)),
        When(role='vice_chairperson', then=Value(2)),
        When(role='member', then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )
    participants = list(
        meeting.committee.members.filter(is_active=True)
        .exclude(role='substitute_member')
        .select_related('user')
        .order_by(role_order, 'user__last_name', 'user__first_name')
    )
    substitute_map = {
        sub.member_id: sub.substitute_member
        for sub in CommitteeParticipationSubstitute.objects.filter(
            committee_meeting=meeting,
        ).select_related('substitute_member', 'substitute_member__user')
    }
    participant_payload = []
    for member in participants:
        substitute = substitute_map.get(member.pk)
        user = member.user
        entry = {
            'member_id': member.pk,
            'user_id': user.pk,
            'name': user.get_full_name() or user.username,
            'role': member.role,
            'substitute': None,
        }
        if substitute is not None:
            sub_user = substitute.user
            entry['substitute'] = {
                'member_id': substitute.pk,
                'user_id': sub_user.pk,
                'name': sub_user.get_full_name() or sub_user.username,
            }
        participant_payload.append(entry)
    url = meeting.get_absolute_url()
    if request is not None:
        url = request.build_absolute_uri(url)
    return {
        'id': meeting.pk,
        'title': meeting.title,
        'committee': _serialize_committee_ref(meeting.committee),
        'scheduled_date': meeting.scheduled_date.isoformat(),
        'location': meeting.location or '',
        'status': meeting.status,
        'agenda': meeting.description or '',
        'attachments': [
            _serialize_attachment(attachment, request)
            for attachment in meeting.attachments.all()
        ],
        'participants': participant_payload,
        'url': url,
    }


def _list_attachments_for_parent(parent_type, parent_id, user, request):
    _validate_attachment_parent_type(parent_type)
    if parent_type == 'session':
        session = _get_session_or_error(parent_id)
        if not _user_can_view_session(user, session):
            raise McpToolError('You do not have permission to view this session.')
        attachments = session.attachments.all()
    elif parent_type == 'motion':
        motion = _get_motion_or_error(parent_id)
        if not _user_can_view_motion(user, motion.pk):
            raise McpToolError('You do not have permission to view this motion.')
        attachments = motion.attachments.all()
    elif parent_type == 'inquiry':
        inquiry = _get_inquiry_or_error(parent_id)
        if not user_can_view_inquiry(user, inquiry.pk):
            raise McpToolError('You do not have permission to view this inquiry.')
        attachments = inquiry.attachments.all()
    else:
        meeting = _get_committee_meeting_or_error(parent_id)
        if not _user_can_view_committee_meeting(user, meeting):
            raise McpToolError('You do not have permission to view this committee meeting.')
        attachments = meeting.attachments.all()
    return {
        'parent_type': parent_type,
        'parent_id': parent_id,
        'attachments': [_serialize_attachment(a, request) for a in attachments],
    }


def _delete_attachment_by_type(parent_type, attachment_id, user, request):
    _validate_attachment_parent_type(parent_type)
    if parent_type == 'session':
        try:
            attachment = SessionAttachment.objects.select_related('session').get(pk=attachment_id)
        except SessionAttachment.DoesNotExist as exc:
            raise McpToolError(f'Attachment {attachment_id} not found.') from exc
        if not user_can_delete_session_attachment(user, attachment):
            raise McpToolError('You do not have permission to delete this attachment.')
    elif parent_type == 'motion':
        try:
            attachment = MotionAttachment.objects.select_related('motion').get(pk=attachment_id)
        except MotionAttachment.DoesNotExist as exc:
            raise McpToolError(f'Attachment {attachment_id} not found.') from exc
        if not user_can_delete_motion_attachment(user, attachment):
            raise McpToolError('You do not have permission to delete this attachment.')
    elif parent_type == 'inquiry':
        try:
            attachment = InquiryAttachment.objects.select_related('inquiry').get(pk=attachment_id)
        except InquiryAttachment.DoesNotExist as exc:
            raise McpToolError(f'Attachment {attachment_id} not found.') from exc
        if not user_can_delete_inquiry_attachment(user, attachment):
            raise McpToolError('You do not have permission to delete this attachment.')
    else:
        try:
            attachment = CommitteeMeetingAttachment.objects.select_related(
                'committee_meeting',
            ).get(pk=attachment_id)
        except CommitteeMeetingAttachment.DoesNotExist as exc:
            raise McpToolError(f'Attachment {attachment_id} not found.') from exc
        if not _user_can_delete_committee_meeting_attachment(user, attachment):
            raise McpToolError('You do not have permission to delete this attachment.')
    payload = _serialize_attachment(attachment, request)
    if attachment.file:
        attachment.file.delete(save=False)
    attachment.delete()
    return {'deleted': True, 'attachment': payload}


def _user_can_upload_session_attachment(user):
    return user.is_superuser


def _user_can_upload_motion_attachment(user, motion):
    if user.is_superuser or user.has_role_permission('motion.attach'):
        return True
    if motion.group_id is None:
        return False
    group_ids = _get_user_accessible_group_ids(user)
    return group_ids is not None and motion.group_id in group_ids


def _user_can_upload_inquiry_attachment(user, inquiry):
    if user.is_superuser or user.has_role_permission('motion.attach'):
        return True
    if inquiry.group_id is None:
        return False
    group_ids = _get_user_accessible_group_ids(user)
    return group_ids is not None and inquiry.group_id in group_ids


def _get_session_or_error(session_id):
    try:
        return Session.objects.get(pk=session_id)
    except Session.DoesNotExist as exc:
        raise McpToolError(f'Session {session_id} not found.') from exc


def _get_committee_meeting_or_error(committee_meeting_id):
    try:
        return CommitteeMeeting.objects.get(pk=committee_meeting_id)
    except CommitteeMeeting.DoesNotExist as exc:
        raise McpToolError(f'Committee meeting {committee_meeting_id} not found.') from exc


def _validate_attachment_form(form):
    if not form.is_valid():
        raise McpToolError(json.dumps(form.errors, ensure_ascii=False))
    return form


def _upload_session_attachment(arguments, user):
    session = _get_session_or_error(arguments['session_id'])
    if not _user_can_upload_session_attachment(user):
        raise McpToolError('You do not have permission to upload session attachments.')
    file_type = _validate_choice(
        arguments.get('file_type', 'other'),
        SessionAttachment.ATTACHMENT_TYPE_CHOICES,
        'file_type',
    ) or 'other'
    content_bytes = _resolve_upload_content_bytes(arguments, _UPLOAD_MAX_BYTES_SESSION)
    uploaded_file = _build_uploaded_file(arguments['filename'], content_bytes)
    form = SessionAttachmentForm(
        data={
            'file_type': file_type,
            'description': arguments.get('description', ''),
        },
        files={'file': uploaded_file},
    )
    form = _validate_attachment_form(form)
    attachment = form.save(commit=False)
    attachment.session = session
    attachment.uploaded_by = user
    attachment.save()
    return attachment


def _upload_motion_attachment(arguments, user):
    motion = _get_motion_or_error(arguments['motion_id'])
    if not _user_can_upload_motion_attachment(user, motion):
        raise McpToolError('You do not have permission to upload motion attachments.')
    file_type = _validate_choice(
        arguments.get('file_type', 'document'),
        MotionAttachment.ATTACHMENT_TYPE_CHOICES,
        'file_type',
    ) or 'document'
    content_bytes = _resolve_upload_content_bytes(arguments, _UPLOAD_MAX_BYTES_MOTION_INQUIRY)
    uploaded_file = _build_uploaded_file(arguments['filename'], content_bytes)
    form = MotionAttachmentForm(
        data={
            'file_type': file_type,
            'description': arguments.get('description', ''),
        },
        files={'file': uploaded_file},
    )
    form = _validate_attachment_form(form)
    attachment = form.save(commit=False)
    attachment.motion = motion
    attachment.uploaded_by = user
    attachment.save()
    return attachment


def _upload_inquiry_attachment(arguments, user):
    inquiry = _get_inquiry_or_error(arguments['inquiry_id'])
    if not _user_can_upload_inquiry_attachment(user, inquiry):
        raise McpToolError('You do not have permission to upload inquiry attachments.')
    file_type = _validate_choice(
        arguments.get('file_type', 'document'),
        InquiryAttachment.ATTACHMENT_TYPE_CHOICES,
        'file_type',
    ) or 'document'
    content_bytes = _resolve_upload_content_bytes(arguments, _UPLOAD_MAX_BYTES_MOTION_INQUIRY)
    uploaded_file = _build_uploaded_file(arguments['filename'], content_bytes)
    form = InquiryAttachmentForm(
        data={
            'file_type': file_type,
            'description': arguments.get('description', ''),
        },
        files={'file': uploaded_file},
    )
    form = _validate_attachment_form(form)
    attachment = form.save(commit=False)
    attachment.inquiry = inquiry
    attachment.uploaded_by = user
    attachment.save()
    return attachment


def _create_committee_meeting_upload_url(arguments, user, request):
    meeting = _get_committee_meeting_or_error(arguments['committee_meeting_id'])
    if not _can_user_edit_committee_meeting(user, meeting):
        raise McpToolError('You do not have permission to upload committee meeting attachments.')
    file_type = _validate_choice(
        arguments.get('file_type', 'other'),
        CommitteeMeetingAttachment.ATTACHMENT_TYPE_CHOICES,
        'file_type',
    ) or 'other'
    try:
        safe_filename = normalize_upload_filename(arguments['filename'])
        validate_upload_extension(safe_filename)
    except ValueError as exc:
        raise McpToolError(str(exc)) from exc
    payload = build_committee_meeting_upload_payload(
        committee_meeting_id=meeting.pk,
        user_id=user.pk,
        filename=safe_filename,
        file_type=file_type,
        description=arguments.get('description', ''),
    )
    upload_url = build_attachment_upload_url(request, payload)
    return {
        'upload_url': upload_url,
        'committee_meeting_id': meeting.pk,
        **upload_url_response_fields(),
    }


def _upload_committee_meeting_attachment(arguments, user):
    meeting = _get_committee_meeting_or_error(arguments['committee_meeting_id'])
    if not _can_user_edit_committee_meeting(user, meeting):
        raise McpToolError('You do not have permission to upload committee meeting attachments.')
    file_type = _validate_choice(
        arguments.get('file_type', 'other'),
        CommitteeMeetingAttachment.ATTACHMENT_TYPE_CHOICES,
        'file_type',
    ) or 'other'
    content_bytes = _resolve_upload_content_bytes(arguments, _UPLOAD_MAX_BYTES_SESSION)
    uploaded_file = _build_uploaded_file(arguments['filename'], content_bytes)
    form = CommitteeMeetingAttachmentForm(
        data={
            'file_type': file_type,
            'description': arguments.get('description', ''),
        },
        files={'file': uploaded_file},
        committee_meeting=meeting,
        uploaded_by=user,
    )
    form = _validate_attachment_form(form)
    attachment = form.save()
    _complete_committee_meeting_if_protocol_uploaded(meeting, attachment.file_type)
    _invite_committee_meeting_if_invitation_uploaded(meeting, attachment.file_type)
    meeting.refresh_from_db()
    return attachment, meeting


def _serialize_motion(motion, request=None):
    url = motion.get_absolute_url()
    if request is not None:
        url = request.build_absolute_uri(url)
    return {
        'id': motion.pk,
        'title': motion.title,
        'text': motion.text,
        'rationale': motion.rationale,
        'motion_type': motion.motion_type,
        'status': motion.status,
        'session_id': motion.session_id,
        'group_id': motion.group_id,
        'committee_id': motion.committee_id,
        'party_ids': list(motion.parties.values_list('pk', flat=True)),
        'intervention_ids': list(motion.interventions.values_list('pk', flat=True)),
        'tags': list(motion.tags.values_list('name', flat=True)),
        'attachments': [
            _serialize_attachment(attachment, request)
            for attachment in motion.attachments.all()
        ],
        'url': url,
    }


def _serialize_inquiry(inquiry, request=None):
    url = inquiry.get_absolute_url()
    if request is not None:
        url = request.build_absolute_uri(url)
    return {
        'id': inquiry.pk,
        'title': inquiry.title,
        'text': inquiry.text,
        'answer': inquiry.answer,
        'status': inquiry.status,
        'session_id': inquiry.session_id,
        'group_id': inquiry.group_id,
        'party_ids': list(inquiry.parties.values_list('pk', flat=True)),
        'intervention_ids': list(inquiry.interventions.values_list('pk', flat=True)),
        'tags': list(inquiry.tags.values_list('name', flat=True)),
        'attachments': [
            _serialize_attachment(attachment, request)
            for attachment in inquiry.attachments.all()
        ],
        'url': url,
    }


def _build_motion_form_data(arguments, *, instance=None):
    data = QueryDict(mutable=True)
    if instance:
        data['title'] = arguments.get('title', instance.title)
        data['text'] = arguments.get('text', instance.text or '')
        data['rationale'] = arguments.get('rationale', instance.rationale or '')
        data['motion_type'] = arguments.get('motion_type', instance.motion_type)
        data['status'] = instance.status
        data['session'] = str(arguments.get('session_id', instance.session_id))
        data['group'] = str(arguments.get('group_id', instance.group_id))
        if 'committee_id' in arguments:
            committee_id = arguments['committee_id']
            data['committee'] = str(committee_id) if committee_id else ''
        else:
            data['committee'] = str(instance.committee_id) if instance.committee_id else ''
        if 'party_ids' in arguments:
            data.setlist('parties', [str(x) for x in arguments['party_ids']])
        else:
            data.setlist('parties', [str(p) for p in instance.parties.values_list('pk', flat=True)])
        if 'intervention_ids' in arguments:
            data.setlist('interventions', [str(x) for x in arguments['intervention_ids']])
        else:
            data.setlist(
                'interventions',
                [str(u) for u in instance.interventions.values_list('pk', flat=True)],
            )
        if 'tags' in arguments:
            data['tags'] = _tags_to_string(arguments['tags'])
        else:
            data['tags'] = ', '.join(instance.tags.values_list('name', flat=True))
    else:
        data['title'] = arguments.get('title', '')
        data['text'] = arguments.get('text', '')
        data['rationale'] = arguments.get('rationale', '')
        data['motion_type'] = arguments.get('motion_type', 'general')
        data['status'] = 'draft'
        data['session'] = str(arguments['session_id'])
        data['group'] = str(arguments['group_id'])
        committee_id = arguments.get('committee_id')
        data['committee'] = str(committee_id) if committee_id else ''
        if 'party_ids' in arguments:
            data.setlist('parties', [str(x) for x in arguments['party_ids']])
        if 'tags' in arguments:
            data['tags'] = _tags_to_string(arguments['tags'])
        else:
            data['tags'] = ''
    return data


def _build_inquiry_form_data(arguments, *, instance=None):
    data = QueryDict(mutable=True)
    if instance:
        data['title'] = arguments.get('title', instance.title)
        data['text'] = arguments.get('text', instance.text or '')
        data['answer'] = arguments.get('answer', instance.answer or '')
        data['status'] = instance.status
        data['session'] = str(arguments.get('session_id', instance.session_id))
        data['group'] = str(arguments.get('group_id', instance.group_id))
        if 'party_ids' in arguments:
            data.setlist('parties', [str(x) for x in arguments['party_ids']])
        else:
            data.setlist('parties', [str(p) for p in instance.parties.values_list('pk', flat=True)])
        if 'intervention_ids' in arguments:
            data.setlist('interventions', [str(x) for x in arguments['intervention_ids']])
        else:
            data.setlist(
                'interventions',
                [str(u) for u in instance.interventions.values_list('pk', flat=True)],
            )
        if 'tags' in arguments:
            data['tags'] = _tags_to_string(arguments['tags'])
        else:
            data['tags'] = ', '.join(instance.tags.values_list('name', flat=True))
    else:
        data['title'] = arguments.get('title', '')
        data['text'] = arguments.get('text', '')
        data['answer'] = arguments.get('answer', '')
        data['status'] = 'draft'
        data['session'] = str(arguments['session_id'])
        data['group'] = str(arguments['group_id'])
        if 'party_ids' in arguments:
            data.setlist('parties', [str(x) for x in arguments['party_ids']])
        if 'intervention_ids' in arguments:
            data.setlist('interventions', [str(x) for x in arguments['intervention_ids']])
        if 'tags' in arguments:
            data['tags'] = _tags_to_string(arguments['tags'])
        else:
            data['tags'] = ''
    return data


def _validate_motion_form(arguments, user, *, instance=None):
    form_data = _build_motion_form_data(arguments, instance=instance)
    form = MotionForm(data=form_data, instance=instance, user=user)
    if not form.is_valid():
        raise McpToolError(json.dumps(form.errors, ensure_ascii=False))
    return form


def _validate_inquiry_form(arguments, user, *, instance=None):
    form_data = _build_inquiry_form_data(arguments, instance=instance)
    form = InquiryForm(data=form_data, instance=instance, user=user)
    if not form.is_valid():
        raise McpToolError(json.dumps(form.errors, ensure_ascii=False))
    return form


def _committee_meeting_scheduled_date_form_value(meeting):
    local_dt = timezone.localtime(meeting.scheduled_date)
    return local_dt.strftime('%Y-%m-%dT%H:%M')


def _build_committee_meeting_form_data(arguments, *, instance):
    data = QueryDict(mutable=True)
    data['committee'] = str(instance.committee_id)
    data['title'] = arguments.get('title', instance.title)
    data['scheduled_date'] = _committee_meeting_scheduled_date_form_value(instance)
    data['location'] = arguments.get('location', instance.location or '')
    data['description'] = arguments.get('agenda', instance.description or '')
    data['status'] = instance.status
    return data


def _validate_committee_meeting_form(arguments, *, instance):
    form_data = _build_committee_meeting_form_data(arguments, instance=instance)
    form = CommitteeMeetingForm(
        data=form_data,
        instance=instance,
        committee=instance.committee,
    )
    if not form.is_valid():
        raise McpToolError(json.dumps(form.errors, ensure_ascii=False))
    return form


def _get_motion_or_error(motion_id):
    try:
        return Motion.objects.select_related(
            'session', 'group', 'committee',
        ).prefetch_related(
            'parties', 'interventions', 'tags', 'attachments',
        ).get(pk=motion_id)
    except Motion.DoesNotExist as exc:
        raise McpToolError(f'Motion {motion_id} not found.') from exc


def _get_inquiry_or_error(inquiry_id):
    try:
        return Inquiry.objects.select_related(
            'session', 'group',
        ).prefetch_related(
            'parties', 'interventions', 'tags', 'attachments',
        ).get(pk=inquiry_id)
    except Inquiry.DoesNotExist as exc:
        raise McpToolError(f'Inquiry {inquiry_id} not found.') from exc


def call_tool(name, arguments, user, request=None):
    """Execute a tool and return a JSON-serializable result."""
    arguments = arguments or {}

    if name == 'list_districts':
        districts = District.objects.filter(is_active=True).order_by('name')
        result = []
        for district in districts:
            if not user_is_district_member(user, district):
                continue
            result.append({
                'id': district.pk,
                'name': district.name,
                'code': district.code,
                'can_manage_events': user_can_manage_district_events(user, district),
            })
        return {'districts': result}

    if name == 'list_district_events':
        district = _get_district_or_error(user, arguments['district_id'])
        qs = DistrictEvent.objects.filter(district=district, is_active=True).order_by('scheduled_date')
        if arguments.get('upcoming_only'):
            qs = qs.filter(scheduled_date__gte=timezone.now())
        return {
            'events': [_serialize_event(event, request) for event in qs],
        }

    if name == 'get_district_event':
        try:
            event = DistrictEvent.objects.select_related('district').get(
                pk=arguments['event_id'],
                is_active=True,
            )
        except DistrictEvent.DoesNotExist as exc:
            raise McpToolError(f'Event {arguments["event_id"]} not found.') from exc
        if not user_is_district_member(user, event.district):
            raise McpToolError('You do not have access to this event.')
        return {'event': _serialize_event(event, request)}

    if name == 'create_district_event':
        district = _get_district_or_error(user, arguments['district_id'])
        _require_manage(user, district)
        form = _validate_event_fields(arguments, district=district)
        event = form.save(commit=False)
        event.district = district
        event.created_by = user
        event.save()
        return {'event': _serialize_event(event, request)}

    if name == 'update_district_event':
        try:
            event = DistrictEvent.objects.select_related('district').get(pk=arguments['event_id'])
        except DistrictEvent.DoesNotExist as exc:
            raise McpToolError(f'Event {arguments["event_id"]} not found.') from exc
        _require_manage(user, event.district)
        form = _validate_event_fields(arguments, district=event.district, instance=event)
        event = form.save()
        return {'event': _serialize_event(event, request)}

    if name == 'delete_district_event':
        try:
            event = DistrictEvent.objects.select_related('district').get(pk=arguments['event_id'])
        except DistrictEvent.DoesNotExist as exc:
            raise McpToolError(f'Event {arguments["event_id"]} not found.') from exc
        _require_manage(user, event.district)
        payload = _serialize_event(event, request)
        event.delete()
        return {'deleted': True, 'event': payload}

    if name == 'list_motions':
        _require_list_motions_or_inquiries(user)
        limit, offset = _parse_pagination(arguments)
        queryset = _filter_motions_queryset(_motion_base_queryset(user), arguments)
        return _paginated_list(
            queryset,
            limit=limit,
            offset=offset,
            serialize_fn=_serialize_motion,
            request=request,
            result_key='motions',
        )

    if name == 'get_motion':
        motion = _get_motion_or_error(arguments['motion_id'])
        if not _user_can_view_motion(user, motion.pk):
            raise McpToolError('You do not have permission to view this motion.')
        return {'motion': _serialize_motion(motion, request)}

    if name == 'list_inquiries':
        _require_list_motions_or_inquiries(user)
        limit, offset = _parse_pagination(arguments)
        queryset = _filter_inquiries_queryset(_inquiry_base_queryset(user), arguments)
        return _paginated_list(
            queryset,
            limit=limit,
            offset=offset,
            serialize_fn=_serialize_inquiry,
            request=request,
            result_key='inquiries',
        )

    if name == 'create_motion':
        if not _user_can_create_motion_or_inquiry(user):
            raise McpToolError('You do not have permission to create motions.')
        if 'session_id' not in arguments:
            raise McpToolError('session_id is required.')
        form_args = dict(arguments)
        form_args['group_id'] = _resolve_group_id(user, arguments.get('group_id'))
        form = _validate_motion_form(form_args, user)
        form.instance.submitted_by = user
        motion = form.save()
        return {'motion': _serialize_motion(motion, request)}

    if name == 'update_motion':
        motion = _get_motion_or_error(arguments['motion_id'])
        if not _user_can_update_motion(user, motion):
            raise McpToolError('You do not have permission to update this motion.')
        form = _validate_motion_form(arguments, user, instance=motion)
        motion = form.save()
        return {'motion': _serialize_motion(motion, request)}

    if name == 'get_inquiry':
        inquiry = _get_inquiry_or_error(arguments['inquiry_id'])
        if not user_can_view_inquiry(user, inquiry.pk):
            raise McpToolError('You do not have permission to view this inquiry.')
        return {'inquiry': _serialize_inquiry(inquiry, request)}

    if name == 'create_inquiry':
        if not _user_can_create_motion_or_inquiry(user):
            raise McpToolError('You do not have permission to create inquiries.')
        if 'session_id' not in arguments:
            raise McpToolError('session_id is required.')
        form_args = dict(arguments)
        form_args['group_id'] = _resolve_group_id(user, arguments.get('group_id'))
        form = _validate_inquiry_form(form_args, user)
        form.instance.submitted_by = user
        inquiry = form.save()
        return {'inquiry': _serialize_inquiry(inquiry, request)}

    if name == 'update_inquiry':
        inquiry = _get_inquiry_or_error(arguments['inquiry_id'])
        if not _user_can_update_inquiry(user, inquiry):
            raise McpToolError('You do not have permission to update this inquiry.')
        form = _validate_inquiry_form(arguments, user, instance=inquiry)
        inquiry = form.save()
        return {'inquiry': _serialize_inquiry(inquiry, request)}

    if name == 'upload_session_attachment':
        attachment = _upload_session_attachment(arguments, user)
        return {'attachment': _serialize_attachment(attachment, request)}

    if name == 'upload_motion_attachment':
        attachment = _upload_motion_attachment(arguments, user)
        return {'attachment': _serialize_attachment(attachment, request)}

    if name == 'upload_inquiry_attachment':
        attachment = _upload_inquiry_attachment(arguments, user)
        return {'attachment': _serialize_attachment(attachment, request)}

    if name == 'upload_committee_meeting_attachment':
        attachment, meeting = _upload_committee_meeting_attachment(arguments, user)
        return {
            'attachment': _serialize_attachment(attachment, request),
            'committee_meeting_id': meeting.pk,
            'meeting_status': meeting.status,
        }

    if name == 'create_committee_meeting_upload_url':
        if request is None:
            raise McpToolError('Request context is required to build an upload URL.')
        return _create_committee_meeting_upload_url(arguments, user, request)

    if name == 'list_committees':
        district = _get_district_or_error(user, arguments['district_id'])
        council_ids = _accessible_council_ids_in_district(user, district.pk)
        if not council_ids:
            return {'committees': []}
        committees = (
            Committee.objects.filter(council_id__in=council_ids, is_active=True)
            .order_by('name')
        )
        return {
            'committees': [
                {
                    'id': committee.pk,
                    'name': committee.name,
                    'abbreviation': committee.abbreviation or '',
                    'committee_type': committee.committee_type,
                }
                for committee in committees
            ],
        }

    if name == 'list_committee_meetings':
        district = _get_district_or_error(user, arguments['district_id'])
        council_ids = _accessible_council_ids_in_district(user, district.pk)
        if not council_ids:
            return {'committee_meetings': []}
        queryset = (
            CommitteeMeeting.objects.filter(
                committee__council_id__in=council_ids,
                is_active=True,
            )
            .select_related('committee')
            .prefetch_related('attachments')
            .order_by('-scheduled_date')
        )
        if arguments.get('committee_id') is not None:
            committee_id = arguments['committee_id']
            if not Committee.objects.filter(
                pk=committee_id,
                council_id__in=council_ids,
                is_active=True,
            ).exists():
                raise McpToolError(f'Committee {committee_id} not found in this district.')
            queryset = queryset.filter(committee_id=committee_id)
        queryset = _apply_scheduled_date_filters(queryset, arguments)
        return {
            'committee_meetings': [
                _serialize_committee_meeting_list_item(meeting, request)
                for meeting in queryset
            ],
        }

    if name == 'list_sessions':
        district = _get_district_or_error(user, arguments['district_id'])
        council_ids = _accessible_council_ids_in_district(user, district.pk)
        if not council_ids:
            return {'sessions': []}
        queryset = (
            Session.objects.filter(council_id__in=council_ids, is_active=True)
            .prefetch_related('attachments')
            .order_by('-scheduled_date')
        )
        queryset = _apply_scheduled_date_filters(queryset, arguments)
        return {
            'sessions': [
                _serialize_session_list_item(session, request)
                for session in queryset
            ],
        }

    if name == 'get_committee_meeting':
        meeting = _get_committee_meeting_or_error(arguments['id'])
        if not meeting.is_active:
            raise McpToolError(f'Committee meeting {arguments["id"]} not found.')
        if not _user_can_view_committee_meeting(user, meeting):
            raise McpToolError('You do not have permission to view this committee meeting.')
        meeting = (
            CommitteeMeeting.objects.filter(pk=meeting.pk)
            .select_related('committee')
            .prefetch_related('attachments')
            .get()
        )
        return {'committee_meeting': _serialize_committee_meeting_detail(meeting, request)}

    if name == 'update_committee_meeting':
        meeting = _get_committee_meeting_or_error(arguments['committee_meeting_id'])
        if not meeting.is_active:
            raise McpToolError(f'Committee meeting {arguments["committee_meeting_id"]} not found.')
        if not _can_user_edit_committee_meeting(user, meeting):
            raise McpToolError('You do not have permission to update this committee meeting.')
        form = _validate_committee_meeting_form(arguments, instance=meeting)
        meeting = form.save()
        meeting = (
            CommitteeMeeting.objects.filter(pk=meeting.pk)
            .select_related('committee')
            .prefetch_related('attachments')
            .get()
        )
        return {'committee_meeting': _serialize_committee_meeting_detail(meeting, request)}

    if name == 'list_attachments':
        return _list_attachments_for_parent(
            arguments['parent_type'],
            arguments['parent_id'],
            user,
            request,
        )

    if name == 'delete_attachment':
        return _delete_attachment_by_type(
            arguments['parent_type'],
            arguments['attachment_id'],
            user,
            request,
        )

    raise McpToolError(f'Unknown tool: {name}')


def tool_result_content(result, *, is_error=False):
    """Format a tool result as MCP content blocks."""
    return {
        'content': [
            {
                'type': 'text',
                'text': json.dumps(result, ensure_ascii=False, indent=2),
            }
        ],
        'isError': is_error,
    }
