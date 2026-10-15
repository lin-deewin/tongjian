import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        if not password:
            raise ValueError('Administrator password is required')
        return self.create_user(email, password, **extra)

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='unique_lower_email')]

class EmailIdentity(models.Model):
    email = models.EmailField(unique=True)

class EmailChallenge(models.Model):
    identity = models.ForeignKey(EmailIdentity, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=16, default='login', choices=[('login', '登录'), ('register', '注册')])
    digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class RateLimitBucket(models.Model):
    key = models.CharField(max_length=160)
    window = models.BigIntegerField()
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['key', 'window'], name='rate_window_unique')]


class GraphicChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_digest = models.CharField(max_length=64)
    answer_digest = models.CharField(max_length=64)
    image = models.BinaryField(editable=False)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True)
