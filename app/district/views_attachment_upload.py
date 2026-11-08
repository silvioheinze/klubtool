"""Token-authenticated PUT uploads for attachment parents."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from district.forms import (
    CommitteeMeetingAttachmentForm,
    DistrictEventAttachmentForm,
    SessionAttachmentForm,
)
from district.models import CommitteeMeeting, DistrictEvent, Session
from district.upload_tokens import consume_upload_jti, verify_upload_token
from district.upload_validation import (
    UPLOAD_MOTION_INQUIRY_PUT_MAX_BYTES,
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
from motion.forms import InquiryAttachmentForm, MotionAttachmentForm
from motion.models import Inquiry, Motion
from motion.views import user_can_upload_inquiry_attachment, user_can_upload_motion_attachment

User = get_user_model()
_PROBE_SIZE = 16
_ALLOWED_PARENTS = frozenset(
    {'committee_meeting', 'district_event', 'motion', 'inquiry', 'session'},
)


def _user_can_upload_session_attachment(user, _session) -> bool:
    return user.is_superuser


def _reject(status: int = 403) -> HttpResponse:
    return HttpResponse(status=status)


def _parse_content_length(request, *, max_bytes: int) -> int | HttpResponse:
    content_length = request.META.get('CONTENT_LENGTH')
    if content_length is None or content_length == '':
        return HttpResponse(status=411)
    try:
        declared_size = int(content_length)
    except (TypeError, ValueError):
        return _reject(400)
    if declared_size < 0 or declared_size > max_bytes:
        return HttpResponse(status=413)
    return declared_size


def _read_put_body(request, filename: str, declared_size: int, *, max_bytes: int):
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
            if total > max_bytes:
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


def _finish_generic_upload(
    request,
    payload,
    user,
    *,
    max_bytes: int,
    permission_check,
    form_class,
    parent,
    parent_kwarg: str,
    default_file_type: str = 'other',
    after_save=None,
):
    if not permission_check(user, parent):
        return _reject(403)

    filename = payload.get('filename') or 'upload.bin'
    declared_size = _parse_content_length(request, max_bytes=max_bytes)
    if isinstance(declared_size, HttpResponse):
        return declared_size

    jti = payload.get('jti')
    if not jti:
        return _reject(403)

    body = _read_put_body(request, filename, declared_size, max_bytes=max_bytes)
    if isinstance(body, HttpResponse):
        return body
    temp, total, _head = body

    if not permission_check(user, parent):
        temp.close()
        return _reject(403)

    if not consume_upload_jti(jti):
        temp.close()
        return HttpResponse(status=409)

    form = form_class(
        data={
            'file_type': payload.get('file_type', default_file_type),
            'description': payload.get('description', ''),
        },
        files={'file': temp},
        uploaded_by=user,
        **{parent_kwarg: parent},
    )
    if not form.is_valid():
        temp.close()
        return JsonResponse(form.errors, status=400)

    attachment = form.save()
    if after_save is not None:
        after_save(parent, attachment)
    return _attachment_created_response(attachment, total)


def _finish_committee_meeting_upload(request, payload, user, meeting):
    def after_save(parent_meeting, attachment):
        _complete_committee_meeting_if_protocol_uploaded(parent_meeting, attachment.file_type)
        _invite_committee_meeting_if_invitation_uploaded(parent_meeting, attachment.file_type)

    return _finish_generic_upload(
        request,
        payload,
        user,
        max_bytes=UPLOAD_PUT_MAX_BYTES,
        permission_check=_can_user_edit_committee_meeting,
        form_class=CommitteeMeetingAttachmentForm,
        parent=meeting,
        parent_kwarg='committee_meeting',
        after_save=after_save,
    )


def _finish_district_event_upload(request, payload, user, event):
    return _finish_generic_upload(
        request,
        payload,
        user,
        max_bytes=UPLOAD_PUT_MAX_BYTES,
        permission_check=lambda u, e: user_can_manage_district_events(u, e.district),
        form_class=DistrictEventAttachmentForm,
        parent=event,
        parent_kwarg='event',
    )


def _finish_motion_upload(request, payload, user, motion):
    return _finish_generic_upload(
        request,
        payload,
        user,
        max_bytes=UPLOAD_MOTION_INQUIRY_PUT_MAX_BYTES,
        permission_check=user_can_upload_motion_attachment,
        form_class=MotionAttachmentForm,
        parent=motion,
        parent_kwarg='motion',
        default_file_type='document',
    )


def _finish_inquiry_upload(request, payload, user, inquiry):
    return _finish_generic_upload(
        request,
        payload,
        user,
        max_bytes=UPLOAD_MOTION_INQUIRY_PUT_MAX_BYTES,
        permission_check=user_can_upload_inquiry_attachment,
        form_class=InquiryAttachmentForm,
        parent=inquiry,
        parent_kwarg='inquiry',
        default_file_type='document',
    )


def _finish_session_upload(request, payload, user, session):
    return _finish_generic_upload(
        request,
        payload,
        user,
        max_bytes=UPLOAD_PUT_MAX_BYTES,
        permission_check=_user_can_upload_session_attachment,
        form_class=SessionAttachmentForm,
        parent=session,
        parent_kwarg='session',
    )


@csrf_exempt
@require_http_methods(['PUT'])
def attachment_upload_view(request, token: str):
    payload = verify_upload_token(token)
    if payload is None:
        return _reject(403)

    parent = payload.get('parent')
    if parent not in _ALLOWED_PARENTS:
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

    if parent == 'district_event':
        try:
            event = DistrictEvent.objects.select_related('district').get(pk=payload['parent_id'])
        except (DistrictEvent.DoesNotExist, KeyError, TypeError):
            return _reject(403)
        return _finish_district_event_upload(request, payload, user, event)

    if parent == 'motion':
        try:
            motion = Motion.objects.get(pk=payload['parent_id'])
        except (Motion.DoesNotExist, KeyError, TypeError):
            return _reject(403)
        return _finish_motion_upload(request, payload, user, motion)

    if parent == 'inquiry':
        try:
            inquiry = Inquiry.objects.get(pk=payload['parent_id'])
        except (Inquiry.DoesNotExist, KeyError, TypeError):
            return _reject(403)
        return _finish_inquiry_upload(request, payload, user, inquiry)

    try:
        session = Session.objects.get(pk=payload['parent_id'])
    except (Session.DoesNotExist, KeyError, TypeError):
        return _reject(403)
    return _finish_session_upload(request, payload, user, session)
