"""Token-authenticated PUT uploads for attachment parents (committee meetings, district events)."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from district.forms import CommitteeMeetingAttachmentForm, DistrictEventAttachmentForm
from district.models import CommitteeMeeting, DistrictEvent
from district.upload_tokens import consume_upload_jti, verify_upload_token
from district.upload_validation import (
    UPLOAD_PUT_MAX_BYTES,
    content_matches_extension,
    extension_for_filename,
)
from district.views import (
    _can_user_edit_committee_meeting,
    _complete_committee_meeting_if_protocol_uploaded,
    _invite_committee_meeting_if_invitation_uploaded,
    user_can_manage_district_events,
)

User = get_user_model()
_PROBE_SIZE = 16


def _reject(status: int = 403) -> HttpResponse:
    return HttpResponse(status=status)


def _parse_content_length(request) -> int | HttpResponse:
    content_length = request.META.get('CONTENT_LENGTH')
    if content_length is None or content_length == '':
        return HttpResponse(status=411)
    try:
        declared_size = int(content_length)
    except (TypeError, ValueError):
        return _reject(400)
    if declared_size < 0 or declared_size > UPLOAD_PUT_MAX_BYTES:
        return HttpResponse(status=413)
    return declared_size


def _read_put_body(request, filename: str, declared_size: int):
    """
    Stream the PUT body into a TemporaryUploadedFile.

    Returns (temp, total, head) or an HttpResponse on error.
    """
    temp = TemporaryUploadedFile(
        name=filename,
        content_type=request.META.get('CONTENT_TYPE') or 'application/octet-stream',
        size=declared_size,
        charset=None,
    )

    total = 0
    head = b''
    try:
        for chunk in request:
            if not chunk:
                continue
            total += len(chunk)
            if total > UPLOAD_PUT_MAX_BYTES:
                temp.close()
                return HttpResponse(status=413)
            if len(head) < _PROBE_SIZE:
                need = _PROBE_SIZE - len(head)
                head += chunk[:need]
            temp.write(chunk)
    finally:
        temp.seek(0)

    if total != declared_size:
        temp.close()
        return _reject(400)

    ext = extension_for_filename(filename)
    if not content_matches_extension(ext, head):
        temp.close()
        return _reject(400)

    return temp, total, head


def _attachment_created_response(attachment, total: int) -> JsonResponse:
    try:
        file_size = attachment.file.size
    except OSError:
        file_size = total

    return JsonResponse(
        {
            'id': attachment.pk,
            'filename': attachment.filename,
            'file_size': file_size,
        },
        status=201,
    )


def _finish_committee_meeting_upload(request, payload, user, meeting):
    if not _can_user_edit_committee_meeting(user, meeting):
        return _reject(403)

    filename = payload.get('filename') or 'upload.bin'
    declared_size = _parse_content_length(request)
    if isinstance(declared_size, HttpResponse):
        return declared_size

    jti = payload.get('jti')
    if not jti:
        return _reject(403)

    body = _read_put_body(request, filename, declared_size)
    if isinstance(body, HttpResponse):
        return body
    temp, total, _head = body

    if not _can_user_edit_committee_meeting(user, meeting):
        temp.close()
        return _reject(403)

    if not consume_upload_jti(jti):
        temp.close()
        return HttpResponse(status=409)

    form = CommitteeMeetingAttachmentForm(
        data={
            'file_type': payload.get('file_type', 'other'),
            'description': payload.get('description', ''),
        },
        files={'file': temp},
        committee_meeting=meeting,
        uploaded_by=user,
    )
    if not form.is_valid():
        temp.close()
        return JsonResponse(form.errors, status=400)

    attachment = form.save()
    file_type = attachment.file_type
    _complete_committee_meeting_if_protocol_uploaded(meeting, file_type)
    _invite_committee_meeting_if_invitation_uploaded(meeting, file_type)

    return _attachment_created_response(attachment, total)


def _finish_district_event_upload(request, payload, user, event):
    if not user_can_manage_district_events(user, event.district):
        return _reject(403)

    filename = payload.get('filename') or 'upload.bin'
    declared_size = _parse_content_length(request)
    if isinstance(declared_size, HttpResponse):
        return declared_size

    jti = payload.get('jti')
    if not jti:
        return _reject(403)

    body = _read_put_body(request, filename, declared_size)
    if isinstance(body, HttpResponse):
        return body
    temp, total, _head = body

    if not user_can_manage_district_events(user, event.district):
        temp.close()
        return _reject(403)

    if not consume_upload_jti(jti):
        temp.close()
        return HttpResponse(status=409)

    form = DistrictEventAttachmentForm(
        data={
            'file_type': payload.get('file_type', 'other'),
            'description': payload.get('description', ''),
        },
        files={'file': temp},
        event=event,
        uploaded_by=user,
    )
    if not form.is_valid():
        temp.close()
        return JsonResponse(form.errors, status=400)

    attachment = form.save()
    return _attachment_created_response(attachment, total)


@csrf_exempt
@require_http_methods(['PUT'])
def attachment_upload_view(request, token: str):
    payload = verify_upload_token(token)
    if payload is None:
        return _reject(403)

    parent = payload.get('parent')
    if parent not in ('committee_meeting', 'district_event'):
        return _reject(403)

    try:
        user = User.objects.get(pk=payload['user_id'])
    except (User.DoesNotExist, KeyError, TypeError):
        return _reject(403)

    if parent == 'committee_meeting':
        try:
            meeting = CommitteeMeeting.objects.get(pk=payload['parent_id'])
        except (CommitteeMeeting.DoesNotExist, KeyError, TypeError):
            return _reject(403)
        return _finish_committee_meeting_upload(request, payload, user, meeting)

    try:
        event = DistrictEvent.objects.select_related('district').get(pk=payload['parent_id'])
    except (DistrictEvent.DoesNotExist, KeyError, TypeError):
        return _reject(403)
    return _finish_district_event_upload(request, payload, user, event)
