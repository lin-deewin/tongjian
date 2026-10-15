from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label='邮箱', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))

    code = forms.RegexField(regex=r'^[0-9]{6}$', label='邮箱验证码', max_length=6,
                           error_messages={'invalid': '请输入邮件中的 6 位数字验证码。'},
                           widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}))

    field_order = ('email', 'code', 'password1', 'password2')

    class Meta:
        model = User
        fields = ('email',)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('该邮箱已注册，请直接登录；忘记密码可通过邮箱找回。')
        return email


class PasswordLoginForm(AuthenticationForm):
    username = forms.EmailField(label='邮箱', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email', 'autofocus': True}))
    error_messages = {**AuthenticationForm.error_messages, 'invalid_login': '邮箱或密码不正确，请重新输入。'}

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or user.is_superuser:
            raise ValidationError('管理员请使用管理后台登录。')


class ReaderPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def get_users(self, email):
        # Former OTP readers can set their first password after proving mailbox ownership.
        # Do not replace their user row: orders and access grants retain the same owner.
        return User.objects.filter(email__iexact=email, is_active=True, is_staff=False, is_superuser=False)


class RegistrationEmailForm(forms.Form):
    email = forms.EmailField(label='邮箱', max_length=254)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('该邮箱已注册，请直接登录；忘记密码可通过邮箱找回。')
        return email


class GraphicCaptchaForm(forms.Form):
    captcha_id = forms.UUIDField(widget=forms.HiddenInput, error_messages={
        'required': '图形验证码已失效，请刷新后重试。',
        'invalid': '图形验证码已失效，请刷新后重试。',
    })
    captcha = forms.CharField(label='图形验证码', min_length=4, max_length=4,
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'characters',
                                     'spellcheck': 'false', 'aria-describedby': 'captcha-help'}),
        error_messages={'required': '请输入图形验证码。',
                        'min_length': '请输入图中的 4 位字符。',
                        'max_length': '请输入图中的 4 位字符。'})
