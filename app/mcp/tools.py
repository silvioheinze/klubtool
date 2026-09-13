"""MCP tools for district events, motions, and inquiries."""

import base64
import binascii
import json
from datetime import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone

from district.forms import DistrictEventForm, SessionAttachmentForm
from district.models import District, DistrictEvent, Session, SessionAttachment
from district.views import user_can_manage_district_events, user_is_district_member
from group.models import Group
from motion.forms import InquiryAttachmentForm, InquiryForm, MotionAttachmentForm, MotionForm
from motion.models import Inquiry, InquiryAttachment, Motion, MotionAttachment
from motion.views import (
    _get_user_accessible_group_ids,
    user_can_view_inquiry,
)


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
            'description': 'Upload a file attachment to a council session (superuser only).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'session_id': {'type': 'integer'},
                    'filename': {'type': 'string', 'description': 'Original filename including extension'},
                    'content_base64': {'type': 'string', 'description': 'File content as base64 (optional data: URL prefix allowed)'},
                    'file_type': {
                        'type': 'string',
                        'enum': ['agenda', 'budget', 'invitation', 'minutes', 'other'],
                        'description': 'Defaults to other',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['session_id', 'filename', 'content_base64'],
            },
        },
        {
            'name': 'upload_motion_attachment',
            'description': 'Upload a file attachment to a motion (same permissions as web upload).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'motion_id': {'type': 'integer'},
                    'filename': {'type': 'string'},
                    'content_base64': {'type': 'string'},
                    'file_type': {
                        'type': 'string',
                        'enum': ['document', 'image', 'spreadsheet', 'presentation', 'other'],
                        'description': 'Defaults to document',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['motion_id', 'filename', 'content_base64'],
            },
        },
        {
            'name': 'upload_inquiry_attachment',
            'description': 'Upload a file attachment to an inquiry (same permissions as web upload).',
            'inputSchema': {
                'type': 'object',
                'properties': {
                    'inquiry_id': {'type': 'integer'},
                    'filename': {'type': 'string'},
                    'content_base64': {'type': 'string'},
                    'file_type': {
                        'type': 'string',
                        'enum': ['document', 'image', 'spreadsheet', 'presentation', 'other'],
                        'description': 'Defaults to document',
                    },
                    'description': {'type': 'string'},
                },
                'required': ['inquiry_id', 'filename', 'content_base64'],
            },
        },
    ]


def _serialize_event(event, request=None):
    url = event.get_absolute_url()
    if request is not None:
        url = request.build_absolute_uri(url)
    return {
        'id': event.pk,
        'title': event.title,
        'scheduled_date': event.scheduled_date.isoformat(),
        'district_id': event.district_id,
        'description': event.description,
        'external_link': event.external_link,
        'is_active': event.is_active,
        'url': url,
    }


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
        'district': district.pk,
    }
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


def _build_uploaded_file(filename, content_bytes):
    if not filename or not isinstance(filename, str):
        raise McpToolError('filename is required.')
    return SimpleUploadedFile(filename, content_bytes)


def _serialize_attachment(attachment, request=None):
    file_url = attachment.file.url
    if request is not None:
        file_url = request.build_absolute_uri(file_url)
    return {
        'id': attachment.pk,
        'filename': attachment.filename,
        'file_type': attachment.file_type,
        'description': attachment.description or '',
        'url': file_url,
    }


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
    content_bytes = _decode_base64_content(arguments['content_base64'])
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
    content_bytes = _decode_base64_content(arguments['content_base64'])
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
    content_bytes = _decode_base64_content(arguments['content_base64'])
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
