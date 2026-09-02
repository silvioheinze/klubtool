"""MCP tools for district event management."""

import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from district.forms import DistrictEventForm
from district.models import District, DistrictEvent
from district.views import user_can_manage_district_events, user_is_district_member


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
