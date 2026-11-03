"""Token-authenticated PUT uploads for committee meeting attachments."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from district.forms import CommitteeMeetingAttachmentForm
from district.models import CommitteeMeeting
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
)

User = get_user_model()
_CHUNK_SIZE = 64 * 1024
_PROBE_SIZE = 16


def _reject(status: int = 403) -> HttpResponse:
    return HttpResponse(status=status)


@csrf_exempt
@require_http_methods(['PUT'])
def attachment_upload_view(request, token: str):
    payload = verify_upload_token(token)
    if payload is None:
        return _reject(403)

    if payload.get('parent') != 'committee_meeting':
        return _reject(403)

    try:
        meeting = CommitteeMeeting.objects.get(pk=payload['parent_id'])
    except (CommitteeMeeting.DoesNotExist, KeyError, TypeError):
        return _reject(403)

    try:
        user = User.objects.get(pk=payload['user_id'])
    except (User.DoesNotExist, KeyError, TypeError):
        return _reject(403)

    if not _can_user_edit_committee_meeting(user, meeting):
        return _reject(403)

    filename = payload.get('filename') or 'upload.bin'
    ext = extension_for_filename(filename)

    content_length = request.META.get('CONTENT_LENGTH')
    if content_length is None or content_length == '':
        return HttpResponse(status=411)
    try:
        declared_size = int(content_length)
    except (TypeError, ValueError):
        return _reject(400)
    if declared_size < 0 or declared_size > UPLOAD_PUT_MAX_BYTES:
        return HttpResponse(status=413)

    jti = payload.get('jti')
    if not jti:
        return _reject(403)
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

    if not content_matches_extension(ext, head):
        temp.close()
        return _reject(400)

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
