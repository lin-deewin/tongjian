"""Session-bound, one-attempt graphical challenges; no plaintext answers stored."""
from datetime import timedelta
import hashlib
import hmac
from io import BytesIO
import secrets
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from .models import GraphicChallenge
from .services import rate


PROOF_KEY = 'registration_graphic_proof'
ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'


def new_code():
    return ''.join(secrets.choice(ALPHABET) for _ in range(4))


def digest(purpose, value):
    return hmac.new(settings.OTP_HMAC_KEY.encode(),
                    f'graphic:{purpose}:{value}'.encode(), hashlib.sha256).hexdigest()


def answer_digest(challenge_id, answer):
    return digest('answer', f'{challenge_id}:{answer.strip().upper()}')


def image_bytes(code):
    scale = 2
    canvas = Image.new('RGB', (176 * scale, 56 * scale), '#fffef9')
    draw = ImageDraw.Draw(canvas)
    for _ in range(4):
        draw.line([(secrets.randbelow(canvas.width), secrets.randbelow(canvas.height))
                   for _ in range(3)], fill=(189, 202, 181), width=scale)
    for _ in range(55):
        x, y = secrets.randbelow(canvas.width), secrets.randbelow(canvas.height)
        draw.ellipse((x, y, x + scale, y + scale), fill=(161, 178, 158))
    font = ImageFont.load_default(size=36 * scale)
    for index, character in enumerate(code):
        tile = Image.new('RGBA', (40 * scale, 56 * scale))
        ink = secrets.choice(['#285342', '#35483d', '#384345', '#493f35'])
        ImageDraw.Draw(tile).text((4 * scale, 4 * scale), character, font=font, fill=ink)
        tile = tile.rotate(secrets.randbelow(21) - 10, resample=Image.Resampling.BICUBIC)
        canvas.paste(tile, ((8 + index * 40) * scale, 0), tile)
    canvas = canvas.resize((176, 56), Image.Resampling.LANCZOS)
    output = BytesIO()
    canvas.save(output, format='PNG')
    return output.getvalue()


def challenge_id(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def issue(request, address, previous=None):
    now = timezone.now()
    with transaction.atomic():
        rate('graphic-create:ip:' + address, 600, 120, now)
        rate('graphic-create:global', 3600, 2000, now)
    if not request.session.session_key:
        request.session.create()
    binding = digest('session', request.session.session_key)
    # Keep expired image data bounded without touching live challenges in other tabs.
    GraphicChallenge.objects.filter(expires_at__lte=now).delete()
    if previous_id := challenge_id(previous):
        GraphicChallenge.objects.filter(pk=previous_id, session_digest=binding,
                                         consumed_at__isnull=True).update(consumed_at=now)
    identifier = uuid.uuid4()
    code = new_code()
    return GraphicChallenge.objects.create(id=identifier, session_digest=binding,
        answer_digest=answer_digest(identifier, code), image=image_bytes(code),
        expires_at=now + timedelta(minutes=5))


def consume(request, identifier, answer, address):
    now = timezone.now()
    valid = False
    with transaction.atomic():
        rate('graphic-verify:ip:' + address, 600, 60, now)
        challenge = GraphicChallenge.objects.select_for_update().filter(pk=challenge_id(identifier)).first()
        if (challenge and request.session.session_key and challenge.consumed_at is None
                and challenge.expires_at > now
                and hmac.compare_digest(challenge.session_digest,
                                        digest('session', request.session.session_key))):
            valid = isinstance(answer, str) and hmac.compare_digest(
                challenge.answer_digest, answer_digest(challenge.pk, answer))
            # A wrong answer also consumes the image: a new guess needs a new image.
            challenge.consumed_at = now
            challenge.save(update_fields=['consumed_at'])
    return valid


def verified(request, email):
    proof = request.session.get(PROOF_KEY)
    return (isinstance(proof, dict) and isinstance(email, str)
            and proof.get('email') == email.strip().lower()
            and isinstance(proof.get('expires'), (int, float))
            and proof['expires'] > timezone.now().timestamp())


def remember(request, email):
    request.session[PROOF_KEY] = {'email': email,
        'expires': (timezone.now() + timedelta(minutes=10)).timestamp()}


def clear(request):
    request.session.pop(PROOF_KEY, None)
